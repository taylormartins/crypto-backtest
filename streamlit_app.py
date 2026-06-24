"""
streamlit_app.py — Web UI for the crypto backtester.

Run locally:
    streamlit run streamlit_app.py

Deploy for free:
    1. Push this repo to GitHub
    2. Go to https://share.streamlit.io → "New app" → pick your repo
    3. Set Main file path to: streamlit_app.py
    4. Deploy — you get a public URL instantly
"""

import sys
import os

# Make sure local modules are importable when running from any working dir
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timezone

from core.backtester import Backtester
from core.data import fetch_ohlcv
from core.models import BaseStrategy
from core.results import summarise
from strategies.hhhll import HHHLLStrategy

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Crypto Backtester",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for mobile-friendliness ────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        border: 1px solid #313244;
    }
    .metric-value { font-size: 1.6rem; font-weight: 700; }
    .metric-label { font-size: 0.8rem; color: #a6adc8; margin-top: 4px; }
    .positive { color: #a6e3a1; }
    .negative { color: #f38ba8; }
    .neutral  { color: #cdd6f4; }
    div[data-testid="stSidebarContent"] { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar — configuration ───────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")

    ALL_SYMBOLS = [
        "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT",
        "XRP/USDT", "ADA/USDT", "AVAX/USDT", "DOGE/USDT",
    ]
    symbols = st.multiselect(
        "Symbols",
        options=ALL_SYMBOLS,
        default=ALL_SYMBOLS,
        help="Binance pairs to backtest",
    )

    timeframe = st.selectbox(
        "Timeframe",
        options=["15m", "1h", "4h", "1d"],
        index=0,
    )

    lookback_days = st.slider(
        "Lookback (days)",
        min_value=7,
        max_value=365,
        value=90,
        step=7,
    )

    initial_capital = st.number_input(
        "Capital per symbol (USDT)",
        min_value=100,
        max_value=1_000_000,
        value=10_000,
        step=500,
    )

    risk_pct = st.slider(
        "Risk per trade (%)",
        min_value=0.5,
        max_value=10.0,
        value=2.0,
        step=0.5,
    )

    swing_lookback = st.slider(
        "Swing lookback (candles)",
        min_value=2,
        max_value=20,
        value=5,
    )

    st.divider()
    run_btn = st.button("🚀 Run Backtest", use_container_width=True, type="primary")

# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)   # cache 15 min
def _fetch(symbol: str, tf: str, days: int) -> pd.DataFrame:
    return fetch_ohlcv(symbol, tf, days)


def _build_equity_curve(trades, initial_capital: float) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=["time", "equity"])
    records = []
    equity = initial_capital
    for t in sorted(trades, key=lambda x: x.exit_time):
        equity += t.pnl
        records.append({"time": t.exit_time, "equity": equity})
    return pd.DataFrame(records)


def _color_pnl(val: str) -> str:
    """Return a CSS color string for a PnL string like '$1,234.56'."""
    try:
        numeric = float(val.replace("$", "").replace(",", ""))
        return "color: #a6e3a1" if numeric >= 0 else "color: #f38ba8"
    except Exception:
        return ""


# ── Main layout ───────────────────────────────────────────────────────────────
st.title("📈 Crypto Backtester")
st.caption(
    f"HH/HL–LH/LL Market Structure strategy · "
    f"data via Binance (no API key required) · "
    f"results update each run"
)

if not run_btn:
    st.info("👈 Configure your settings in the sidebar, then press **Run Backtest**.")
    st.markdown("""
**How it works**

1. Data is fetched live from Binance's public API — no account needed.
2. The backtester scans each candle for market-structure trend flips (HH/HL → long, LH/LL → short).
3. Each trade risks the % you set, with stop loss at 1× ATR and take profit at 2× ATR (1:2 R:R).
4. Results show hypothetical PnL assuming you started with the capital amount above *per symbol*.

**Timeframe guide**

| Timeframe | Trade frequency | Best for |
|---|---|---|
| 15m | High (swing scalps) | Short-term signals |
| 1h | Medium | Balanced swing trades |
| 4h | Low | Positional trades |
| 1d | Very low | Long-term trends |
    """)
    st.stop()

if not symbols:
    st.warning("Select at least one symbol.")
    st.stop()

# ── Run ───────────────────────────────────────────────────────────────────────
backtester = Backtester(capital=initial_capital, risk=risk_pct / 100)
strategy = HHHLLStrategy(swing_lookback=swing_lookback)

all_results = []
all_trades: dict[str, list] = {}

progress = st.progress(0, text="Starting…")

for idx, symbol in enumerate(symbols):
    progress.progress(idx / len(symbols), text=f"Fetching {symbol}…")
    try:
        df = _fetch(symbol, timeframe, lookback_days)
    except Exception as exc:
        st.warning(f"Could not fetch {symbol}: {exc}")
        continue

    progress.progress((idx + 0.5) / len(symbols), text=f"Running backtest on {symbol}…")
    trades = backtester.run(df, strategy, symbol)
    result = summarise(trades, symbol, strategy)
    all_results.append(result)
    all_trades[symbol] = trades

progress.progress(1.0, text="Done!")
progress.empty()

if not all_results:
    st.error("No results — check your symbol selection or try a different timeframe.")
    st.stop()

# ── Summary metrics ───────────────────────────────────────────────────────────
total_pnl = sum(
    float(r["total_pnl"].replace("$", "").replace(",", "")) for r in all_results
)
total_trades = sum(r["trades"] for r in all_results)
winning_rows = [r for r in all_results if float(r["total_pnl"].replace("$", "").replace(",", "")) > 0]
total_invested = initial_capital * len(symbols)
pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    pnl_class = "positive" if total_pnl >= 0 else "negative"
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value {pnl_class}">${total_pnl:,.0f}</div>
        <div class="metric-label">Total PnL (all symbols)</div>
    </div>""", unsafe_allow_html=True)
with col2:
    pct_class = "positive" if pnl_pct >= 0 else "negative"
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value {pct_class}">{pnl_pct:+.1f}%</div>
        <div class="metric-label">Return on ${total_invested:,.0f} deployed</div>
    </div>""", unsafe_allow_html=True)
with col3:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value neutral">{total_trades}</div>
        <div class="metric-label">Total trades</div>
    </div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value neutral">{len(winning_rows)}/{len(all_results)}</div>
        <div class="metric-label">Profitable symbols</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Results table ─────────────────────────────────────────────────────────────
st.subheader("Results by Symbol")

df_results = pd.DataFrame(all_results).drop(columns=["strategy"], errors="ignore")

def style_results(df: pd.DataFrame) -> pd.DataFrame.style:
    def _pnl_color(val):
        return _color_pnl(str(val))
    return (
        df.style
        .map(_pnl_color, subset=["total_pnl", "avg_pnl", "best", "worst"])
        .set_properties(**{"text-align": "center"})
        .hide(axis="index")
    )

st.dataframe(
    style_results(df_results),
    use_container_width=True,
    hide_index=True,
)

# ── Equity curves ─────────────────────────────────────────────────────────────
st.subheader("Equity Curves")

fig = go.Figure()
for symbol, trades in all_trades.items():
    eq = _build_equity_curve(trades, initial_capital)
    if eq.empty:
        continue
    # Prepend starting point
    start_row = pd.DataFrame([{"time": trades[0].entry_time if trades else datetime.now(timezone.utc), "equity": initial_capital}])
    eq = pd.concat([start_row, eq], ignore_index=True)

    fig.add_trace(go.Scatter(
        x=eq["time"],
        y=eq["equity"],
        mode="lines",
        name=symbol.replace("/USDT", ""),
        hovertemplate="%{x|%b %d %H:%M}<br>$%{y:,.0f}<extra>%{fullData.name}</extra>",
    ))

fig.add_hline(
    y=initial_capital,
    line_dash="dot",
    line_color="rgba(255,255,255,0.3)",
    annotation_text=f"Start ${initial_capital:,}",
    annotation_position="bottom right",
)

fig.update_layout(
    template="plotly_dark",
    height=420,
    margin=dict(l=10, r=10, t=20, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    yaxis_title="Equity (USDT)",
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# ── PnL bar chart ─────────────────────────────────────────────────────────────
st.subheader("Total PnL by Symbol")

pnl_data = pd.DataFrame([
    {
        "symbol": r["symbol"].replace("/USDT", ""),
        "pnl": float(r["total_pnl"].replace("$", "").replace(",", "")),
    }
    for r in all_results
]).sort_values("pnl", ascending=False)

bar_fig = px.bar(
    pnl_data,
    x="symbol",
    y="pnl",
    color="pnl",
    color_continuous_scale=["#f38ba8", "#313244", "#a6e3a1"],
    color_continuous_midpoint=0,
    labels={"pnl": "PnL (USDT)", "symbol": ""},
    template="plotly_dark",
)
bar_fig.update_layout(
    height=320,
    margin=dict(l=10, r=10, t=10, b=10),
    coloraxis_showscale=False,
    showlegend=False,
)
bar_fig.update_traces(hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>")
st.plotly_chart(bar_fig, use_container_width=True)

# ── Trade log ─────────────────────────────────────────────────────────────────
with st.expander("📋 Full trade log"):
    trade_rows = []
    for symbol, trades in all_trades.items():
        for t in trades:
            trade_rows.append({
                "symbol": t.symbol,
                "direction": t.direction,
                "entry": t.entry_time.strftime("%Y-%m-%d %H:%M") if t.entry_time else "",
                "exit":  t.exit_time.strftime("%Y-%m-%d %H:%M") if t.exit_time else "",
                "entry_price": f"${t.entry_price:,.4f}",
                "exit_price":  f"${t.exit_price:,.4f}" if t.exit_price else "",
                "pnl":    f"${t.pnl:,.2f}",
                "reason": t.exit_reason,
            })
    if trade_rows:
        df_trades = pd.DataFrame(trade_rows)
        st.dataframe(df_trades, use_container_width=True, hide_index=True)
    else:
        st.info("No trades recorded.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "⚠️ This is for educational and research purposes only — not financial advice. "
    "Past backtested performance does not guarantee future results."
)
