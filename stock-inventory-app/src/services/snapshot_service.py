import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'snapshots.db')

def _conn():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with _conn() as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS daily_snapshot (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                date         TEXT NOT NULL,
                total_value  REAL NOT NULL,
                total_cost   REAL NOT NULL,
                total_profit REAL NOT NULL,
                holdings     TEXT NOT NULL,
                created_at   TEXT NOT NULL
            )
        ''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_date ON daily_snapshot(date)')

def save_snapshot(inventory):
    """從庫存資料計算並儲存當日快照，同一天只存一筆（覆蓋）"""
    if not inventory:
        return
    total_value  = sum(int(s.get('value_now', 0)) for s in inventory)
    total_cost   = sum(abs(int(s.get('cost_sum', 0))) for s in inventory)
    total_profit = sum(int(s.get('make_a_sum', 0)) for s in inventory)
    holdings = json.dumps([
        {
            'symbol': s.get('stk_no'),
            'name':   s.get('stk_na'),
            'qty':    int(s.get('qty_l', 0)),
            'value':  int(s.get('value_now', 0)),
            'profit': int(s.get('make_a_sum', 0)),
        }
        for s in inventory
    ], ensure_ascii=False)
    today = datetime.now().strftime('%Y-%m-%d')
    now   = datetime.now().isoformat()
    with _conn() as db:
        db.execute('DELETE FROM daily_snapshot WHERE date = ?', (today,))
        db.execute(
            'INSERT INTO daily_snapshot (date, total_value, total_cost, total_profit, holdings, created_at) VALUES (?,?,?,?,?,?)',
            (today, total_value, total_cost, total_profit, holdings, now)
        )

def get_history(days=90):
    """取最近 N 天的快照，回傳 list of dict"""
    with _conn() as db:
        rows = db.execute(
            'SELECT date, total_value, total_cost, total_profit FROM daily_snapshot ORDER BY date DESC LIMIT ?',
            (days,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]

def get_stock_history(days=90):
    """取最近 N 天每檔股票的損益，回傳 {symbol: {name, data:[{date, profit, value}]}}"""
    with _conn() as db:
        rows = db.execute(
            'SELECT date, holdings FROM daily_snapshot ORDER BY date DESC LIMIT ?',
            (days,)
        ).fetchall()
    rows = list(reversed(rows))

    stocks = {}
    for row in rows:
        date = row['date']
        holdings = json.loads(row['holdings'])
        for h in holdings:
            sym = h['symbol']
            if sym not in stocks:
                stocks[sym] = {'name': h['name'], 'data': []}
            stocks[sym]['data'].append({
                'date':   date,
                'profit': h['profit'],
                'value':  h['value'],
            })
    return stocks
