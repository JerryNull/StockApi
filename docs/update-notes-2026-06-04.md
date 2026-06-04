# 更新說明（2026-06-04）

## 本次重點

### 1) 庫存刷新頻率調整
- 檔案：`GetPrice.py`
- 變更：`INVENTORY_REFRESH_MS` 由 `6000` 調整為 `10000`
- 影響：庫存查詢由每 6 秒改為每 10 秒，降低 API 呼叫頻率與系統負載。
- 備註：`INVENTORY_BACKOFF_MS = 60000` 維持不變。

### 2) 產業 Dashboard API/前端增強
- 路由檔案：`stock-inventory-app/src/app.py`
- 服務檔案：`stock-inventory-app/src/services/sector_service.py`
- 前端檔案：`stock-inventory-app/src/templates/sector_dashboard.html`
- 主要調整：
  - API 支援 `days` 參數（`days=1` 即時、`days>1` 歷史）
  - 後端新增歷史 CSV 聚合與 `meta + data` 回傳格式
  - 前端新增期間切換（1d / 120d）與狀態顯示

### 3) 設定讀取修正
- 檔案：`stock-inventory-app/src/services/account_client.py`
- 變更：設定鍵位改為讀取 `Core/Entry` 與 `Api/Key`。

### 4) 相關文件
- `docs/sector-api-flow.md`：新增 API 流程與資料流說明。

---

## 驗證摘要
- `GET /api/sector/summaries?days=1` 回應狀態：`200`
- 可取得 `meta.source` 與 `data` 陣列內容。

---

## 注意事項
- 目前工作區仍有本機產物（如 `obj/`、`__pycache__/`、`window.geometry.txt`、大量 `data/*.csv`）屬執行環境檔案，未納入本次說明文件提交。
