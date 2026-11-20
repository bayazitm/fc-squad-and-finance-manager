USE [FutbolKadroFinansDB];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF @@TRANCOUNT<>0 THROW 51200,N'Bu testi açık başka işlem bulunmayan yeni sorguda çalıştırın.',1;
IF OBJECT_ID(N'dbo.vw_ClubFinancialSummary',N'V') IS NULL
 OR OBJECT_ID(N'dbo.vw_ClubSquadSummary',N'V') IS NULL
 OR OBJECT_ID(N'dbo.vw_ContractAlerts',N'V') IS NULL
 OR OBJECT_ID(N'dbo.DatabaseChangeLog',N'U') IS NULL
    THROW 51201,N'Önce 06_views.sql ve 07_triggers.sql dosyalarını çalıştırın.',1;
IF (SELECT COUNT(*) FROM sys.triggers WHERE name IN (N'trg_Contracts_Audit',N'trg_Sponsorships_Audit') AND is_disabled=0)<>2
    THROW 51202,N'İki audit trigger da etkin olmalı.',1;

-- Pure reads: compare grouped view results to the underlying rows.
IF COALESCE((SELECT SUM(PlayerCount) FROM dbo.vw_ClubSquadSummary),0)
    <> (SELECT COUNT_BIG(*) FROM dbo.Players)
    THROW 51203,N'Kadro view oyuncu toplamı eşleşmiyor.',1;
IF COALESCE((SELECT SUM(TransactionCount) FROM dbo.vw_ClubFinancialSummary),0)
    <> (SELECT COUNT_BIG(*) FROM dbo.FinancialTransactions)
    THROW 51204,N'Finans view hareket toplamı eşleşmiyor.',1;
IF EXISTS (
    SELECT ClubID,Season,
           SUM(CASE WHEN TransactionType=N'Gelir' THEN Amount ELSE CONVERT(decimal(18,2),0) END),
           SUM(CASE WHEN TransactionType=N'Gider' THEN Amount ELSE CONVERT(decimal(18,2),0) END)
    FROM dbo.FinancialTransactions GROUP BY ClubID,Season
    EXCEPT
    SELECT ClubID,Season,TotalIncome,TotalExpense FROM dbo.vw_ClubFinancialSummary
) THROW 51205,N'Finans view tutarları eşleşmiyor.',1;

SELECT * FROM dbo.vw_ClubSquadSummary ORDER BY ClubName;
SELECT * FROM dbo.vw_ClubFinancialSummary ORDER BY Season,ClubName;
SELECT * FROM dbo.vw_ContractAlerts ORDER BY DaysRemaining,ClubName;

-- Optional runtime checks below modify temporary test rows/values and then ROLLBACK.
-- Identity counters can have gaps after rolled-back INSERTs.
DECLARE @TestClub int=(SELECT MIN(ClubID) FROM dbo.Clubs);
DECLARE @TestPlayer int=(SELECT MIN(PlayerID) FROM dbo.Players);
IF @TestClub IS NULL OR @TestPlayer IS NULL
    THROW 51206,N'Trigger testi için en az bir kulüp ve oyuncu gerekiyor.',1;

DECLARE @Contracts TABLE (ContractID int PRIMARY KEY,Salary decimal(18,2));
DECLARE @Sponsors TABLE (SponsorshipID int PRIMARY KEY,Amount decimal(18,2));
INSERT @Contracts SELECT TOP(2) ContractID,AnnualSalary FROM dbo.Contracts ORDER BY ContractID;
INSERT @Sponsors SELECT TOP(2) SponsorshipID,AnnualAmount FROM dbo.Sponsorships ORDER BY SponsorshipID;
IF (SELECT COUNT(*) FROM @Contracts)<>2 OR (SELECT COUNT(*) FROM @Sponsors)<>2
    THROW 51207,N'Çoklu satır testi için en az iki sözleşme ve iki sponsorluk gerekiyor.',1;

BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @Before bigint=COALESCE((SELECT MAX(AuditID) FROM dbo.DatabaseChangeLog),0);
    DECLARE @ContractPK int,@SponsorPK int;

    INSERT dbo.Contracts(PlayerID,ClubID,StartDate,EndDate,AnnualSalary,ReleaseClause,ContractStatus)
    VALUES(@TestPlayer,@TestClub,CAST(GETDATE() AS date),DATEADD(year,1,CAST(GETDATE() AS date)),0,NULL,N'Test');
    SET @ContractPK=CONVERT(int,SCOPE_IDENTITY());
    IF (SELECT COUNT(*) FROM dbo.DatabaseChangeLog WHERE AuditID>@Before AND SessionID=@@SPID
        AND TableName=N'Contracts' AND RecordID=@ContractPK AND Operation=N'INSERT'
        AND OldValues IS NULL AND ISJSON(NewValues)=1)<>1
        THROW 51210,N'Sözleşme INSERT audit testi başarısız.',1;
    DELETE dbo.Contracts WHERE ContractID=@ContractPK;
    IF (SELECT COUNT(*) FROM dbo.DatabaseChangeLog WHERE AuditID>@Before AND SessionID=@@SPID
        AND TableName=N'Contracts' AND RecordID=@ContractPK AND Operation=N'DELETE'
        AND NewValues IS NULL AND ISJSON(OldValues)=1)<>1
        THROW 51211,N'Sözleşme DELETE audit testi başarısız.',1;

    SET @Before=COALESCE((SELECT MAX(AuditID) FROM dbo.DatabaseChangeLog),0);
    UPDATE c SET AnnualSalary=CASE WHEN c.AnnualSalary>=0.01 THEN c.AnnualSalary-0.01 ELSE 0.01 END
    FROM dbo.Contracts AS c JOIN @Contracts AS t ON t.ContractID=c.ContractID;
    IF (SELECT COUNT(*) FROM dbo.DatabaseChangeLog AS l JOIN @Contracts AS t ON t.ContractID=l.RecordID
        WHERE l.AuditID>@Before AND l.SessionID=@@SPID AND l.TableName=N'Contracts' AND l.Operation=N'UPDATE')<>2
        THROW 51212,N'Sözleşme çoklu UPDATE audit testi başarısız.',1;
    IF EXISTS (
        SELECT 1 FROM dbo.DatabaseChangeLog AS l JOIN @Contracts AS t ON t.ContractID=l.RecordID
        JOIN dbo.Contracts AS c ON c.ContractID=t.ContractID
        WHERE l.AuditID>@Before AND l.SessionID=@@SPID AND l.TableName=N'Contracts' AND l.Operation=N'UPDATE'
          AND (TRY_CONVERT(decimal(18,2),JSON_VALUE(l.OldValues,'$.AnnualSalary'))<>t.Salary
               OR TRY_CONVERT(decimal(18,2),JSON_VALUE(l.NewValues,'$.AnnualSalary'))<>c.AnnualSalary)
    ) THROW 51213,N'Sözleşme eski/yeni maaş bilgisi eşleşmiyor.',1;
    SET @Before=COALESCE((SELECT MAX(AuditID) FROM dbo.DatabaseChangeLog),0);
    UPDATE c SET AnnualSalary=c.AnnualSalary FROM dbo.Contracts AS c JOIN @Contracts AS t ON t.ContractID=c.ContractID;
    IF EXISTS (SELECT 1 FROM dbo.DatabaseChangeLog WHERE AuditID>@Before AND SessionID=@@SPID AND TableName=N'Contracts')
        THROW 51214,N'Değişmeyen sözleşme için gereksiz log üretildi.',1;

    SET @Before=COALESCE((SELECT MAX(AuditID) FROM dbo.DatabaseChangeLog),0);
    INSERT dbo.Sponsorships(ClubID,SponsorName,SponsorshipType,AnnualAmount,StartDate,EndDate,ContractStatus)
    VALUES(@TestClub,N'TRIGGER TEST',N'Test',0,CAST(GETDATE() AS date),DATEADD(year,1,CAST(GETDATE() AS date)),N'Test');
    SET @SponsorPK=CONVERT(int,SCOPE_IDENTITY());
    IF (SELECT COUNT(*) FROM dbo.DatabaseChangeLog WHERE AuditID>@Before AND SessionID=@@SPID
        AND TableName=N'Sponsorships' AND RecordID=@SponsorPK AND Operation=N'INSERT'
        AND OldValues IS NULL AND ISJSON(NewValues)=1)<>1
        THROW 51215,N'Sponsorluk INSERT audit testi başarısız.',1;
    DELETE dbo.Sponsorships WHERE SponsorshipID=@SponsorPK;
    IF (SELECT COUNT(*) FROM dbo.DatabaseChangeLog WHERE AuditID>@Before AND SessionID=@@SPID
        AND TableName=N'Sponsorships' AND RecordID=@SponsorPK AND Operation=N'DELETE'
        AND NewValues IS NULL AND ISJSON(OldValues)=1)<>1
        THROW 51216,N'Sponsorluk DELETE audit testi başarısız.',1;

    SET @Before=COALESCE((SELECT MAX(AuditID) FROM dbo.DatabaseChangeLog),0);
    UPDATE s SET AnnualAmount=CASE WHEN s.AnnualAmount>=0.01 THEN s.AnnualAmount-0.01 ELSE 0.01 END
    FROM dbo.Sponsorships AS s JOIN @Sponsors AS t ON t.SponsorshipID=s.SponsorshipID;
    IF (SELECT COUNT(*) FROM dbo.DatabaseChangeLog AS l JOIN @Sponsors AS t ON t.SponsorshipID=l.RecordID
        WHERE l.AuditID>@Before AND l.SessionID=@@SPID AND l.TableName=N'Sponsorships' AND l.Operation=N'UPDATE')<>2
        THROW 51217,N'Sponsorluk çoklu UPDATE audit testi başarısız.',1;
    IF EXISTS (
        SELECT 1 FROM dbo.DatabaseChangeLog AS l JOIN @Sponsors AS t ON t.SponsorshipID=l.RecordID
        JOIN dbo.Sponsorships AS s ON s.SponsorshipID=t.SponsorshipID
        WHERE l.AuditID>@Before AND l.SessionID=@@SPID AND l.TableName=N'Sponsorships' AND l.Operation=N'UPDATE'
          AND (TRY_CONVERT(decimal(18,2),JSON_VALUE(l.OldValues,'$.AnnualAmount'))<>t.Amount
               OR TRY_CONVERT(decimal(18,2),JSON_VALUE(l.NewValues,'$.AnnualAmount'))<>s.AnnualAmount)
    ) THROW 51218,N'Sponsorluk eski/yeni tutar bilgisi eşleşmiyor.',1;
    SET @Before=COALESCE((SELECT MAX(AuditID) FROM dbo.DatabaseChangeLog),0);
    UPDATE s SET AnnualAmount=s.AnnualAmount FROM dbo.Sponsorships AS s JOIN @Sponsors AS t ON t.SponsorshipID=s.SponsorshipID;
    IF EXISTS (SELECT 1 FROM dbo.DatabaseChangeLog WHERE AuditID>@Before AND SessionID=@@SPID AND TableName=N'Sponsorships')
        THROW 51219,N'Değişmeyen sponsorluk için gereksiz log üretildi.',1;

    ROLLBACK TRANSACTION;
    SELECT N'TESTLER GEÇTİ: view toplamları ve iki trigger kontrol edildi. Test veri değişiklikleri geri alındı.' AS TestResult;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
