import os
import json
import threading
import urllib.request
from configparser import ConfigParser
from flask import Flask, render_template, jsonify, request
from services.account_client import AccountClient
from services.sector_service import SectorService
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
                    q = rest_stock.intraday.quote(symbol=sym)
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
                                   error='API 頻率限制，請稍後再試（每分鐘限制一次）')
        return render_template('inventory_view.html', inventory=None, error=err)
    return render_template('inventory_view.html', inventory=inventory_details, error=None)


@app.route('/api/prices')
def api_prices():
    symbols = load_watchlist()
    result  = []
    for sym in symbols:
        try:
            q = rest_stock.intraday.quote(symbol=sym)
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
