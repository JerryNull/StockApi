# 台股波段策略 CLI / Web - 使用文件

## 目錄
1. [專案概述](#專案概述)
2. [架構說明](#架構說明)
3. [安裝與設置](#安裝與設置)
4. [快速開始](#快速開始)
5. [Web 介面操作](#web-介面操作)
6. [CLI 指令詳解](#cli-指令詳解)
7. [設定檔說明](#設定檔說明)
8. [常見使用場景](#常見使用場景)
9. [開發者指南](#開發者指南)
10. [疑難排解](#疑難排解)
11. [網頁操作手冊（獨立文件）](WEB_GUIDE.md)

---

## 專案概述

**台股波段策略 CLI / Web** 是一個用於台灣股票市場波段操作的量化工具，提供以下功能：

- 📊 **資料擷取**：從玉山 API 抓取歷史 K 線資料
- 🔧 **技術指標計算**：MA、RSI、MACD、KD、成交量
- 🎯 **自動選股**：根據超賣反彈、均線突破等條件篩選
- 📈 **訊號生成**：產生進出場訊號
- 🧪 **回測引擎**：評估策略績效（勝率、報酬、夏普比率等）
- 🌐 **網頁操作台**：以瀏覽器執行 fetch/scan/signal/backtest/run

---

## 架構說明

專案採用 **Clean Architecture + 手動依賴注入** 的多層設計：

```
presentation/          # CLI 層 - 使用者介面
  └─ commands/
     └─ stock_commands.py

application/           # 應用層 - 業務協調
  └─ services/
     └─ price_data_service.py

domain/                # 業務層 - 核心邏輯
  ├─ indicators/
  ├─ scanner/
  ├─ signal/
  └─ backtest/

infrastructure/        # 基礎設施層 - 外部依賴
  ├─ config/
  │   └─ config_provider.py
  └─ marketdata/
     ├─ sdk_wrapper.py
     └─ repository.py

app_container.py       # DI 容器
main.py               # 入口點
```

### 各層職責

| 層級 | 職責 | 範例 |
|-----|------|------|
| **Presentation** | 參數解析、結果輸出 | CLI 指令、使用者提示 |
| **Application** | 協調各服務、對外提供接口 | `PriceDataService` |
| **Domain** | 純業務邏輯 | 指標計算、選股條件、回測邏輯 |
| **Infrastructure** | 隱藏外部依賴 | SDK 封裝、檔案 I/O、設定讀取 |

---

## 安裝與設置

### 1. 克隆/下載專案

```bash
cd c:\StockApi
```

### 2. 建立虛擬環境（建議）

```bash
python -m venv venv
```

### 3. 啟用虛擬環境

**Windows (PowerShell)**
```bash
.\venv\Scripts\Activate.ps1
```

**Windows (CMD)**
```bash
.\venv\Scripts\activate.bat
```

**Linux/macOS**
```bash
source venv/bin/activate
```

### 4. 安裝依賴

```bash
pip install -r requirements.txt
```

**requirements.txt 內容**
```
esun-marketdata
pandas>=2.0
numpy>=1.24
click>=8.1
flask>=3.0
apscheduler>=3.10
plotly>=5.0
```

### 5. 設定玉山 API 認證

編輯 `config.simulation.ini` 或 `config.production.ini`：

```ini
[API]
key = your_api_key_here
secret = your_api_secret_here
endpoint = https://api.example.com
```

### 6. 驗證安裝

```bash
python main.py --help
```

應該看到所有可用指令列表。

### 7. 啟動 Web 介面

```bash
python web_app.py
```

開啟瀏覽器：

```text
http://127.0.0.1:5000
```

---

## Web 介面操作

啟動後可在同一頁面選擇操作項目：

- `fetch`：批次擷取資料
- `indicators`：單一股票指標計算
- `scan`：選股
- `signal`：進出場訊號
- `backtest`：回測
- `run`：一鍵完整流程

### Web 欄位說明

- `設定檔路徑`：預設 `config.simulation.ini`
- `股票清單`：可填 `2330,2454` 或 `watchlist.txt`
- `單一股票代號`：`indicators` 使用
- `起訖日期`：`fetch/indicators/scan/signal/backtest` 使用
- `save`：`1` 儲存輸出、`0` 不儲存
- `plot`：`backtest` 是否產生圖表，`1/0`

---

## 快速開始

> [!IMPORTANT]
> 你目前是 Windows PowerShell 環境：README 內使用 `\` 換行的範例屬於 Bash 寫法。
> 在 PowerShell 請改用「單行指令」或以反引號 `` ` `` 換行，否則會出現 `unexpected extra arguments (\ ...)`。
>
> 例如以下 Bash：
> `python main.py backtest \ --symbols "2330" \ --from "2024-01-01" \ --to "2025-12-31"`
>
> PowerShell 請改成：
> `python main.py backtest --symbols "2330" --from "2024-01-01" --to "2025-12-31"`

> 另外你也可以直接改用 Web 介面，避免命令列換行差異：
> `python web_app.py` 後開啟 `http://127.0.0.1:5000`

### 執行完整流程（推薦新手）

```bash
# 擷取資料 → 計算指標 → 執行選股（一鍵完成）
python main.py run --symbols "2330,2454,3105"
```

### 逐步操作

**步驟 1：擷取歷史資料**
```bash
python main.py fetch \
  --symbols "2330,2454" \
  --from "2024-01-01" \
  --to "2025-12-31"
```

**步驟 2：檢查技術指標**
```bash
python main.py indicators \
  --symbol "2330" \
  --from "2025-01-01" \
  --to "2025-12-31"
```

**步驟 3：執行今日選股**
```bash
python main.py scan \
  --symbols "watchlist.production.txt" \
  --rsi-threshold 30 \
  --vol-ratio 1.5
```

**步驟 4：產生進出場訊號**
```bash
python main.py signal \
  --symbols "2330,2454" \
  --stop-loss 0.07 \
  --take-profit 0.15
```

**步驟 5：執行回測**
```bash
python main.py backtest \
  --symbols "2330,2454" \
  --from "2024-01-01" \
  --to "2025-12-31" \
  --stop-loss 0.07 \
  --take-profit 0.15
```

---

## CLI 指令詳解

### `python main.py fetch`

**功能**：擷取歷史 K 線資料並存至 `data/` 目錄

**選項**
```
--symbols TEXT          股票代號（逗號分隔）或 .txt 檔路徑
                        預設：watchlist.production.txt

--from TEXT             起始日期 (YYYY-MM-DD)
                        預設：365 天前

--to TEXT               結束日期 (YYYY-MM-DD)
                        預設：今日

--no-save               不儲存 CSV 檔
```

**範例**
```bash
# 指定股票代號與日期
python main.py fetch --symbols "2330,2454" --from "2024-01-01" --to "2025-12-31"

# 從檔案讀取清單
python main.py fetch --symbols "my_watchlist.txt"

# 只在本地查詢，不儲存
python main.py fetch --symbols "2330" --no-save
```

---

### `python main.py indicators`

**功能**：計算並顯示技術指標（MA、RSI、MACD、KD、成交量均量）

**選項**
```
--symbol TEXT           股票代號（必須）

--from TEXT             起始日期 (YYYY-MM-DD)
                        預設：365 天前

--to TEXT               結束日期 (YYYY-MM-DD)
                        預設：今日
```

**範例**
```bash
# 查看 2330 最近一年的指標
python main.py indicators --symbol "2330"

# 查看特定日期區間
python main.py indicators --symbol "2330" --from "2025-01-01" --to "2025-04-20"
```

**輸出示例**
```
        close    ma5   ma20    ma60      rsi  macd_hist      k      d  vol_ma20
2025-04-18  180.00 179.50  178.25  177.80   65.30    0.1234  72.50  68.30  1200000
2025-04-19  181.50 180.25  179.50  178.50   72.50    0.1456  78.20  73.50  1250000
2025-04-20  180.80 180.75  180.10  179.20   68.20    0.0890  75.30  76.20  1280000
```

---

### `python main.py scan`

**功能**：根據波段策略條件進行每日選股篩選

**選項**
```
--symbols TEXT          股票清單（預設：watchlist.production.txt）

--from TEXT             歷史資料起始日期
                        預設：400 天前

--rsi-threshold FLOAT   RSI 超賣閾值（預設：30）

--vol-ratio FLOAT       成交量放大倍數（預設：1.5）

--min-hits INTEGER      最少符合幾個條件（預設：2）

--no-save               不儲存結果 CSV
```

**篩選條件**（預設至少符合 2 個）
1. RSI 由超賣反彈（前日 < 30，今日 >= 30）
2. 收盤站上 20 日均線且均線向上
3. MACD 柱狀圖由負轉正
4. 成交量 > 20 日均量 × `--vol-ratio`

**範例**
```bash
# 標準選股
python main.py scan

# 嚴格條件（必須符合 4 個）
python main.py scan --min-hits 4

# 放寬 RSI 閾值到 35
python main.py scan --rsi-threshold 35

# 自訂監控清單
python main.py scan --symbols "2330,2454,3105"
```

**輸出示例**
```
=== 選股結果（共 3 筆）===
   symbol  close   rsi    ma20  macd_hist  volume  vol_ma20 scan_date
     2330  180.50  32.50  178.25     0.0234 1500000 1000000  2025-04-20
     2454  125.30  31.20  123.50     0.0156  800000  600000   2025-04-20
     3105   95.80  30.90   94.20     0.0089  500000  350000   2025-04-20
```

---

### `python main.py signal`

**功能**：產生進出場訊號

**選項**
```
--symbols TEXT          股票清單（預設：watchlist.production.txt）

--from TEXT             歷史資料起始日期（預設：400 天前）

--stop-loss FLOAT       停損比例，如 0.07 = 7%（預設：0.07）

--take-profit FLOAT     停利比例，如 0.15 = 15%（預設：0.15）
```

**進出場邏輯**
- **進場**：RSI 超賣反彈（< 30 → >= 30）
- **出場**（三選一最先觸發）：
  - 停損：跌破進場價 7%
  - 停利：獲利達 15% 或 RSI > 70 開始回落
  - 均線出場：收盤跌破 20 日均線

**範例**
```bash
# 標準參數
python main.py signal --symbols "2330"

# 激進策略（停損 5%，停利 20%）
python main.py signal --symbols "2330" --stop-loss 0.05 --take-profit 0.20

# 保守策略（停損 10%，停利 10%）
python main.py signal --symbols "2330" --stop-loss 0.10 --take-profit 0.10
```

**輸出**
- `output/signals_summary.csv`：進場訊號彙整
- 輸出資訊：「訊號產生完成，共處理 X 支股票。」

---

### `python main.py backtest`

**功能**：執行歷史回測評估策略績效

**選項**
```
--symbols TEXT          股票清單（預設：watchlist.production.txt）

--from TEXT             回測起始日期（預設：730 天前）

--to TEXT               回測結束日期（預設：今日）

--stop-loss FLOAT       停損比例（預設：0.07）

--take-profit FLOAT     停利比例（預設：0.15）

--no-plot               不產生 Plotly 圖表（預設會產生）
```

**回測指標**
- **勝率**：獲利筆數 / 總筆數
- **平均報酬**：平均報酬率
- **最大回撤**：累積報酬的最大跌幅
- **夏普比率**：風險調整後的報酬

**範例**
```bash
# 標準回測
python main.py backtest --symbols "2330"

# 2 年回測
python main.py backtest \
  --symbols "2330,2454" \
  --from "2024-01-01" \
  --to "2025-12-31"

# 不產生圖表（加快速度）
python main.py backtest --symbols "2330" --no-plot
```

**輸出**
- `output/backtest_summary.csv`：績效彙整
- `output/trades_[股票代號].csv`：詳細交易紀錄
- `report/backtest_[股票代號].html`：互動式 Plotly 圖表

**輸出示例**
```
=== 回測績效彙整 ===
symbol  total_trades  win_rate  avg_return  max_drawdown  sharpe
  2330            15     60.00        8.50       -12.30   1.234
  2454            12     58.33        7.20       -15.50   0.987
```

---

### `python main.py run`

**功能**：一鍵執行完整流程（擷取 → 指標 → 選股）

**選項**
```
--symbols TEXT          股票清單（預設：watchlist.production.txt）
```

**範例**
```bash
# 執行完整流程
python main.py run

# 指定股票清單
python main.py run --symbols "2330,2454,3105"
```

**執行步驟**
1. 擷取過去 400 天的 K 線資料
2. 計算所有技術指標
3. 執行今日選股篩選

---

## 設定檔說明

### 配置檔位置

- `config.simulation.ini`：模擬環境（測試用）
- `config.production.ini`：生產環境（實際交易用）

### 配置檔範本

```ini
[API]
# 玉山證券 API 認證
key = your_api_key_here
secret = your_api_secret_here
endpoint = https://api.example.com

[Database]
# 資料庫連線（可選）
host = localhost
port = 5432
user = stockapi
password = your_password

[Strategy]
# 策略參數
rsi_threshold = 30
vol_ratio = 1.5
min_hits = 2

[Logging]
# 日誌設定
level = INFO
file = logs/strategy.log
```

### 使用特定配置檔

```bash
python main.py --config config.production.ini fetch --symbols "2330"
```

---

## 常見使用場景

### 場景 1：每日篩選

**需求**：每天開盤後自動篩選符合條件的股票

```bash
# 批次運行（可搭配 Windows Task Scheduler 或 cron）
python main.py scan --symbols "watchlist.txt" --no-save
```

### 場景 2：評估新策略

**需求**：測試新的進出場參數

```bash
# 先做回測驗證
python main.py backtest \
  --symbols "2330" \
  --stop-loss 0.05 \
  --take-profit 0.20

# 檢查 HTML 圖表
# 打開 report/backtest_2330.html
```

### 場景 3：查看進出場訊號

**需求**：看特定股票的進出場時間點

```bash
# 產生訊號
python main.py signal --symbols "2330"

# 查看詳細交易紀錄
cat output/signals_summary.csv
```

### 場景 4：跨年度回測

**需求**：測試 2 年期的策略績效

```bash
python main.py backtest \
  --symbols "2330,2454,3105" \
  --from "2023-01-01" \
  --to "2025-04-20" \
  --stop-loss 0.07 \
  --take-profit 0.15
```

### 場景 5：使用自訂監控清單

**需求**：維護多個不同的股票監控清單

**建立檔案 `my_watchlist.txt`**
```
2330
2454
3105
2303
```

**執行**
```bash
python main.py scan --symbols "my_watchlist.txt"
python main.py backtest --symbols "my_watchlist.txt"
```

---

## 開發者指南

### 專案結構簡述

```
StockApi/
├── presentation/           # CLI 層
│   └── commands/
│       └── stock_commands.py      # 所有 CLI 指令在此
├── application/            # 應用層
│   └── services/
│       └── price_data_service.py  # 資料服務入口
├── domain/                 # 業務層
│   ├── indicators/         # 技術指標計算
│   ├── scanner/           # 選股篩選邏輯
│   ├── signal/            # 訊號產生邏輯
│   └── backtest/          # 回測引擎
├── infrastructure/         # 基礎設施層
│   ├── config/            # 設定管理
│   └── marketdata/        # 資料取得（SDK + CSV）
├── app_container.py       # 依賴注入容器
└── main.py                # 入口點
```

### 新增功能流程

**例如：新增一個「止盈指數」的選股條件**

1. 在 `domain/scanner/scanner.py` 的 `check_conditions()` 函式中新增條件
2. 在 `presentation/commands/stock_commands.py` 的 `scan` 指令中新增 CLI 選項
3. 測試確認功能

### 修改資料來源

**例如：改用 MongoDB 存儲而非 CSV**

1. 新增 `infrastructure/database/mongo_repository.py`
2. 修改 `app_container.py` 的 `build_container()` 調整依賴
3. 無需修改上層邏輯

### 執行單元測試

```bash
# 安裝測試依賴
pip install pytest pytest-cov

# 運行測試
pytest tests/

# 產生覆蓋率報告
pytest --cov=domain tests/
```

### 程式碼風格

- 使用 PEP 8 命名規範
- 每個模組須含 docstring
- 盡量避免強耦合

---

## 疑難排解

### Q1：執行 `fetch` 時出現「找不到設定檔」

**原因**：沒有正確設定 API 認證

**解決**
```bash
# 確認設定檔存在
ls config.*.ini

# 編輯設定檔並填入 API key
notepad config.simulation.ini
```

### Q2：執行 `scan` 後沒有符合條件的股票

**原因**
- 資料不足（少於 60 日）
- 條件太嚴格
- 市場沒有符合波段的股票

**解決**
```bash
# 檢查資料是否足夠
python main.py indicators --symbol "2330"

# 放寬條件重試
python main.py scan --min-hits 1 --rsi-threshold 35

# 使用更多股票清單
python main.py scan --symbols "my_big_watchlist.txt"
```

### Q3：回測速度很慢

**原因**：生成 Plotly 圖表時間長

**解決**
```bash
# 關閉圖表生成
python main.py backtest --symbols "2330" --no-plot
```

### Q4：匯入模組時出現「ModuleNotFoundError」

**原因**：Python 路徑問題或模組未安裝

**解決**
```bash
# 確認在專案根目錄執行
cd c:\StockApi

# 重裝依賴
pip install -r requirements.txt --force-reinstall

# 檢查 Python 路徑
python -c "import sys; print(sys.path)"
```

### Q5：玉山 API 限流問題

**現象**：執行 `fetch` 時出現 429 錯誤

**解決**
- API 預設在每次呼叫後等待 0.5 秒
- 檢查 API 配額是否已用完
- 聯絡玉山證券客服提高額度

### Q6：CSV 檔案編碼問題（亂碼）

**原因**：Windows 預設編碼為 Big5/CP1252

**解決**
```bash
# 使用記事本++或 VS Code 打開，選擇 UTF-8 with BOM 編碼
# 或使用 Python 轉檔
python -c "
import pandas as pd
df = pd.read_csv('data/2330_2024-01-01_2025-12-31.csv')
df.to_csv('data/2330_utf8.csv', encoding='utf-8-sig', index=False)
"
```

---

## 聯絡與支援

- **問題回報**：提交至專案 Issue tracker
- **功能建議**：歡迎 Pull Request
- **技術討論**：GitHub Discussions

---

**最後更新**：2026 年 4 月 20 日
