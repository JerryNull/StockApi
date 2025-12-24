from configparser import ConfigParser
from esun_marketdata import EsunMarketdata
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import threading
import os

config = ConfigParser()
config.read('./config.simulation.ini')
sdk = EsunMarketdata(config)

sdk.login()

rest_stock = sdk.rest_client.stock

LOG_DIR = r'D:\StockApiLog'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def write_log(symbol, response):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_path = os.path.join(LOG_DIR, 'log.txt')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"Time: {timestamp}, Request: {symbol}, Response: {response}\n")

def start_update():
    # 取得輸入框中的股票代號
    input_txt = entry.get()
    symbols = [s.strip() for s in input_txt.split(',') if s.strip()]
    threading.Thread(target=fetch_data, args=(symbols,), daemon=True).start()

def fetch_data(symbols):
    results = []
    for symbol in symbols:
        try:
            quote = rest_stock.intraday.quote(symbol=symbol)
            write_log(symbol, quote)
            name = quote.get('name', 'N/A')
            price = quote.get('closePrice')
            change = quote.get('change')
            
            if price is None:
                continue

            current_time = datetime.now().strftime('%H:%M:%S')
            
            tag = 'equal'
            if change is not None:
                if change > 0: tag = 'up'
                elif change < 0: tag = 'down'
            
            results.append((symbol, name, price, change, current_time, tag))
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    
    # 資料獲取完畢後，通知主執行緒更新 UI
    root.after(0, update_ui, results)

def update_ui(results):
    valid_ids = set()
    for symbol, name, price, change, time, tag in results:
        valid_ids.add(symbol)
        if tree.exists(symbol):
            tree.item(symbol, values=(symbol, name, price, change, time), tags=(tag,))
        else:
            tree.insert('', 'end', iid=symbol, values=(symbol, name, price, change, time), tags=(tag,))
            
    # 清除畫面上沒有成交價或已移除的股票
    for item in tree.get_children():
        if item not in valid_ids:
            tree.delete(item)
            
    # 500毫秒後再次呼叫自己
    root.after(500, start_update)

root = tk.Tk()
root.title("即時股價監控")
root.configure(bg='black')

# 設定黑色主題樣式
style = ttk.Style()
style.theme_use("default")
style.configure("Treeview", background="black", fieldbackground="black", foreground="white")
style.configure("Treeview.Heading", background="#333333", foreground="white")
style.map('Treeview', background=[('selected', '#555555')])

frame = tk.Frame(root, bg='black')
frame.pack(pady=10)
tk.Label(frame, text="股票代號 (逗號分隔):", bg='black', fg='white').pack(side=tk.LEFT)
entry = tk.Entry(frame, width=30, bg='#222222', fg='white', insertbackground='white')
entry.insert(0, "0050,2317,2330,2454,8358")
entry.pack(side=tk.LEFT, padx=5)

tree = ttk.Treeview(root, columns=('Symbol', 'Name', 'Price', 'Change', 'Time'), show='headings')
tree.heading('Symbol', text='代號')
tree.heading('Name', text='名稱')
tree.heading('Price', text='成交價')
tree.heading('Change', text='漲跌')
tree.heading('Time', text='時間')

tree.tag_configure('up', foreground='red')
tree.tag_configure('down', foreground='green')
tree.tag_configure('equal', foreground='white')

tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

start_update()
root.mainloop()