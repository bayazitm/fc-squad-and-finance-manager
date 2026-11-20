import csv
import datetime
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, Count
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from .models import *
from .catalog import CATALOG, LABELS
from .forms import form_for, RenewalForm, ProfileForm, LiveTransferForm
from .permissions import visible_clubs, can_edit, require_edit, scope, transfer_editable, is_global
from .services import snapshot, audit, renew_contract, apply_transfer, cancel_transfer, evaluate_squad


def current_season():
    d=datetime.date.today();y=d.year if d.month>=7 else d.year-1
    return f'{y}/{y+1}'

def context(request):
    clubs=visible_clubs(request.user)
    raw=request.GET.get('club',request.session.get('club',''))
    selected=clubs.filter(pk=raw).first() if str(raw).isdigit() else None
    request.session['club']=str(selected.pk) if selected else ''
    season=request.GET.get('season',request.session.get('season',current_season()))
    import re
    if not re.fullmatch(r'\d{4}/\d{4}',season) or int(season[5:])!=int(season[:4])+1:season=current_season()
    request.session['season']=season
    cs=ClubSettings.objects.filter(club=selected).first() if selected else None
    currency=cs.currency if cs else 'UNKNOWN'
    return {'club_options':clubs,'selected_club':selected,'selected_season':season,'editable':can_edit(request.user),
      'menu':[(key,info[1]) for key,info in CATALOG.items()], 'currency':currency,
      'currency_label':{'UNKNOWN':'Para birimi tanımlanmadı','EUR':'EUR','TRY':'TRY','USD':'USD'}.get(currency,currency),
      'today':datetime.date.today(), 'global_access':is_global(request.user)}

def qs_for(request,kind,ctx=None):
    if kind not in CATALOG:raise Http404
    model=CATALOG[kind][0];qs=scope(model.objects.all(),request.user,kind)
    for f in model._meta.fields:
        if f.is_relation:qs=qs.select_related(f.name)
    if ctx and ctx['selected_club']:
        c=ctx['selected_club']
        if kind=='clubs':qs=qs.filter(pk=c.pk)
        elif kind=='transfers':qs=qs.filter(Q(fromclubid=c)|Q(toclubid=c))
        else:qs=qs.filter(clubid=c)
    return qs

def money_total(qs,field):return qs.aggregate(v=Sum(field))['v'] or Decimal('0')

def cell(obj,name):
    value=getattr(obj,name)
    if value is None:return '—'
    if isinstance(value,(datetime.date,datetime.datetime)):return value.strftime('%d.%m.%Y')
    if isinstance(value,Decimal):return f'{value:,.2f}'.replace(',',' ').replace('.',',')
    return str(value)

def payment_linked(pk):
    # JSON containment support varies on SQL Server, so avoid backend-dependent lookups.
    return any(pk in ids for ids in TransferWorkflow.objects.filter(status='APPLIED').values_list('transaction_ids',flat=True))

@login_required
def dashboard(request):
    ctx=context(request);clubs=ctx['club_options'];c=ctx['selected_club'];season=ctx['selected_season']
    players=qs_for(request,'players',ctx).exclude(profile__archived=True)
    cons=qs_for(request,'contracts',ctx).filter(contractstatus='Aktif')
    finances=qs_for(request,'finance',ctx).filter(season=season)
    # Monetary records have no per-row currency column: do not add unrelated clubs together.
    money_enabled=c is not None
    income=money_total(finances.filter(transactiontype='Gelir'),'amount') if money_enabled else None
    expense=money_total(finances.filter(transactiontype='Gider'),'amount') if money_enabled else None
    monthly=[]
    if money_enabled:
        sums={}
        for row in finances.values('transactiondate','transactiontype').annotate(total=Sum('amount')):
            key=row['transactiondate'].strftime('%Y-%m');sums.setdefault(key,{'Gelir':Decimal(0),'Gider':Decimal(0)})
            if row['transactiontype'] in sums[key]:sums[key][row['transactiontype']]+=row['total']
        maximum=max([v for r in sums.values() for v in r.values()]+[Decimal(1)])
        for key,v in sorted(sums.items()):monthly.append({'label':key,'income':v['Gelir'],'expense':v['Gider'],
          'in_width':float(v['Gelir']/maximum*100),'out_width':float(v['Gider']/maximum*100)})
    counts=dict(Players.objects.filter(clubid__in=clubs).exclude(profile__archived=True).values('clubid').annotate(n=Count('pk')).values_list('clubid','n'))
    budgets=[{'club':club,'count':counts.get(club.pk,0)} for club in clubs]
    ctx.update(title='Genel bakış',active='dashboard',player_count=players.count(),club_count=clubs.count(),
       market_total=money_total(players,'marketvalue') if money_enabled else None,
       salary_total=money_total(cons,'annualsalary') if money_enabled else None,income=income,expense=expense,
       net=income-expense if money_enabled else None,monthly=monthly,clubs_summary=budgets,
       expiring=cons.filter(enddate__lte=datetime.date.today()+datetime.timedelta(days=180)).order_by('enddate')[:8],
       recent=qs_for(request,'transfers',ctx).order_by('-transferdate','-pk')[:5],money_enabled=money_enabled)
    return render(request,'clubs/dashboard.html',ctx)

@login_required
def records(request,kind):
    ctx=context(request);model,title,cols=CATALOG.get(kind,(None,None,None))
    if model is None:raise Http404
    qs=qs_for(request,kind,ctx)
    q=request.GET.get('q','').strip()
    if q:
        conditions=Q()
        for f in model._meta.fields:
            if f.get_internal_type() in ('CharField','TextField'):conditions|=Q(**{f'{f.name}__icontains':q})
        if any(f.name=='playerid' and f.is_relation for f in model._meta.fields):
            conditions|=Q(playerid__firstname__icontains=q)|Q(playerid__lastname__icontains=q)
        qs=qs.filter(conditions)
    if kind=='players':
        archive=request.GET.get('archive','active')
        if archive=='active':qs=qs.exclude(profile__archived=True)
        elif archive=='archived':qs=qs.filter(profile__archived=True)
        if request.GET.get('position'):qs=qs.filter(position=request.GET['position'])
        if request.GET.get('nationality'):qs=qs.filter(nationality=request.GET['nationality'])
    if kind in ('transfers','finance') and request.GET.get('all_seasons')!='1':qs=qs.filter(season=ctx['selected_season'])
    if kind in ('contracts','sponsorships') and request.GET.get('status'):qs=qs.filter(contractstatus=request.GET['status'])
    if kind=='finance' and request.GET.get('type') in ('Gelir','Gider'):qs=qs.filter(transactiontype=request.GET['type'])
    for param in ('from_date','to_date'):
        if request.GET.get(param):
            try:day=datetime.date.fromisoformat(request.GET[param])
            except ValueError:continue
            date_field={'finance':'transactiondate','transfers':'transferdate','contracts':'enddate','sponsorships':'enddate'}.get(kind)
            if date_field:qs=qs.filter(**{date_field+('__gte' if param=='from_date' else '__lte'):day})
    order=request.GET.get('sort',cols[0])
    if order.lstrip('-') not in cols:order=cols[0]
    qs=qs.order_by(order,'pk')
    if request.GET.get('export')=='csv':
        response=HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition']=f'attachment; filename="{kind}.csv"';response.write('\ufeff')
        writer=csv.writer(response);writer.writerow([LABELS.get(x,x) for x in cols])
        for obj in qs.iterator():
            vals=[cell(obj,x) for x in cols]
            writer.writerow(["'"+v if v.startswith(('=','+','-','@','\t','\r')) else v for v in vals])
        return response
    page=Paginator(qs,20).get_page(request.GET.get('page'))
    rows=[]
    for obj in page:
        workflow=getattr(obj,'workflow',None) if kind=='transfers' else None
        rows.append({'obj':obj,'values':[cell(obj,k) for k in cols],'workflow':workflow})
    query=request.GET.copy();query.pop('page',None);export=query.copy();export['export']='csv'
    ctx.update(title=title,active=kind,kind=kind,columns=[{'name':k,'label':LABELS.get(k,k)} for k in cols],
       rows=rows,page=page,q=q,query=query.urlencode(),export_query=export.urlencode(),
       positions=qs_for(request,'players',ctx).values_list('position',flat=True).distinct() if kind=='players' else [])
    return render(request,'clubs/records.html',ctx)

@login_required
def edit_record(request,kind,pk=None):
    require_edit(request.user);ctx=context(request)
    if kind not in CATALOG:raise Http404
    model,title,_=CATALOG[kind];obj=get_object_or_404(qs_for(request,kind),pk=pk) if pk else None
    if kind=='clubs' and pk is None and not (request.user.is_superuser or request.user.groups.filter(name='Yönetici').exists()):raise PermissionDenied
    if kind=='transfers' and obj:
        if not transfer_editable(request.user,obj):raise PermissionDenied
        if hasattr(obj,'workflow'):
            messages.error(request,'İşlenmiş transferi doğrudan değiştiremezsiniz. Önce iptal işlemini kullanın.');return redirect('clubs:records',kind=kind)
    if kind=='finance' and obj and payment_linked(obj.pk):
        messages.error(request,'Bu hareket canlı transfere bağlı. Önce ilgili transferi iptal edin.');return redirect('clubs:records',kind=kind)
    initial={}
    if ctx['selected_club'] and kind not in ('clubs','transfers'):initial['clubid']=ctx['selected_club'].pk
    if kind in ('finance','transfers'):initial['season']=ctx['selected_season']
    original_snapshot=snapshot(obj) if obj else {}
    form=form_for(kind)(request.POST or None,instance=obj,user=request.user,kind=kind,initial=initial)
    if obj and kind=='contracts':
        form.fields['playerid'].disabled=True;form.fields['clubid'].disabled=True
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                before=original_snapshot
                item=form.save(commit=False)
                if item.createdat is None:item.createdat=timezone.now()
                item.save();audit(request.user,'UPDATE' if obj else 'CREATE',item,before)
            messages.success(request,'Kayıt kaydedildi.');return redirect('clubs:records',kind=kind)
        except IntegrityError:form.add_error(None,'Kayıt ilişkisi veya benzersizlik kuralı nedeniyle kaydedilemedi. Bilgileri kontrol edin.')
    ctx.update(title=f'{title} · '+('Düzenle' if obj else 'Yeni kayıt'),active=kind,form=form,kind=kind,
       form_note='Bu ekran geçmiş transfer kaydıdır; oyuncunun mevcut kulübünü, sözleşmesini ve finansını değiştirmez.' if kind=='transfers' else '')
    return render(request,'clubs/form.html',ctx)

@login_required
def delete_record(request,kind,pk):
    require_edit(request.user);ctx=context(request);obj=get_object_or_404(qs_for(request,kind),pk=pk)
    if kind=='transfers':
        if not transfer_editable(request.user,obj):raise PermissionDenied
        if hasattr(obj,'workflow'):
            messages.error(request,'Canlı transferleri silmek yerine iptal edin. İşlem geçmişi korunur.');return redirect('clubs:records',kind=kind)
    if kind=='finance' and payment_linked(obj.pk):
        messages.error(request,'Canlı transfere bağlı hareket silinemez. Transfer iptalini kullanın.');return redirect('clubs:records',kind=kind)
    if kind=='contracts' and any(obj.pk==w.new_contract_id or obj.pk in w.old_contract_ids for w in TransferWorkflow.objects.filter(status='APPLIED')):
        messages.error(request,'Bu sözleşme canlı transfer işlemine bağlı. Silmek için önce transferi iptal edin.');return redirect('clubs:records',kind=kind)
    error=None
    if request.method=='POST':
        try:
            with transaction.atomic():
                audit(request.user,'DELETE',obj,snapshot(obj));obj.delete()
            messages.success(request,'Kayıt silindi.');return redirect('clubs:records',kind=kind)
        except (ProtectedError,IntegrityError):error='Bu kayda bağlı başka kayıtlar var. Oyuncularda arşivlemeyi kullanabilir veya önce ilişkili kayıtları inceleyebilirsiniz.'
    ctx.update(title='Kaydı sil',active=kind,obj=obj,kind=kind,error=error)
    return render(request,'clubs/confirm.html',ctx)

@login_required
def player_detail(request,pk):
    ctx=context(request);p=get_object_or_404(qs_for(request,'players'),pk=pk)
    profile=PlayerProfile.objects.filter(player=p).first()
    ctx.update(title=str(p),active='players',player=p,profile=profile,
       contracts=scope(Contracts.objects.filter(playerid=p),request.user,'contracts').select_related('clubid').order_by('-startdate'),
       transfers=scope(Transfers.objects.filter(playerid=p),request.user,'transfers').select_related('fromclubid','toclubid').order_by('-transferdate'))
    return render(request,'clubs/player.html',ctx)

@login_required
def edit_profile(request,pk):
    require_edit(request.user);ctx=context(request);p=get_object_or_404(qs_for(request,'players'),pk=pk)
    obj=PlayerProfile.objects.filter(player=p).first() or PlayerProfile(player=p)
    original_snapshot=snapshot(obj) if obj.pk else {}
    form=ProfileForm(request.POST or None,instance=obj)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            before=original_snapshot;obj=form.save();audit(request.user,'PROFILE',obj,before)
            if obj.archived:SquadEntry.objects.filter(player=p).delete()
        messages.success(request,'Oyuncu uygunluk/arşiv bilgisi kaydedildi.');return redirect('clubs:player',pk=pk)
    ctx.update(title=f'{p} · Uygunluk ve arşiv',active='players',form=form,kind='players')
    return render(request,'clubs/form.html',ctx)

@login_required
def renew(request,pk):
    require_edit(request.user);ctx=context(request);obj=get_object_or_404(qs_for(request,'contracts'),pk=pk)
    form=RenewalForm(request.POST or None,initial={'startdate':datetime.date.today(),'enddate':obj.enddate,'annualsalary':obj.annualsalary,'releaseclause':obj.releaseclause})
    if request.method=='POST' and form.is_valid():
        try:
            renew_contract(request.user,pk,form.cleaned_data)
            messages.success(request,'Yeni sözleşme oluşturuldu; eski kayıt geçmişte korundu. Gelecekte başlayan sözleşme Planlandı olarak kaydedilir.');return redirect('clubs:records',kind='contracts')
        except ValidationError as e:form.add_error(None,e)
    ctx.update(title=f'{obj.playerid} · Sözleşme yenile',active='contracts',form=form,kind='contracts',
       form_note='Başlangıç bugün veya geçmişse eski sözleşme Yenilendi olur. Gelecekteki başlangıçta eski kayıt korunur ve yenisi Planlandı olur; zamanı geldiğinde sözleşme ekranındaki Başlat işlemini kullanın.')
    return render(request,'clubs/form.html',ctx)

@login_required
def live_transfer(request):
    require_edit(request.user);ctx=context(request)
    form=LiveTransferForm(request.POST or None,user=request.user,kind='transfers',initial={'transferdate':datetime.date.today(),'new_start':datetime.date.today(),'season':ctx['selected_season']})
    if request.method=='POST' and form.is_valid():
        try:
            apply_transfer(request.user,form.cleaned_data);messages.success(request,'Transfer, kulüp değişikliği ve yeni sözleşme birlikte kaydedildi.');return redirect('clubs:records',kind='transfers')
        except (ValidationError,IntegrityError) as e:
            form.add_error(None,e if isinstance(e,ValidationError) else 'Veritabanı kısıtı nedeniyle işlem bütünüyle geri alındı.')
    ctx.update(title='Canlı transfer işlemi',active='transfers',form=form,kind='transfers',
       form_note='Oyuncunun mevcut kulübünü değiştirir ve yeni sözleşme açar. Yalnızca yönetebildiğiniz kayıtlı kulüpler arasında kalıcı transfer içindir. Kiralık ve dış kulüp transferlerini geçmiş kayıt olarak ekleyin.')
    return render(request,'clubs/form.html',ctx)

@login_required
def cancel_live_transfer(request,pk):
    require_edit(request.user);ctx=context(request);obj=get_object_or_404(qs_for(request,'transfers'),pk=pk)
    if not transfer_editable(request.user,obj):raise PermissionDenied
    if not hasattr(obj,'workflow'):raise Http404
    error=None
    if request.method=='POST':
        try:
            cancel_transfer(request.user,pk);messages.success(request,'Transfer iptal edildi; kulüp ve bağlantılı kayıtlar geri alındı.');return redirect('clubs:records',kind='transfers')
        except (ValidationError,IntegrityError) as e:error='; '.join(e.messages) if isinstance(e,ValidationError) else 'İlişkili kayıtlar değiştiği için iptal tamamlanamadı.'
    ctx.update(title='Transferi iptal et',active='transfers',obj=obj,kind='transfers',error=error,cancel=True)
    return render(request,'clubs/confirm.html',ctx)

@login_required
def squad(request):
    from .services import squad_status, squad_youth_info
    ctx=context(request);club=ctx['selected_club'];season=ctx['selected_season']
    if not club:
        ctx.update(title='Kadro planlama',active='squad');return render(request,'clubs/squad.html',ctx)
    obj=SeasonSquad.objects.filter(club=club,season=season).first()
    players=list(Players.objects.filter(clubid=club).exclude(profile__archived=True).order_by('position','firstname').select_related('profile'))
    valid={str(p.pk) for p in players}
    selected=set(obj.entries.values_list('player_id',flat=True)) & {p.pk for p in players} if obj else {p.pk for p in players}
    ruleset=obj.ruleset if obj and obj.ruleset != 'UNASSIGNED' else ('SUPERLIG_2627' if season=='2026/2027' else 'UNASSIGNED')
    error=None
    if request.method=='POST':
        require_edit(request.user)
        ids=set(request.POST.getlist('players'))
        selected={int(pk) for pk in ids & valid}
        ruleset=request.POST.get('ruleset','UNASSIGNED')
        action=request.POST.get('action','save')
        if not ids<=valid:error='Seçilen oyunculardan biri bu kulüpte değil veya arşivlenmiş.'
        elif ruleset not in ('UNASSIGNED','SUPERLIG_2627'):error='Geçersiz kural seti.'
        elif ruleset=='SUPERLIG_2627' and season!='2026/2027':error='Bu kural seti yalnızca 2026/2027 sezonu içindir.'
        elif action not in ('save','preview'):error='Geçersiz işlem.'
        elif action=='save':
            with transaction.atomic():
                obj,_=SeasonSquad.objects.get_or_create(club=club,season=season)
                before={**snapshot(obj),'player_ids':list(obj.entries.values_list('player_id',flat=True))};obj.ruleset=ruleset;obj.save()
                SquadEntry.objects.filter(squad=obj).delete()
                SquadEntry.objects.bulk_create([SquadEntry(squad=obj,player_id=pk) for pk in selected])
                log=audit(request.user,'SQUAD_SAVE',obj,before)
                log.after['player_ids']=sorted(selected);log.save(update_fields=['after'])
            messages.success(request,'Taslak kaydedildi. Kontrol sonucu sağdaki panelde; uyarılar taslak kaydını engellemez.')
            return redirect(reverse('clubs:squad')+f'?club={club.pk}&season={season}')
    youth_info=squad_youth_info(players,season)
    listed=[];rows=[]
    for p in players:
        profile=getattr(p,'profile',None)
        status,estimated=squad_status(p,profile,use_nationality=True)
        rows.append({'player':p,'profile':profile,'selected':p.pk in selected,'status':status,'estimated':estimated,'young':youth_info[p.pk]['young'],'youth_reason':youth_info[p.pk]['reason'],'youth_estimated':youth_info[p.pk]['estimated']})
        if p.pk in selected:listed.append((p,profile))
    ctx.update(title='Kadro planlama',active='squad',squad=obj,squad_rows=rows,selected_count=len(selected),error=error,
       selected_ruleset=ruleset,is_new_draft=obj is None,
       result=evaluate_squad(listed,ruleset,season,use_nationality=True,youth_info=youth_info))
    if request.method=='POST' and request.POST.get('action')=='preview' and request.headers.get('X-Requested-With')=='XMLHttpRequest':
        return render(request,'clubs/squad_result.html',ctx)
    return render(request,'clubs/squad.html',ctx)

@login_required
def club_settings(request,pk):
    require_edit(request.user);ctx=context(request);club=get_object_or_404(visible_clubs(request.user),pk=pk)
    obj=ClubSettings.objects.filter(club=club).first()
    if request.method=='POST':
        currency=request.POST.get('currency')
        if currency in ('UNKNOWN','EUR','TRY','USD'):
            with transaction.atomic():
                before=snapshot(obj) if obj else {};obj,_=ClubSettings.objects.update_or_create(club=club,defaults={'currency':currency});audit(request.user,'CURRENCY',obj,before)
            messages.success(request,'Para birimi etiketi kaydedildi. Bu işlem mevcut tutarları dönüştürmez.');return redirect('clubs:dashboard')
    ctx.update(title=f'{club} · Para birimi',active='clubs',club_setting=obj,club=club)
    return render(request,'clubs/currency.html',ctx)

@login_required
def history(request):
    ctx=context(request)
    logs=AuditLog.objects.select_related('user').order_by('-created_at')
    if not is_global(request.user):logs=logs.filter(user=request.user)
    q=request.GET.get('q','')
    if q:logs=logs.filter(Q(summary__icontains=q)|Q(entity__icontains=q)|Q(action__icontains=q))
    ctx.update(title='İşlem geçmişi',active='history',logs=Paginator(logs,30).get_page(request.GET.get('page')),q=q)
    return render(request,'clubs/history.html',ctx)

@login_required
def activate(request,pk):
    from .services import activate_contract
    require_edit(request.user);ctx=context(request);obj=get_object_or_404(qs_for(request,'contracts'),pk=pk)
    error=None
    if request.method=='POST':
        try:
            activate_contract(request.user,pk);messages.success(request,'Planlanan sözleşme başlatıldı; önceki aktif sözleşme geçmişte korundu.');return redirect('clubs:records',kind='contracts')
        except ValidationError as e:error='; '.join(e.messages)
    ctx.update(title='Planlanan sözleşmeyi başlat',active='contracts',obj=obj,kind='contracts',error=error,activate=True)
    return render(request,'clubs/confirm.html',ctx)


@login_required
def database_reports(request):
    from .reporting import read_report
    ctx = context(request)
    report = request.GET.get('report', 'finance')
    if report not in ('finance', 'squad', 'alerts'):
        report = 'finance'
    ids = list(ctx['club_options'].values_list('pk', flat=True))
    if ctx['selected_club']:
        ids = [ctx['selected_club'].pk]
    rows, error = read_report(report, ids, ctx['selected_season'])
    ctx.update(title='Veritabanı raporları', active='database_reports', report=report,
               report_rows=rows, report_error=error)
    return render(request, 'clubs/database_reports.html', ctx)

@login_required
def database_history(request):
    from .reporting import read_database_history
    if not is_global(request.user):
        raise PermissionDenied('Veritabanı günlüğü için genel kulüp erişimi gerekiyor.')
    ctx = context(request)
    table = request.GET.get('table', '')
    operation = request.GET.get('operation', '')
    rows, error = read_database_history(ctx['selected_club'].pk if ctx['selected_club'] else None, table, operation)
    ctx.update(title='Veritabanı değişiklikleri', active='database_history', db_logs=rows,
               report_error=error, table_filter=table, operation_filter=operation)
    return render(request, 'clubs/database_history.html', ctx)
