from typing import Optional

import pandas as pd

from config import INITIAL_CAPITAL, MAX_LEVERAGE, RISK_PER_TRADE
from core.models import BaseStrategy, Trade


class Backtester:
    def __init__(self, capital: float = INITIAL_CAPITAL, risk: float = RISK_PER_TRADE, fee_pct: float = 0.0):
        self.capital = capital
        self.risk = risk
        self.fee_pct = fee_pct  # fraction, e.g. 0.001 for 0.1% per side

    def run(self, df: pd.DataFrame, strategy: BaseStrategy, symbol: str) -> list[Trade]:
        signals = strategy.generate_signals(df)
        trades: list[Trade] = []
        open_trade: Optional[Trade] = None
        equity = self.capital

        for i, (ts, row) in enumerate(df.iterrows()):
            price = row["close"]
            sig = signals[ts]

            if open_trade and not open_trade.closed:
                hit_sl = hit_tp = False

                if open_trade.direction == "long":
                    if open_trade.stop_loss and row["low"] <= open_trade.stop_loss:
                        hit_sl = True
                    elif open_trade.take_profit and row["high"] >= open_trade.take_profit:
                        hit_tp = True
                else:
                    if open_trade.stop_loss and row["high"] >= open_trade.stop_loss:
                        hit_sl = True
                    elif open_trade.take_profit and row["low"] <= open_trade.take_profit:
                        hit_tp = True

                if hit_sl:
                    open_trade.close(open_trade.stop_loss, ts, "stop_loss")
                elif hit_tp:
                    open_trade.close(open_trade.take_profit, ts, "take_profit")
                elif sig != 0 and (
                    (open_trade.direction == "long" and sig == -1)
                    or (open_trade.direction == "short" and sig == 1)
                ):
                    open_trade.close(price, ts, "signal_exit")

                if open_trade.closed:
                    if self.fee_pct > 0:
                        fee = (open_trade.entry_price + open_trade.exit_price) * open_trade.size * self.fee_pct
                        open_trade.pnl -= fee
                    equity += open_trade.pnl
                    trades.append(open_trade)
                    open_trade = None

            if sig != 0 and open_trade is None:
                direction = "long" if sig == 1 else "short"
                atr = self._atr(df, i)
                risk_amount = equity * self.risk
                stop_dist = atr if atr > 0 else price * 0.01

                if direction == "long":
                    stop_loss = price - stop_dist
                    take_profit = price + stop_dist * 2
                else:
                    stop_loss = price + stop_dist
                    take_profit = price - stop_dist * 2

                size = risk_amount / stop_dist if stop_dist > 0 else 0
                max_size = (equity * MAX_LEVERAGE) / price
                size = min(size, max_size)

                if size > 0:
                    open_trade = Trade(
                        symbol=symbol,
                        direction=direction,
                        entry_time=ts,
                        entry_price=price,
                        size=size,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                    )

        if open_trade and not open_trade.closed:
            last_ts = df.index[-1]
            open_trade.close(df.iloc[-1]["close"], last_ts, "end_of_data")
            trades.append(open_trade)

        return trades

    @staticmethod
    def _atr(df: pd.DataFrame, i: int, period: int = 14) -> float:
        start = max(0, i - period)
        window = df.iloc[start : i + 1]
        if len(window) < 2:
            return 0.0
        trs = []
        for j in range(1, len(window)):
            prev_close = window.iloc[j - 1]["close"]
            high = window.iloc[j]["high"]
            low = window.iloc[j]["low"]
            trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        return sum(trs) / len(trs)
