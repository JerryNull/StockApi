"""
fetch.py — 玉山 API 歷史 K 線資料擷取模組
"""
import os
import time
import logging
from configparser import ConfigParser
from pathlib import Path

import pandas as pd
from esun_marketdata import EsunMarketdata

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / 'data'
DATA_DIR.mkdir(exist_ok=True)


def _get_sdk(config: ConfigParser) -> EsunMarketdata:
    sdk = EsunMarketdata(config)
    sdk.login()
    return sdk


def _year_ranges(date_from: str, date_to: str) -> list:
    """將日期區間拆分為不跨年的子區間（API 限制單次最多 1 年）。"""
    from datetime import date as dt_date
    start = dt_date.fromisoformat(date_from)
    end = dt_date.fromisoformat(date_to)
    ranges = []
    cur = start
    while cur <= end:
        year_end = dt_date(cur.year, 12, 31)
        seg_end = min(year_end, end)
        ranges.append((cur.strftime('%Y-%m-%d'), seg_end.strftime('%Y-%m-%d')))
        from datetime import timedelta
        cur = dt_date(cur.year + 1, 1, 1)
    return ranges


def fetch_candles(
    symbol: str,
    date_from: str,
    date_to: str,
    config: ConfigParser,
    save: bool = True,
    sleep_sec: float = 0.5,
) -> pd.DataFrame:
    """
    擷取單一股票歷史 K 線，回傳 DataFrame（index 為日期，ascending）。
    自動分段處理跨年請求（API 單次限制 1 年內）。

    Parameters
    ----------
    symbol    : 股票代號，如 '2330'
    date_from : 起始日期 'YYYY-MM-DD'
    date_to   : 結束日期 'YYYY-MM-DD'
    config    : ConfigParser 物件
    save      : 是否存成 CSV
    sleep_sec : 每次 API 請求後的等待秒數（避免限流）
    """
    sdk = _get_sdk(config)
    rest = sdk.rest_client.stock.historical

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
    symbols: list,
    date_from: str,
    date_to: str,
    config: ConfigParser,
    save: bool = True,
    sleep_sec: float = 0.5,
) -> dict:
    """
    批次擷取多支股票，回傳 {symbol: DataFrame} 字典。
    """
    result = {}
    for symbol in symbols:
        try:
            df = fetch_candles(symbol, date_from, date_to, config, save=save, sleep_sec=sleep_sec)
            if not df.empty:
                result[symbol] = df
        except Exception as e:
            logger.error(f'Error fetching {symbol}: {e}')
    return result


def load_local(symbol: str, date_from: str, date_to: str) -> pd.DataFrame:
    """從本地 CSV 載入資料（若已存在）。"""
    csv_path = DATA_DIR / f'{symbol}_{date_from}_{date_to}.csv'
    if csv_path.exists():
        df = pd.read_csv(csv_path, index_col='date', parse_dates=True)
        return df
    return pd.DataFrame()
