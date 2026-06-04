# 產業 Dashboard API 文件與流程圖

## 1. 系統入口與 SDK 初始化

來源程式：
- [stock-inventory-app/src/app.py](../stock-inventory-app/src/app.py)
- [stock-inventory-app/src/services/sector_service.py](../stock-inventory-app/src/services/sector_service.py)

啟動時在 [stock-inventory-app/src/app.py](../stock-inventory-app/src/app.py#L8-L21) 會做：

1. 載入 `config.simulation.ini`
2. 建立 `EsunMarketdata(config)`
3. 呼叫 `marketdata_sdk.login()`
4. 取得 `rest_stock = marketdata_sdk.rest_client.stock`
5. 將 `rest_stock` 注入 `SectorService(rest_stock)`

---

## 2. API 一：`/api/sector/summaries`

路由： [stock-inventory-app/src/app.py](../stock-inventory-app/src/app.py#L34-L39)

### 功能
取得「所有產業」漲跌彙總（給產業漲跌圖使用）。

### 參數
- `days`（query，可選，預設 1）
  - `1`：即時模式（snapshot）
  - `>1`：歷史模式（CSV 聚合）

### 回傳格式
- `meta`：資料來源、期間、時間戳
- `data`：每個產業統計（平均漲跌、總量、股票數）

### 流程圖
```mermaid
flowchart TD
    A[GET /api/sector/summaries?days=N] --> B[app.py: sector_summaries()]
    B --> C[SectorService.get_sector_summaries(days)]
    C --> D{days > 1 ?}
    D -- 否 --> E[即時模式: _build_snapshot_sector_summaries()]
    D -- 是 --> F[歷史模式: _build_historical_sector_summaries(days)]

    E --> E1[SDK: snapshot.quotes(TSE/OTC)]
    E --> E2[SDK: intraday.tickers(...)]
    E1 --> E3[依產業分組計算平均漲跌/總量/股票數]
    E2 --> E3
    E3 --> G[回傳 meta + data]

    F --> F1[讀取 data/*.csv]
    F1 --> F2[計算個股區間漲跌與區間量]
    F2 --> F3[依產業聚合]
    F3 --> G
```

---

## 3. API 二：`/api/sector/stocks/<industry_code>`

路由： [stock-inventory-app/src/app.py](../stock-inventory-app/src/app.py#L42-L47)

### 功能
取得指定產業底下個股明細（給類股交易量 Treemap 使用）。

### 參數
- `industry_code`（path，必填）
- `days`（query，可選，預設 1）
  - `1`：即時模式（snapshot）
  - `>1`：歷史模式（CSV 聚合）

### 回傳格式
- `meta`：資料來源、期間、時間戳
- `data`：該產業股票清單（symbol/name/changePercent/volume）

### 流程圖
```mermaid
flowchart TD
    A[GET /api/sector/stocks/<industry_code>?days=N] --> B[app.py: sector_stocks(industry_code)]
    B --> C[SectorService.get_stocks_in_sector(industry_code, days)]
    C --> D{days > 1 ?}
    D -- 否 --> E[即時模式: fetch_snapshot()]
    D -- 是 --> F[歷史模式: fetch_historical()]

    E --> E1[SDK: intraday.tickers(exchange, industry_code)]
    E1 --> E2[取得該產業 symbols]
    E2 --> E3[SDK: snapshot.quotes(TSE/OTC)]
    E3 --> E4[過濾該產業股票，組成 data]
    E4 --> G[回傳 meta(source=snapshot) + data]

    F --> F1[先取該產業 symbols]
    F1 --> F2[逐股讀 CSV 歷史資料]
    F2 --> F3[計算區間漲跌與區間總量]
    F3 --> H[回傳 meta(source=historical) + data]
```

---

## 4. 實際使用到的 SDK 功能

在 [stock-inventory-app/src/services/sector_service.py](../stock-inventory-app/src/services/sector_service.py) 主要用到：

1. `self._rest.snapshot.quotes(market='TSE'/'OTC')`
   - 用途：抓即時行情（`changePercent`, `tradeVolume`）
   - 位置： [stock-inventory-app/src/services/sector_service.py](../stock-inventory-app/src/services/sector_service.py#L55-L60)

2. `self._rest.intraday.tickers(type='EQUITY', exchange='TWSE'/'TPEx', industry=code)`
   - 用途：抓產業成分股（symbol 與 name）
   - 位置： [stock-inventory-app/src/services/sector_service.py](../stock-inventory-app/src/services/sector_service.py#L62-L68)

---

## 5. 快取機制

- `SectorService` 使用 5 分鐘 TTL 快取（`_cache_ttl = 300`）
- 同條件重複查詢可減少 SDK 呼叫與運算耗時
- 位置： [stock-inventory-app/src/services/sector_service.py](../stock-inventory-app/src/services/sector_service.py#L34-L52)

---

## 6. 重點總結

- `/api/sector/summaries`：產業層級彙總
- `/api/sector/stocks/<industry_code>`：個股層級明細
- `days=1`：主要依賴 SDK 即時 API
- `days>1`：主要依賴本機 CSV 歷史資料聚合
