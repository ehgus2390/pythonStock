"""Run with: python -m pytest tests  (or python tests/test_strategy_metrics.py)."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.strategy_metrics import (  # noqa: E402
    backtest_with_costs,
    score_history,
    summarize_score_history,
    trade_positions,
)


def frame(closes, buys=(), sells=()):
    index = pd.bdate_range("2024-01-01", periods=len(closes))
    df = pd.DataFrame({"Close": closes}, index=index)
    df["BuySignal"] = False
    df["SellSignal"] = False
    df.iloc[list(buys), df.columns.get_loc("BuySignal")] = True
    df.iloc[list(sells), df.columns.get_loc("SellSignal")] = True
    return df


def test_positions_follow_the_trade_rule():
    df = frame([10, 10, 11, 12, 12, 13, 13], buys=[1, 3], sells=[4, 6])
    # Second buy at index 3 is ignored while holding; exit at the first sell (index 4).
    assert trade_positions(df).tolist() == [0, 1, 1, 1, 0, 0, 0]


def test_costs_reduce_a_single_round_trip():
    df = frame([100, 100, 110, 110], buys=[1], sells=[2])
    free = backtest_with_costs(df, fee_rate=0.0, sell_tax_rate=0.0)
    paid = backtest_with_costs(df, fee_rate=0.001, sell_tax_rate=0.002)
    assert round(free["total_return_net"], 6) == 10.0
    assert paid["total_return_net"] < free["total_return_net"]
    assert free["trade_count"] == paid["trade_count"] == 1
    assert free["win_rate_net"] == 100.0
    assert round(free["buy_hold_return"], 6) == 10.0


def test_drawdown_and_open_position():
    df = frame([100, 100, 120, 90, 95], buys=[1])
    result = backtest_with_costs(df, fee_rate=0.0, sell_tax_rate=0.0)
    assert result["open_position"] is True
    assert round(result["max_drawdown_net"], 6) == -25.0
    assert result["trade_count"] == 0


def test_score_history_uses_only_past_data_and_forward_returns():
    closes = list(np.linspace(100, 200, 200))
    df = frame(closes)
    seen_lengths = []

    def score(window):
        seen_lengths.append(len(window))
        return {"buy_score": 70.0, "decision": "BUY"}

    history = score_history(df, score, step=10, min_history=120, horizons=(20,))
    assert seen_lengths[0] == 121 and all(b - a == 10 for a, b in zip(seen_lengths, seen_lengths[1:]))
    first = history.iloc[0]
    assert round(first["fwd_20d"], 6) == round((closes[140] / closes[120] - 1) * 100, 6)
    assert np.isnan(history.iloc[-1]["fwd_20d"])
    summary = summarize_score_history(history, horizons=(20,))
    buy = summary[summary["decision"] == "BUY"].iloc[0]
    assert buy["samples"] == len(history) and buy["rise_rate_20d"] == 100.0


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print("ok", name)
