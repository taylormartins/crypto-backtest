import os
import time

import ccxt
import pandas as pd

from config import TIMEFRAME, LOOKBACK_DAYS

# KuCoin works from any IP worldwide including cloud servers.
# Override with EXCHANGE env var if needed, e.g. EXCHANGE=binanceus for local.
_EXCHANGE_ID = os.environ.get("EXCHANGE", "kucoin")


def fetch_ohlcv(symbol: str, timeframe: str = TIMEFRAME, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    """Fetch OHLCV candles from the configured exchange (no API key required)."""
    exchange: ccxt.Exchange = getattr(ccxt, _EXCHANGE_ID)({"enableRateLimit": True})
    since_ms = exchange.milliseconds() - days * 24 * 60 * 60 * 1000
    limit = 1000

    all_candles: list = []
    fetch_since = since_ms

    while True:
        candles = exchange.fetch_ohlcv(symbol, timeframe, since=fetch_since, limit=limit)
        if not candles:
            break
        all_candles.extend(candles)
        if len(candles) < limit:
            break
        fetch_since = candles[-1][0] + 1
        time.sleep(exchange.rateLimit / 1000)

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime").drop(columns=["timestamp"])
    df = df[~df.index.duplicated(keep="last")]
    return df
