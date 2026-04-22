"""
scanner.py — 選股條件篩選模組
依據波段策略每日對監控清單進行篩選，輸出候選清單
"""
import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from domain.indicators.indicators import add_all

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent.parent / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)


def check_conditions(df: pd.DataFrame, conditions: dict) -> bool:
    """
    對最新一筆資料（最後一列）檢查買進條件。

    預設條件（可透過 conditions dict 調整閾值）：
      1. RSI 由 30 以下回升至 30 以上（前一日 < 30，今日 >= 30）
      2. 收盤站上 20 日均線，且 20 日均線向上
      3. MACD 柱狀圖由負轉正
      4. 成交量 > 20 日均量 * volume_ratio
    """
    rsi_threshold = conditions.get('rsi_threshold', 30)
    vol_ratio = conditions.get('vol_ratio', 1.5)
    require_all = conditions.get('require_all', False)  # False=任一條件符合即入選

    if len(df) < 2:
        return False

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    hits = []

    # 條件1：RSI 超賣反彈
    rsi_bounce = (
        not pd.isna(prev.get('rsi')) and not pd.isna(latest.get('rsi'))
        and prev['rsi'] < rsi_threshold
        and latest['rsi'] >= rsi_threshold
    )
    hits.append(rsi_bounce)

    # 條件2：收盤站上 20MA 且均線向上
    ma20_breakout = (
        not pd.isna(latest.get('ma20')) and not pd.isna(prev.get('ma20'))
        and latest['close'] > latest['ma20']
        and latest['ma20'] > prev['ma20']
    )
    hits.append(ma20_breakout)

    # 條件3：MACD 柱狀圖由負轉正
    macd_cross = (
        not pd.isna(prev.get('macd_hist')) and not pd.isna(latest.get('macd_hist'))
        and prev['macd_hist'] < 0
        and latest['macd_hist'] > 0
    )
    hits.append(macd_cross)

    # 條件4：量能放大
    vol_breakout = (
        not pd.isna(latest.get('vol_ma20'))
        and latest['vol_ma20'] > 0
        and latest['volume'] > latest['vol_ma20'] * vol_ratio
    )
    hits.append(vol_breakout)

    if require_all:
        return all(hits)
    # 預設：至少兩個條件符合
    min_hits = conditions.get('min_hits', 2)
    return sum(hits) >= min_hits


def scan(
    data_map: dict,
    conditions: dict = None,
    scan_date: date = None,
    save: bool = True,
) -> pd.DataFrame:
    """
    對 data_map 中所有股票進行篩選。

    Parameters
    ----------
    data_map   : {symbol: DataFrame} 含 OHLCV 的字典
    conditions : 條件參數 dict（可覆蓋預設值）
    scan_date  : 掃描日期（預設今日）
    save       : 是否輸出 CSV

    Returns
    -------
    DataFrame：符合條件的股票清單
    """
    if conditions is None:
        conditions = {}
    if scan_date is None:
        scan_date = date.today()

    results = []
    for symbol, df in data_map.items():
        if df.empty or len(df) < 60:
            logger.debug(f'{symbol}: 資料不足，跳過')
            continue

        df = add_all(df.copy())

        if check_conditions(df, conditions):
            latest = df.iloc[-1]
            results.append({
                'symbol': symbol,
                'close': latest['close'],
                'rsi': round(latest.get('rsi', float('nan')), 2),
                'ma20': round(latest.get('ma20', float('nan')), 2),
                'macd_hist': round(latest.get('macd_hist', float('nan')), 4),
                'volume': int(latest['volume']),
                'vol_ma20': int(latest.get('vol_ma20', 0)),
                'scan_date': scan_date.strftime('%Y-%m-%d'),
            })
            logger.info(f'{symbol} 符合條件')

    result_df = pd.DataFrame(results)

    if save and not result_df.empty:
        date_str = scan_date.strftime('%Y%m%d')
        csv_path = OUTPUT_DIR / f'scan_{date_str}.csv'
        try:
            result_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        except PermissionError:
            backup_path = OUTPUT_DIR / f'scan_{date_str}_{datetime.now().strftime("%H%M%S")}.csv'
            result_df.to_csv(backup_path, index=False, encoding='utf-8-sig')
            logger.warning(
                f'原檔案被占用，已改存：{backup_path}（共 {len(result_df)} 筆）'
            )
        else:
            logger.info(f'選股結果已儲存：{csv_path}（共 {len(result_df)} 筆）')

    return result_df
