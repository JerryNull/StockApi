"""
backtest.py — 回測引擎
使用向量化方式計算績效，支援文字報告與 HTML 圖表輸出
"""
import logging
from pathlib import Path

import pandas as pd
import numpy as np

from domain.signal.signal import generate_signals

logger = logging.getLogger(__name__)

REPORT_DIR = Path(__file__).parent.parent.parent / 'report'
REPORT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR = Path(__file__).parent.parent.parent / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)


def _extract_trades(sig_df: pd.DataFrame) -> pd.DataFrame:
    """從含訊號的 DataFrame 萃取交易紀錄。"""
    trades = []
    in_pos = False
    entry_date = None
    entry_price = None

    for idx, row in sig_df.iterrows():
        if row['signal'] == 1 and not in_pos:
            in_pos = True
            entry_date = idx
            entry_price = row['entry_price'] if not pd.isna(row['entry_price']) else row['open']
        elif row['signal'] == -1 and in_pos:
            exit_price = row['close']
            ret = (exit_price - entry_price) / entry_price
            trades.append({
                'entry_date': entry_date,
                'exit_date': idx,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'return': ret,
                'exit_reason': row['exit_reason'],
            })
            in_pos = False
            entry_date = None
            entry_price = None

    return pd.DataFrame(trades)


def _calc_metrics(trades_df: pd.DataFrame, annual_rf: float = 0.02) -> dict:
    """計算回測績效指標。"""
    if trades_df.empty:
        return {
            'total_trades': 0,
            'win_rate': None,
            'avg_return': None,
            'max_drawdown': None,
            'sharpe': None,
        }

    rets = trades_df['return']
    wins = (rets > 0).sum()
    total = len(rets)

    # 最大回撤（累積報酬序列）
    cumulative = (1 + rets).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_dd = drawdown.min()

    # 夏普比率（假設每筆交易為獨立樣本）
    daily_rf = annual_rf / 252
    excess = rets - daily_rf
    sharpe = excess.mean() / excess.std() * (252 ** 0.5) if excess.std() > 0 else None

    return {
        'total_trades': total,
        'win_rate': round(wins / total * 100, 2),
        'avg_return': round(rets.mean() * 100, 2),
        'max_drawdown': round(max_dd * 100, 2),
        'sharpe': round(sharpe, 3) if sharpe is not None else None,
    }


def run_backtest(
    symbol: str,
    df: pd.DataFrame,
    stop_loss: float = 0.07,
    take_profit: float = 0.15,
    rsi_overbought: float = 70.0,
    plot: bool = True,
) -> dict:
    """
    對單一股票執行回測。

    Returns
    -------
    dict：{metrics, trades, sig_df}
    """
    sig_df = generate_signals(df, stop_loss, take_profit, rsi_overbought)
    trades_df = _extract_trades(sig_df)
    metrics = _calc_metrics(trades_df)

    logger.info(
        f'{symbol} 回測完成 — '
        f'交易次數:{metrics["total_trades"]} '
        f'勝率:{metrics["win_rate"]}% '
        f'平均報酬:{metrics["avg_return"]}% '
        f'最大回撤:{metrics["max_drawdown"]}% '
        f'夏普:{metrics["sharpe"]}'
    )

    # 儲存交易明細
    if not trades_df.empty:
        trades_df.to_csv(OUTPUT_DIR / f'trades_{symbol}.csv', index=False, encoding='utf-8-sig')

    # 輸出 HTML 圖表（需 plotly）
    if plot:
        _plot_backtest(symbol, sig_df, trades_df)

    return {'metrics': metrics, 'trades': trades_df, 'sig_df': sig_df}


def _plot_backtest(symbol: str, sig_df: pd.DataFrame, trades_df: pd.DataFrame):
    """產生 plotly 互動圖表並存為 HTML。"""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True,
            row_heights=[0.5, 0.25, 0.25],
            subplot_titles=[f'{symbol} K 線與訊號', 'RSI', 'MACD']
        )

        # K 線
        fig.add_trace(go.Candlestick(
            x=sig_df.index,
            open=sig_df['open'], high=sig_df['high'],
            low=sig_df['low'], close=sig_df['close'],
            name='K線', increasing_line_color='red', decreasing_line_color='green'
        ), row=1, col=1)

        # MA
        for ma, color in [('ma5', 'orange'), ('ma20', 'blue'), ('ma60', 'purple')]:
            if ma in sig_df.columns:
                fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df[ma],
                                         name=ma.upper(), line=dict(color=color, width=1)), row=1, col=1)

        # 進出場標記
        if not trades_df.empty:
            fig.add_trace(go.Scatter(
                x=trades_df['entry_date'], y=trades_df['entry_price'],
                mode='markers', name='進場',
                marker=dict(symbol='triangle-up', color='red', size=12)
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=trades_df['exit_date'], y=trades_df['exit_price'],
                mode='markers', name='出場',
                marker=dict(symbol='triangle-down', color='green', size=12)
            ), row=1, col=1)

        # RSI
        if 'rsi' in sig_df.columns:
            fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df['rsi'], name='RSI',
                                     line=dict(color='orange')), row=2, col=1)
            fig.add_hline(y=70, line_dash='dash', line_color='red', row=2, col=1)
            fig.add_hline(y=30, line_dash='dash', line_color='green', row=2, col=1)

        # MACD
        if 'macd_hist' in sig_df.columns:
            colors = ['red' if v >= 0 else 'green' for v in sig_df['macd_hist'].fillna(0)]
            fig.add_trace(go.Bar(x=sig_df.index, y=sig_df['macd_hist'],
                                  name='MACD Hist', marker_color=colors), row=3, col=1)

        fig.update_layout(
            title=f'{symbol} 回測報告',
            xaxis_rangeslider_visible=False,
            template='plotly_dark',
            height=800,
        )

        out_path = REPORT_DIR / f'backtest_{symbol}.html'
        fig.write_html(str(out_path))
        logger.info(f'圖表已儲存：{out_path}')

    except ImportError:
        logger.warning('plotly 未安裝，跳過圖表輸出。可執行：pip install plotly')


def run_backtest_batch(
    data_map: dict,
    stop_loss: float = 0.07,
    take_profit: float = 0.15,
    rsi_overbought: float = 70.0,
    plot: bool = True,
) -> pd.DataFrame:
    """批次回測，回傳彙整績效表。"""
    rows = []
    for symbol, df in data_map.items():
        if df.empty or len(df) < 60:
            continue
        result = run_backtest(symbol, df, stop_loss, take_profit, rsi_overbought, plot)
        row = {'symbol': symbol, **result['metrics']}
        rows.append(row)

    summary = pd.DataFrame(rows)
    if not summary.empty:
        out_path = OUTPUT_DIR / 'backtest_summary.csv'
        summary.to_csv(out_path, index=False, encoding='utf-8-sig')
        logger.info(f'回測彙整已儲存：{out_path}')

    return summary
