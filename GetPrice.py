from configparser import ConfigParser
from esun_marketdata import EsunMarketdata
from esun_trade.sdk import SDK as EsunTradeSDK
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import threading
import time
import os
import concurrent.futures
import sys
import subprocess
import json
import urllib.parse
import urllib.request


def resolve_config_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cli_args = sys.argv[1:]

    for index, arg in enumerate(cli_args):
        if arg == '--config' and index + 1 < len(cli_args):
            return os.path.abspath(cli_args[index + 1])
        if arg.startswith('--config='):
            return os.path.abspath(arg.split('=', 1)[1])

    env_path = os.environ.get('ESUN_CONFIG_FILE')
    if env_path:
        return os.path.abspath(env_path)

    env_name = os.environ.get('ESUN_ENV', 'simulation').strip().lower()
    filename = 'config.production.ini' if env_name in ('prod', 'production') else 'config.simulation.ini'
    return os.path.join(base_dir, filename)

config = ConfigParser()
config_path = resolve_config_path()
config.read(config_path)

if not config.sections():
    raise FileNotFoundError(f'Config not found or unreadable: {config_path}')

entry_url = config.get('Core', 'Entry', fallback='').lower()
environment_name = config.get('Core', 'Environment', fallback='').strip().upper()
if not environment_name:
    environment_name = 'PRODUCTION' if 'simulation' not in entry_url else 'SIMULATION'

environment_label = '正式環境' if environment_name in ('PROD', 'PRODUCTION') else '模擬環境'
config_display_name = os.path.basename(config_path)
base_dir = os.path.dirname(os.path.abspath(__file__))
simulation_config_path = os.path.join(base_dir, 'config.simulation.ini')
production_config_path = os.path.join(base_dir, 'config.production.ini')
is_production = environment_name in ('PROD', 'PRODUCTION')
switch_target_path = simulation_config_path if is_production else production_config_path
switch_target_label = '測試環境' if is_production else '正式環境'
DEFAULT_SIM_SYMBOLS = "0050,2313,2337,2344,2408,8358"
WATCHLIST_FILE = os.path.join(base_dir, 'watchlist.production.txt')
WINDOW_GEOMETRY_FILE = os.path.join(base_dir, 'window.geometry.txt')
DEFAULT_WINDOW_GEOMETRY = '1000x600'

marketdata_sdk = EsunMarketdata(config)
marketdata_sdk.login()
rest_stock = marketdata_sdk.rest_client.stock

trade_sdk = None
trade_sdk_init_error = None
if is_production:
    try:
        trade_sdk = EsunTradeSDK(config)
        trade_sdk.login()
    except Exception as e:
        trade_sdk_init_error = str(e)
INVENTORY_REFRESH_MS = 10000
INVENTORY_BACKOFF_MS = 60000
TG_NOTIFY_INTERVAL_MS = 10000
TG_NOTIFY_DURATION_MS = 60000
DEFAULT_TG_BOT_TOKEN = '8891183690:AAFO7_oSKS8O_GFD10mKqMRTks-f-7KFS5I'
DEFAULT_TG_CHAT_ID = '888921358'

LOG_DIR = r'D:\StockApiLog'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

inventory_inflight = False
last_quote_map = {}
next_inventory_delay_ms = INVENTORY_REFRESH_MS
tg_alert_lock = threading.Lock()
tg_alert_state = {}
alert_settings = {
    'enabled': False,
    'target_symbol': '全部',
    'price': None,
    'pct_abs': None,
    'total_volume': None,
    'single_volume': None,
    'token': DEFAULT_TG_BOT_TOKEN,
    'chat_id': DEFAULT_TG_CHAT_ID,
}
tg_enable_var = None
target_symbol_var = None
target_symbol_combo = None
price_threshold_var = None
pct_threshold_var = None
total_volume_threshold_var = None
single_volume_threshold_var = None
tg_status_var = None
last_chat_id_discovery_at = 0.0

def write_log_batch(log_lines):
    if not log_lines:
        return
    now = datetime.now()
    log_path = os.path.join(LOG_DIR, f"{now.strftime('%Y%m%d')}.txt")
    with open(log_path, 'a', encoding='utf-8') as f:
        f.writelines(log_lines)

def load_window_geometry():
    if not os.path.exists(WINDOW_GEOMETRY_FILE):
        return DEFAULT_WINDOW_GEOMETRY

    try:
        with open(WINDOW_GEOMETRY_FILE, 'r', encoding='utf-8') as f:
            geom = f.read().strip()
            if geom:
                return geom
    except Exception:
        pass
    return DEFAULT_WINDOW_GEOMETRY

def save_window_geometry():
    try:
        geom = root.geometry()
        with open(WINDOW_GEOMETRY_FILE, 'w', encoding='utf-8') as f:
            f.write(geom)
    except Exception:
        pass

def on_window_resize(event=None):
    '''動態調整 Treeview 欄位寬度以適應視窗大小'''
    try:
        if quote_tree:
            total_width = quote_tree.winfo_width()
            if total_width > 1:
                col_width = max(60, total_width // 6)
                quote_tree.column('Symbol', width=col_width)
                quote_tree.column('Name', width=col_width)
                quote_tree.column('Price', width=col_width)
                quote_tree.column('Change', width=col_width)
                quote_tree.column('PctChange', width=col_width)
                quote_tree.column('Time', width=col_width)
        
        if is_production and inventory_tree:
            total_width = inventory_tree.winfo_width()
            if total_width > 1:
                col_width = max(70, total_width // 6)
                inventory_tree.column('Symbol', width=col_width)
                inventory_tree.column('Name', width=col_width)
                inventory_tree.column('Qty', width=col_width)
                inventory_tree.column('Unrealized', width=col_width)
                inventory_tree.column('ReturnRate', width=col_width)
                inventory_tree.column('Time', width=col_width)
    except Exception:
        pass

def normalize_symbols_text(input_text):
    text = (input_text or '').replace('，', ',')
    parts = [s.strip() for s in text.split(',') if s.strip()]

    deduped = []
    seen = set()
    for symbol in parts:
        if symbol not in seen:
            seen.add(symbol)
            deduped.append(symbol)

    return ','.join(deduped)

def sync_target_symbol_options(symbols):
    if target_symbol_combo is None or target_symbol_var is None:
        return

    options = ['全部'] + symbols
    current = target_symbol_var.get().strip() if target_symbol_var.get() else ''
    target_symbol_combo['values'] = options

    if current in options:
        return

    if symbols:
        target_symbol_var.set(symbols[0])
    else:
        target_symbol_var.set('全部')

def bind_tree_mousewheel(tree):
    if tree is None:
        return

    def _on_mousewheel(event):
        tree.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        return 'break'

    tree.bind('<MouseWheel>', _on_mousewheel)

def load_saved_watchlist():
    if not is_production:
        return DEFAULT_SIM_SYMBOLS

    if not os.path.exists(WATCHLIST_FILE):
        return ''

    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            return normalize_symbols_text(f.read())
    except Exception:
        return ''

def persist_current_watchlist(show_message=True):
    if not is_production:
        return

    symbols_text = normalize_symbols_text(entry.get())

    try:
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            f.write(symbols_text)

        entry.delete(0, tk.END)
        entry.insert(0, symbols_text)

        if show_message:
            environment_var.set(f'目前環境：{environment_label}｜設定檔：{config_display_name}｜已儲存自選股')
    except Exception as e:
        if show_message:
            environment_var.set(f'儲存自選股失敗：{e}')

def switch_environment():
    save_window_geometry()
    if is_production:
        persist_current_watchlist(show_message=False)

    target_path = switch_target_path
    if not os.path.exists(target_path):
        environment_var.set(f'切換失敗：找不到設定檔 {os.path.basename(target_path)}')
        return

    command = [sys.executable, os.path.abspath(__file__), '--config', target_path]
    env = os.environ.copy()
    env['ESUN_CONFIG_FILE'] = target_path
    subprocess.Popen(command, cwd=base_dir, env=env)
    root.destroy()

def update_quote_cache(quote_map):
    global last_quote_map
    last_quote_map.update(quote_map)

def on_close_app():
    save_window_geometry()
    if is_production:
        persist_current_watchlist(show_message=False)
    root.destroy()

def start_update():
    # 取得輸入框中的股票代號
    refresh_alert_settings()
    input_txt = entry.get()
    symbols = [s.strip() for s in input_txt.split(',') if s.strip()]
    sync_target_symbol_options(symbols)
    
    if not symbols:
        root.after(500, start_update)
        return
        
    threading.Thread(target=fetch_data, args=(symbols,), daemon=True).start()

def fetch_single_quote(symbol):
    try:
        quote = rest_stock.intraday.quote(symbol=symbol)
        return symbol, quote, None
    except Exception as e:
        return symbol, None, e

def safe_float(value):
    try:
        if value is None or value == '':
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

def safe_int(value):
    try:
        if value is None or value == '':
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0

def fmt_num(value, digits=2):
    if value is None:
        return '-'
    return f"{value:.{digits}f}"

def safe_threshold_float(value):
    text = str(value).strip() if value is not None else ''
    if text == '':
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None

def safe_threshold_int(value):
    text = str(value).strip() if value is not None else ''
    if text == '':
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None

def is_valid_chat_id(chat_id):
    text = str(chat_id or '').strip()
    if not text:
        return False
    if text.startswith('-'):
        return text[1:].isdigit()
    return text.isdigit()

def discover_chat_id_from_updates(token):
    if not token:
        return None

    url = f'https://api.telegram.org/bot{token}/getUpdates'
    request_obj = urllib.request.Request(url, method='GET')

    try:
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            body = response.read().decode('utf-8', errors='ignore')
            result = json.loads(body) if body else {}
            if not result.get('ok'):
                return None
            updates = result.get('result') or []
            if not updates:
                return None

            latest = updates[-1]
            message = latest.get('message') or latest.get('channel_post') or {}
            chat = message.get('chat') or {}
            chat_id = chat.get('id')
            return str(chat_id) if chat_id is not None else None
    except Exception:
        return None

def refresh_alert_settings():
    global alert_settings, last_chat_id_discovery_at
    resolved_chat_id = (DEFAULT_TG_CHAT_ID or '').strip()
    now = time.time()
    if not is_valid_chat_id(resolved_chat_id) and (now - last_chat_id_discovery_at) > 30:
        discovered = discover_chat_id_from_updates(DEFAULT_TG_BOT_TOKEN)
        last_chat_id_discovery_at = now
        if discovered and is_valid_chat_id(discovered):
            resolved_chat_id = discovered

    alert_settings = {
        'enabled': bool(tg_enable_var.get()) if tg_enable_var is not None else False,
        'target_symbol': (target_symbol_var.get().strip() if target_symbol_var is not None else '全部') or '全部',
        'price': safe_threshold_float(price_threshold_var.get() if price_threshold_var is not None else ''),
        'pct_abs': safe_threshold_float(pct_threshold_var.get() if pct_threshold_var is not None else ''),
        'total_volume': safe_threshold_int(total_volume_threshold_var.get() if total_volume_threshold_var is not None else ''),
        'single_volume': safe_threshold_int(single_volume_threshold_var.get() if single_volume_threshold_var is not None else ''),
        'token': DEFAULT_TG_BOT_TOKEN,
        'chat_id': resolved_chat_id,
    }

def update_tg_status(text):
    if tg_status_var is None:
        return
    root.after(0, lambda: tg_status_var.set(text))

def send_telegram_message(text):
    token = alert_settings.get('token') or ''
    chat_id = alert_settings.get('chat_id') or ''
    if not token:
        return False, 'Telegram Token 未設定'
    if not is_valid_chat_id(chat_id):
        return False, 'Chat ID 無效。請先對 Bot 發 /start 或在群組發言，讓程式可從 getUpdates 自動取得 Chat ID'

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text,
    }
    data = urllib.parse.urlencode(payload).encode('utf-8')
    request_obj = urllib.request.Request(url, data=data, method='POST')

    try:
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            body = response.read().decode('utf-8', errors='ignore')
            result = json.loads(body) if body else {}
            if result.get('ok'):
                return True, 'ok'
            return False, str(result)
    except Exception as e:
        return False, str(e)

def extract_quote_metrics(quote, price, pct_change):
    total_volume = safe_int(
        quote.get('tradeVolume')
        or quote.get('totalVolume')
        or quote.get('volume')
        or quote.get('accumulateVolume')
    )
    single_volume = safe_int(
        quote.get('tradeQty')
        or quote.get('lastSize')
        or quote.get('lastQty')
        or quote.get('size')
    )
    return {
        'price': safe_float(price),
        'pct_change': safe_float(pct_change),
        'total_volume': total_volume,
        'single_volume': single_volume,
    }

def get_trigger_reasons(metrics):
    reasons = []
    p = alert_settings.get('price')
    pct_abs = alert_settings.get('pct_abs')
    tv = alert_settings.get('total_volume')
    sv = alert_settings.get('single_volume')

    if p is not None and metrics.get('price') is not None and metrics.get('price') >= p:
        reasons.append(f"成交價 {metrics.get('price'):.2f} >= {p:.2f}")
    if pct_abs is not None and metrics.get('pct_change') is not None and abs(metrics.get('pct_change')) >= pct_abs:
        reasons.append(f"漲跌幅 {metrics.get('pct_change'):.2f}% >= ±{pct_abs:.2f}%")
    if tv is not None and metrics.get('total_volume', 0) >= tv:
        reasons.append(f"總量 {metrics.get('total_volume', 0):,} >= {tv:,}")
    if sv is not None and metrics.get('single_volume', 0) >= sv:
        reasons.append(f"單量 {metrics.get('single_volume', 0):,} >= {sv:,}")

    return reasons

def register_alert_if_needed(symbol, name, metrics, reasons):
    if not reasons:
        return

    now = time.time()
    with tg_alert_lock:
        state = tg_alert_state.get(symbol)
        if state is None:
            tg_alert_state[symbol] = {
                'symbol': symbol,
                'name': name,
                'metrics': metrics,
                'reasons': reasons,
                'next_send': now,
                'end_at': now + (TG_NOTIFY_DURATION_MS / 1000.0),
            }
        else:
            state['name'] = name
            state['metrics'] = metrics
            state['reasons'] = reasons
            state['end_at'] = max(state['end_at'], now + (TG_NOTIFY_DURATION_MS / 1000.0))

def flush_alert_notifications(latest_metrics_map):
    if not alert_settings.get('enabled'):
        return

    now = time.time()
    to_remove = []

    with tg_alert_lock:
        items = list(tg_alert_state.items())

    for symbol, state in items:
        if now > state.get('end_at', 0):
            to_remove.append(symbol)
            continue

        if now < state.get('next_send', 0):
            continue

        latest = latest_metrics_map.get(symbol, state.get('metrics', {}))
        name = state.get('name', 'N/A')
        pct = latest.get('pct_change')
        pct_text = '-' if pct is None else f"{pct:+.2f}%"
        text = (
            f"📢 觸發監控條件\n"
            f"代號：{symbol}\n"
            f"名稱：{name}\n"
            f"成交價：{fmt_num(latest.get('price'))}\n"
            f"漲跌幅：{pct_text}\n"
            f"總量：{latest.get('total_volume', 0):,}\n"
            f"單量：{latest.get('single_volume', 0):,}\n"
            f"條件：{'; '.join(state.get('reasons', []))}"
        )
        ok, msg = send_telegram_message(text)
        if ok:
            update_tg_status(f"TG 通知成功：{symbol} {datetime.now().strftime('%H:%M:%S')}")
        else:
            update_tg_status(f"TG 通知失敗：{msg}")

        with tg_alert_lock:
            current = tg_alert_state.get(symbol)
            if current is not None:
                current['metrics'] = latest
                current['next_send'] = now + (TG_NOTIFY_INTERVAL_MS / 1000.0)

    if to_remove:
        with tg_alert_lock:
            for symbol in to_remove:
                tg_alert_state.pop(symbol, None)

def invoke_sdk_method(path, *args, **kwargs):
    obj = marketdata_sdk
    for part in path.split('.'):
        if not hasattr(obj, part):
            return None, f"method-not-found: {path}"
        obj = getattr(obj, part)

    if not callable(obj):
        return None, f"not-callable: {path}"

    try:
        return obj(*args, **kwargs), None
    except Exception as e:
        return None, f"{path}: {e}"

def find_inventory_list(payload):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ('inventories', 'inventory', 'items', 'data', 'result', 'stk_data', 'list'):
            if key in payload:
                found = find_inventory_list(payload[key])
                if found is not None:
                    return found

    return None

def fetch_inventories_raw():
    if trade_sdk is None:
        reason = trade_sdk_init_error or '交易 SDK 尚未初始化'
        raise RuntimeError(f'無法使用交易 SDK 取得庫存：{reason}')

    return trade_sdk.get_inventories()

def fetch_quotes_map(symbols):
    quote_map = {}
    if not symbols:
        return quote_map

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(symbols))) as executor:
        futures = {executor.submit(fetch_single_quote, sym): sym for sym in symbols}
        for future in concurrent.futures.as_completed(futures):
            symbol, quote, error = future.result()
            if error is None and isinstance(quote, dict):
                quote_map[symbol] = quote
    return quote_map

def build_inventory_rows(inventory_items):
    '''快速組裝庫存列，只用帳務 API，不同步查詢報價以避免超時。報價用緩存補充。'''
    rows = []
    for item in inventory_items:
        if not isinstance(item, dict):
            continue

        symbol = str(
            item.get('stk_no')
            or item.get('symbol')
            or item.get('stockNo')
            or item.get('stock_no')
            or ''
        ).strip()
        if not symbol:
            continue

        row = {
            'symbol': symbol,
            'name': item.get('stk_na') or item.get('name') or item.get('stockName') or 'N/A',
            'qty': safe_int(item.get('qty_l') if 'qty_l' in item else item.get('qty')),
            'avg_price': safe_float(item.get('price_avg') if 'price_avg' in item else item.get('avg_price')),
            'current_price': safe_float(item.get('price_now') if 'price_now' in item else item.get('price_mkt')),
            'market_value': safe_float(item.get('value_now') if 'value_now' in item else item.get('value_mkt')),
            'unrealized': safe_float(item.get('make_a_sum') if 'make_a_sum' in item else item.get('make_a')),
            'return_rate': safe_float(item.get('make_a_per')),
        }
        rows.append(row)

    for row in rows:
        quote = last_quote_map.get(row['symbol'])
        if quote:
            if row['current_price'] is None:
                row['current_price'] = safe_float(quote.get('closePrice'))
            if row['name'] in ('N/A', '', None):
                row['name'] = quote.get('name', row['name'])

        if row['market_value'] is None and row['qty'] and row['current_price'] is not None:
            row['market_value'] = row['qty'] * row['current_price']

        if row['unrealized'] is None and row['qty'] and row['avg_price'] is not None and row['current_price'] is not None:
            row['unrealized'] = (row['current_price'] - row['avg_price']) * row['qty']

        if row['return_rate'] is None and row['unrealized'] is not None and row['qty'] and row['avg_price']:
            cost = row['qty'] * row['avg_price']
            if cost != 0:
                row['return_rate'] = (row['unrealized'] / cost) * 100

    return rows

def fetch_data(symbols):
    results = []
    log_lines = []
    latest_metrics_map = {}
    
    # 1. 使用 ThreadPool 行平行查詢，大幅縮短整體等待時間
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(symbols))) as executor:
        futures = {executor.submit(fetch_single_quote, sym): sym for sym in symbols}
        for future in concurrent.futures.as_completed(futures):
            symbol, quote, error = future.result()
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if error is not None:
                print(f"Error fetching {symbol}: {error}")
                continue
                
            # 組織 Log 字串 (批次寫入)
            log_lines.append(f"Time: {timestamp}, Request: {symbol}, Response: {quote}\n")
            
            name = quote.get('name', 'N/A')
            price = quote.get('closePrice')
            change = quote.get('change')
            
            if price is None:
                continue

            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            
            tag = 'equal'
            pct_change_str = "0.00%"
            pct_change_val = 0.0

            if change is not None:
                if change > 0: tag = 'up'
                elif change < 0: tag = 'down'
                
                previous_close = price - change
                if previous_close != 0:
                    pct_change_val = (change / previous_close) * 100
                    pct_change_str = f"{pct_change_val:.2f}%"

            metrics = extract_quote_metrics(quote, price, pct_change_val)
            latest_metrics_map[symbol] = {
                'price': metrics.get('price'),
                'pct_change': metrics.get('pct_change'),
                'total_volume': metrics.get('total_volume'),
                'single_volume': metrics.get('single_volume'),
            }

            reasons = get_trigger_reasons(metrics)
            selected_target = alert_settings.get('target_symbol', '全部')
            target_match = (selected_target in ('', '全部')) or (symbol == selected_target)
            if reasons and target_match:
                register_alert_if_needed(symbol, name, latest_metrics_map[symbol], reasons)
            
            results.append((symbol, name, price, change, pct_change_str, current_time, tag))
            
    # 2. 一次性寫入所有 Log
    try:
        write_log_batch(log_lines)
    except Exception as e:
        print(f"Error writing logs: {e}")
    
    # 資料獲取完畢後，通知主執行緒更新 UI，並提供 symbols 比對避免閃爍
    root.after(0, update_quote_ui, results, symbols)
    update_quote_cache({r[0]: {'closePrice': r[2], 'name': r[1]} for r in results})
    flush_alert_notifications(latest_metrics_map)

def start_inventory_update():
    if not is_production:
        return

    global inventory_inflight, next_inventory_delay_ms

    if inventory_inflight:
        root.after(next_inventory_delay_ms, start_inventory_update)
        return

    inventory_inflight = True
    threading.Thread(target=fetch_inventory_data, daemon=True).start()

def fetch_inventory_data():
    if not is_production:
        return

    global inventory_inflight, next_inventory_delay_ms
    now_str = datetime.now().strftime('%H:%M:%S')

    try:
        raw = fetch_inventories_raw()
        inventory_items = raw if isinstance(raw, list) else find_inventory_list(raw)
        if inventory_items is None:
            inventory_items = []

        rows = build_inventory_rows(inventory_items)
        status = f"更新成功：{len(rows)} 筆 ({now_str})"
        next_inventory_delay_ms = INVENTORY_REFRESH_MS
        root.after(0, finalize_inventory_refresh, rows, status)
    except Exception as e:
        msg = str(e)
        if 'Invalid IP' in msg:
            msg = '庫存更新失敗：IP 不在券商白名單（請到玉山 API 後台設定可連線 IP）'
        elif 'AGR0003' in msg or 'Exceed Transaction Rate Limit' in msg:
            msg = '庫存更新失敗：超過交易頻率限制，將於 60 秒後自動重試'
            next_inventory_delay_ms = INVENTORY_BACKOFF_MS
        else:
            msg = f'庫存更新失敗：{msg}'
            next_inventory_delay_ms = INVENTORY_REFRESH_MS
        status = f"{msg} ({now_str})"
        root.after(0, finalize_inventory_refresh, None, status)
    finally:
        inventory_inflight = False

sort_col = None
sort_desc = False
inv_sort_col = None
inv_sort_desc = False

def on_heading_click(col):
    global sort_col, sort_desc
    if sort_col == col:
        sort_desc = not sort_desc
    else:
        sort_col = col
        sort_desc = True
    reorder_tree()

def reorder_tree():
    if sort_col is None:
        return
    items = quote_tree.get_children()
    data = []
    for iid in items:
        val = quote_tree.set(iid, sort_col)
        try:
            if sort_col == 'PctChange':
                sort_val = float(val.strip('%'))
            elif sort_col in ('Price', 'Change'):
                sort_val = float(val)
            else:
                sort_val = val
        except (ValueError, TypeError):
            sort_val = -float('inf')
        data.append((sort_val, iid))
    data.sort(key=lambda x: x[0], reverse=sort_desc)
    for index, (val, iid) in enumerate(data):
        quote_tree.move(iid, '', index)

def on_inventory_heading_click(col):
    global inv_sort_col, inv_sort_desc
    if inv_sort_col == col:
        inv_sort_desc = not inv_sort_desc
    else:
        inv_sort_col = col
        inv_sort_desc = True
    reorder_inventory_tree()

def reorder_inventory_tree():
    if not is_production or inventory_tree is None:
        return

    if inv_sort_col is None:
        return

    items = inventory_tree.get_children()
    data = []
    for iid in items:
        val = inventory_tree.set(iid, inv_sort_col)
        try:
            if inv_sort_col in ('Qty',):
                sort_val = int(float(val.replace(',', '')))
            elif inv_sort_col in ('Unrealized',):
                sort_val = float(val.replace(',', ''))
            elif inv_sort_col == 'ReturnRate':
                sort_val = float(val.strip('%').replace(',', ''))
            else:
                sort_val = val
        except (ValueError, TypeError):
            sort_val = -float('inf')
        data.append((sort_val, iid))

    data.sort(key=lambda x: x[0], reverse=inv_sort_desc)
    for index, (val, iid) in enumerate(data):
        inventory_tree.move(iid, '', index)

def update_quote_ui(results, current_symbols):
    valid_ids = set()
    for symbol, name, price, change, pct_change, time, tag in results:
        valid_ids.add(symbol)
        if quote_tree.exists(symbol):
            quote_tree.item(symbol, values=(symbol, name, price, change, pct_change, time), tags=(tag,))
        else:
            quote_tree.insert('', 'end', iid=symbol, values=(symbol, name, price, change, pct_change, time), tags=(tag,))
            
    # 3. 解決 UI 閃爍：只清除使用者從輸入框中移除的股票，而不是沒拿到價格就刪除
    for item in quote_tree.get_children():
        if item not in current_symbols:
            quote_tree.delete(item)
            
    reorder_tree()

    # 500毫秒後再次呼叫自己
    root.after(500, start_update)

def update_inventory_ui(rows):
    if not is_production or inventory_tree is None or rows is None:
        return

    row_ids = set()
    now_str = datetime.now().strftime('%H:%M:%S.%f')[:-3]

    for row in rows:
        symbol = row['symbol']
        row_ids.add(symbol)

        unrealized = row['unrealized']
        tag = 'equal'
        if unrealized is not None:
            if unrealized > 0:
                tag = 'up'
            elif unrealized < 0:
                tag = 'down'

        values = (
            symbol,
            row['name'],
            f"{row['qty']:,}",
            fmt_num(unrealized),
            '-' if row['return_rate'] is None else f"{row['return_rate']:.2f}%",
            now_str
        )

        if inventory_tree.exists(symbol):
            inventory_tree.item(symbol, values=values, tags=(tag,))
        else:
            inventory_tree.insert('', 'end', iid=symbol, values=values, tags=(tag,))

    for item in inventory_tree.get_children():
        if item not in row_ids:
            inventory_tree.delete(item)

    reorder_inventory_tree()

def finalize_inventory_refresh(rows, status):
    if not is_production or inventory_status_var is None:
        return

    inventory_status_var.set(status)
    update_inventory_ui(rows)
    root.after(next_inventory_delay_ms, start_inventory_update)

root = tk.Tk()
root.title(f"即時股價與庫存明細 - {environment_label}")
root.configure(bg='black')
root.attributes('-topmost', True)
root.geometry(load_window_geometry())

inventory_tree = None
inventory_status_var = None

# 設定黑色主題樣式
style = ttk.Style()
style.theme_use("default")
style.configure("Treeview", background="black", fieldbackground="black", foreground="white")
style.configure("Treeview.Heading", background="#333333", foreground="white")
style.map('Treeview', background=[('selected', '#555555')])
environment_var = tk.StringVar(value=f'目前環境：{environment_label}｜設定檔：{config_display_name}')
environment_label_widget = tk.Label(root, textvariable=environment_var, bg='black', fg='yellow', anchor='w')
environment_label_widget.pack(fill=tk.X, padx=10, pady=(10, 0))

switch_button = tk.Button(
    root,
    text=f'切換到{switch_target_label}',
    command=switch_environment,
    bg='#444444',
    fg='white',
    activebackground='#666666',
    activeforeground='white'
)
switch_button.pack(anchor='e', padx=10, pady=(6, 0))

style.configure("TNotebook", background="black")
style.configure("TNotebook.Tab", background="#333333", foreground="white")

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

quote_tab = tk.Frame(notebook, bg='black')
notebook.add(quote_tab, text='即時報價')

notify_tab = tk.Frame(notebook, bg='black')
notebook.add(notify_tab, text='通知設定')

inventory_tab = None
if is_production:
    inventory_tab = tk.Frame(notebook, bg='black')
    notebook.add(inventory_tab, text='庫存明細')

frame = tk.Frame(quote_tab, bg='black')
frame.pack(pady=10)
tk.Label(frame, text="股票代號 (逗號分隔):", bg='black', fg='white').pack(side=tk.LEFT)
entry = tk.Entry(frame, width=30, bg='#222222', fg='white', insertbackground='white')
entry.insert(0, load_saved_watchlist())
entry.pack(side=tk.LEFT, padx=5)

if is_production:
    save_button = tk.Button(
        frame,
        text='儲存自選股',
        command=lambda: persist_current_watchlist(show_message=True),
        bg='#444444',
        fg='white',
        activebackground='#666666',
        activeforeground='white'
    )
    save_button.pack(side=tk.LEFT, padx=5)

alert_frame = tk.Frame(notify_tab, bg='black')
alert_frame.pack(fill=tk.X, padx=10, pady=(10, 6))

tg_enable_var = tk.BooleanVar(value=False)
target_symbol_var = tk.StringVar(value='全部')
price_threshold_var = tk.StringVar(value='')
pct_threshold_var = tk.StringVar(value='')
total_volume_threshold_var = tk.StringVar(value='')
single_volume_threshold_var = tk.StringVar(value='')
tg_status_var = tk.StringVar(value='TG 通知：未啟用（Token/ChatID 由程式內常數提供）')

for col in range(8):
    alert_frame.grid_columnconfigure(col, weight=0)
alert_frame.grid_columnconfigure(7, weight=1)

tk.Checkbutton(alert_frame, text='啟用 TG 通知', variable=tg_enable_var, bg='black', fg='white', selectcolor='#222222').grid(row=0, column=0, padx=(0, 8), sticky='w')
tk.Label(alert_frame, text='目標股票', bg='black', fg='white').grid(row=0, column=1, sticky='e')
target_symbol_combo = ttk.Combobox(alert_frame, width=10, state='readonly', textvariable=target_symbol_var, values=['全部'])
target_symbol_combo.grid(row=0, column=2, padx=(4, 10), sticky='w')

tk.Label(alert_frame, text='成交價>=', bg='black', fg='white').grid(row=0, column=3, sticky='e')
tk.Entry(alert_frame, width=8, textvariable=price_threshold_var, bg='#222222', fg='white', insertbackground='white').grid(row=0, column=4, padx=(4, 10))
tk.Label(alert_frame, text='漲跌幅>=', bg='black', fg='white').grid(row=0, column=5, sticky='e')
tk.Entry(alert_frame, width=8, textvariable=pct_threshold_var, bg='#222222', fg='white', insertbackground='white').grid(row=0, column=6, padx=(4, 2))
tk.Label(alert_frame, text='%', bg='black', fg='white').grid(row=0, column=7, sticky='w')

tk.Label(alert_frame, text='總量>=', bg='black', fg='white').grid(row=1, column=1, sticky='e', pady=(6, 0))
tk.Entry(alert_frame, width=10, textvariable=total_volume_threshold_var, bg='#222222', fg='white', insertbackground='white').grid(row=1, column=2, padx=(4, 10), sticky='w', pady=(6, 0))
tk.Label(alert_frame, text='單量>=', bg='black', fg='white').grid(row=1, column=3, sticky='e', pady=(6, 0))
tk.Entry(alert_frame, width=10, textvariable=single_volume_threshold_var, bg='#222222', fg='white', insertbackground='white').grid(row=1, column=4, padx=(4, 10), sticky='w', pady=(6, 0))
tk.Label(alert_frame, text='達標後每10秒通知，持續1分鐘', bg='black', fg='yellow').grid(row=1, column=5, columnspan=3, sticky='w', pady=(6, 0))

tg_status_label = tk.Label(notify_tab, textvariable=tg_status_var, bg='black', fg='yellow', anchor='w')
tg_status_label.pack(fill=tk.X, padx=10, pady=(0, 4))

quote_tree_frame = tk.Frame(quote_tab, bg='black')
quote_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

quote_tree = ttk.Treeview(quote_tree_frame, columns=('Symbol', 'Name', 'Price', 'Change', 'PctChange', 'Time'), show='headings')
quote_tree.heading('Symbol', text='代號', command=lambda: on_heading_click('Symbol'))
quote_tree.heading('Name', text='名稱', command=lambda: on_heading_click('Name'))
quote_tree.heading('Price', text='成交價', command=lambda: on_heading_click('Price'))
quote_tree.heading('Change', text='漲跌', command=lambda: on_heading_click('Change'))
quote_tree.heading('PctChange', text='漲跌幅', command=lambda: on_heading_click('PctChange'))
quote_tree.heading('Time', text='時間', command=lambda: on_heading_click('Time'))

quote_tree.column('Symbol', width=60, anchor='center')
quote_tree.column('Name', width=100, anchor='w')
quote_tree.column('Price', width=80, anchor='e')
quote_tree.column('Change', width=80, anchor='e')
quote_tree.column('PctChange', width=80, anchor='e')
quote_tree.column('Time', width=100, anchor='center')

quote_tree.tag_configure('up', foreground='red')
quote_tree.tag_configure('down', foreground='green')
quote_tree.tag_configure('equal', foreground='white')

quote_scrollbar = ttk.Scrollbar(quote_tree_frame, orient='vertical', command=quote_tree.yview)
quote_tree.configure(yscrollcommand=quote_scrollbar.set)

quote_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
quote_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
bind_tree_mousewheel(quote_tree)

if is_production:
    inventory_status_var = tk.StringVar(value='庫存尚未更新')
    inventory_status_label = tk.Label(inventory_tab, textvariable=inventory_status_var, bg='black', fg='white', anchor='w')
    inventory_status_label.pack(fill=tk.X, padx=10, pady=(10, 0))

    inventory_tree_frame = tk.Frame(inventory_tab, bg='black')
    inventory_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    inventory_tree = ttk.Treeview(
        inventory_tree_frame,
        columns=('Symbol', 'Name', 'Qty', 'Unrealized', 'ReturnRate', 'Time'),
        show='headings'
    )
    inventory_tree.heading('Symbol', text='代號', command=lambda: on_inventory_heading_click('Symbol'))
    inventory_tree.heading('Name', text='名稱', command=lambda: on_inventory_heading_click('Name'))
    inventory_tree.heading('Qty', text='庫存股數', command=lambda: on_inventory_heading_click('Qty'))
    inventory_tree.heading('Unrealized', text='未實現損益', command=lambda: on_inventory_heading_click('Unrealized'))
    inventory_tree.heading('ReturnRate', text='報酬率', command=lambda: on_inventory_heading_click('ReturnRate'))
    inventory_tree.heading('Time', text='更新時間', command=lambda: on_inventory_heading_click('Time'))

    inventory_tree.column('Symbol', width=70, anchor='center')
    inventory_tree.column('Name', width=100, anchor='w')
    inventory_tree.column('Qty', width=100, anchor='e')
    inventory_tree.column('Unrealized', width=120, anchor='e')
    inventory_tree.column('ReturnRate', width=100, anchor='e')
    inventory_tree.column('Time', width=120, anchor='center')

    inventory_tree.tag_configure('up', foreground='red')
    inventory_tree.tag_configure('down', foreground='green')
    inventory_tree.tag_configure('equal', foreground='white')

    inventory_scrollbar = ttk.Scrollbar(inventory_tree_frame, orient='vertical', command=inventory_tree.yview)
    inventory_tree.configure(yscrollcommand=inventory_scrollbar.set)

    inventory_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    inventory_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    bind_tree_mousewheel(inventory_tree)

start_update()
if is_production:
    start_inventory_update()
root.protocol("WM_DELETE_WINDOW", on_close_app)
root.bind('<Configure>', on_window_resize)
root.mainloop()