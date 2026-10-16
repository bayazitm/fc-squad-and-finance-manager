USE [FutbolKadroFinansDB]
GO
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[TechnicalStaff](
	[StaffID] [int] IDENTITY(1,1) NOT NULL,
	[ClubID] [int] NOT NULL,
	[FirstName] [nvarchar](50) NOT NULL,
	[LastName] [nvarchar](50) NOT NULL,
	[Role] [nvarchar](50) NOT NULL,
	[Nationality] [nvarchar](50) NOT NULL,
	[ContractStartDate] [date] NOT NULL,
	[ContractEndDate] [date] NOT NULL,
	[AnnualSalary] [decimal](18, 2) NOT NULL,
	[CreatedAt] [datetime2](7) NULL,
PRIMARY KEY CLUSTERED 
(
	[StaffID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
