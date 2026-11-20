from .models import Clubs, Players, Contracts, Technicalstaff, Stadiums, Sponsorships, Transfers, Financialtransactions
CATALOG = {
 'clubs': (Clubs, 'Kulüpler', ['clubname','shortcode','city','foundingyear','budget']),
 'players': (Players, 'Oyuncular', ['firstname','lastname','clubid','position','jerseynumber','marketvalue']),
 'contracts': (Contracts, 'Sözleşmeler', ['playerid','clubid','startdate','enddate','annualsalary','contractstatus']),
 'transfers': (Transfers, 'Transferler', ['playerid','fromclubname','toclubid','transferdate','transferfee','season']),
 'sponsorships': (Sponsorships, 'Sponsorlar', ['sponsorname','clubid','sponsorshiptype','annualamount','enddate','contractstatus']),
 'finance': (Financialtransactions, 'Finans hareketleri', ['clubid','transactiontype','category','amount','transactiondate','season']),
 'staff': (Technicalstaff, 'Teknik ekip', ['firstname','lastname','clubid','role','annualsalary','contractenddate']),
 'stadiums': (Stadiums, 'Stadyumlar', ['stadiumname','clubid','city','capacity','builtyear']),
}
LABELS = {
 'clubname':'Kulüp adı','shortcode':'Kısa kod','city':'Şehir','foundingyear':'Kuruluş yılı','budget':'Bütçe',
 'firstname':'Ad','lastname':'Soyad','clubid':'Kulüp','position':'Mevki','jerseynumber':'Forma no',
 'marketvalue':'Piyasa değeri','birthdate':'Doğum tarihi','nationality':'Uyruk',
 'playerid':'Oyuncu','startdate':'Başlangıç','enddate':'Bitiş','annualsalary':'Yıllık maaş',
 'releaseclause':'Serbest kalma bedeli','contractstatus':'Durum','fromclubname':'Geldiği kulüp',
 'fromclubid':'Kaynak kulüp (kayıtlıysa)','toclubid':'Hedef kulüp','transferdate':'Transfer tarihi',
 'transferfee':'Transfer bedeli','transfertype':'Transfer türü','season':'Sezon',
 'sponsorname':'Sponsor','sponsorshiptype':'Sponsorluk türü','annualamount':'Yıllık tutar',
 'transactiontype':'Hareket türü','category':'Kategori','amount':'Tutar','transactiondate':'İşlem tarihi',
 'description':'Açıklama','role':'Görev','contractstartdate':'Sözleşme başlangıcı',
 'contractenddate':'Sözleşme bitişi','stadiumname':'Stadyum','capacity':'Kapasite','builtyear':'Yapım yılı',
}
