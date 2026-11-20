# Database snapshot — 20 November 2026

The snapshot was exported from `FutbolKadroFinansDB` using SSMS with **Schema and data**, selecting the eight core project tables. Django authentication, session, audit, and application helper data are excluded. The Django application uses its migrations to create its own helper tables separately.

## Verified record counts

| Table | Rows |
|---|---:|
| `Clubs` | 18 |
| `Contracts` | 517 |
| `FinancialTransactions` | 216 |
| `Players` | 517 |
| `Sponsorships` | 55 |
| `Stadiums` | 18 |
| `TechnicalStaff` | 18 |
| `Transfers` | 154 |

## Changes compared with the original export

- 495 existing contract rows have at least one date change: 405 start-date fields and 314 end-date fields changed, with overlap between those groups.
- All 405 contract records belonging to clubs outside the four major clubs use the owner-selected project scenario 2026-07-01 through 2029-06-30.
- The 112 major-club end dates match the prepared source-referenced list. See `contract-sources.md` for references and limits.
- Three transfer source-club IDs and six club-name spelling variants were corrected.
- The Fenerbahçe technical director name is Emre Belözoğlu. The annual salary remains 500000.00; the technical staff contract dates were retained.
- All original player records and all monetary fields were preserved.

## Validation

All 1,513 INSERT statements were retained exactly after decoding/newline normalization. Table definitions and constraint statements match the earlier organized schema after whitespace normalization. Eight primary-key definitions, ten foreign keys, three added unique rules, and fourteen defaults are retained.

The data check found no missing referenced club/player IDs, reversed contract/sponsorship/staff date intervals, negative amounts in the checked monetary columns, duplicate primary keys, or duplicated non-null jersey numbers within a club. Transfer/finance season labels match their dates using a July–June convention. These checks establish internal consistency, not the factual accuracy of every football record.

The new split files have not been executed on a fresh SQL Server instance in this environment. The exported source database was running on the owner's computer. Authentication and application helper state are deliberately not reproduced by this core-table snapshot.
