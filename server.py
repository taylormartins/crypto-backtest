"""
server.py — FastAPI backend for the crypto backtester UI.

Run:
    uvicorn server:app --reload

Then open http://localhost:8000
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import INITIAL_CAPITAL, SYMBOLS
from core.backtester import Backtester
from core.data import fetch_ohlcv
from core.models import Trade
from strategies.hhhll import HHHLLStrategy

app = FastAPI(title="Crypto Backtester API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

# ── Strategy registry — add new strategies here ──────────────────────────────
STRATEGY_MAP: dict = {
    "hhhll": HHHLLStrategy,
}

# ── In-memory OHLCV cache — persists for the server's lifetime ───────────────
_ohlcv_cache: dict[str, pd.DataFrame] = {}


def _get_ohlcv(symbol: str) -> pd.DataFrame:
    if symbol not in _ohlcv_cache:
        _ohlcv_cache[symbol] = fetch_ohlcv(symbol)
    return _ohlcv_cache[symbol]


# ── Metrics helpers ───────────────────────────────────────────────────────────

def _build_equity_curve(trades: list[Trade], initial: float, df: pd.DataFrame) -> list[dict]:
    pnl_at: dict = {}
    for t in trades:
        k = t.exit_time
        pnl_at[k] = pnl_at.get(k, 0.0) + t.pnl
    equity = initial
    curve = []
    for ts in df.index:
        if ts in pnl_at:
            equity += pnl_at[ts]
        curve.append({"t": int(ts.timestamp() * 1000), "v": round(equity, 2)})
    return curve


def _drawdown_periods(curve: list[dict]) -> list[dict]:
    if not curve:
        return []
    peak = curve[0]["v"]
    periods, in_dd, dd_start = [], False, None
    for pt in curve:
        v = pt["v"]
        if v >= peak:
            peak = v
            if in_dd:
                periods.append({"start": dd_start, "end": pt["t"]})
                in_dd = False
        elif not in_dd:
            in_dd, dd_start = True, pt["t"]
    if in_dd:
        periods.append({"start": dd_start, "end": curve[-1]["t"]})
    return periods


def _compute_stats(trades: list[Trade], window_initial: float, curve: list[dict]) -> dict:
    empty = dict(total_return_pct=0, sharpe_ratio=0, max_drawdown_pct=0,
                 win_rate=0, total_trades=0, avg_win=0, avg_loss=0, profit_factor=0)
    if not trades or not curve:
        return empty

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0

    values = np.array([p["v"] for p in curve])
    rets = np.diff(values) / values[:-1]
    # 15 m candles → 365 × 96 periods per year
    sharpe = float((rets.mean() / rets.std()) * np.sqrt(365 * 96)) if len(rets) > 1 and rets.std() > 0 else 0

    peak, max_dd = window_initial, 0.0
    for pt in curve:
        v = pt["v"]
        if v > peak:
            peak = v
        dd = (v - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd

    return dict(
        total_return_pct=round((curve[-1]["v"] - window_initial) / window_initial * 100, 2),
        sharpe_ratio=round(sharpe, 2),
        max_drawdown_pct=round(max_dd, 2),
        win_rate=round(len(wins) / len(pnls) * 100, 1) if pnls else 0,
        total_trades=len(trades),
        avg_win=round(sum(wins) / len(wins), 2) if wins else 0,
        avg_loss=round(sum(losses) / len(losses), 2) if losses else 0,
        profit_factor=round(profit_factor, 2),
    )


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/symbols")
def api_symbols():
    return {
        "symbols": SYMBOLS,
        "strategies": list(STRATEGY_MAP.keys()),
    }


@app.get("/api/backtest")
def api_backtest(
    symbol: str = Query("BTC/USDT"),
    strategy: str = Query("hhhll"),
    start: int = Query(None),   # ms epoch
    end: int = Query(None),     # ms epoch
):
    strat = STRATEGY_MAP.get(strategy, HHHLLStrategy)()
    full_df = _get_ohlcv(symbol)

    # Window bounds — default to full dataset
    start_ts = pd.Timestamp(start, unit="ms", tz="UTC") if start else full_df.index[0]
    end_ts   = pd.Timestamp(end,   unit="ms", tz="UTC") if end   else full_df.index[-1]

    # Slice to the selected window and run a fresh backtest starting with
    # INITIAL_CAPITAL — this answers "what if I put $10k in at this date?"
    df = full_df.loc[start_ts:end_ts]
    trades = Backtester(capital=INITIAL_CAPITAL).run(df, strat, symbol)

    curve      = _build_equity_curve(trades, INITIAL_CAPITAL, df)
    dd_periods = _drawdown_periods(curve)
    stats      = _compute_stats(trades, INITIAL_CAPITAL, curve)

    candles = [
        {"t": int(ts.timestamp() * 1000),
         "o": float(row.open), "h": float(row.high),
         "l": float(row.low),  "c": float(row.close), "v": float(row.volume)}
        for ts, row in df.iterrows()
    ]

    trade_list = []
    for i, t in enumerate(trades):
        entry_ms = int(pd.Timestamp(t.entry_time).timestamp() * 1000)
        exit_ms  = int(pd.Timestamp(t.exit_time).timestamp()  * 1000) if t.exit_time else None
        dur = None
        if t.entry_time and t.exit_time:
            dur = int((pd.Timestamp(t.exit_time) - pd.Timestamp(t.entry_time)).total_seconds() / 60)
        cost = float(t.entry_price) * float(t.size)
        pnl_pct = float(t.pnl) / cost * 100 if cost else 0
        trade_list.append(dict(
            id=i + 1,
            entry_time=entry_ms, exit_time=exit_ms,
            side=t.direction,
            entry_price=round(float(t.entry_price), 4),
            exit_price=round(float(t.exit_price), 4) if t.exit_price else None,
            size=round(float(t.size), 6),
            pnl=round(float(t.pnl), 2),
            pnl_pct=round(pnl_pct, 2),
            exit_reason=t.exit_reason,
            duration_mins=dur,
        ))

    return dict(
        candles=candles,
        equity_curve=curve,
        drawdown_periods=dd_periods,
        trades=trade_list,
        stats=stats,
        meta=dict(
            symbol=symbol,
            strategy=strat.name,
            initial_capital=INITIAL_CAPITAL,
            start=candles[0]["t"] if candles else None,
            end=candles[-1]["t"]  if candles else None,
            full_start=int(full_df.index[0].timestamp() * 1000),
            full_end=int(full_df.index[-1].timestamp()  * 1000),
        ),
    )


# Serve frontend — must be last so /api/* routes take precedence
app.mount("/", StaticFiles(directory="static", html=True), name="static")
