# Reporting views and database audit triggers

These are additive SQL Server scripts for the existing `FutbolKadroFinansDB` database. They can be committed directly to GitHub without exporting the database again. Uploading the files does not execute them; run `06_views.sql` followed by `07_triggers.sql` once in SSMS to activate them locally.

## Installation order

For a new database: run `01` through `07` in order. For the existing populated database: run only `06_views.sql` and `07_triggers.sql`. Both scripts use `CREATE OR ALTER` for the views/triggers; the audit table and index are created only if absent. Reapplying these definitions preserves the audit history and does not change core business rows.

`08_verify_features.sql` is an optional local runtime test. It compares the views with the core tables, tests INSERT/UPDATE/DELETE logging, verifies multi-row changes and no-op updates, then rolls back its test data changes. It needs at least two existing contracts and two sponsorships. Identity counters can have gaps after rolled-back test inserts. Run it in a separate query window while no other editing is taking place.

## Views

| View | Result |
|---|---|
| `dbo.vw_ClubFinancialSummary` | One row per registered club and each season present in financial transactions; income, expense, recorded net movement, transaction count, and unclassified-type count. |
| `dbo.vw_ClubSquadSummary` | One row per club; number of core player records, goalkeeper count, total recorded market value, and average age as of the SQL Server's local current date. |
| `dbo.vw_ContractAlerts` | Active-marked contracts that have expired or will end within 180 days; days remaining and alert category. |

Financial values have no per-row currency field in the current schema. Interpret each club's amounts only after verifying their units; these are recorded movements, not audited profit. The squad view counts the core Players table and does not apply Django's archive metadata. National-team eligibility is not inferred from nationality. Contract alerts are calculated when queried; they do not automatically change contract status.

### Example reports

```sql
SELECT *
FROM dbo.vw_ClubFinancialSummary
WHERE ClubID = 2 AND Season = N'2026/2027';

SELECT *
FROM dbo.vw_ClubSquadSummary
ORDER BY PlayerCount DESC, ClubName;

SELECT *
FROM dbo.vw_ContractAlerts
ORDER BY DaysRemaining, ClubName;
```

An alert result can be empty after contract dates have been extended. That is a valid result, not a failed view. To demonstrate alerts, use an appropriate existing contract or perform a temporary test in a transaction and roll it back.

## Audit triggers

| Trigger | Table | Events |
|---|---|---|
| `dbo.trg_Contracts_Audit` | `Contracts` | INSERT, UPDATE, DELETE |
| `dbo.trg_Sponsorships_Audit` | `Sponsorships` | INSERT, UPDATE, DELETE |

Each changed row produces one entry in the additional `dbo.DatabaseChangeLog` table. An UPDATE that changes no audited field is ignored. String comparisons use a binary collation so case-only changes are recorded, even when the underlying columns use a case-insensitive collation. Nullable fields are compared with SQL EXCEPT semantics so NULL-to-value and value-to-NULL transitions are detected.

The log contains the record ID, operation, old/new JSON values, UTC timestamp, SQL login, application/host metadata, and SQL session ID. For INSERT the old value is NULL; for DELETE the new value is NULL. The audit insert is part of the same transaction as the business change; rollback removes both. It is an operational course-project audit trail, not a tamper-proof log.

`LoginName` is the SQL connection identity. With Windows Authentication it usually identifies the Windows account, not the Django username. Host/application metadata are connection-supplied information. The separate Django `AuditLog` still tracks application actions with web-user identity; it is not replaced by this table.

### Read database audit history

```sql
SELECT TOP (50)
    AuditID, TableName, RecordID, Operation,
    ChangedAtUTC, LoginName, OldValues, NewValues
FROM dbo.DatabaseChangeLog
ORDER BY AuditID DESC;

SELECT
    RecordID,
    JSON_VALUE(OldValues, '$.AnnualSalary') AS OldSalary,
    JSON_VALUE(NewValues, '$.AnnualSalary') AS NewSalary,
    ChangedAtUTC
FROM dbo.DatabaseChangeLog
WHERE TableName = N'Contracts' AND Operation = N'UPDATE'
ORDER BY AuditID DESC;
```

The log starts with changes made after the triggers are installed. Historical edits made before installation are not reconstructed. Audit records contain operational data and should not be added to the public seed-data export.

## Django compatibility

No application model changes are needed for these separate SQL objects. The existing UI reports still use their ORM queries; the three views are SQL reports and are not yet wired into those pages. Contract and sponsorship changes from either SSMS or Django will be logged once the triggers are enabled.

The source of `mssql-django 2.0.0` was inspected: single-row inserts that return an AutoField ID use `SCOPE_IDENTITY()`, and its other single-row returning path uses a temporary OUTPUT INTO table. These paths avoid SQL Server's restriction on bare OUTPUT with an enabled INSERT trigger. Bulk row returning must stay disabled (the backend default):

```python
# Inside DATABASES['default']['OPTIONS'], keep the existing driver/extra_params:
'return_rows_bulk_insert': False,
```

The current application does not bulk-insert Contracts or Sponsorships with returned rows. Other SQL clients that use bare `INSERT ... OUTPUT inserted...` need `OUTPUT ... INTO` when targeting these triggered tables. Do not disable logging to work around a client incompatibility.

## Verification status

The scripts were checked against the supplied table/column definitions and parsed without errors using SQLFluff with the T-SQL dialect. Reporting-query equivalents were tested on an isolated SQLite copy of the export: 18 clubs / 517 players, finance totals by club/season, contract alert IDs, empty-club behavior, and birthday boundaries matched. The SQLite substitutions are not a SQL Server execution test. Additive installation is designed not to rewrite original data. SQL Server execution is not available in this workspace; successful local installation and runtime tests must be confirmed in SSMS. `08_verify_features.sql` supplies those checks rather than claiming that they have already passed.

## References

- [SQL Server CREATE VIEW](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-view-transact-sql)
- [SQL Server CREATE TRIGGER](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-trigger-transact-sql)
- [Handling multiple rows in triggers](https://learn.microsoft.com/en-us/sql/relational-databases/triggers/create-dml-triggers-to-handle-multiple-rows-of-data)
- [OUTPUT restrictions with triggers](https://learn.microsoft.com/en-us/sql/t-sql/queries/output-clause-transact-sql)
- [mssql-django bulk operations](https://learn.microsoft.com/en-us/sql/connect/python/mssql-django/bulk-operations)
