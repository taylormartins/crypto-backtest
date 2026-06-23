import pandas as pd

from config import SWING_LOOKBACK
from core.models import BaseStrategy
from indicators.swing import label_market_structure


class HHHLLStrategy(BaseStrategy):
    """
    Market-structure trend-flip strategy using HH/HL/LH/LL swing labels.

    Signal rules:
      Long  (+1): structure shifts from non-uptrend → uptrend  (HL confirmed)
      Short (-1): structure shifts from non-downtrend → downtrend (LH confirmed)
      Flat  ( 0): no structural change

    Entry is fired on the first candle after the trend label flips, so you're
    trading the structural break rather than chasing an established trend.

    Customisation tips:
      - Require both HH + HL before going long for a stricter filter.
      - Add a volume or RSI confluence check before returning the signal.
      - Adjust swing_lookback to trade higher/lower timeframe structures.
    """

    name = "HH/HL–LH/LL Market Structure"

    def __init__(self, swing_lookback: int = SWING_LOOKBACK):
        self.swing_lookback = swing_lookback

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        df = label_market_structure(df, self.swing_lookback)
        signals = pd.Series(0, index=df.index)
        prev_structure = "undefined"

        for ts, row in df.iterrows():
            cur = row["structure"]
            if cur == "uptrend" and prev_structure != "uptrend":
                signals[ts] = 1
            elif cur == "downtrend" and prev_structure != "downtrend":
                signals[ts] = -1
            prev_structure = cur

        return signals
