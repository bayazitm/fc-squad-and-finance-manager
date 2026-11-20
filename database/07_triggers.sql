USE [FutbolKadroFinansDB];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- Separate database-level log; no dependency on Django authentication tables.
IF OBJECT_ID(N'dbo.DatabaseChangeLog',N'U') IS NULL
BEGIN
    CREATE TABLE dbo.DatabaseChangeLog (
        AuditID bigint IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_DatabaseChangeLog PRIMARY KEY,
        TableName nvarchar(128) NOT NULL,
        RecordID int NOT NULL,
        Operation nvarchar(10) NOT NULL,
        OldValues nvarchar(max) NULL,
        NewValues nvarchar(max) NULL,
        ChangedAtUTC datetime2(7) NOT NULL
            CONSTRAINT DF_DatabaseChangeLog_ChangedAtUTC DEFAULT SYSUTCDATETIME(),
        LoginName nvarchar(128) NOT NULL,
        HostName nvarchar(128) NULL,
        ApplicationName nvarchar(128) NULL,
        SessionID int NOT NULL,
        CONSTRAINT CK_DatabaseChangeLog_Operation CHECK (Operation IN (N'INSERT',N'UPDATE',N'DELETE')),
        CONSTRAINT CK_DatabaseChangeLog_OldJSON CHECK (OldValues IS NULL OR ISJSON(OldValues)=1),
        CONSTRAINT CK_DatabaseChangeLog_NewJSON CHECK (NewValues IS NULL OR ISJSON(NewValues)=1)
    );
END;
GO

-- Fail instead of reusing an unrelated table with an incompatible shape.
IF COL_LENGTH(N'dbo.DatabaseChangeLog',N'AuditID') IS NULL
   OR COL_LENGTH(N'dbo.DatabaseChangeLog',N'OldValues') IS NULL
   OR COL_LENGTH(N'dbo.DatabaseChangeLog',N'NewValues') IS NULL
   OR COL_LENGTH(N'dbo.DatabaseChangeLog',N'SessionID') IS NULL
    THROW 51100,N'DatabaseChangeLog tablosu beklenen yapıda değil. Önce tabloyu inceleyin.',1;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id=OBJECT_ID(N'dbo.DatabaseChangeLog')
      AND name=N'IX_DatabaseChangeLog_RecordHistory'
)
    CREATE INDEX IX_DatabaseChangeLog_RecordHistory
        ON dbo.DatabaseChangeLog(TableName,RecordID,AuditID DESC);
GO

CREATE OR ALTER TRIGGER dbo.trg_Contracts_Audit
ON dbo.Contracts
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS(SELECT 1 FROM inserted) AND NOT EXISTS(SELECT 1 FROM deleted) RETURN;

    INSERT dbo.DatabaseChangeLog
        (TableName,RecordID,Operation,OldValues,NewValues,LoginName,HostName,ApplicationName,SessionID)
    SELECT N'Contracts',COALESCE(i.ContractID,d.ContractID),
           CASE WHEN d.ContractID IS NULL THEN N'INSERT'
                WHEN i.ContractID IS NULL THEN N'DELETE' ELSE N'UPDATE' END,
           CASE WHEN d.ContractID IS NULL THEN NULL ELSE (
               SELECT d.ContractID,d.PlayerID,d.ClubID,d.StartDate,d.EndDate,
                      d.AnnualSalary,d.ReleaseClause,d.ContractStatus,d.CreatedAt
               FOR JSON PATH, INCLUDE_NULL_VALUES, WITHOUT_ARRAY_WRAPPER
           ) END,
           CASE WHEN i.ContractID IS NULL THEN NULL ELSE (
               SELECT i.ContractID,i.PlayerID,i.ClubID,i.StartDate,i.EndDate,
                      i.AnnualSalary,i.ReleaseClause,i.ContractStatus,i.CreatedAt
               FOR JSON PATH, INCLUDE_NULL_VALUES, WITHOUT_ARRAY_WRAPPER
           ) END,
           ORIGINAL_LOGIN(),HOST_NAME(),APP_NAME(),@@SPID
    FROM inserted AS i
    FULL OUTER JOIN deleted AS d ON d.ContractID=i.ContractID
    WHERE i.ContractID IS NULL OR d.ContractID IS NULL
       OR EXISTS (
           SELECT i.PlayerID,i.ClubID,i.StartDate,i.EndDate,i.AnnualSalary,
                  i.ReleaseClause,i.ContractStatus COLLATE Latin1_General_100_BIN2,i.CreatedAt
           EXCEPT
           SELECT d.PlayerID,d.ClubID,d.StartDate,d.EndDate,d.AnnualSalary,
                  d.ReleaseClause,d.ContractStatus COLLATE Latin1_General_100_BIN2,d.CreatedAt
       );
END;
GO

CREATE OR ALTER TRIGGER dbo.trg_Sponsorships_Audit
ON dbo.Sponsorships
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS(SELECT 1 FROM inserted) AND NOT EXISTS(SELECT 1 FROM deleted) RETURN;

    INSERT dbo.DatabaseChangeLog
        (TableName,RecordID,Operation,OldValues,NewValues,LoginName,HostName,ApplicationName,SessionID)
    SELECT N'Sponsorships',COALESCE(i.SponsorshipID,d.SponsorshipID),
           CASE WHEN d.SponsorshipID IS NULL THEN N'INSERT'
                WHEN i.SponsorshipID IS NULL THEN N'DELETE' ELSE N'UPDATE' END,
           CASE WHEN d.SponsorshipID IS NULL THEN NULL ELSE (
               SELECT d.SponsorshipID,d.ClubID,d.SponsorName,d.SponsorshipType,
                      d.AnnualAmount,d.StartDate,d.EndDate,d.ContractStatus,d.CreatedAt
               FOR JSON PATH, INCLUDE_NULL_VALUES, WITHOUT_ARRAY_WRAPPER
           ) END,
           CASE WHEN i.SponsorshipID IS NULL THEN NULL ELSE (
               SELECT i.SponsorshipID,i.ClubID,i.SponsorName,i.SponsorshipType,
                      i.AnnualAmount,i.StartDate,i.EndDate,i.ContractStatus,i.CreatedAt
               FOR JSON PATH, INCLUDE_NULL_VALUES, WITHOUT_ARRAY_WRAPPER
           ) END,
           ORIGINAL_LOGIN(),HOST_NAME(),APP_NAME(),@@SPID
    FROM inserted AS i
    FULL OUTER JOIN deleted AS d ON d.SponsorshipID=i.SponsorshipID
    WHERE i.SponsorshipID IS NULL OR d.SponsorshipID IS NULL
       OR EXISTS (
           SELECT i.ClubID,i.SponsorName COLLATE Latin1_General_100_BIN2,i.SponsorshipType COLLATE Latin1_General_100_BIN2,i.AnnualAmount,
                  i.StartDate,i.EndDate,i.ContractStatus COLLATE Latin1_General_100_BIN2,i.CreatedAt
           EXCEPT
           SELECT d.ClubID,d.SponsorName COLLATE Latin1_General_100_BIN2,d.SponsorshipType COLLATE Latin1_General_100_BIN2,d.AnnualAmount,
                  d.StartDate,d.EndDate,d.ContractStatus COLLATE Latin1_General_100_BIN2,d.CreatedAt
       );
END;
GO

SELECT name AS CreatedTrigger,OBJECT_NAME(parent_id) AS ParentTable,is_disabled AS IsDisabled
FROM sys.triggers
WHERE name IN (N'trg_Contracts_Audit',N'trg_Sponsorships_Audit')
ORDER BY name;
GO
