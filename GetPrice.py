from configparser import ConfigParser
from esun_marketdata import EsunMarketdata
from esun_trade.sdk import SDK as EsunTradeSDK
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import threading
import os
import concurrent.futures
import sys
import subprocess


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
INVENTORY_REFRESH_MS = 5000

LOG_DIR = r'D:\StockApiLog'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

inventory_inflight = False

def write_log_batch(log_lines):
    if not log_lines:
        return
    now = datetime.now()
    log_path = os.path.join(LOG_DIR, f"{now.strftime('%Y%m%d')}.txt")
    with open(log_path, 'a', encoding='utf-8') as f:
        f.writelines(log_lines)

def switch_environment():
    target_path = switch_target_path
    if not os.path.exists(target_path):
        environment_var.set(f'切換失敗：找不到設定檔 {os.path.basename(target_path)}')
        return

    command = [sys.executable, os.path.abspath(__file__), '--config', target_path]
    env = os.environ.copy()
    env['ESUN_CONFIG_FILE'] = target_path
    subprocess.Popen(command, cwd=base_dir, env=env)
    root.destroy()

def start_update():
    # 取得輸入框中的股票代號
    input_txt = entry.get()
    symbols = [s.strip() for s in input_txt.split(',') if s.strip()]
    
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

    symbols_missing_price = [r['symbol'] for r in rows if r['current_price'] is None]
    quote_map = fetch_quotes_map(symbols_missing_price)

    for row in rows:
        quote = quote_map.get(row['symbol'])
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

            if change is not None:
                if change > 0: tag = 'up'
                elif change < 0: tag = 'down'
                
                previous_close = price - change
                if previous_close != 0:
                    pct_change_str = f"{(change / previous_close) * 100:.2f}%"
            
            results.append((symbol, name, price, change, pct_change_str, current_time, tag))
            
    # 2. 一次性寫入所有 Log
    try:
        write_log_batch(log_lines)
    except Exception as e:
        print(f"Error writing logs: {e}")
    
    # 資料獲取完畢後，通知主執行緒更新 UI，並提供 symbols 比對避免閃爍
    root.after(0, update_quote_ui, results, symbols)

def start_inventory_update():
    if not is_production:
        return

    global inventory_inflight

    if inventory_inflight:
        root.after(INVENTORY_REFRESH_MS, start_inventory_update)
        return

    inventory_inflight = True
    threading.Thread(target=fetch_inventory_data, daemon=True).start()

def fetch_inventory_data():
    if not is_production:
        return

    global inventory_inflight
    now_str = datetime.now().strftime('%H:%M:%S')

    try:
        raw = fetch_inventories_raw()
        inventory_items = raw if isinstance(raw, list) else find_inventory_list(raw)
        if inventory_items is None:
            inventory_items = []

        rows = build_inventory_rows(inventory_items)
        status = f"更新成功：{len(rows)} 筆 ({now_str})"
        root.after(0, finalize_inventory_refresh, rows, status)
    except Exception as e:
        msg = str(e)
        if 'Invalid IP' in msg:
            msg = '庫存更新失敗：IP 不在券商白名單（請到玉山 API 後台設定可連線 IP）'
        else:
            msg = f'庫存更新失敗：{msg}'
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
            elif inv_sort_col in ('AvgPrice', 'CurrentPrice', 'MarketValue', 'Unrealized'):
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
            fmt_num(row['avg_price']),
            fmt_num(row['current_price']),
            fmt_num(row['market_value']),
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
    root.after(INVENTORY_REFRESH_MS, start_inventory_update)

root = tk.Tk()
root.title(f"即時股價與庫存明細 - {environment_label}")
root.configure(bg='black')
root.attributes('-topmost', True)

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

inventory_tab = None
if is_production:
    inventory_tab = tk.Frame(notebook, bg='black')
    notebook.add(inventory_tab, text='庫存明細')

frame = tk.Frame(quote_tab, bg='black')
frame.pack(pady=10)
tk.Label(frame, text="股票代號 (逗號分隔):", bg='black', fg='white').pack(side=tk.LEFT)
entry = tk.Entry(frame, width=30, bg='#222222', fg='white', insertbackground='white')
entry.insert(0, "0050,2313,2337,2344,2408,8358")
entry.pack(side=tk.LEFT, padx=5)

quote_tree = ttk.Treeview(quote_tab, columns=('Symbol', 'Name', 'Price', 'Change', 'PctChange', 'Time'), show='headings')
quote_tree.heading('Symbol', text='代號', command=lambda: on_heading_click('Symbol'))
quote_tree.heading('Name', text='名稱', command=lambda: on_heading_click('Name'))
quote_tree.heading('Price', text='成交價', command=lambda: on_heading_click('Price'))
quote_tree.heading('Change', text='漲跌', command=lambda: on_heading_click('Change'))
quote_tree.heading('PctChange', text='漲跌幅', command=lambda: on_heading_click('PctChange'))
quote_tree.heading('Time', text='時間', command=lambda: on_heading_click('Time'))

quote_tree.tag_configure('up', foreground='red')
quote_tree.tag_configure('down', foreground='green')
quote_tree.tag_configure('equal', foreground='white')

quote_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

if is_production:
    inventory_status_var = tk.StringVar(value='庫存尚未更新')
    inventory_status_label = tk.Label(inventory_tab, textvariable=inventory_status_var, bg='black', fg='white', anchor='w')
    inventory_status_label.pack(fill=tk.X, padx=10, pady=(10, 0))

    inventory_tree = ttk.Treeview(
        inventory_tab,
        columns=('Symbol', 'Name', 'Qty', 'AvgPrice', 'CurrentPrice', 'MarketValue', 'Unrealized', 'ReturnRate', 'Time'),
        show='headings'
    )
    inventory_tree.heading('Symbol', text='代號', command=lambda: on_inventory_heading_click('Symbol'))
    inventory_tree.heading('Name', text='名稱', command=lambda: on_inventory_heading_click('Name'))
    inventory_tree.heading('Qty', text='庫存股數', command=lambda: on_inventory_heading_click('Qty'))
    inventory_tree.heading('AvgPrice', text='均價', command=lambda: on_inventory_heading_click('AvgPrice'))
    inventory_tree.heading('CurrentPrice', text='現價', command=lambda: on_inventory_heading_click('CurrentPrice'))
    inventory_tree.heading('MarketValue', text='市值', command=lambda: on_inventory_heading_click('MarketValue'))
    inventory_tree.heading('Unrealized', text='未實現損益', command=lambda: on_inventory_heading_click('Unrealized'))
    inventory_tree.heading('ReturnRate', text='報酬率', command=lambda: on_inventory_heading_click('ReturnRate'))
    inventory_tree.heading('Time', text='更新時間', command=lambda: on_inventory_heading_click('Time'))

    inventory_tree.tag_configure('up', foreground='red')
    inventory_tree.tag_configure('down', foreground='green')
    inventory_tree.tag_configure('equal', foreground='white')

    inventory_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

start_update()
if is_production:
    start_inventory_update()
root.mainloop()