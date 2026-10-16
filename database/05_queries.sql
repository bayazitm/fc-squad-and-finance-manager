USE [FutbolKadroFinansDB]
GO

SELECT c.ClubName, p.FirstName, p.LastName, p.Position, p.JerseyNumber
FROM dbo.Players AS p JOIN dbo.Clubs AS c ON c.ClubID = p.ClubID
ORDER BY c.ClubName, p.JerseyNumber;
GO
SELECT c.ClubName, COUNT(p.PlayerID) AS PlayerCount, COALESCE(SUM(p.MarketValue), 0) AS TotalMarketValue
FROM dbo.Clubs AS c LEFT JOIN dbo.Players AS p ON p.ClubID = c.ClubID
GROUP BY c.ClubID, c.ClubName;
GO
SELECT c.ClubName, ft.Season,
SUM(CASE WHEN ft.TransactionType = N'Gelir' THEN ft.Amount ELSE 0 END) AS Gelir,
SUM(CASE WHEN ft.TransactionType = N'Gider' THEN ft.Amount ELSE 0 END) AS Gider,
SUM(CASE WHEN ft.TransactionType = N'Gelir' THEN ft.Amount WHEN ft.TransactionType = N'Gider' THEN -ft.Amount ELSE 0 END) AS NetTutar
FROM dbo.FinancialTransactions AS ft JOIN dbo.Clubs AS c ON c.ClubID = ft.ClubID
GROUP BY c.ClubName, ft.Season;
GO
SELECT t.TransferID, t.FromClubID, c.ClubName AS ReferencedClub, t.FromClubName
FROM dbo.Transfers AS t JOIN dbo.Clubs AS c ON c.ClubID = t.FromClubID
WHERE t.FromClubName <> c.ClubName;
GO
SELECT * FROM dbo.Contracts WHERE EndDate < StartDate;
GO
SELECT DISTINCT TransactionType FROM dbo.FinancialTransactions;
GO
