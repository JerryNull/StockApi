"""
indicators.py — 技術指標計算模組
支援 MA、RSI、MACD、KD、成交量均量
"""
import pandas as pd
import numpy as np


def add_ma(df: pd.DataFrame, periods: list = [5, 20, 60]) -> pd.DataFrame:
    """計算移動平均線（MA）。"""
    for p in periods:
        df[f'ma{p}'] = df['close'].rolling(p).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """計算 RSI（Wilder 平滑法）。"""
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """計算 MACD（DIF、DEA、柱狀圖）。"""
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd_dif'] = ema_fast - ema_slow
    df['macd_dea'] = df['macd_dif'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = (df['macd_dif'] - df['macd_dea']) * 2
    return df


def add_kd(df: pd.DataFrame, period: int = 9) -> pd.DataFrame:
    """計算 KD 指標（RSV → K → D）。"""
    low_min = df['low'].rolling(period).min()
    high_max = df['high'].rolling(period).max()
    rsv = (df['close'] - low_min) / (high_max - low_min).replace(0, np.nan) * 100

    k_values = []
    d_values = []
    k_prev, d_prev = 50.0, 50.0
    for rsv_val in rsv:
        if pd.isna(rsv_val):
            k_values.append(np.nan)
            d_values.append(np.nan)
        else:
            k = k_prev * 2 / 3 + rsv_val / 3
            d = d_prev * 2 / 3 + k / 3
            k_values.append(k)
            d_values.append(d)
            k_prev, d_prev = k, d

    df['k'] = k_values
    df['d'] = d_values
    return df


def add_volume_ma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """計算成交量均量。"""
    df[f'vol_ma{period}'] = df['volume'].rolling(period).mean()
    return df


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    """一次加入所有指標。"""
    df = add_ma(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_kd(df)
    df = add_volume_ma(df)
    return df
