# 快速參考卡

## 常用指令速查

### 資料擷取
```bash
python main.py fetch --symbols "2330" --from "2024-01-01"
```

### 檢查指標
```bash
python main.py indicators --symbol "2330"
```

### 每日選股
```bash
python main.py scan --symbols "watchlist.txt"
```

### 進出場訊號
```bash
python main.py signal --symbols "2330" --stop-loss 0.07 --take-profit 0.15
```

### 回測績效
```bash
python main.py backtest --symbols "2330" --from "2024-01-01"
```

### 一鍵完整流程
```bash
python main.py run --symbols "watchlist.txt"
```

---

## 選項速查

| 指令 | 常用選項 | 預設值 |
|------|---------|--------|
| `fetch` | `--from`, `--to`, `--no-save` | 365 天前到今日 |
| `indicators` | `--symbol` (必須) | — |
| `scan` | `--rsi-threshold`, `--vol-ratio`, `--min-hits` | 30, 1.5, 2 |
| `signal` | `--stop-loss`, `--take-profit` | 0.07, 0.15 |
| `backtest` | `--from`, `--to`, `--no-plot` | 730 天前到今日 |
| `run` | `--symbols` | watchlist.production.txt |

---

## 檔案位置

| 用途 | 位置 |
|------|------|
| 股票清單 | `watchlist.production.txt` |
| K 線資料 | `data/` |
| 選股結果 | `output/scan_*.csv` |
| 訊號摘要 | `output/signals_summary.csv` |
| 交易紀錄 | `output/trades_*.csv` |
| 回測報告 | `output/backtest_summary.csv` |
| 圖表 | `report/backtest_*.html` |
| 日誌 | `D:\StockApiLog\strategy_*.log` |

---

## 篩選條件（預設至少 2 個）

1. **RSI 超賣反彈**：前日 RSI < 30，今日 >= 30
2. **20MA 突破**：收盤 > 20MA，且 20MA 向上
3. **MACD 正轉**：前日 MACD_HIST < 0，今日 > 0
4. **量能放大**：今日成交量 > 20 日均量 × 倍數

---

## 技術指標說明

| 指標 | 公式/周期 | 信號 |
|------|---------|------|
| MA5/20/60 | 5/20/60 日移動平均 | 支撐/壓力 |
| RSI | 14 日相對強弱指數 | < 30 超賣，> 70 超買 |
| MACD | 12/26/9 日指數移動平均 | 正負轉換 |
| KD | 9 日隨機指標 | 0~100 區間 |
| Vol_MA20 | 20 日成交量均量 | 量能參考 |

---

## 進出場邏輯

### 進場
- RSI 由 < 30 上升到 >= 30（超賣反彈）

### 出場（三選一）
1. **停損**：`(close - entry_price) / entry_price <= -stop_loss`
2. **停利**：`(close - entry_price) / entry_price >= take_profit`
3. **RSI 超買回落**：`RSI > 70 且開始下降`
4. **20MA 跌破**：`close < ma20`

---

## 回測指標

| 指標 | 說明 | 計算 |
|------|------|------|
| 勝率 | 獲利筆數 % | 獲利筆數 / 總筆數 × 100 |
| 平均報酬 | 平均每筆報酬率 | Σ 報酬率 / 筆數 |
| 最大回撤 | 最大跌幅 | (高點 - 低點) / 高點 |
| 夏普比率 | 風險調整報酬 | (平均報酬 - 無風險利率) / σ |

---

## 設定檔範本

```ini
[API]
key = your_key
secret = your_secret
endpoint = https://api.esun.com

[Strategy]
rsi_threshold = 30
vol_ratio = 1.5
min_hits = 2
```

---

## 故障排除

| 症狀 | 可能原因 | 解決 |
|------|---------|------|
| "找不到設定檔" | API 未設定 | 編輯 config.*.ini |
| 0 筆選股結果 | 條件太嚴格 | `--min-hits 1` |
| 回測很慢 | 圖表生成耗時 | `--no-plot` |
| ModuleNotFoundError | 依賴缺失 | `pip install -r requirements.txt` |
| 亂碼 | 編碼問題 | UTF-8 with BOM |

---

## 實用技巧

### 建立自訂監控清單
```bash
# 建立 my_stocks.txt
echo 2330 > my_stocks.txt
echo 2454 >> my_stocks.txt
echo 3105 >> my_stocks.txt

# 使用該清單
python main.py scan --symbols "my_stocks.txt"
```

### 查看詳細的回測交易紀錄
```bash
# 產生回測
python main.py backtest --symbols "2330"

# 查看交易明細
cat output/trades_2330.csv | more
```

### 設定 Windows 排程工作（每日早上 9 點執行）
```batch
# 建立 run_daily.bat
@echo off
cd c:\StockApi
call venv\Scripts\activate.bat
python main.py scan --symbols "watchlist.txt"
```

### 快速比較不同策略參數
```bash
# 激進（高風險高報酬）
python main.py backtest --symbols "2330" --stop-loss 0.05 --take-profit 0.20

# 保守（低風險低報酬）
python main.py backtest --symbols "2330" --stop-loss 0.10 --take-profit 0.10

# 均衡（標準）
python main.py backtest --symbols "2330" --stop-loss 0.07 --take-profit 0.15
```

---

## 環境變數（選用）

```bash
# 設定預設配置檔
set STOCKAPI_CONFIG=config.production.ini

# 設定日誌目錄
set STOCKAPI_LOG_DIR=C:\Logs\StockApi
```

---

**提示**：按 `Ctrl+F` 搜尋關鍵字快速查找

**最後更新**：2026 年 4 月 20 日
