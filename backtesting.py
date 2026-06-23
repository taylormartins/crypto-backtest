"""
backtesting.py — entry point for the crypto backtesting framework.

Usage:
    python backtesting.py

To add a new strategy:
    1. Create a class in strategies/ that subclasses BaseStrategy and implements
       generate_signals(df) -> pd.Series returning 1 / -1 / 0.
    2. Import it below and add an instance to STRATEGIES.

Key config knobs are in config.py:
    SYMBOLS, TIMEFRAME, LOOKBACK_DAYS, INITIAL_CAPITAL, RISK_PER_TRADE, SWING_LOOKBACK
"""

from config import (
    INITIAL_CAPITAL,
    LOOKBACK_DAYS,
    RISK_PER_TRADE,
    SYMBOLS,
    TIMEFRAME,
)
from core.backtester import Backtester
from core.data import fetch_ohlcv
from core.models import BaseStrategy
from core.results import print_results, summarise
from strategies.hhhll import HHHLLStrategy

# ── Register strategies here ──────────────────────────────────────────────────
STRATEGIES: list[BaseStrategy] = [
    HHHLLStrategy(),
    # Add more strategies below, e.g.:
    # RSIMeanReversion(),
]
# ─────────────────────────────────────────────────────────────────────────────


def main():
    backtester = Backtester()
    all_results = []

    for symbol in SYMBOLS:
        print(f"  Fetching {symbol} {TIMEFRAME} …", end="", flush=True)
        try:
            df = fetch_ohlcv(symbol, TIMEFRAME, LOOKBACK_DAYS)
            print(f" {len(df)} candles")
        except Exception as exc:
            print(f" ERROR: {exc}")
            continue

        for strategy in STRATEGIES:
            trades = backtester.run(df, strategy, symbol)
            result = summarise(trades, symbol, strategy)
            all_results.append(result)

    print_results(all_results)


if __name__ == "__main__":
    print(f"\n{'=' * 60}")
    print(f"  Crypto Backtester  |  {TIMEFRAME} candles  |  {LOOKBACK_DAYS}d history")
    print(f"  Symbols : {', '.join(SYMBOLS)}")
    print(f"  Capital : ${INITIAL_CAPITAL:,}  |  Risk/trade: {RISK_PER_TRADE * 100:.0f}%")
    print(f"{'=' * 60}\n")
    main()
