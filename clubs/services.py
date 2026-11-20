import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from .models import (Players, Contracts, Transfers, Financialtransactions, TransferWorkflow,
                     AuditLog, SquadEntry, SeasonSquad, PlayerProfile, ClubSettings)
from .permissions import visible_clubs, transfer_editable

def snapshot(obj):
    values = model_to_dict(obj)
    for field in obj._meta.fields:
        if field.name in values and values[field.name] is not None and field.get_internal_type() == 'DecimalField':
            values[field.name] = format(Decimal(str(values[field.name])), f'.{field.decimal_places}f')
    return {k: str(v) if v is not None else None for k,v in values.items()}

def audit(user,action,obj,before=None):
    return AuditLog.objects.create(user=user,action=action,entity=obj._meta.model_name,object_id=str(obj.pk),
                            summary=str(obj)[:255],before=before or {},after=snapshot(obj) if action!='DELETE' else {})

@transaction.atomic
def renew_contract(user,pk,data):
    old=Contracts.objects.select_for_update().select_related('playerid','clubid').get(pk=pk)
    if old.clubid_id not in visible_clubs(user).values_list('pk',flat=True):raise PermissionDenied
    if old.playerid.clubid_id!=old.clubid_id:raise ValidationError('Oyuncu artık bu kulüpte değil. Önce güncel kulübünü kontrol edin.')
    if old.contractstatus!='Aktif':raise ValidationError('Yalnızca aktif sözleşme yenilenebilir.')
    if data['startdate'] < old.startdate:raise ValidationError('Yeni başlangıç eski sözleşmenin başlangıcından önce olamaz.')
    others=Contracts.objects.filter(playerid=old.playerid,contractstatus__in=['Aktif','Planlandı'],startdate__lte=data['enddate'],enddate__gte=data['startdate']).exclude(pk=old.pk)
    if others.exists():raise ValidationError('Başka bir aktif veya planlanan sözleşmeyle çakışıyor.')
    before=snapshot(old)
    status='Planlandı' if data['startdate']>datetime.date.today() else 'Aktif'
    if status=='Aktif':
        old.contractstatus='Yenilendi';old.save(update_fields=['contractstatus'])
        audit(user,'RENEW_OLD',old,before)
    new=Contracts.objects.create(playerid=old.playerid,clubid=old.clubid,startdate=data['startdate'],enddate=data['enddate'],
        annualsalary=data['annualsalary'],releaseclause=data.get('releaseclause'),contractstatus=status,createdat=timezone.now())
    audit(user,'RENEW_NEW',new)
    return new

@transaction.atomic
def apply_transfer(user,data):
    p=Players.objects.select_for_update().select_related('clubid').get(pk=data['playerid'].pk)
    if PlayerProfile.objects.filter(player=p,archived=True).exists():raise ValidationError('Arşivlenmiş oyuncu canlı transfer edilemez.')
    dest=data['toclubid'];allowed=set(visible_clubs(user).values_list('pk',flat=True))
    if p.clubid_id not in allowed or dest.pk not in allowed:raise PermissionDenied
    if p.clubid_id==dest.pk:raise ValidationError('Kaynak ve hedef kulüp aynı.')
    if Transfers.objects.filter(playerid=p,transferdate__gt=data['transferdate']).exists():
        raise ValidationError('Oyuncunun daha sonraki tarihli transferi var. Geçmiş kayıt ekranını kullanın.')
    active=list(Contracts.objects.select_for_update().filter(playerid=p,contractstatus__in=['Aktif','Planlandı']))
    if any(c.clubid_id!=p.clubid_id or c.startdate>data['transferdate'] for c in active):
        raise ValidationError('Oyuncunun sözleşme/kulüp bilgisi veya planlanan sözleşmesi bu işlemle çakışıyor. Önce sözleşmeleri inceleyin.')
    if p.jerseynumber and Players.objects.filter(clubid=dest,jerseynumber=p.jerseynumber).exclude(pk=p.pk).exists():
        raise ValidationError('Forma numarası hedef kulüpte kullanılıyor. Oyuncunun forma numarasını değiştirin veya boşaltın.')
    fee=data['transferfee'];source=p.clubid;payment=data.get('record_payment',False)
    if payment and fee>0:
        curr=dict(ClubSettings.objects.filter(club_id__in=[source.pk,dest.pk]).values_list('club_id','currency'))
        if curr.get(source.pk,'UNKNOWN')=='UNKNOWN' or curr.get(source.pk)!=curr.get(dest.pk):
            raise ValidationError('Ödeme kaydı için iki kulübün para birimi aynı ve tanımlı olmalı. Kulüp ayarlarından kontrol edin.')
    tr=Transfers.objects.create(playerid=p,fromclubid=source,fromclubname=source.clubname,toclubid=dest,
       transferdate=data['transferdate'],transferfee=fee,transfertype=data['transfertype'],season=data['season'],createdat=timezone.now())
    before_player=snapshot(p);old_snap={str(c.pk):snapshot(c) for c in active}
    for c in active:
        before=snapshot(c);c.contractstatus='Transfer';c.save(update_fields=['contractstatus']);audit(user,'TRANSFER_CLOSE',c,before)
    p.clubid=dest;p.save(update_fields=['clubid']);audit(user,'TRANSFER_PLAYER',p,before_player)
    # A squad list is an explicit user selection; remove stale memberships after moving clubs.
    removed=list(SquadEntry.objects.filter(player=p).values_list('squad_id',flat=True))
    SquadEntry.objects.filter(player=p).delete()
    new=Contracts.objects.create(playerid=p,clubid=dest,startdate=data['new_start'],enddate=data['new_end'],annualsalary=data['new_salary'],
        contractstatus='Aktif',createdat=timezone.now())
    audit(user,'TRANSFER_CONTRACT',new)
    money=[];money_snap={}
    if payment and fee>0:
        for club,typ in [(source,'Gelir'),(dest,'Gider')]:
            m=Financialtransactions.objects.create(clubid=club,transactiontype=typ,category='Transfer',amount=fee,
               transactiondate=data['transferdate'],description=f'Transfer #{tr.pk}: {p}',season=data['season'],createdat=timezone.now())
            money.append(m.pk);money_snap[str(m.pk)]=snapshot(m);audit(user,'TRANSFER_PAYMENT',m)
    TransferWorkflow.objects.create(transfer=tr,previous_club_id=source.pk,old_contract_ids=[c.pk for c in active],new_contract_id=new.pk,
       transaction_ids=money,snapshot={'player_before':before_player,'player_after':snapshot(p),'contracts_before':old_snap,
       'new_contract':snapshot(new),'payments':money_snap,'removed_squads':removed,'transfer':snapshot(tr)})
    audit(user,'TRANSFER_APPLY',tr)
    return tr

@transaction.atomic
def cancel_transfer(user,pk):
    tr=Transfers.objects.select_for_update().select_related('playerid').get(pk=pk)
    if not transfer_editable(user,tr):raise PermissionDenied
    wf=TransferWorkflow.objects.select_for_update().get(transfer=tr)
    if wf.status!='APPLIED':raise ValidationError('Bu transfer zaten iptal edilmiş.')
    p=Players.objects.select_for_update().get(pk=tr.playerid_id)
    if snapshot(p)!=wf.snapshot['player_after']:raise ValidationError('Oyuncu transferden sonra değişmiş. Otomatik iptal yerine kayıtları inceleyin.')
    if Transfers.objects.filter(playerid=p,transferdate__gte=tr.transferdate).exclude(pk=tr.pk).exists():raise ValidationError('Aynı veya daha sonraki tarihli başka transfer var; iptal sırasını kontrol edin.')
    new=Contracts.objects.select_for_update().filter(pk=wf.new_contract_id).first()
    if new is None:raise ValidationError('Transferde oluşturulan sözleşme bulunamadı.')
    if snapshot(new)!=wf.snapshot['new_contract']:raise ValidationError('Yeni sözleşme değiştirilmiş. Otomatik iptal yapılamıyor.')
    if Contracts.objects.filter(playerid=p,createdat__gt=wf.created_at).exclude(pk=new.pk).exists():raise ValidationError('Transferden sonra yeni sözleşme eklenmiş.')
    if snapshot(tr)!=wf.snapshot['transfer']:raise ValidationError('Transfer kaydı sonradan değiştirilmiş.')
    old=list(Contracts.objects.select_for_update().filter(pk__in=wf.old_contract_ids))
    if len(old)!=len(wf.old_contract_ids):raise ValidationError('Eski sözleşmelerden biri bulunamadı.')
    for c in old:
        expected=dict(wf.snapshot['contracts_before'][str(c.pk)]);expected['contractstatus']='Transfer'
        if snapshot(c)!=expected:raise ValidationError('Önceki sözleşme sonradan değiştirilmiş.')
    money=list(Financialtransactions.objects.select_for_update().filter(pk__in=wf.transaction_ids))
    if len(money)!=len(wf.transaction_ids):raise ValidationError('İlgili ödeme kaydı bulunamadı.')
    for m in money:
        if snapshot(m)!=wf.snapshot['payments'][str(m.pk)]:raise ValidationError('İlgili ödeme değiştirilmiş.')
    for m in money:audit(user,'DELETE',m,snapshot(m));m.delete()
    audit(user,'DELETE',new,snapshot(new));new.delete()
    for c in old:
        before=snapshot(c);c.contractstatus=wf.snapshot['contracts_before'][str(c.pk)]['contractstatus'];c.save(update_fields=['contractstatus']);audit(user,'RESTORE',c,before)
    before=snapshot(p);p.clubid_id=wf.previous_club_id;p.save(update_fields=['clubid']);audit(user,'RESTORE',p,before)
    for squad in SeasonSquad.objects.filter(pk__in=wf.snapshot.get('removed_squads',[]),club_id=p.clubid_id):
        SquadEntry.objects.get_or_create(squad=squad,player=p)
    wf.status='CANCELLED';wf.save(update_fields=['status']);audit(user,'TRANSFER_CANCEL',tr)
    return tr

RULE_SOURCE='https://www.tff.org/Resources/TFF/Documents/STATULER/2026-2027/2026-2027-sezonu-super-lig-musabakalari-statusu.pdf'

def squad_status(player, profile, use_nationality=False):
    """Verified eligibility wins; nationality is only an explicitly labelled estimate."""
    if profile is not None and profile.eligible_turkey is not None and profile.eligibility_source.strip():
        return ('domestic' if profile.eligible_turkey else 'foreign'), False
    if use_nationality:
        import re
        import unicodedata
        raw = unicodedata.normalize('NFKD', player.nationality or '')
        raw = ''.join(c for c in raw if not unicodedata.combining(c)).casefold().strip()
        tokens = [v.strip() for v in re.split(r'[/,;|&+]', raw) if v.strip()]
        turkish = {'turkiye', 'turkey', 'turk', 'turkish', 'tur', 'tr', 't.c.', 'tc'}
        missing = {'', '-', '—', 'unknown', 'bilinmiyor', 'belirsiz', 'n/a', 'null', 'none'}
        if raw not in missing:
            if len(tokens) == 1 and tokens[0] in turkish:
                return 'domestic', True
            if tokens and not any(v in turkish or v in missing for v in tokens):
                return 'foreign', True
    return 'unknown', False


def squad_young(player, profile):
    return bool(player.birthdate and (player.birthdate >= datetime.date(2003, 1, 1) or (
        player.birthdate.year == 2002 and profile is not None and profile.youth_2002_exception
        and profile.exception_verified and profile.exception_note.strip())))


def squad_youth_info(players, season):
    """Bulk, read-only planning estimate. Transfer history is not a TFF registration list."""
    info = {}
    candidates = []
    for player in players:
        profile = getattr(player, 'profile', None)
        if squad_young(player, profile):
            info[player.pk] = {'young': True, 'estimated': False,
                'reason': 'Doğum tarihi: 01.01.2003 veya sonrası' if player.birthdate.year >= 2003 else 'Kaynaklı 2002 istisnası'}
        else:
            info[player.pk] = {'young': False, 'estimated': False, 'reason': 'Genç kontenjanı dışında'}
            if season == '2026/2027' and player.birthdate and player.birthdate.year == 2002:
                candidates.append(player)
    if season != '2026/2027':
        return {p.pk: {'young': False, 'estimated': False, 'reason': 'Bu sezon için kural tanımlı değil'} for p in players}
    if not candidates:
        return info
    boundary = datetime.date(2026, 7, 1)
    as_of = max(boundary, min(datetime.date.today(), datetime.date(2027, 6, 30)))
    ids = [p.pk for p in candidates]
    continuing = set(Contracts.objects.filter(playerid_id__in=ids, contractstatus='Aktif',
        startdate__lt=boundary, enddate__gte=as_of).values_list('playerid_id', 'clubid_id'))
    latest = {}
    events = Transfers.objects.filter(playerid_id__in=ids, transferdate__lte=as_of).exclude(
        workflow__status='CANCELLED').order_by('-transferdate', '-pk')
    for event in events:
        latest.setdefault(event.playerid_id, event)
    for player in candidates:
        event = latest.get(player.pk)
        reason = '2002 istisnası için devam eden sözleşme / önceki kulüp kaydı eksik'
        if event and event.toclubid_id == player.clubid_id and event.transferdate < boundary and (player.pk, player.clubid_id) in continuing:
            transfer_type = (event.transfertype or '').casefold()
            if 'kiral' not in transfer_type and 'loan' not in transfer_type:
                info[player.pk] = {'young': True, 'estimated': True,
                    'reason': '2002 devam hakkı: önceki sezon kulüp kaydı + devam eden sözleşme (otomatik tahmin)'}
                continue
            reason = 'Kiralık geçmişi nedeniyle 2002 devam hakkı belirsiz'
        info[player.pk]['reason'] = reason
    return info


def evaluate_squad(entries, ruleset, season, use_nationality=False, youth_info=None):
    if ruleset!='SUPERLIG_2627' or season!='2026/2027':
        return {'state':'unknown','title':'Kural seti seçilmedi','issues':['Bu lig/sezon için doğrulanmış kural seti seçin.'],'foreign':0,'young':0,'domestic':0,'unknown':len(entries),'estimated':0,'youth_estimated':0,'young_players':[],'source':RULE_SOURCE}
    foreign=young=domestic=young_domestic=keepers=domestic_keepers=unknown=estimated=youth_estimated=0;issues=[];manual=[];young_players=[]
    for p,profile in entries:
        is_keeper=p.position.casefold() in ('kaleci','gk','goalkeeper')
        keepers+=is_keeper
        status, inferred = squad_status(p, profile, use_nationality)
        estimated += inferred
        if status == 'unknown':
            unknown+=1;continue
        if status == 'domestic':
            domestic+=1;young_domestic+=p.birthdate>=datetime.date(2003,1,1);domestic_keepers+=is_keeper
        else:
            foreign+=1
            detail = (youth_info or {}).get(p.pk)
            eligible_young = detail['young'] if detail is not None else squad_young(p, profile)
            if profile is not None and profile.youth_2002_exception and not squad_young(p, profile):
                issues.append(f'{p}: 2002 istisnasının tarih/kaynak bilgisi uygun değil.')
            young += eligible_young
            if eligible_young:
                inferred_youth = bool(detail and detail['estimated'])
                youth_estimated += inferred_youth
                young_players.append({'name': str(p), 'estimated': inferred_youth,
                    'reason': detail['reason'] if detail else 'Doğum tarihi veya kaynaklı 2002 istisnası'})
        if profile is not None and profile.archived:issues.append(f'{p}: arşivlenmiş oyuncu listede.')
    n=len(entries)
    if n>28:issues.append(f'A takım listesinde {n} oyuncu var; üst sınır 28.')
    if foreign>14:issues.append(f'{foreign} yabancı var; normal kontenjan üst sınırı 14.')
    if foreign==14 and young<4:issues.append(f'14 yabancı için en az 4 genç yabancı gerekli; mevcut sayı {young}.')
    # Report 11–13 player age allocations for manual review: official wording explicitly addresses all 14 slots.
    if 10<foreign<14 and foreign-young>10:manual.append('11–13 yabancılı listede yaş kontenjanı için TFF teyidi gerekli.')
    if keepers>3:issues.append('A takım listesinde en fazla 3 kaleci olabilir.')
    if not unknown:
        if domestic<14:issues.append(f'Normal tam liste için en az 14 yerli statülü oyuncu gerekli; mevcut sayı {domestic}.')
        if young_domestic<4:issues.append(f'En az 4 genç yerli statülü oyuncu gerekli; mevcut sayı {young_domestic}.')
        if domestic_keepers<2:issues.append('En az 2 kaleci yerli statüsünde olmalı.')
    if estimated:manual.append(f'{estimated} oyuncu uyruk alanından tahmini sınıflandırıldı; millî takım uygunluğu doğrulanmadı.')
    if youth_estimated:manual.append(f'{youth_estimated} oyuncunun 2002 devam hakkı geçmiş transfer ve sözleşme kayıtlarından otomatik tahmin edildi; TFF liste tescili ayrıca doğrulanmış değildir.')
    if unknown:manual.append(f'{unknown} oyuncunun millî takım uygunluk bilgisi/kaynağı eksik.')
    manual.append('Kazanılmış vatandaşlık/mavi kart hakları ve liste dışı genç oyuncu istisnaları otomatik onaylanmaz. Bu ekran temel liste ön kontrolüdür.')
    state='bad' if issues else ('unknown' if unknown or estimated or youth_estimated or len(manual)>1 else 'good')
    return {'state':state,'title':{'bad':'Düzeltilmesi gereken kayıtlar var','unknown':'Bilgi / inceleme gerekiyor','good':'Temel liste kontrolleri geçti'}[state],
       'issues':issues,'notes':manual,'foreign':foreign,'young':young,'domestic':domestic,'unknown':unknown,'estimated':estimated,'youth_estimated':youth_estimated,'young_players':young_players,'source':RULE_SOURCE}

@transaction.atomic
def activate_contract(user, pk):
    obj=Contracts.objects.select_for_update().select_related('playerid').get(pk=pk)
    if obj.clubid_id not in visible_clubs(user).values_list('pk',flat=True):raise PermissionDenied
    if obj.contractstatus!='Planlandı':raise ValidationError('Sözleşme planlanan durumda değil.')
    if obj.startdate>datetime.date.today():raise ValidationError('Sözleşmenin başlangıç tarihi henüz gelmedi.')
    if obj.enddate<datetime.date.today():raise ValidationError('Planlanan sözleşmenin bitiş tarihi geçmiş.')
    if obj.playerid.clubid_id!=obj.clubid_id:raise ValidationError('Oyuncunun güncel kulübü farklı.')
    for old in Contracts.objects.select_for_update().filter(playerid=obj.playerid,contractstatus='Aktif').exclude(pk=obj.pk):
        if old.clubid_id!=obj.clubid_id:raise ValidationError('Başka kulüpte aktif sözleşme var.')
        before=snapshot(old);old.contractstatus='Yenilendi';old.save(update_fields=['contractstatus']);audit(user,'RENEW_OLD',old,before)
    before=snapshot(obj);obj.contractstatus='Aktif';obj.save(update_fields=['contractstatus']);audit(user,'ACTIVATE',obj,before)
    return obj
