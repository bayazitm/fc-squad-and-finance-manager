import json
from django.db import connection, DatabaseError

REPORTS = {
    'finance': ('vw_ClubFinancialSummary', 'ClubName, Season, TotalIncome, TotalExpense, NetCashMovement, TransactionCount, UnclassifiedTransactionCount', 'ClubName'),
    'squad': ('vw_ClubSquadSummary', 'ClubName, PlayerCount, GoalkeeperCount, AverageAge, TotalMarketValue', 'ClubName'),
    'alerts': ('vw_ContractAlerts', 'ContractID, ClubName, FirstName, LastName, EndDate, DaysRemaining, AlertType, AnnualSalary', 'EndDate, ContractID'),
}

def fetch(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        keys = [col[0] for col in cursor.description]
        return [dict(zip(keys, row)) for row in cursor.fetchall()]

def read_report(kind, club_ids, season):
    if not club_ids:
        return [], ''
    view, columns, order = REPORTS[kind]
    placeholders = ','.join(['%s'] * len(club_ids))
    sql = f'SELECT {columns} FROM dbo.{view} WHERE ClubID IN ({placeholders})'
    params = list(club_ids)
    if kind == 'finance':
        sql += ' AND Season = %s'
        params.append(season)
    sql += f' ORDER BY {order}'
    try:
        return fetch(sql, params), ''
    except DatabaseError:
        return [], 'Rapor okunamadı. Aynı veritabanında 06_views.sql dosyasının hatasız çalıştığını ve okuma yetkisini kontrol edin.'

def read_database_history(club_id, table, operation):
    clauses, params = [], []
    if club_id is not None:
        clauses.append("(TRY_CONVERT(int, JSON_VALUE(OldValues, '$.ClubID')) = %s OR TRY_CONVERT(int, JSON_VALUE(NewValues, '$.ClubID')) = %s)")
        params += [club_id, club_id]
    if table in ('Contracts', 'Sponsorships'):
        clauses.append('TableName = %s'); params.append(table)
    if operation in ('INSERT', 'UPDATE', 'DELETE'):
        clauses.append('Operation = %s'); params.append(operation)
    sql = 'SELECT TOP (200) AuditID, TableName, RecordID, Operation, OldValues, NewValues, ChangedAtUTC, LoginName FROM dbo.DatabaseChangeLog'
    if clauses:
        sql += ' WHERE ' + ' AND '.join(clauses)
    sql += ' ORDER BY AuditID DESC'
    try:
        rows = fetch(sql, params)
    except DatabaseError:
        return [], 'Günlük okunamadı. 07_triggers.sql dosyasını ve DatabaseChangeLog okuma yetkisini kontrol edin.'
    for row in rows:
        before = json.loads(row.pop('OldValues') or '{}')
        after = json.loads(row.pop('NewValues') or '{}')
        row['changes'] = [{'field': key, 'before': before.get(key), 'after': after.get(key)}
                          for key in dict.fromkeys([*before, *after]) if before.get(key) != after.get(key)]
    return rows, ''
