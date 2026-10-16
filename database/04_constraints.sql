USE [FutbolKadroFinansDB]
GO
SET ANSI_PADDING ON
GO

ALTER TABLE [dbo].[Clubs] ADD UNIQUE NONCLUSTERED 
(
	[ShortCode] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, IGNORE_DUP_KEY = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO

ALTER TABLE [dbo].[Clubs] ADD UNIQUE NONCLUSTERED 
(
	[ClubName] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, IGNORE_DUP_KEY = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO

ALTER TABLE [dbo].[Stadiums] ADD UNIQUE NONCLUSTERED 
(
	[ClubID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, IGNORE_DUP_KEY = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
ALTER TABLE [dbo].[Clubs] ADD  DEFAULT ((0.00)) FOR [Budget]
GO
ALTER TABLE [dbo].[Clubs] ADD  DEFAULT (getdate()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Contracts] ADD  DEFAULT (N'Aktif') FOR [ContractStatus]
GO
ALTER TABLE [dbo].[Contracts] ADD  DEFAULT (getdate()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[FinancialTransactions] ADD  DEFAULT (getdate()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Players] ADD  DEFAULT (N'Türkiye') FOR [Nationality]
GO
ALTER TABLE [dbo].[Players] ADD  DEFAULT ((0.00)) FOR [MarketValue]
GO
ALTER TABLE [dbo].[Players] ADD  DEFAULT (getdate()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Sponsorships] ADD  DEFAULT (N'Aktif') FOR [ContractStatus]
GO
ALTER TABLE [dbo].[Sponsorships] ADD  DEFAULT (getdate()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Stadiums] ADD  DEFAULT (getdate()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[TechnicalStaff] ADD  DEFAULT (N'Teknik Direktör') FOR [Role]
GO
ALTER TABLE [dbo].[TechnicalStaff] ADD  DEFAULT (getdate()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Transfers] ADD  DEFAULT (getdate()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Contracts]  WITH CHECK ADD  CONSTRAINT [FK_Contracts_Clubs] FOREIGN KEY([ClubID])
REFERENCES [dbo].[Clubs] ([ClubID])
GO
ALTER TABLE [dbo].[Contracts] CHECK CONSTRAINT [FK_Contracts_Clubs]
GO
ALTER TABLE [dbo].[Contracts]  WITH CHECK ADD  CONSTRAINT [FK_Contracts_Players] FOREIGN KEY([PlayerID])
REFERENCES [dbo].[Players] ([PlayerID])
GO
ALTER TABLE [dbo].[Contracts] CHECK CONSTRAINT [FK_Contracts_Players]
GO
ALTER TABLE [dbo].[FinancialTransactions]  WITH CHECK ADD  CONSTRAINT [FK_FinancialTransactions_Clubs] FOREIGN KEY([ClubID])
REFERENCES [dbo].[Clubs] ([ClubID])
GO
ALTER TABLE [dbo].[FinancialTransactions] CHECK CONSTRAINT [FK_FinancialTransactions_Clubs]
GO
ALTER TABLE [dbo].[Players]  WITH CHECK ADD  CONSTRAINT [FK_Players_Clubs] FOREIGN KEY([ClubID])
REFERENCES [dbo].[Clubs] ([ClubID])
GO
ALTER TABLE [dbo].[Players] CHECK CONSTRAINT [FK_Players_Clubs]
GO
ALTER TABLE [dbo].[Sponsorships]  WITH CHECK ADD  CONSTRAINT [FK_Sponsorships_Clubs] FOREIGN KEY([ClubID])
REFERENCES [dbo].[Clubs] ([ClubID])
GO
ALTER TABLE [dbo].[Sponsorships] CHECK CONSTRAINT [FK_Sponsorships_Clubs]
GO
ALTER TABLE [dbo].[Stadiums]  WITH CHECK ADD  CONSTRAINT [FK_Stadiums_Clubs] FOREIGN KEY([ClubID])
REFERENCES [dbo].[Clubs] ([ClubID])
GO
ALTER TABLE [dbo].[Stadiums] CHECK CONSTRAINT [FK_Stadiums_Clubs]
GO
ALTER TABLE [dbo].[TechnicalStaff]  WITH CHECK ADD  CONSTRAINT [FK_TechnicalStaff_Clubs] FOREIGN KEY([ClubID])
REFERENCES [dbo].[Clubs] ([ClubID])
GO
ALTER TABLE [dbo].[TechnicalStaff] CHECK CONSTRAINT [FK_TechnicalStaff_Clubs]
GO
ALTER TABLE [dbo].[Transfers]  WITH CHECK ADD  CONSTRAINT [FK_Transfers_FromClub] FOREIGN KEY([FromClubID])
REFERENCES [dbo].[Clubs] ([ClubID])
GO
ALTER TABLE [dbo].[Transfers] CHECK CONSTRAINT [FK_Transfers_FromClub]
GO
ALTER TABLE [dbo].[Transfers]  WITH CHECK ADD  CONSTRAINT [FK_Transfers_Players] FOREIGN KEY([PlayerID])
REFERENCES [dbo].[Players] ([PlayerID])
GO
ALTER TABLE [dbo].[Transfers] CHECK CONSTRAINT [FK_Transfers_Players]
GO
ALTER TABLE [dbo].[Transfers]  WITH CHECK ADD  CONSTRAINT [FK_Transfers_ToClub] FOREIGN KEY([ToClubID])
REFERENCES [dbo].[Clubs] ([ClubID])
GO
ALTER TABLE [dbo].[Transfers] CHECK CONSTRAINT [FK_Transfers_ToClub]
GO
