from django.db import models
from django.conf import settings
class Clubs(models.Model):
    clubid = models.AutoField(db_column='ClubID', primary_key=True)
    clubname = models.CharField(db_column='ClubName', unique=True, max_length=100, db_collation='Turkish_CI_AS')
    shortcode = models.CharField(db_column='ShortCode', unique=True, max_length=10, db_collation='Turkish_CI_AS')
    foundingyear = models.IntegerField(db_column='FoundingYear')
    city = models.CharField(db_column='City', max_length=50, db_collation='Turkish_CI_AS')
    budget = models.DecimalField(db_column='Budget', max_digits=18, decimal_places=2)
    createdat = models.DateTimeField(db_column='CreatedAt', blank=True, null=True)

    def __str__(self):
        return self.clubname

    class Meta:
        managed = False
        db_table = 'Clubs'
class Players(models.Model):
    playerid = models.AutoField(db_column='PlayerID', primary_key=True)
    clubid = models.ForeignKey(Clubs, models.PROTECT, db_column='ClubID')
    firstname = models.CharField(db_column='FirstName', max_length=50, db_collation='Turkish_CI_AS')
    lastname = models.CharField(db_column='LastName', max_length=50, db_collation='Turkish_CI_AS')
    birthdate = models.DateField(db_column='BirthDate')
    nationality = models.CharField(db_column='Nationality', max_length=50, db_collation='Turkish_CI_AS')
    position = models.CharField(db_column='Position', max_length=20, db_collation='Turkish_CI_AS')
    jerseynumber = models.IntegerField(db_column='JerseyNumber', blank=True, null=True)
    marketvalue = models.DecimalField(db_column='MarketValue', max_digits=18, decimal_places=2)
    createdat = models.DateTimeField(db_column='CreatedAt', blank=True, null=True)

    def __str__(self):
        return f'{self.firstname} {self.lastname}'

    class Meta:
        managed = False
        db_table = 'Players'
class Contracts(models.Model):
    contractid = models.AutoField(db_column='ContractID', primary_key=True)
    playerid = models.ForeignKey(Players, models.PROTECT, db_column='PlayerID')
    clubid = models.ForeignKey(Clubs, models.PROTECT, db_column='ClubID')
    startdate = models.DateField(db_column='StartDate')
    enddate = models.DateField(db_column='EndDate')
    annualsalary = models.DecimalField(db_column='AnnualSalary', max_digits=18, decimal_places=2)
    releaseclause = models.DecimalField(db_column='ReleaseClause', max_digits=18, decimal_places=2, blank=True, null=True)
    contractstatus = models.CharField(db_column='ContractStatus', max_length=20, db_collation='Turkish_CI_AS')
    createdat = models.DateTimeField(db_column='CreatedAt', blank=True, null=True)

    def __str__(self):
        return f'{self.playerid} · {self.enddate:%d.%m.%Y}'

    class Meta:
        managed = False
        db_table = 'Contracts'
class Technicalstaff(models.Model):
    staffid = models.AutoField(db_column='StaffID', primary_key=True)
    clubid = models.ForeignKey(Clubs, models.PROTECT, db_column='ClubID')
    firstname = models.CharField(db_column='FirstName', max_length=50, db_collation='Turkish_CI_AS')
    lastname = models.CharField(db_column='LastName', max_length=50, db_collation='Turkish_CI_AS')
    role = models.CharField(db_column='Role', max_length=50, db_collation='Turkish_CI_AS')
    nationality = models.CharField(db_column='Nationality', max_length=50, db_collation='Turkish_CI_AS')
    contractstartdate = models.DateField(db_column='ContractStartDate')
    contractenddate = models.DateField(db_column='ContractEndDate')
    annualsalary = models.DecimalField(db_column='AnnualSalary', max_digits=18, decimal_places=2)
    createdat = models.DateTimeField(db_column='CreatedAt', blank=True, null=True)

    def __str__(self):
        return f'{self.firstname} {self.lastname}'

    class Meta:
        managed = False
        db_table = 'TechnicalStaff'
class Stadiums(models.Model):
    stadiumid = models.AutoField(db_column='StadiumID', primary_key=True)
    clubid = models.OneToOneField(Clubs, models.PROTECT, db_column='ClubID')
    stadiumname = models.CharField(db_column='StadiumName', max_length=100, db_collation='Turkish_CI_AS')
    city = models.CharField(db_column='City', max_length=50, db_collation='Turkish_CI_AS')
    capacity = models.IntegerField(db_column='Capacity')
    builtyear = models.IntegerField(db_column='BuiltYear', blank=True, null=True)
    createdat = models.DateTimeField(db_column='CreatedAt', blank=True, null=True)

    def __str__(self):
        return self.stadiumname

    class Meta:
        managed = False
        db_table = 'Stadiums'
class Sponsorships(models.Model):
    sponsorshipid = models.AutoField(db_column='SponsorshipID', primary_key=True)
    clubid = models.ForeignKey(Clubs, models.PROTECT, db_column='ClubID')
    sponsorname = models.CharField(db_column='SponsorName', max_length=100, db_collation='Turkish_CI_AS')
    sponsorshiptype = models.CharField(db_column='SponsorshipType', max_length=50, db_collation='Turkish_CI_AS')
    annualamount = models.DecimalField(db_column='AnnualAmount', max_digits=18, decimal_places=2)
    startdate = models.DateField(db_column='StartDate')
    enddate = models.DateField(db_column='EndDate')
    contractstatus = models.CharField(db_column='ContractStatus', max_length=20, db_collation='Turkish_CI_AS')
    createdat = models.DateTimeField(db_column='CreatedAt', blank=True, null=True)

    def __str__(self):
        return self.sponsorname

    class Meta:
        managed = False
        db_table = 'Sponsorships'
class Transfers(models.Model):
    transferid = models.AutoField(db_column='TransferID', primary_key=True)
    playerid = models.ForeignKey(Players, models.PROTECT, db_column='PlayerID')
    fromclubid = models.ForeignKey(Clubs, models.PROTECT, db_column='FromClubID', blank=True, null=True)
    fromclubname = models.CharField(db_column='FromClubName', max_length=100, db_collation='Turkish_CI_AS')
    toclubid = models.ForeignKey(Clubs, models.PROTECT, db_column='ToClubID', related_name='transfers_toclubid_set')
    transferdate = models.DateField(db_column='TransferDate')
    transferfee = models.DecimalField(db_column='TransferFee', max_digits=18, decimal_places=2)
    transfertype = models.CharField(db_column='TransferType', max_length=30, db_collation='Turkish_CI_AS')
    season = models.CharField(db_column='Season', max_length=10, db_collation='Turkish_CI_AS')
    createdat = models.DateTimeField(db_column='CreatedAt', blank=True, null=True)

    def __str__(self):
        return f'{self.playerid} · {self.season}'

    class Meta:
        managed = False
        db_table = 'Transfers'
class Financialtransactions(models.Model):
    transactionid = models.AutoField(db_column='TransactionID', primary_key=True)
    clubid = models.ForeignKey(Clubs, models.PROTECT, db_column='ClubID')
    transactiontype = models.CharField(db_column='TransactionType', max_length=20, db_collation='Turkish_CI_AS')
    category = models.CharField(db_column='Category', max_length=50, db_collation='Turkish_CI_AS')
    amount = models.DecimalField(db_column='Amount', max_digits=18, decimal_places=2)
    transactiondate = models.DateField(db_column='TransactionDate')
    description = models.CharField(db_column='Description', max_length=255, db_collation='Turkish_CI_AS')
    season = models.CharField(db_column='Season', max_length=10, db_collation='Turkish_CI_AS')
    createdat = models.DateTimeField(db_column='CreatedAt', blank=True, null=True)

    def __str__(self):
        return f'{self.category} · {self.amount}'

    class Meta:
        managed = False
        db_table = 'FinancialTransactions'

class PlayerProfile(models.Model):
    player = models.OneToOneField(Players, on_delete=models.CASCADE, related_name='profile')
    archived = models.BooleanField(default=False)
    eligible_turkey = models.BooleanField(null=True, blank=True)
    eligibility_source = models.CharField(max_length=255, blank=True)
    youth_2002_exception = models.BooleanField(default=False)
    exception_verified = models.BooleanField(default=False)
    exception_note = models.CharField(max_length=255, blank=True)


class ClubSettings(models.Model):
    club = models.OneToOneField(Clubs, on_delete=models.CASCADE)
    currency = models.CharField(max_length=10, default='UNKNOWN')


class ClubAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    club = models.ForeignKey(Clubs, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'club'], name='unique_club_user_access')]


class SeasonSquad(models.Model):
    club = models.ForeignKey(Clubs, on_delete=models.PROTECT)
    season = models.CharField(max_length=10)
    ruleset = models.CharField(max_length=20, default='UNASSIGNED')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['club', 'season'], name='unique_club_season_squad')]


class SquadEntry(models.Model):
    squad = models.ForeignKey(SeasonSquad, on_delete=models.CASCADE, related_name='entries')
    player = models.ForeignKey(Players, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['squad', 'player'], name='unique_squad_player')]


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=30)
    entity = models.CharField(max_length=60)
    object_id = models.CharField(max_length=40)
    summary = models.CharField(max_length=255)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class TransferWorkflow(models.Model):
    transfer = models.OneToOneField(Transfers, on_delete=models.PROTECT, related_name='workflow')
    previous_club_id = models.IntegerField()
    old_contract_ids = models.JSONField(default=list)
    new_contract_id = models.IntegerField(null=True)
    transaction_ids = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='APPLIED')
    created_at = models.DateTimeField(auto_now_add=True)

    snapshot = models.JSONField(default=dict)
