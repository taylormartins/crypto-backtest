from core.models import BaseStrategy, Trade


def summarise(trades: list[Trade], symbol: str, strategy: BaseStrategy) -> dict:
    if not trades:
        return {
            "symbol": symbol,
            "strategy": strategy.name,
            "trades": 0,
            "win_rate": "0.0%",
            "total_pnl": "$0.00",
            "avg_pnl": "$0.00",
            "best": "$0.00",
            "worst": "$0.00",
        }

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    return {
        "symbol": symbol,
        "strategy": strategy.name,
        "trades": len(pnls),
        "win_rate": f"{len(wins) / len(pnls) * 100:.1f}%",
        "total_pnl": f"${sum(pnls):,.2f}",
        "avg_pnl": f"${sum(pnls) / len(pnls):,.2f}",
        "best": f"${max(pnls):,.2f}",
        "worst": f"${min(pnls):,.2f}",
    }


def print_results(all_results: list[dict]) -> None:
    try:
        from tabulate import tabulate
        print("\n" + tabulate(all_results, headers="keys", tablefmt="outline"))
    except ImportError:
        if all_results:
            headers = list(all_results[0].keys())
            print("  ".join(f"{h:>15}" for h in headers))
            for row in all_results:
                print("  ".join(f"{str(v):>15}" for v in row.values()))
