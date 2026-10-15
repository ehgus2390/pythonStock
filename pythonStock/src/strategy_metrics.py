"""Backtest metrics and score validation built on the app's existing signals and scores.

Nothing here changes how signals or scores are calculated: the RSI signal columns come from
``add_indicators`` and the score comes from the caller's ``compute_decision_score``.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


def trade_positions(df: pd.DataFrame) -> pd.Series:
    """End-of-day holding state for the trade rule used by the app's trade count and win rate.

    Enter at the close of a BuySignal day while flat, exit at the close of the next SellSignal day.
    """
    held = []
    in_position = False
    for buy, sell in zip(df["BuySignal"].fillna(False), df["SellSignal"].fillna(False)):
        if not in_position and bool(buy):
            in_position = True
        elif in_position and bool(sell):
            in_position = False
        held.append(1 if in_position else 0)
    return pd.Series(held, index=df.index, dtype=float)


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    return float((equity / equity.cummax() - 1.0).min() * 100.0)


def _cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return float("nan")
    days = (pd.Timestamp(equity.index[-1]) - pd.Timestamp(equity.index[0])).days
    if days <= 0 or equity.iloc[-1] <= 0:
        return float("nan")
    return float((equity.iloc[-1] ** (365.25 / days) - 1.0) * 100.0)


def backtest_with_costs(
    df: pd.DataFrame,
    fee_rate: float,
    sell_tax_rate: float,
    benchmark_close: pd.Series | None = None,
) -> dict:
    """Trade-based backtest with transaction costs, drawdown and comparisons.

    ``fee_rate`` is charged on every buy and sell; ``sell_tax_rate`` only on sells (as fractions,
    e.g. 0.00015 for 0.015%).
    """
    close = df["Close"].astype(float)
    held = trade_positions(df)
    daily_return = close.pct_change().fillna(0.0)
    gross = daily_return * held.shift(1).fillna(0.0)

    change = held.diff().fillna(held)
    buys = change > 0
    sells = change < 0
    cost = buys * fee_rate + sells * (fee_rate + sell_tax_rate)
    net = gross - cost

    equity_gross = (1.0 + gross).cumprod()
    equity_net = (1.0 + net).cumprod()

    trade_returns = []
    entry_price = None
    for price, is_buy, is_sell in zip(close, buys, sells):
        if is_buy:
            entry_price = float(price)
        elif is_sell and entry_price:
            gross_trade = float(price) / entry_price
            trade_returns.append(gross_trade * (1 - fee_rate) * (1 - fee_rate - sell_tax_rate) - 1.0)
            entry_price = None

    buy_hold_return = float((close.iloc[-1] / close.iloc[0] - 1.0) * 100.0) if len(close) > 1 else float("nan")

    benchmark_return = float("nan")
    if benchmark_close is not None and not benchmark_close.empty:
        index = pd.DatetimeIndex(close.index)
        if index.tz is not None:
            index = index.tz_localize(None)
        bench = benchmark_close.copy()
        bench.index = pd.DatetimeIndex(bench.index)
        if bench.index.tz is not None:
            bench.index = bench.index.tz_localize(None)
        bench = bench[(bench.index >= index[0]) & (bench.index <= index[-1])].dropna()
        if len(bench) > 1:
            benchmark_return = float((bench.iloc[-1] / bench.iloc[0] - 1.0) * 100.0)

    trade_count = len(trade_returns)
    return {
        "equity_gross": equity_gross,
        "equity_net": equity_net,
        "total_return_gross": float((equity_gross.iloc[-1] - 1.0) * 100.0),
        "total_return_net": float((equity_net.iloc[-1] - 1.0) * 100.0),
        "cagr_net": _cagr(equity_net),
        "max_drawdown_net": _max_drawdown(equity_net),
        "buy_hold_return": buy_hold_return,
        "buy_hold_max_drawdown": _max_drawdown(close / close.iloc[0]),
        "benchmark_return": benchmark_return,
        "exposure_pct": float(held.mean() * 100.0),
        "trade_count": trade_count,
        "win_rate_net": (sum(1 for r in trade_returns if r > 0) / trade_count * 100.0) if trade_count else 0.0,
        "open_position": bool(held.iloc[-1]) if len(held) else False,
    }


def score_history(
    df: pd.DataFrame,
    score_fn: Callable[[pd.DataFrame], dict],
    step: int = 5,
    min_history: int = 120,
    horizons: tuple[int, ...] = (20, 60),
) -> pd.DataFrame:
    """Re-run the score at past dates using only data up to each date, then attach forward returns."""
    close = df["Close"].astype(float)
    rows = []
    for end in range(min_history, len(df), step):
        window = df.iloc[: end + 1]
        try:
            result = score_fn(window)
        except Exception:
            continue
        row = {
            "date": df.index[end],
            "close": float(close.iloc[end]),
            "buy_score": float(result.get("buy_score", np.nan)),
            "decision": result.get("decision", ""),
        }
        for horizon in horizons:
            target = end + horizon
            row[f"fwd_{horizon}d"] = (
                float((close.iloc[target] / close.iloc[end] - 1.0) * 100.0) if target < len(close) else np.nan
            )
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_score_history(history: pd.DataFrame, horizons: tuple[int, ...] = (20, 60)) -> pd.DataFrame:
    """Average forward return and share of rises for each past decision."""
    if history.empty:
        return pd.DataFrame()
    summary = []
    for decision in ["BUY", "HOLD", "SELL"]:
        group = history[history["decision"] == decision]
        row = {"decision": decision, "samples": int(len(group))}
        for horizon in horizons:
            values = group[f"fwd_{horizon}d"].dropna()
            row[f"evaluated_{horizon}d"] = int(len(values))
            row[f"avg_return_{horizon}d"] = float(values.mean()) if len(values) else np.nan
            row[f"rise_rate_{horizon}d"] = float((values > 0).mean() * 100.0) if len(values) else np.nan
        summary.append(row)
    return pd.DataFrame(summary)
