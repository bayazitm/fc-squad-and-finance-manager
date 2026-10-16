USE [FutbolKadroFinansDB]
GO
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[FinancialTransactions](
	[TransactionID] [int] IDENTITY(1,1) NOT NULL,
	[ClubID] [int] NOT NULL,
	[TransactionType] [nvarchar](20) NOT NULL,
	[Category] [nvarchar](50) NOT NULL,
	[Amount] [decimal](18, 2) NOT NULL,
	[TransactionDate] [date] NOT NULL,
	[Description] [nvarchar](255) NOT NULL,
	[Season] [nvarchar](10) NOT NULL,
	[CreatedAt] [datetime2](7) NULL,
PRIMARY KEY CLUSTERED 
(
	[TransactionID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
