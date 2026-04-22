"""
signal.py — 進出場訊號產生模組
根據策略條件計算每支股票的進出場時間點
"""
import logging
from pathlib import Path

import pandas as pd
import numpy as np

from domain.indicators.indicators import add_all

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent.parent / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)


def generate_signals(
    df: pd.DataFrame,
    stop_loss: float = 0.07,
    take_profit: float = 0.15,
    rsi_overbought: float = 70.0,
) -> pd.DataFrame:
    """
    產生進出場訊號。

    進場條件：前一日 RSI < 30 且今日 RSI >= 30（超賣反彈）
    出場條件（三選一最先觸發）：
      1. 停損：跌破進場價 stop_loss%
      2. 停利：獲利達 take_profit% 或 RSI > rsi_overbought 開始回落
      3. 均線出場：收盤跌破 20 日均線

    Returns
    -------
    DataFrame 含欄位：signal (1=買, -1=賣)、entry_price、exit_reason
    """
    df = add_all(df.copy())
    df['signal'] = 0
    df['entry_price'] = np.nan
    df['exit_reason'] = ''

    in_position = False
    entry_price = None
    entry_date = None

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        idx = df.index[i]

        if not in_position:
            # 進場：RSI 超賣反彈
            rsi_ok = (not pd.isna(prev['rsi']) and not pd.isna(row['rsi'])
                      and prev['rsi'] < 30 and row['rsi'] >= 30)
            if rsi_ok:
                df.at[idx, 'signal'] = 1
                entry_price = row['open']  # 隔日開盤進場
                df.at[idx, 'entry_price'] = entry_price
                in_position = True
                entry_date = idx
        else:
            current_return = (row['close'] - entry_price) / entry_price

            # 停損
            if current_return <= -stop_loss:
                df.at[idx, 'signal'] = -1
                df.at[idx, 'exit_reason'] = f'停損({current_return:.1%})'
                in_position = False

            # 停利：獲利達標 或 RSI 超買回落
            elif current_return >= take_profit:
                df.at[idx, 'signal'] = -1
                df.at[idx, 'exit_reason'] = f'停利({current_return:.1%})'
                in_position = False

            elif (not pd.isna(prev['rsi']) and not pd.isna(row['rsi'])
                  and prev['rsi'] > rsi_overbought and row['rsi'] < prev['rsi']):
                df.at[idx, 'signal'] = -1
                df.at[idx, 'exit_reason'] = f'RSI超買回落({row["rsi"]:.1f})'
                in_position = False

            # 均線出場
            elif not pd.isna(row['ma20']) and row['close'] < row['ma20']:
                df.at[idx, 'signal'] = -1
                df.at[idx, 'exit_reason'] = f'跌破20MA'
                in_position = False

    return df


def generate_signals_batch(
    data_map: dict,
    stop_loss: float = 0.07,
    take_profit: float = 0.15,
    rsi_overbought: float = 70.0,
    save: bool = True,
) -> dict:
    """對多支股票批次產生訊號，回傳 {symbol: DataFrame}。"""
    results = {}
    for symbol, df in data_map.items():
        if df.empty or len(df) < 60:
            continue
        sig_df = generate_signals(df, stop_loss, take_profit, rsi_overbought)
        results[symbol] = sig_df
        logger.info(f'{symbol}: 訊號產生完成，進場 {(sig_df["signal"] == 1).sum()} 次')

    if save:
        summary_rows = []
        for symbol, sig_df in results.items():
            entries = sig_df[sig_df['signal'] == 1]
            for idx, row in entries.iterrows():
                summary_rows.append({
                    'symbol': symbol,
                    'entry_date': idx.strftime('%Y-%m-%d'),
                    'entry_price': row['entry_price'],
                })
        if summary_rows:
            out_path = OUTPUT_DIR / 'signals_summary.csv'
            pd.DataFrame(summary_rows).to_csv(out_path, index=False, encoding='utf-8-sig')
            logger.info(f'訊號摘要已儲存：{out_path}')

    return results
