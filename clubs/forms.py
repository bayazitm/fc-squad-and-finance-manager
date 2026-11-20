import datetime
import re
from decimal import Decimal
from django import forms
from django.db.models import Q
from .models import Players, Contracts, PlayerProfile
from .catalog import CATALOG, LABELS
from .permissions import visible_clubs

class RecordForm(forms.ModelForm):
    def __init__(self, *args, user=None, kind=None, **kwargs):
        self.kind = kind
        super().__init__(*args, **kwargs)
        clubs = visible_clubs(user)
        for name, field in self.fields.items():
            field.label = LABELS.get(name, field.label)
            if isinstance(field, forms.DateField):
                field.widget = forms.DateInput(format='%Y-%m-%d', attrs={'type':'date'})
                field.input_formats = ['%Y-%m-%d']
            if isinstance(field, forms.DecimalField):
                field.min_value = Decimal('0')
                field.widget.attrs['min'] = '0'
            if name in ('clubid','fromclubid','toclubid'):
                field.queryset = clubs
            if name == 'playerid':
                field.queryset = Players.objects.filter(clubid__in=clubs).order_by('firstname','lastname')
                if self.instance.pk:
                    field.queryset = Players.objects.filter(Q(clubid__in=clubs) | Q(pk=self.instance.playerid_id)).order_by('firstname')
        if 'contractstatus' in self.fields:
            self.fields['contractstatus'].initial = 'Aktif'
        if 'transactiontype' in self.fields:
            self.fields['transactiontype'] = forms.ChoiceField(label='Hareket türü', choices=[('Gelir','Gelir'),('Gider','Gider')])
        if kind == 'players' and self.instance.pk:
            self.fields['clubid'].disabled = True
            self.fields['clubid'].help_text = 'Kulüp değişikliğini transfer ekranından yapın.'

    def clean(self):
        d = super().clean()
        for name, value in list(d.items()):
            if isinstance(value, Decimal) and value < 0:
                self.add_error(name, 'Tutar negatif olamaz.')
        for a,b in [('startdate','enddate'),('contractstartdate','contractenddate')]:
            if d.get(a) and d.get(b) and d[b] < d[a]:
                self.add_error(b, 'Bitiş tarihi başlangıçtan önce olamaz.')
        if d.get('season') and not re.fullmatch(r'\d{4}/\d{4}', d['season']):
            self.add_error('season','2026/2027 biçiminde yazın.')
        elif d.get('season'):
            a,b = map(int,d['season'].split('/'))
            if b != a+1: self.add_error('season','Sezon yılları ardışık olmalı.')
        if self.kind == 'players':
            dob=d.get('birthdate'); number=d.get('jerseynumber')
            if dob and dob >= datetime.date.today(): self.add_error('birthdate','Geçmiş bir tarih girin.')
            if number is not None:
                if not 1 <= number <= 99: self.add_error('jerseynumber','1–99 arasında olmalı.')
                elif d.get('clubid') and Players.objects.filter(clubid=d['clubid'],jerseynumber=number).exclude(pk=self.instance.pk).exists():
                    self.add_error('jerseynumber','Bu kulüpte forma numarası kullanılıyor.')
        if self.kind == 'contracts':
            p=d.get('playerid');c=d.get('clubid')
            if not self.instance.pk and p and c and p.clubid_id != c.pk: self.add_error('clubid','Yeni sözleşme oyuncunun mevcut kulübüne ait olmalı.')
            if p and d.get('startdate') and d.get('enddate') and d.get('contractstatus')=='Aktif':
                if Contracts.objects.filter(playerid=p,contractstatus='Aktif',startdate__lte=d['enddate'],enddate__gte=d['startdate']).exclude(pk=self.instance.pk).exists():
                    self.add_error(None,'Aktif sözleşmeyle çakışıyor. Mevcut kayıttaki “Yenile” işlemini kullanın.')
        if self.kind == 'transfers':
            if d.get('fromclubid') and d.get('toclubid') and d['fromclubid']==d['toclubid']:
                self.add_error('toclubid','Kaynak ve hedef kulüp aynı olamaz.')
            if d.get('fromclubid'): d['fromclubname']=d['fromclubid'].clubname
        if self.kind == 'stadiums':
            if d.get('capacity',0) <= 0: self.add_error('capacity','Kapasite pozitif olmalı.')
        for field in ('foundingyear','builtyear'):
            if d.get(field) is not None and not 1800 <= d[field] <= datetime.date.today().year:
                self.add_error(field,'1800 ile bu yıl arasında bir yıl girin.')
        return d

def form_for(kind):
    model = CATALOG[kind][0]
    return forms.modelform_factory(model,form=RecordForm,exclude=['createdat'])

class RenewalForm(forms.Form):
    startdate = forms.DateField(label='Yeni sözleşme başlangıcı', widget=forms.DateInput(attrs={'type':'date'}))
    enddate = forms.DateField(label='Yeni sözleşme bitişi', widget=forms.DateInput(attrs={'type':'date'}))
    annualsalary = forms.DecimalField(label='Yeni yıllık maaş',min_value=0,max_digits=18,decimal_places=2)
    releaseclause = forms.DecimalField(label='Serbest kalma bedeli',min_value=0,max_digits=18,decimal_places=2,required=False)
    def clean(self):
        d=super().clean()
        if d.get('startdate') and d.get('enddate') and d['enddate']<=d['startdate']:
            self.add_error('enddate','Bitiş başlangıçtan sonra olmalı.')
        return d

class ProfileForm(forms.ModelForm):
    eligible_turkey=forms.TypedChoiceField(label='Türkiye A Millî Takımı uygunluğu', choices=[('','Bilinmiyor'),('yes','Uygun'),('no','Uygun değil')],coerce=lambda v: {'yes':True,'no':False}.get(v),empty_value=None,required=False)
    class Meta:
        model=PlayerProfile
        fields=['archived','eligible_turkey','eligibility_source','youth_2002_exception','exception_verified','exception_note']
        labels={'archived':'Oyuncuyu arşivle','eligibility_source':'Uygunluk kaynağı / TFF bağlantısı','youth_2002_exception':'2002 doğumlu yabancı için kazanılmış genç kontenjan hakkı','exception_verified':'İstisna kaynağını doğruladım','exception_note':'İstisna dayanağı / açıklaması'}
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.initial['eligible_turkey']={True:'yes',False:'no',None:''}.get(self.instance.eligible_turkey,'')
    def clean(self):
        d=super().clean()
        if d.get('eligible_turkey') is not None and not d.get('eligibility_source'):
            self.add_error('eligibility_source','Uygunluk kararının kaynağını yazın.')
        if d.get('youth_2002_exception') and (not d.get('exception_verified') or not d.get('exception_note')):
            self.add_error('exception_note','İstisna için doğrulama ve kaynak açıklaması gerekli.')
        return d

class LiveTransferForm(RecordForm):
    new_start=forms.DateField(label='Yeni sözleşme başlangıcı',widget=forms.DateInput(attrs={'type':'date'}))
    new_end=forms.DateField(label='Yeni sözleşme bitişi',widget=forms.DateInput(attrs={'type':'date'}))
    new_salary=forms.DecimalField(label='Yeni yıllık maaş',min_value=0,max_digits=18,decimal_places=2)
    record_payment=forms.BooleanField(label='Bonservis bedelini şimdi ödenmiş olarak finans hareketine ekle',required=False)
    class Meta:
        model=CATALOG['transfers'][0]
        fields=['playerid','toclubid','transferdate','transferfee','transfertype','season']
    def clean(self):
        d=super().clean();p=d.get('playerid');c=d.get('toclubid');dt=d.get('transferdate')
        if p and c and p.clubid_id==c.pk:self.add_error('toclubid','Oyuncu zaten bu kulüpte.')
        if dt and dt>datetime.date.today():self.add_error('transferdate','Gelecek transferi geçmiş kayıt olarak planlayın; canlı transfer tarihi gelecekte olamaz.')
        if d.get('new_start') and dt and d['new_start']!=dt:self.add_error('new_start','Canlı işlemde sözleşme başlangıcı transfer tarihiyle aynı olmalı.')
        if d.get('new_start') and d.get('new_end') and d['new_end']<=d['new_start']:self.add_error('new_end','Bitiş başlangıçtan sonra olmalı.')
        if 'kiral' in d.get('transfertype','').casefold() or 'loan' in d.get('transfertype','').casefold():
            self.add_error('transfertype','Kiralık transferi geçmiş kayıt olarak ekleyin. Canlı kiralama dönüşü bu sürümde otomatik yönetilmez.')
        return d
