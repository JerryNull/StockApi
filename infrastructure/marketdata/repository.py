"""
市場資料存取層 - 封裝 CSV 讀寫與 API 呼叫。
"""
import logging
import time
from datetime import date as dt_date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / 'data'
DATA_DIR.mkdir(exist_ok=True)


def _year_ranges(date_from: str, date_to: str) -> list:
    """將日期區間拆分為不跨年的子區間（API 限制單次最多 1 年）。"""
    start = dt_date.fromisoformat(date_from)
    end = dt_date.fromisoformat(date_to)
    ranges = []
    cur = start
    while cur <= end:
        year_end = dt_date(cur.year, 12, 31)
        seg_end = min(year_end, end)
        ranges.append((cur.strftime('%Y-%m-%d'), seg_end.strftime('%Y-%m-%d')))
        cur = dt_date(cur.year + 1, 1, 1)
    return ranges


class MarketDataRepository:
    """市場資料的存取層 - 優先查本地，不足才遠端抓。"""

    def __init__(self, config_provider):
        self._config_provider = config_provider
        self._sdk = None
        self._rest_client = None

    def _get_rest_client(self):
        """取得可重用的 REST client，避免重複登入觸發限流。"""
        if self._rest_client is not None:
            return self._rest_client

        try:
            from infrastructure.marketdata.sdk_wrapper import get_sdk
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(
                '缺少玉山 SDK 依賴（esun_marketdata）。若僅使用本地 CSV，可先準備完整資料避免觸發遠端抓取。'
            ) from e

        try:
            self._sdk = get_sdk(self._config_provider.get_config())
            self._rest_client = self._sdk.rest_client.stock.historical
            return self._rest_client
        except ValueError as e:
            msg = str(e)
            if 'AGR0000' in msg or 'Exceed Login Rate Limit' in msg:
                raise RuntimeError(
                    '玉山 API 登入限流（AGR0000）。請等待 1 分鐘後重試，或先以本地 CSV 模式執行。'
                ) from e
            raise

    def load_local(self, symbol: str, date_from: str, date_to: str) -> pd.DataFrame:
        """從本地 CSV 載入資料（若已存在）。"""
        csv_path = DATA_DIR / f'{symbol}_{date_from}_{date_to}.csv'
        if csv_path.exists():
            df = pd.read_csv(csv_path, index_col='date', parse_dates=True)
            return df
        return pd.DataFrame()

    def fetch_candles(
        self,
        symbol: str,
        date_from: str,
        date_to: str,
        save: bool = True,
        sleep_sec: float = 0.5,
    ) -> pd.DataFrame:
        """
        擷取單一股票歷史 K 線，回傳 DataFrame（index 為日期，ascending）。
        自動分段處理跨年請求（API 單次限制 1 年內）。
        """
        rest = self._get_rest_client()

        segments = _year_ranges(date_from, date_to)
        all_records = []

        for seg_from, seg_to in segments:
            logger.info(f'Fetching {symbol}: {seg_from} ~ {seg_to}')
            raw = rest.candles(symbol=symbol, **{'from': seg_from, 'to': seg_to,
                                                  'fields': 'open,high,low,close,volume'})
            time.sleep(sleep_sec)
            records = raw.get('data', [])
            all_records.extend(records)

        if not all_records:
            logger.warning(f'No data returned for {symbol}')
            return pd.DataFrame()

        df = pd.DataFrame(all_records)
        df['date'] = pd.to_datetime(df['date'])
        df = df.drop_duplicates('date').sort_values('date').set_index('date')
        df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

        if save:
            csv_path = DATA_DIR / f'{symbol}_{date_from}_{date_to}.csv'
            df.to_csv(csv_path, encoding='utf-8-sig')
            logger.info(f'Saved {len(df)} rows to {csv_path}')

        return df

    def fetch_batch(
        self,
        symbols: list,
        date_from: str,
        date_to: str,
        save: bool = True,
        sleep_sec: float = 0.5,
    ) -> dict:
        """批次擷取多支股票，回傳 {symbol: DataFrame} 字典。"""
        result = {}
        for symbol in symbols:
            try:
                df = self.fetch_candles(symbol, date_from, date_to, save=save, sleep_sec=sleep_sec)
                if not df.empty:
                    result[symbol] = df
            except Exception as e:
                logger.error(f'Error fetching {symbol}: {e}')
        return result
