from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd


@dataclass
class Trade:
    symbol: str
    direction: str          # "long" or "short"
    entry_time: datetime
    entry_price: float
    size: float             # units of base asset
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    closed: bool = False
    exit_reason: str = ""

    def close(self, price: float, ts: datetime, reason: str = "signal"):
        self.exit_price = price
        self.exit_time = ts
        self.exit_reason = reason
        if self.direction == "long":
            self.pnl = (price - self.entry_price) * self.size
        else:
            self.pnl = (self.entry_price - price) * self.size
        self.closed = True


class BaseStrategy(ABC):
    """
    Subclass this to implement a new strategy.

    generate_signals() receives the full OHLCV DataFrame and must return a
    Series indexed identically to df with values:
        1  = go long
       -1  = go short
        0  = flat / hold
    """

    name: str = "Unnamed"

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        ...

    def __str__(self):
        return self.name
