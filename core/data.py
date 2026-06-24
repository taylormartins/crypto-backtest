import os
import time

import ccxt
import pandas as pd

from config import TIMEFRAME, LOOKBACK_DAYS

# KuCoin works from any IP worldwide including cloud servers.
# Override with EXCHANGE env var if needed.
_EXCHANGE_ID = os.environ.get("EXCHANGE", "kucoin")


def fetch_ohlcv(symbol: str, timeframe: str = TIMEFRAME, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    """Fetch OHLCV candles from the configured exchange (no API key required)."""
    exchange: ccxt.Exchange = getattr(ccxt, _EXCHANGE_ID)({"enableRateLimit": True})

    tf_ms    = exchange.parse_timeframe(timeframe) * 1000   # ms per candle
    since_ms = exchange.milliseconds() - days * 24 * 60 * 60 * 1000
    now_ms   = exchange.milliseconds()

    all_candles: list = []
    fetch_since = since_ms

    while True:
        candles = exchange.fetch_ohlcv(symbol, timeframe, since=fetch_since, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        last_ts = candles[-1][0]
        # Stop when we've reached (or are within one candle of) the current time
        if last_ts >= now_ms - tf_ms:
            break
        # Guard against no forward progress (some exchanges repeat the last candle)
        if last_ts <= fetch_since:
            break
        fetch_since = last_ts + 1
        time.sleep(exchange.rateLimit / 1000)

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime").drop(columns=["timestamp"])
    df = df[~df.index.duplicated(keep="last")]
    return df
