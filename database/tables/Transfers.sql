USE [FutbolKadroFinansDB]
GO
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Transfers](
	[TransferID] [int] IDENTITY(1,1) NOT NULL,
	[PlayerID] [int] NOT NULL,
	[FromClubID] [int] NULL,
	[FromClubName] [nvarchar](100) NOT NULL,
	[ToClubID] [int] NOT NULL,
	[TransferDate] [date] NOT NULL,
	[TransferFee] [decimal](18, 2) NOT NULL,
	[TransferType] [nvarchar](30) NOT NULL,
	[Season] [nvarchar](10) NOT NULL,
	[CreatedAt] [datetime2](7) NULL,
PRIMARY KEY CLUSTERED 
(
	[TransferID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
