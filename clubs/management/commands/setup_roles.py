from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
class Command(BaseCommand):
    help='Uygulama rollerini oluşturur; mevcut kullanıcılara yetki atamaz.'
    def handle(self,*args,**options):
        for name in ['Yönetici','Kulüp Yetkilisi','Görüntüleyici']:
            Group.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS('Roller hazır. Kullanıcıları /admin/ üzerinden gruplara atayabilirsiniz.'))
