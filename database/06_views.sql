USE [FutbolKadroFinansDB];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- One row per club and season appearing in FinancialTransactions.
-- Amounts are recorded cash movements, not audited accounting profit.
CREATE OR ALTER VIEW dbo.vw_ClubFinancialSummary
AS
WITH Seasons AS (
    SELECT DISTINCT Season FROM dbo.FinancialTransactions
), Totals AS (
    SELECT ClubID, Season,
        SUM(CASE WHEN TransactionType=N'Gelir' THEN Amount ELSE CONVERT(decimal(18,2),0) END) AS TotalIncome,
        SUM(CASE WHEN TransactionType=N'Gider' THEN Amount ELSE CONVERT(decimal(18,2),0) END) AS TotalExpense,
        SUM(CASE WHEN TransactionType=N'Gelir' THEN Amount
                 WHEN TransactionType=N'Gider' THEN -Amount ELSE CONVERT(decimal(18,2),0) END) AS NetCashMovement,
        COUNT_BIG(*) AS TransactionCount,
        SUM(CONVERT(bigint,CASE WHEN TransactionType IN (N'Gelir',N'Gider') THEN 0 ELSE 1 END)) AS UnclassifiedTransactionCount
    FROM dbo.FinancialTransactions
    GROUP BY ClubID, Season
)
SELECT c.ClubID, c.ClubName, s.Season,
       COALESCE(t.TotalIncome,CONVERT(decimal(38,2),0)) AS TotalIncome,
       COALESCE(t.TotalExpense,CONVERT(decimal(38,2),0)) AS TotalExpense,
       COALESCE(t.NetCashMovement,CONVERT(decimal(38,2),0)) AS NetCashMovement,
       COALESCE(t.TransactionCount,CONVERT(bigint,0)) AS TransactionCount,
       COALESCE(t.UnclassifiedTransactionCount,CONVERT(bigint,0)) AS UnclassifiedTransactionCount
FROM dbo.Clubs AS c
CROSS JOIN Seasons AS s
LEFT JOIN Totals AS t ON t.ClubID=c.ClubID AND t.Season=s.Season;
GO

-- Core player rows only. Django archive metadata is not part of this view.
-- Aggregate players before joining to avoid multiplication by contracts.
CREATE OR ALTER VIEW dbo.vw_ClubSquadSummary
AS
WITH PlayerTotals AS (
    SELECT ClubID,
        COUNT_BIG(*) AS PlayerCount,
        SUM(MarketValue) AS TotalMarketValue,
        SUM(CONVERT(bigint,CASE WHEN Position IN (N'Kaleci',N'GK',N'Goalkeeper') THEN 1 ELSE 0 END)) AS GoalkeeperCount,
        CAST(AVG(CAST(
            DATEDIFF(year,BirthDate,CAST(GETDATE() AS date))
            - CASE WHEN DATEADD(year,DATEDIFF(year,BirthDate,CAST(GETDATE() AS date)),BirthDate)
                        > CAST(GETDATE() AS date) THEN 1 ELSE 0 END
            AS decimal(8,2))) AS decimal(8,2)) AS AverageAge
    FROM dbo.Players
    GROUP BY ClubID
)
SELECT c.ClubID, c.ClubName,
       COALESCE(p.PlayerCount,CONVERT(bigint,0)) AS PlayerCount,
       COALESCE(p.TotalMarketValue,CONVERT(decimal(38,2),0)) AS TotalMarketValue,
       COALESCE(p.GoalkeeperCount,CONVERT(bigint,0)) AS GoalkeeperCount,
       p.AverageAge
FROM dbo.Clubs AS c
LEFT JOIN PlayerTotals AS p ON p.ClubID=c.ClubID;
GO

-- Evaluated on each SELECT; no automatic status/date updates.
CREATE OR ALTER VIEW dbo.vw_ContractAlerts
AS
SELECT c.ContractID, c.PlayerID, c.ClubID, cl.ClubName,
       p.FirstName, p.LastName, c.StartDate, c.EndDate,
       c.AnnualSalary, c.ContractStatus,
       CAST(GETDATE() AS date) AS AsOfDate,
       DATEDIFF(day,CAST(GETDATE() AS date),c.EndDate) AS DaysRemaining,
       CASE WHEN c.EndDate < CAST(GETDATE() AS date) THEN N'Süresi geçmiş'
            WHEN c.EndDate <= DATEADD(day,30,CAST(GETDATE() AS date)) THEN N'30 gün içinde'
            WHEN c.EndDate <= DATEADD(day,90,CAST(GETDATE() AS date)) THEN N'90 gün içinde'
            ELSE N'180 gün içinde' END AS AlertType
FROM dbo.Contracts AS c
JOIN dbo.Players AS p ON p.PlayerID=c.PlayerID
JOIN dbo.Clubs AS cl ON cl.ClubID=c.ClubID
WHERE c.ContractStatus=N'Aktif'
  AND c.EndDate <= DATEADD(day,180,CAST(GETDATE() AS date));
GO

SELECT name AS CreatedView
FROM sys.views
WHERE schema_id=SCHEMA_ID(N'dbo')
  AND name IN (N'vw_ClubFinancialSummary',N'vw_ClubSquadSummary',N'vw_ContractAlerts')
ORDER BY name;
GO
