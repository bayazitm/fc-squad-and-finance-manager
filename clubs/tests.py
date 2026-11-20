import datetime
from decimal import Decimal
from django.test import TransactionTestCase, Client
from django.contrib.auth.models import User, Group
from django.db import connection
from django.core.exceptions import ValidationError, PermissionDenied
from .models import *
from .forms import ProfileForm, LiveTransferForm
from .services import renew_contract,apply_transfer,cancel_transfer,evaluate_squad
from .catalog import CATALOG

LEGACY=[Clubs,Players,Contracts,Technicalstaff,Stadiums,Sponsorships,Transfers,Financialtransactions]
class ClubAppTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as editor:
            for model in LEGACY:editor.create_model(model)
    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as editor:
            for model in reversed(LEGACY):editor.delete_model(model)
        super().tearDownClass()
    def tearDown(self):
        with connection.constraint_checks_disabled():
            with connection.cursor() as cursor:
                for model in reversed(LEGACY):
                    cursor.execute("DELETE FROM " + connection.ops.quote_name(model._meta.db_table))
        super().tearDown()
    def setUp(self):
        self.admin=User.objects.create_superuser('admin','a@example.com','testing-password')
        self.c1=Clubs.objects.create(clubname='Fenerbahçe SK',shortcode='FB',city='İstanbul',foundingyear=1907,budget=100000)
        self.c2=Clubs.objects.create(clubname='Trabzonspor',shortcode='TS',city='Trabzon',foundingyear=1967,budget=200000)
        self.p=Players.objects.create(clubid=self.c1,firstname='Deneme',lastname='Oyuncu',birthdate='2004-05-01',nationality='Türkiye',position='Forvet',jerseynumber=9,marketvalue=50000)
        self.c=Contracts.objects.create(playerid=self.p,clubid=self.c1,startdate='2024-07-01',enddate='2027-06-30',annualsalary=123456,releaseclause=1000000,contractstatus='Aktif')
        self.client.force_login(self.admin)
        self.today=datetime.date.today()
    def data(self):
        return {'playerid':self.p,'toclubid':self.c2,'transferdate':self.today,'transferfee':Decimal('1000'),
          'transfertype':'Bonservis','season':'2026/2027','new_start':self.today,'new_end':self.today.replace(year=self.today.year+3),
          'new_salary':Decimal('123456'),'record_payment':False}
    def test_every_screen_and_form_renders(self):
        urls=['/','/?club='+str(self.c1.pk),'/kadro/','/kadro/?club='+str(self.c1.pk),'/gecmis/',
          f'/oyuncu/{self.p.pk}/',f'/oyuncu/{self.p.pk}/uygunluk/',f'/sozlesme/{self.c.pk}/yenile/',
          '/transfer/yeni-islem/',f'/kulup/{self.c1.pk}/ayarlar/']
        for kind in CATALOG:urls += [f'/kayitlar/{kind}/',f'/kayitlar/{kind}/yeni/']
        for url in urls:
            with self.subTest(url=url):self.assertEqual(self.client.get(url).status_code,200)
    def test_legacy_models_remain_unmanaged(self):
        self.assertTrue(all(not m._meta.managed for m in LEGACY))
    def test_sponsor_create_update_delete_audited(self):
        d={'clubid':self.c1.pk,'sponsorname':'Sponsor A','sponsorshiptype':'Forma','annualamount':'1000','startdate':'2026-07-01','enddate':'2029-06-30','contractstatus':'Aktif'}
        self.assertEqual(self.client.post('/kayitlar/sponsorships/yeni/',d).status_code,302)
        obj=Sponsorships.objects.get();d['sponsorname']='Sponsor B'
        self.client.post(f'/kayitlar/sponsorships/{obj.pk}/duzenle/',d)
        self.assertEqual(Sponsorships.objects.get().sponsorname,'Sponsor B')
        log=AuditLog.objects.filter(action='UPDATE').get()
        self.assertEqual(log.before['sponsorname'],'Sponsor A')
        self.assertEqual(log.after['sponsorname'],'Sponsor B')
        self.client.post(f'/kayitlar/sponsorships/{obj.pk}/sil/')
        self.assertFalse(Sponsorships.objects.exists());self.assertEqual(AuditLog.objects.count(),3)
    def test_renewal_preserves_old_dates_and_salary(self):
        new=renew_contract(self.admin,self.c.pk,{'startdate':self.today,'enddate':self.today.replace(year=self.today.year+3),'annualsalary':Decimal('200000'),'releaseclause':None})
        self.c.refresh_from_db();self.assertEqual(self.c.annualsalary,123456)
        self.assertEqual(self.c.enddate,datetime.date(2027,6,30));self.assertEqual(self.c.contractstatus,'Yenilendi')
        self.assertEqual(new.annualsalary,200000);self.assertEqual(Contracts.objects.count(),2)
    def test_future_renewal_is_planned(self):
        start=self.today+datetime.timedelta(days=5)
        new=renew_contract(self.admin,self.c.pk,{'startdate':start,'enddate':start.replace(year=start.year+3),'annualsalary':Decimal('123456'),'releaseclause':None})
        self.c.refresh_from_db();self.assertEqual(self.c.contractstatus,'Aktif');self.assertEqual(new.contractstatus,'Planlandı')
    def test_transfer_and_cancel_restore_money_contract_and_squad(self):
        for c in [self.c1,self.c2]:ClubSettings.objects.create(club=c,currency='EUR')
        sq=SeasonSquad.objects.create(club=self.c1,season='2026/2027');SquadEntry.objects.create(squad=sq,player=self.p)
        data=self.data();data['record_payment']=True
        tr=apply_transfer(self.admin,data)
        self.p.refresh_from_db();self.assertEqual(self.p.clubid_id,self.c2.pk)
        self.assertEqual(Financialtransactions.objects.count(),2);self.assertEqual(Contracts.objects.count(),2)
        self.assertFalse(SquadEntry.objects.exists())
        cancel_transfer(self.admin,tr.pk)
        self.p.refresh_from_db();self.c.refresh_from_db()
        self.assertEqual(self.p.clubid_id,self.c1.pk);self.assertEqual(self.c.contractstatus,'Aktif')
        self.assertEqual(self.c.annualsalary,123456);self.assertEqual(Contracts.objects.count(),1)
        self.assertEqual(Financialtransactions.objects.count(),0);self.assertEqual(SquadEntry.objects.count(),1)
        self.assertEqual(TransferWorkflow.objects.get().status,'CANCELLED')
    def test_transfer_rollback_on_unknown_currency(self):
        data=self.data();data['record_payment']=True
        with self.assertRaises(ValidationError):apply_transfer(self.admin,data)
        self.assertFalse(Transfers.objects.exists());self.assertEqual(Contracts.objects.count(),1)
        self.p.refresh_from_db();self.assertEqual(self.p.clubid_id,self.c1.pk)
    def test_cancel_rejects_changed_salary_and_preserves_transfer(self):
        tr=apply_transfer(self.admin,self.data());wf=tr.workflow
        Contracts.objects.filter(pk=wf.new_contract_id).update(annualsalary=42)
        with self.assertRaises(ValidationError):cancel_transfer(self.admin,tr.pk)
        self.p.refresh_from_db();self.assertEqual(self.p.clubid_id,self.c2.pk)
    def test_viewer_cannot_write(self):
        user=User.objects.create_user('viewer',password='testing-password');g,_=Group.objects.get_or_create(name='Görüntüleyici');user.groups.add(g)
        self.client.force_login(user);self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.post('/kayitlar/clubs/yeni/',{}).status_code,403)
    def test_club_user_cannot_access_other_club(self):
        user=User.objects.create_user('limited',password='testing-password');g,_=Group.objects.get_or_create(name='Kulüp Yetkilisi');user.groups.add(g);ClubAccess.objects.create(user=user,club=self.c1)
        self.client.force_login(user)
        self.assertEqual(self.client.get(f'/kayitlar/clubs/{self.c2.pk}/duzenle/').status_code,404)
        with self.assertRaises(PermissionDenied):apply_transfer(user,self.data())
    def test_unauthenticated_redirect(self):
        self.client.logout();self.assertEqual(self.client.get('/').status_code,302)
    def test_csrf_prevents_write(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post('/kayitlar/sponsorships/yeni/',{}).status_code,403)
    def test_protected_player_delete_keeps_contract(self):
        response=self.client.post(f'/kayitlar/players/{self.p.pk}/sil/')
        self.assertEqual(response.status_code,200);self.assertTrue(Players.objects.exists());self.assertTrue(Contracts.objects.exists())
    def test_archive_removes_squad_not_player(self):
        sq=SeasonSquad.objects.create(club=self.c1,season='2026/2027');SquadEntry.objects.create(squad=sq,player=self.p)
        self.client.post(f'/oyuncu/{self.p.pk}/uygunluk/',{'archived':'on','eligible_turkey':''})
        self.assertTrue(Players.objects.exists());self.assertTrue(PlayerProfile.objects.get().archived);self.assertFalse(SquadEntry.objects.exists())
    def test_profile_unknown_not_foreign(self):
        form=ProfileForm({'eligible_turkey':''},instance=PlayerProfile(player=self.p))
        self.assertTrue(form.is_valid(),form.errors);self.assertIsNone(form.cleaned_data['eligible_turkey'])
    def test_squad_does_not_infer_from_nationality(self):
        self.p.birthdate=datetime.date(2004,5,1)
        result=evaluate_squad([(self.p,None)],'SUPERLIG_2627','2026/2027')
        self.assertEqual(result['unknown'],1);self.assertEqual(result['foreign'],0);self.assertEqual(result['state'],'unknown')
    def test_foreign_14_requires_4_young(self):
        entries=[]
        for i in range(14):
            p=Players(firstname='A',lastname=str(i),position='Forvet',birthdate=datetime.date(2000,1,1))
            profile=PlayerProfile(eligible_turkey=False,eligibility_source='TFF')
            entries.append((p,profile))
        result=evaluate_squad(entries,'SUPERLIG_2627','2026/2027')
        self.assertEqual(result['state'],'bad');self.assertTrue(any('4 genç yabancı' in v for v in result['issues']))
    def test_invalid_squad_club_player_not_saved(self):
        self.client.get('/?club='+str(self.c2.pk))
        response=self.client.post('/kadro/',{'ruleset':'SUPERLIG_2627','players':[str(self.p.pk)]})
        self.assertEqual(response.status_code,200);self.assertFalse(SquadEntry.objects.exists())
    def test_csv_formula_neutralized(self):
        self.c1.clubname='=1+1';self.c1.save()
        response=self.client.get('/kayitlar/clubs/?export=csv')
        self.assertIn("'=1+1",response.content.decode())
    def test_historical_transfer_does_not_move_player(self):
        response=self.client.post('/kayitlar/transfers/yeni/',{'playerid':self.p.pk,'fromclubid':self.c1.pk,'fromclubname':'Wrong text','toclubid':self.c2.pk,'transferdate':'2024-07-01','transferfee':'100','transfertype':'Bonservis','season':'2024/2025'})
        self.assertEqual(response.status_code,302)
        self.p.refresh_from_db();self.assertEqual(self.p.clubid_id,self.c1.pk)
        self.assertEqual(Transfers.objects.get().fromclubname,self.c1.clubname)

    def test_activate_planned_contract_preserves_old(self):
        from .services import activate_contract
        new=Contracts.objects.create(playerid=self.p,clubid=self.c1,startdate=self.today,enddate=self.today.replace(year=self.today.year+2),annualsalary=999,contractstatus='Planlandı')
        activate_contract(self.admin,new.pk)
        new.refresh_from_db();self.c.refresh_from_db()
        self.assertEqual(new.contractstatus,'Aktif');self.assertEqual(self.c.contractstatus,'Yenilendi');self.assertEqual(self.c.annualsalary,123456)
    def test_live_transfer_failure_rolls_back_prior_writes(self):
        from unittest.mock import patch
        from django.db import IntegrityError
        with patch('clubs.services.Contracts.objects.create',side_effect=IntegrityError('simulated failure')):
            with self.assertRaises(IntegrityError):apply_transfer(self.admin,self.data())
        self.p.refresh_from_db();self.c.refresh_from_db()
        self.assertEqual(self.p.clubid_id,self.c1.pk);self.assertEqual(self.c.contractstatus,'Aktif')
        self.assertFalse(Transfers.objects.exists());self.assertFalse(AuditLog.objects.exists())
    def test_live_loan_rejected(self):
        data={'playerid':self.p.pk,'toclubid':self.c2.pk,'transferdate':self.today,'transferfee':'0','transfertype':'Kiralık (Opsiyonlu)','season':'2026/2027','new_start':self.today,'new_end':'2029-06-30','new_salary':'100'}
        form=LiveTransferForm(data,user=self.admin,kind='transfers')
        self.assertFalse(form.is_valid());self.assertIn('transfertype',form.errors)
    def test_linked_contract_cannot_be_deleted(self):
        tr=apply_transfer(self.admin,self.data())
        pk=tr.workflow.new_contract_id
        self.assertEqual(self.client.post(f'/kayitlar/contracts/{pk}/sil/').status_code,302)
        self.assertTrue(Contracts.objects.filter(pk=pk).exists())
    def test_finance_not_aggregated_across_all_clubs(self):
        response=self.client.get('/?club=')
        self.assertIsNone(response.context['income']);self.assertIsNone(response.context['salary_total'])
    def test_negative_money_rejected(self):
        response=self.client.post('/kayitlar/finance/yeni/',{'clubid':self.c1.pk,'transactiontype':'Gider','category':'Test','amount':'-5','transactiondate':'2026-11-20','description':'Test','season':'2026/2027'})
        self.assertEqual(response.status_code,200);self.assertFalse(Financialtransactions.objects.exists())

class ReportingTests(ClubAppTests):
    def test_report_query_is_scoped_and_parameterized(self):
        from unittest.mock import patch
        from .reporting import read_report
        with patch('clubs.reporting.fetch', return_value=[{'ClubName': 'FB'}]) as fetch:
            rows, error = read_report('finance', [self.c1.pk], '2026/2027')
            sql, params = fetch.call_args.args
            self.assertIn('dbo.vw_ClubFinancialSummary', sql)
            self.assertIn('ClubID IN (%s)', sql)
            self.assertEqual(params, [self.c1.pk, '2026/2027'])
            self.assertFalse(error)
            self.assertEqual(rows[0]['ClubName'], 'FB')
    def test_history_diffs_and_filters(self):
        from unittest.mock import patch
        from .reporting import read_database_history
        data = [{'AuditID': 1, 'OldValues': '{"AnnualAmount":100}', 'NewValues': '{"AnnualAmount":200}'}]
        with patch('clubs.reporting.fetch', return_value=data) as fetch:
            rows, error = read_database_history(self.c1.pk, 'Sponsorships', 'UPDATE')
            self.assertEqual(fetch.call_args.args[1], [self.c1.pk, self.c1.pk, 'Sponsorships', 'UPDATE'])
            self.assertEqual(rows[0]['changes'], [{'field':'AnnualAmount', 'before':100, 'after':200}])
    def test_report_pages_render_from_database_reader(self):
        from unittest.mock import patch
        with patch('clubs.reporting.fetch', return_value=[]):
            for url in ['/raporlar/', '/raporlar/?report=squad', '/raporlar/?report=alerts', '/veritabani-gecmisi/']:
                self.assertEqual(self.client.get(url).status_code, 200)
    def test_missing_sql_objects_display_error_not_success(self):
        from unittest.mock import patch
        from django.db import DatabaseError
        with patch('clubs.reporting.fetch', side_effect=DatabaseError('missing')):
            self.assertContains(self.client.get('/raporlar/'), 'Rapor okunamadı')
            self.assertContains(self.client.get('/veritabani-gecmisi/'), 'Günlük okunamadı')
    def test_club_only_user_cannot_read_global_audit(self):
        user=User.objects.create_user('limited')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/veritabani-gecmisi/').status_code,403)
    def test_local_demo_opens_without_password_and_writes_audited_records(self):
        from django.test import override_settings
        from django.conf import settings
        middleware=list(settings.MIDDLEWARE)
        middleware.insert(middleware.index('django.contrib.auth.middleware.AuthenticationMiddleware')+1,'clubs.middleware.LocalDemoMiddleware')
        with override_settings(TOUCHLINE_LOCAL_DEMO=True,DEBUG=True,MIDDLEWARE=middleware):
            client=Client()
            self.assertEqual(client.get('/').status_code,200)
            response=client.post('/kayitlar/sponsorships/yeni/', {'clubid':self.c1.pk,'sponsorname':'Demo Sponsor','sponsorshiptype':'Forma','annualamount':'1000','startdate':'2026-07-01','enddate':'2029-06-30','contractstatus':'Aktif'})
            self.assertEqual(response.status_code,302)
            self.assertEqual(AuditLog.objects.get().user.username,'touchline-local-demo')
            user=User.objects.get(username='touchline-local-demo')
            self.assertFalse(user.has_usable_password())
            self.assertFalse(user.is_staff)
            self.assertEqual(client.get('/',REMOTE_ADDR='192.168.1.10').status_code,403)
            with override_settings(DEBUG=False):
                self.assertEqual(client.get('/').status_code,403)
    def test_new_squad_preselects_current_players_without_database_write(self):
        response=self.client.get(f'/kadro/?club={self.c1.pk}&season=2026/2027')
        self.assertEqual(response.context['selected_count'],1)
        self.assertEqual(response.context['selected_ruleset'],'SUPERLIG_2627')
        self.assertFalse(SeasonSquad.objects.exists())
        self.assertTrue(response.context['squad_rows'][0]['selected'])
        self.assertEqual(response.context['result']['estimated'],1)
    def test_squad_preview_does_not_persist_and_save_roundtrips(self):
        self.p.nationality='Brezilya';self.p.save()
        url=f'/kadro/?club={self.c1.pk}&season=2026/2027'
        payload={'ruleset':'SUPERLIG_2627','players':[self.p.pk],'action':'preview'}
        response=self.client.post(url,payload,HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response,'1 / 14')
        self.assertEqual(response.context['result']['foreign'],1)
        self.assertEqual(response.context['result']['estimated'],1)
        self.assertFalse(SeasonSquad.objects.exists())
        self.assertFalse(AuditLog.objects.exists())
        payload['action']='save'
        response=self.client.post(url,payload)
        self.assertEqual(response.status_code,302)
        self.assertEqual(SquadEntry.objects.get().player_id,self.p.pk)
        self.assertEqual(self.client.get(response.url).context['selected_count'],1)
    def test_empty_saved_squad_stays_empty_and_archived_players_are_excluded(self):
        SeasonSquad.objects.create(club=self.c1,season='2026/2027',ruleset='SUPERLIG_2627')
        response=self.client.get(f'/kadro/?club={self.c1.pk}&season=2026/2027')
        self.assertEqual(response.context['selected_count'],0)
        PlayerProfile.objects.create(player=self.p,archived=True)
        self.assertEqual(len(self.client.get(f'/kadro/?club={self.c1.pk}').context['squad_rows']),0)
    def test_nationality_estimates_never_replace_verified_eligibility(self):
        from .services import squad_status
        self.p.nationality='Almanya'
        profile=PlayerProfile(eligible_turkey=True,eligibility_source='verified registry')
        self.assertEqual(squad_status(self.p,profile,True),('domestic',False))
        self.p.nationality='Türkiye / Almanya'
        self.assertEqual(squad_status(self.p,None,True),('unknown',False))
        self.p.nationality='Türkiye'
        self.assertEqual(squad_status(self.p,None,True),('domestic',True))
        self.p.nationality=''
        self.assertEqual(squad_status(self.p,None,True),('unknown',False))
    def test_fourteen_and_fifteen_foreign_players_estimate_limit(self):
        from .services import evaluate_squad
        entries=[(Players(firstname='P',lastname=str(i),nationality='Brezilya',position='Forvet',birthdate=datetime.date(2004 if i<4 else 2000,1,1)),None) for i in range(15)]
        result=evaluate_squad(entries[:14],'SUPERLIG_2627','2026/2027',True)
        self.assertEqual((result['foreign'],result['young'],result['estimated']),(14,4,14))
        self.assertFalse(any('4 genç yabancı gerekli' in s for s in result['issues']))
        result=evaluate_squad(entries,'SUPERLIG_2627','2026/2027',True)
        self.assertTrue(any('üst sınırı 14' in s for s in result['issues']))
    def test_preview_keeps_selection_after_invalid_ruleset(self):
        response=self.client.post(f'/kadro/?club={self.c1.pk}&season=2025/2026',{'ruleset':'SUPERLIG_2627','players':[self.p.pk],'action':'preview'})
        self.assertEqual(response.context['selected_count'],1)
        self.assertIsNotNone(response.context['error'])
        self.assertFalse(SeasonSquad.objects.exists())
    def test_existing_unassigned_ruleset_gets_current_season_preview_default(self):
        squad=SeasonSquad.objects.create(club=self.c1,season='2026/2027')
        SquadEntry.objects.create(squad=squad,player=self.p)
        response=self.client.get(f'/kadro/?club={self.c1.pk}&season=2026/2027')
        self.assertEqual(response.context['selected_ruleset'],'SUPERLIG_2627')
        self.assertEqual(response.context['selected_count'],1)
        squad.refresh_from_db()
        self.assertEqual(squad.ruleset,'UNASSIGNED')
    def prior_youth_transfer(self, date='2025-08-01'):
        self.p.birthdate=datetime.date(2002,5,28);self.p.nationality='İngiltere';self.p.save()
        return Transfers.objects.create(playerid=self.p,fromclubname='Previous club',toclubid=self.c1,transferdate=date,transferfee=1000,transfertype='Bonservis',season='2025/2026')
    def test_2002_continuation_is_automatic_bulk_read_only_estimate(self):
        from .services import squad_youth_info
        self.prior_youth_transfer()
        with self.assertNumQueries(3):
            info=squad_youth_info([self.p],'2026/2027')
        self.assertTrue(info[self.p.pk]['young']);self.assertTrue(info[self.p.pk]['estimated'])
        self.assertFalse(PlayerProfile.objects.exists())
        response=self.client.get(f'/kadro/?club={self.c1.pk}&season=2026/2027')
        self.assertEqual(response.context['result']['young'],1)
        self.assertEqual(response.context['result']['youth_estimated'],1)
        self.assertContains(response,'tahmini devam hakkı')
        self.assertFalse(PlayerProfile.objects.exists());self.assertFalse(SeasonSquad.objects.exists())
    def test_new_2002_signing_gets_no_automatic_continuation(self):
        from .services import squad_youth_info
        self.prior_youth_transfer('2026-08-01')
        self.assertFalse(squad_youth_info([self.p],'2026/2027')[self.p.pk]['young'])
    def test_continuation_requires_current_original_contract(self):
        from .services import squad_youth_info
        self.prior_youth_transfer()
        self.c.enddate=datetime.date(2026,6,30);self.c.save()
        self.assertFalse(squad_youth_info([self.p],'2026/2027')[self.p.pk]['young'])
        self.c.enddate=datetime.date(2030,6,30);self.c.startdate=datetime.date(2026,7,1);self.c.save()
        self.assertFalse(squad_youth_info([self.p],'2026/2027')[self.p.pk]['young'])
    def test_recent_club_change_and_loans_do_not_get_continuation(self):
        from .services import squad_youth_info
        transfer=self.prior_youth_transfer()
        transfer.transfertype='Kiralık';transfer.save()
        self.assertFalse(squad_youth_info([self.p],'2026/2027')[self.p.pk]['young'])
        transfer.transfertype='Bonservis';transfer.save()
        Transfers.objects.create(playerid=self.p,fromclubid=self.c1,fromclubname='Old',toclubid=self.c2,transferdate='2026-08-01',transferfee=100,transfertype='Bonservis',season='2026/2027')
        self.assertFalse(squad_youth_info([self.p],'2026/2027')[self.p.pk]['young'])
    def test_continuation_does_not_apply_in_other_seasons(self):
        from .services import squad_youth_info
        self.prior_youth_transfer()
        self.assertFalse(squad_youth_info([self.p],'2027/2028')[self.p.pk]['young'])
