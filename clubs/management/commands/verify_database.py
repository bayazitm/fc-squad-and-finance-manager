from django.core.management.base import BaseCommand
from django.db import connection
from clubs.models import Clubs,Players,Contracts,Technicalstaff,Stadiums,Sponsorships,Transfers,Financialtransactions
class Command(BaseCommand):
    help='Mevcut sekiz tablonun okunabildigini kontrol eder; veri degistirmez.'
    def handle(self,*args,**options):
        with connection.cursor() as cursor:
            cursor.execute('SELECT DB_NAME()')
            self.stdout.write('Veritabani: '+str(cursor.fetchone()[0]))
        for model in [Clubs,Players,Contracts,Technicalstaff,Stadiums,Sponsorships,Transfers,Financialtransactions]:
            self.stdout.write(f'{model._meta.db_table}: {model.objects.count()}')
