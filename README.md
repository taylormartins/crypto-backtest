# Crypto Backtester

A beginner-friendly Python framework for backtesting crypto trading strategies against historical OHLCV data pulled from Binance (no API key required).

## Project Structure

```
crypto/
├── backtesting.py        # Entry point — run this
├── config.py             # Global settings (symbols, timeframe, capital, risk)
├── requirements.txt
├── core/
│   ├── data.py           # Binance OHLCV fetcher (ccxt)
│   ├── models.py         # Trade dataclass + BaseStrategy ABC
│   ├── backtester.py     # Event-driven backtester with ATR position sizing
│   └── results.py        # Summarise and print results table
├── indicators/
│   └── swing.py          # Swing-high/low detection + market structure labelling
└── strategies/
    └── hhhll.py          # HH/HL–LH/LL market structure trend-flip strategy
```

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python backtesting.py
```

Results are printed as a table showing total trades, win rate, total PnL, average PnL, best and worst trade for each symbol × strategy combination.

## Configuration

Edit `config.py` to adjust:

| Variable | Default | Description |
|---|---|---|
| `SYMBOLS` | 8 major pairs | Binance pairs to test |
| `TIMEFRAME` | `15m` | Candle interval |
| `LOOKBACK_DAYS` | `90` | Days of history to fetch |
| `INITIAL_CAPITAL` | `10000` | Starting USDT per symbol |
| `RISK_PER_TRADE` | `0.02` | Fraction of equity risked per trade |
| `SWING_LOOKBACK` | `5` | Candles each side to confirm a swing point |

## Position Sizing

Each trade risks `RISK_PER_TRADE × equity`. Stop loss is set at `1× ATR` from entry; take profit at `2× ATR` (1:2 RR). Size is calculated as `risk_amount / stop_distance`.

## Adding a New Strategy

1. Create a file in `strategies/`, e.g. `strategies/rsi_reversion.py`.
2. Subclass `BaseStrategy` from `core.models` and implement `generate_signals`:

```python
from core.models import BaseStrategy
import pandas as pd

class RSIMeanReversion(BaseStrategy):
    name = "RSI Mean Reversion"

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # compute RSI, return Series of 1 / -1 / 0
        ...
```

3. Import and add an instance to `STRATEGIES` in `backtesting.py`:

```python
from strategies.rsi_reversion import RSIMeanReversion

STRATEGIES = [
    HHHLLStrategy(),
    RSIMeanReversion(),
]
```

The backtester, position sizing, and results table all work automatically.

## Strategy: HH/HL–LH/LL Market Structure

Detects confirmed swing highs and lows using a rolling window (±`SWING_LOOKBACK` candles), labels each swing as HH, LH, HL, or LL, then fires a signal only when the trend label flips:

- **Long (+1)**: structure shifts to uptrend (first HL confirmed after a downtrend)
- **Short (−1)**: structure shifts to downtrend (first LH confirmed after an uptrend)
- **Flat (0)**: no structural change
