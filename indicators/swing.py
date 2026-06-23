import pandas as pd

from config import SWING_LOOKBACK


def find_swing_highs(df: pd.DataFrame, n: int = SWING_LOOKBACK) -> pd.Series:
    """
    True at index t when the high n bars ago was the highest over a 2n+1 bar window.

    The signal fires n bars *after* the candidate candle, which is the earliest
    point we could know in real time that no subsequent bar exceeded it.
    """
    highs = df["high"]
    rolling_max = highs.rolling(2 * n + 1, min_periods=2 * n + 1).max()
    return highs.shift(n) == rolling_max


def find_swing_lows(df: pd.DataFrame, n: int = SWING_LOOKBACK) -> pd.Series:
    """
    True at index t when the low n bars ago was the lowest over a 2n+1 bar window.
    """
    lows = df["low"]
    rolling_min = lows.rolling(2 * n + 1, min_periods=2 * n + 1).min()
    return lows.shift(n) == rolling_min


def label_market_structure(df: pd.DataFrame, n: int = SWING_LOOKBACK) -> pd.DataFrame:
    """
    Adds columns to df:
        swing_high  — True n bars after a swing high is confirmed
        swing_low   — True n bars after a swing low is confirmed
        sh_label    — 'HH' or 'LH' at each confirmed swing high
        sl_label    — 'HL' or 'LL' at each confirmed swing low
        structure   — rolling last label: 'uptrend', 'downtrend', or 'undefined'

    Prices used for HH/LH/HL/LL comparisons are the actual swing-point prices
    (shifted back n bars from the confirmation bar) to avoid look-ahead.
    """
    df = df.copy()
    df["swing_high"] = find_swing_highs(df, n)
    df["swing_low"] = find_swing_lows(df, n)

    # Actual swing prices live n bars before the confirmation timestamp
    sh_prices = df["high"].shift(n)[df["swing_high"]]
    sl_prices = df["low"].shift(n)[df["swing_low"]]

    df["sh_label"] = ""
    prev_sh = None
    for idx, price in sh_prices.items():
        if prev_sh is None:
            df.at[idx, "sh_label"] = "HH"
        else:
            df.at[idx, "sh_label"] = "HH" if price > prev_sh else "LH"
        prev_sh = price

    df["sl_label"] = ""
    prev_sl = None
    for idx, price in sl_prices.items():
        if prev_sl is None:
            df.at[idx, "sl_label"] = "HL"
        else:
            df.at[idx, "sl_label"] = "HL" if price > prev_sl else "LL"
        prev_sl = price

    trend = "undefined"
    trends = []
    for _, row in df.iterrows():
        if row["sh_label"] in ("HH", "LH") or row["sl_label"] in ("HL", "LL"):
            sh = row["sh_label"]
            sl = row["sl_label"]
            if sh == "HH" or sl == "HL":
                trend = "uptrend"
            if sh == "LH" or sl == "LL":
                trend = "downtrend"
        trends.append(trend)
    df["structure"] = trends

    return df
