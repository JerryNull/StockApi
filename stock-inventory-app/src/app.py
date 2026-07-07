import os
import json
import time
import threading
import urllib.request
from configparser import ConfigParser
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from services.account_client import AccountClient
from services.sector_service import SectorService
from services.snapshot_service import init_db, save_snapshot, get_history, get_stock_history
from esun_marketdata import EsunMarketdata
from esun_trade.sdk import SDK as EsunTradeSDK

# ── 初始化玉山 SDK ──────────────────────────────────────────────
base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, '..', '..', 'config.production.ini')
config = ConfigParser()
config.read(config_path)

marketdata_sdk = EsunMarketdata(config)
marketdata_sdk.login()
rest_stock = marketdata_sdk.rest_client.stock

trade_sdk = EsunTradeSDK(config)
trade_sdk.login()

_sdk_lock = threading.Lock()

def _relogin():
    """重新登入兩個 SDK，thread-safe"""
    global marketdata_sdk, rest_stock, trade_sdk
    with _sdk_lock:
        try:
            marketdata_sdk = EsunMarketdata(config)
            marketdata_sdk.login()
            rest_stock = marketdata_sdk.rest_client.stock
            trade_sdk = EsunTradeSDK(config)
            trade_sdk.login()
            print(f"[{datetime.now()}] SDK 重新登入成功")
        except Exception as e:
            print(f"[{datetime.now()}] SDK 重新登入失敗: {e}")

def safe_quote(symbol):
    """取報價，若 session 失效自動重登一次"""
    global rest_stock
    try:
        q = rest_stock.intraday.quote(symbol=symbol)
        # 若關鍵欄位全空視為 session 失效
        if q.get('lastPrice') is None and q.get('closePrice') is None and q.get('name') == symbol:
            raise ValueError("session_expired")
        return q
    except Exception as e:
        if 'session_expired' in str(e) or '401' in str(e) or 'Unauthorized' in str(e):
            print(f"[{datetime.now()}] 偵測到 session 失效，重新登入...")
            _relogin()
            return rest_stock.intraday.quote(symbol=symbol)
        raise

# ── 自選股 & 到價通知 ────────────────────────────────────────────
WATCHLIST_FILE = os.path.join(base_dir, '..', '..', 'watchlist.production.txt')
ALERTS_FILE    = os.path.join(base_dir, '..', '..', 'price_alerts.json')
TG_BOT_TOKEN   = '8891183690:AAFO7_oSKS8O_GFD10mKqMRTks-f-7KFS5I'
TG_CHAT_ID     = '888921358'

def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        return []
    try:
        text = open(WATCHLIST_FILE, encoding='utf-8').read().strip()
        return [s.strip() for s in text.split(',') if s.strip()]
    except Exception:
        return []

def save_watchlist(symbols):
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        f.write(','.join(symbols))

def load_alerts():
    if not os.path.exists(ALERTS_FILE):
        return {}
    try:
        return json.loads(open(ALERTS_FILE, encoding='utf-8').read())
    except Exception:
        return {}

def save_alerts(alerts):
    with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

price_alerts = load_alerts()
alert_lock   = threading.Lock()

def send_tg(msg):
    try:
        url  = f'https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage'
        body = json.dumps({'chat_id': TG_CHAT_ID, 'text': msg}).encode('utf-8')
        req  = urllib.request.Request(url, data=body,
                                      headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def price_monitor():
    import time
    while True:
        try:
            symbols = load_watchlist()
            with alert_lock:
                alerts = dict(price_alerts)
            for sym in symbols:
                if sym not in alerts:
                    continue
                a = alerts[sym]
                if a.get('triggered'):
                    continue
                try:
                    q = safe_quote(sym)
                    price = q.get('lastPrice') or q.get('closePrice')
                    if price is None:
                        continue
                    target    = float(a['target'])
                    direction = a['direction']
                    hit = (direction == 'above' and price >= target) or \
                          (direction == 'below' and price <= target)
                    if hit:
                        name  = q.get('name', sym)
                        arrow = '▲' if direction == 'above' else '▼'
                        send_tg(f'📈 到價通知\n{name}（{sym}）現價 {price}\n{arrow} 已達目標 {target}')
                        with alert_lock:
                            price_alerts[sym]['triggered'] = True
                        save_alerts(price_alerts)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(15)

threading.Thread(target=price_monitor, daemon=True).start()

# ── 每日快照排程 ─────────────────────────────────────────────────
init_db()

def _daily_snapshot_loop():
    """每天收盤後 14:35 存一次快照"""
    import time as _time
    while True:
        now = datetime.now()
        # 計算距離今天 14:35 的秒數
        target = now.replace(hour=14, minute=35, second=0, microsecond=0)
        if now >= target:
            target = target.replace(day=target.day + 1)
        wait_sec = (target - now).total_seconds()
        _time.sleep(wait_sec)
        try:
            inv = account_client._inventory_cache or account_client.get_inventory_details()
            save_snapshot(inv)
            print(f"[{datetime.now()}] 每日快照已儲存，持股數：{len(inv) if inv else 0}")
        except Exception as e:
            print(f"[{datetime.now()}] 快照失敗: {e}")

threading.Thread(target=_daily_snapshot_loop, daemon=True).start()

# ── Flask 應用 ──────────────────────────────────────────────────
app = Flask(__name__)
account_client = AccountClient(trade_sdk)
sector_service = SectorService(rest_stock)


@app.route('/')
def prices_page():
    return render_template('prices.html')


@app.route('/inventory')
def index():
    try:
        inventory_details = account_client.get_inventory_details()
    except Exception as e:
        err = str(e)
        if 'AGR0003' in err or 'Rate Limit' in err:
            return render_template('inventory_view.html', inventory=None,
                                   error='API 頻率限制，請稍後再試（每分鐘限制一次）',
                                   last_updated=None)
        return render_template('inventory_view.html', inventory=None, error=err, last_updated=None)
    ts = account_client.get_last_updated()
    last_updated = datetime.fromtimestamp(ts).strftime('%H:%M:%S') if ts else None
    return render_template('inventory_view.html', inventory=inventory_details, error=None, last_updated=last_updated)


@app.route('/api/prices')
def api_prices():
    symbols = load_watchlist()
    result  = []
    for sym in symbols:
        try:
            q = safe_quote(sym)
            with alert_lock:
                alert = price_alerts.get(sym)
            result.append({
                'symbol':        sym,
                'name':          q.get('name', sym),
                'lastPrice':     q.get('lastPrice'),
                'closePrice':    q.get('closePrice'),
                'change':        q.get('change'),
                'changePercent': q.get('changePercent'),
                'highPrice':     q.get('highPrice'),
                'lowPrice':      q.get('lowPrice'),
                'alert':         alert,
            })
        except Exception as e:
            result.append({'symbol': sym, 'error': str(e)})
    return jsonify(result)

@app.route('/api/watchlist', methods=['GET'])
def api_watchlist_get():
    return jsonify(load_watchlist())

@app.route('/api/watchlist', methods=['POST'])
def api_watchlist_post():
    data    = request.get_json(force=True) or {}
    symbols = [s.strip() for s in data.get('symbols', []) if s.strip()]
    save_watchlist(symbols)
    return jsonify({'ok': True, 'symbols': symbols})

@app.route('/api/alerts', methods=['GET'])
def api_alerts_get():
    with alert_lock:
        return jsonify(dict(price_alerts))

@app.route('/api/alerts/<symbol>', methods=['POST'])
def api_alert_set(symbol):
    data      = request.get_json(force=True) or {}
    target    = data.get('target')
    direction = data.get('direction', 'above')
    if target is None:
        return jsonify({'error': 'target required'}), 400
    with alert_lock:
        price_alerts[symbol] = {'target': float(target), 'direction': direction, 'triggered': False}
    save_alerts(price_alerts)
    return jsonify({'ok': True})

@app.route('/api/alerts/<symbol>', methods=['DELETE'])
def api_alert_delete(symbol):
    with alert_lock:
        price_alerts.pop(symbol, None)
    save_alerts(price_alerts)
    return jsonify({'ok': True})


@app.route('/history')
def history_page():
    return render_template('history.html')

@app.route('/api/history')
def api_history():
    days = request.args.get('days', default=90, type=int)
    return jsonify(get_history(days))

@app.route('/api/history/stocks')
def api_history_stocks():
    days = request.args.get('days', default=90, type=int)
    return jsonify(get_stock_history(days))

@app.route('/api/history/snapshot', methods=['POST'])
def api_snapshot_now():
    """手動觸發一次快照（只用快取，不額外呼叫 API）"""
    with account_client._lock:
        inv = account_client._inventory_cache
    if not inv:
        return jsonify({'error': '庫存快取尚未建立，請稍後再試（約 90 秒後自動更新）'}), 503
    try:
        save_snapshot(inv)
        return jsonify({'ok': True, 'holdings': len(inv)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/sector')
def sector_dashboard():
    return render_template('sector_dashboard.html')

@app.route('/api/sector/summaries')
def sector_summaries():
    days = request.args.get('days', default=1, type=int)
    data = sector_service.get_sector_summaries(days=days)
    return jsonify(data)

@app.route('/api/sector/stocks/<industry_code>')
def sector_stocks(industry_code):
    days = request.args.get('days', default=1, type=int)
    data = sector_service.get_stocks_in_sector(industry_code, days=days)
    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8768, debug=False)
