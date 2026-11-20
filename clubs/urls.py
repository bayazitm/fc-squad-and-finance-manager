from django.urls import path
from . import views
app_name='clubs'
urlpatterns=[
 path('raporlar/',views.database_reports,name='database_reports'),
 path('veritabani-gecmisi/',views.database_history,name='database_history'),
 path('',views.dashboard,name='dashboard'),
 path('kadro/',views.squad,name='squad'),
 path('gecmis/',views.history,name='history'),
 path('oyuncu/<int:pk>/',views.player_detail,name='player'),
 path('oyuncu/<int:pk>/uygunluk/',views.edit_profile,name='profile'),
 path('sozlesme/<int:pk>/baslat/',views.activate,name='activate'),
 path('sozlesme/<int:pk>/yenile/',views.renew,name='renew'),
 path('transfer/yeni-islem/',views.live_transfer,name='live_transfer'),
 path('transfer/<int:pk>/iptal/',views.cancel_live_transfer,name='cancel_transfer'),
 path('kulup/<int:pk>/ayarlar/',views.club_settings,name='club_settings'),
 path('kayitlar/<slug:kind>/',views.records,name='records'),
 path('kayitlar/<slug:kind>/yeni/',views.edit_record,name='create'),
 path('kayitlar/<slug:kind>/<int:pk>/duzenle/',views.edit_record,name='edit'),
 path('kayitlar/<slug:kind>/<int:pk>/sil/',views.delete_record,name='delete'),
]
