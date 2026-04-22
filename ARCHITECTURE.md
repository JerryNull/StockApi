# 架構設計文件

## 概述

本專案採用 **Clean Architecture + 輕量手動 DI** 的設計模式，目的是讓程式碼：
- 易於測試
- 易於維護
- 易於擴展
- 不依賴特定框架

---

## 架構層級

### 1. Presentation 層（表現層）

**位置**：`presentation/commands/stock_commands.py`

**職責**
- 解析使用者輸入（CLI 參數）
- 調用應用層服務
- 格式化並輸出結果

**特點**
- 不應包含業務邏輯
- 不應直接操作檔案或 API
- 所有依賴都通過 DI 容器注入

**範例**
```python
@cli.command()
@click.option('--symbols', default='watchlist.txt')
def scan(ctx, symbols):
    """Presentation 層只負責：
    1. 解析參數
    2. 呼叫服務
    3. 輸出結果
    """
    container = ctx.obj['container']
    symbol_list = _load_watchlist(symbols)
    
    data_map = container.price_data_service.load_data_map(
        symbol_list, date_from, date_to
    )
    result = run_scan(data_map)
    click.echo(result.to_string())
```

---

### 2. Application 層（應用層）

**位置**：`application/services/price_data_service.py`

**職責**
- 協調不同的業務模組
- 提供統一的服務介面
- 管理業務流程的順序

**特點**
- 依賴於 Domain 層（業務邏輯）和 Infrastructure 層（資料存取）
- 對外隱藏內部複雜度
- 無狀態的服務

**範例**
```python
class PriceDataService:
    """應用服務 - 協調資料存取與業務邏輯"""
    
    def __init__(self, repository: MarketDataRepository):
        self._repository = repository
    
    def load_data_map(self, symbols, date_from, date_to):
        """協調邏輯：
        - 優先查本地 CSV
        - 不足部分再從 API 抓
        - 返回完整資料
        """
        data_map = {}
        for symbol in symbols:
            # 優先本地
            df = self._repository.load_local(symbol, date_from, date_to)
            if df.empty:
                # 遠端抓取
                df = self._repository.fetch_candles(symbol, date_from, date_to)
            if not df.empty:
                data_map[symbol] = df
        return data_map
```

---

### 3. Domain 層（業務層）

**位置**：`domain/`

**模組**

| 模組 | 功能 |
|-----|------|
| `indicators/` | 技術指標計算（MA、RSI、MACD、KD） |
| `scanner/` | 選股篩選邏輯 |
| `signal/` | 進出場訊號產生 |
| `backtest/` | 回測引擎與績效計算 |

**職責**
- 實現核心業務規則
- 完全獨立於外部框架和技術細節
- 對輸入進行驗證和轉換

**特點**
- **最穩定的層級**：業務邏輯一般不變
- **可獨立測試**：無需 mock 外部依賴
- **可重用**：可從不同的 Presentation 層調用（Web、CLI、API）

**範例：指標計算**
```python
# domain/indicators/indicators.py
def add_all(df: pd.DataFrame) -> pd.DataFrame:
    """純業務邏輯：無副作用、無外部依賴"""
    df = add_ma(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_kd(df)
    df = add_volume_ma(df)
    return df
```

**範例：選股篩選**
```python
# domain/scanner/scanner.py
def check_conditions(df: pd.DataFrame, conditions: dict) -> bool:
    """純業務邏輯：檢查條件"""
    # 1. RSI 超賣反彈
    # 2. 站上 20MA
    # 3. MACD 正轉
    # 4. 量能放大
    return sum(hits) >= min_hits
```

---

### 4. Infrastructure 層（基礎設施層）

**位置**：`infrastructure/`

**子模組**

#### `config/config_provider.py`
```python
class ConfigProvider:
    """統一管理設定檔載入"""
    def get_config(self) -> ConfigParser:
        # 惰性載入，避免重複讀檔
        pass
```

#### `marketdata/sdk_wrapper.py`
```python
def get_sdk(config: ConfigParser) -> EsunMarketdata:
    """封裝玉山 SDK，隔離外部依賴"""
    sdk = EsunMarketdata(config)
    sdk.login()
    return sdk
```

#### `marketdata/repository.py`
```python
class MarketDataRepository:
    """資料存取層 - 隱藏 CSV 與 API 的細節"""
    
    def load_local(self, symbol, date_from, date_to):
        # 讀取 CSV
        pass
    
    def fetch_candles(self, symbol, date_from, date_to):
        # 呼叫 API
        pass
    
    def fetch_batch(self, symbols, date_from, date_to):
        # 批次操作
        pass
```

**職責**
- 隱藏所有外部依賴（SDK、檔案系統、資料庫）
- 提供統一的資料存取介面
- 處理技術細節（連接、重試、編碼）

**特點**
- **最容易變更的層級**：改 API 或存儲只影響此層
- **技術決定在此做**：使用 CSV 或 MongoDB、同步或非同步等

---

## 依賴注入（DI）

### DI 容器

**位置**：`app_container.py`

```python
@dataclass
class AppContainer:
    config_provider: ConfigProvider
    price_data_service: PriceDataService

def build_container(config_path: str) -> AppContainer:
    """集中管理物件生命周期與依賴組裝"""
    config_provider = ConfigProvider(config_path)
    repository = MarketDataRepository(config_provider)
    price_data_service = PriceDataService(repository)
    
    return AppContainer(
        config_provider=config_provider,
        price_data_service=price_data_service,
    )
```

### 使用模式

```python
# 在 CLI 指令中
container = build_container(config_path)
data_map = container.price_data_service.load_data_map(...)
```

### 好處

1. **集中管理**：所有依賴在一個地方定義
2. **易於測試**：可以用 mock 物件替換
3. **靈活擴展**：新增服務或改變實現無需改上層代碼

---

## 資料流

### 完整流程：從 CLI 到結果

```
CLI 指令 (main.py)
  ↓
Presentation 層 (stock_commands.py)
  ├─ 解析參數
  ├─ 從容器取得服務
  └─ 呼叫應用層
    ↓
Application 層 (price_data_service.py)
  ├─ 協調資料載入邏輯
  └─ 呼叫基礎設施層
    ↓
Infrastructure 層 (repository.py)
  ├─ 查詢本地 CSV
  └─ 若不足，呼叫 API 並更新本地
    ↓
Application 層 (回傳資料)
  ↓
Presentation 層
  ├─ 呼叫 Domain 層進行運算
  ├─ 格式化結果
  └─ 輸出到使用者
```

### 選股流程示例

```python
# 1. CLI 接收參數
symbols = ["2330", "2454"]
date_from, date_to = "2025-01-01", "2025-04-20"

# 2. Application 協調
data_map = container.price_data_service.load_data_map(symbols, date_from, date_to)
# 返回：{"2330": DataFrame, "2454": DataFrame}

# 3. Domain 層執行業務邏輯
from domain.scanner.scanner import scan
result = scan(data_map, conditions={'rsi_threshold': 30})
# 返回：符合條件的股票 DataFrame

# 4. Presentation 層輸出
click.echo(result.to_string())
```

---

## 擴展指南

### 新增功能：「漲停判斷」選股條件

#### 步驟 1：在 Domain 層新增邏輯

```python
# domain/scanner/scanner.py
def check_limit_up(df: pd.DataFrame) -> bool:
    """檢查是否漲停"""
    latest = df.iloc[-1]
    return latest['close'] >= latest['high_limit']

def check_conditions(df: pd.DataFrame, conditions: dict) -> bool:
    # ... 既有條件 ...
    
    # 新增漲停條件
    limit_up = check_limit_up(df)
    hits.append(limit_up)
    
    # ... 計算 ...
```

#### 步驟 2：在 Presentation 層新增 CLI 選項

```python
# presentation/commands/stock_commands.py
@cli.command()
@click.option('--include-limit-up', is_flag=True, help='包含漲停股票')
def scan(ctx, symbols, include_limit_up):
    conditions = {
        'rsi_threshold': 30,
        'include_limit_up': include_limit_up,
    }
    result = run_scan(data_map, conditions=conditions)
```

#### 步驟 3：無需修改其他層

✅ Application 層無需改動
✅ Infrastructure 層無需改動

---

## 測試策略

### 單位測試：Domain 層

```python
# tests/test_indicators.py
def test_add_rsi():
    df = pd.DataFrame({'close': [100, 101, 99, 102, ...]})
    result = add_rsi(df)
    
    assert 'rsi' in result.columns
    assert result['rsi'].min() >= 0
    assert result['rsi'].max() <= 100

# tests/test_scanner.py
def test_check_conditions():
    df = create_sample_dataframe_with_signals()
    assert check_conditions(df, conditions)
```

### 整合測試：Application 層

```python
# tests/test_price_data_service.py
def test_load_data_map():
    service = PriceDataService(mock_repository)
    data_map = service.load_data_map(['2330'], '2025-01-01', '2025-04-20')
    
    assert '2330' in data_map
    assert isinstance(data_map['2330'], pd.DataFrame)
```

### 端對端測試：CLI 層

```bash
# 實際執行 CLI，驗證整個流程
python main.py scan --symbols "test_watchlist.txt"
```

---

## 效能優化

### 1. 資料快取

```python
# infrastructure/marketdata/repository.py
class MarketDataRepository:
    def __init__(self, config_provider):
        self._config_provider = config_provider
        self._cache = {}  # 簡易快取
    
    def fetch_batch(self, symbols, date_from, date_to):
        for symbol in symbols:
            cache_key = f"{symbol}_{date_from}_{date_to}"
            if cache_key in self._cache:
                # 命中快取
                result[symbol] = self._cache[cache_key]
            else:
                # 查詢並快取
                df = self.fetch_candles(symbol, ...)
                self._cache[cache_key] = df
```

### 2. 並行下載

```python
# infrastructure/marketdata/repository.py
from concurrent.futures import ThreadPoolExecutor

def fetch_batch(self, symbols, ...):
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(self.fetch_candles, sym, ...): sym
            for sym in symbols
        }
        result = {futures[f]: f.result() for f in futures}
```

### 3. 向量化計算

```python
# domain/indicators/indicators.py
# 使用 pandas 內建方法，而非 for 迴圈
df['ma5'] = df['close'].rolling(5).mean()  # 快
# 而不是：
for i in range(5, len(df)):
    df.iloc[i]['ma5'] = sum(df.iloc[i-5:i]['close']) / 5  # 慢
```

---

## 常見決定

### 為何使用手動 DI 而非 Spring/FastAPI 的 DI 框架？

**優點**
- 輕量級：無需額外依賴
- 顯式：清楚看到依賴結構
- 靈活：可隨時調整

**缺點**
- 手動編寫：多一些程式碼
- 不如框架自動化

**我們的選擇**：手動 DI，因為專案規模適中，無需重型框架。

### 為何把業務邏輯都放在 Domain 層？

**優點**
- 獨立性：可在 Web、CLI、API 中重用
- 可測試性：不需要 mock 外部依賴
- 穩定性：業務規則變化較少

### 為何 Infrastructure 層有 Repository 模式？

**優點**
- 隔離外部依賴
- 便於切換存儲方式（CSV → DB → API）
- 統一的資料存取介面

---

## 未來改進

### 可能的升級

1. **非同步 I/O**：使用 `asyncio` 加速 API 呼叫
2. **事件驅動**：使用 Event Bus 解耦各模組
3. **完整 DI 框架**：當功能增加時，可導入 `dependency-injector`
4. **資料庫**：改用 PostgreSQL 存儲而非 CSV
5. **Real-time 監控**：使用 WebSocket 即時推送訊號

### 保持架構穩定的原則

- Domain 層保持純粹的業務邏輯
- Infrastructure 層適配任何外部技術
- Presentation 層快速迭代新功能
- Application 層作為粘合劑

---

**最後更新**：2026 年 4 月 20 日
