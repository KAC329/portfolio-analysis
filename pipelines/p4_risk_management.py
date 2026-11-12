"""Phase 4 — Position sizing & risk management, backtested net of costs.

Strategies compared over the same out-of-sample window (weekly rebalance):
  1. Equal weight (current portfolio proxy), monthly rebalance
  2. VOO buy & hold
  3. Signal tilt — EW tilted by the best Phase 3 model's forecast
  4. Signal tilt + volatility targeting + drawdown stop
  5. Half-Kelly + volatility targeting + drawdown stop
  6. Equal weight + volatility targeting + drawdown stop (isolates the overlay)

The best model is chosen on the VALIDATION split only (see p3.json).
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from common import C, MUTED, SERIES, load_all, save_json, savefig, to_md, plt
from pa import backtest, metrics as M, risk as R


def load_preds(model: str) -> pd.Series:
    return pd.read_parquet(C.METRICS / f"oos_{model}.parquet")["pred"]


def build_targets(pred, rets, rf, close, strength, mode):
    dates = backtest.rebalance_dates(pred.index.get_level_values("date").unique(), "W-FRI")
    out = {}
    for d in dates:
        p = pred.xs(d, level="date").dropna()
        p = p[close.loc[d, p.index].notna()]
        if len(p) < 5:
            continue
        cov = R.ewma_cov(rets, d)
        p = p[p.index.isin(cov.index)]
        if mode.startswith("ew"):
            w = pd.Series(1 / len(p), index=p.index)
        elif mode == "kelly":
            mu = R.kelly_inputs(p, rets, d, float(rf.loc[:d].iloc[-1] * C.TRADING_DAYS))
            w = R.kelly(mu, cov)
        else:
            w = R.signal_tilt(p, strength)
        if mode in ("ew_vt", "tilt_vt", "kelly"):
            w = R.vol_target(w, cov)
        out[d] = w
    return pd.DataFrame(out).T.reindex(columns=C.TICKERS).fillna(0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--strength", type=float, default=0.5)
    a = ap.parse_args()
    p3 = json.loads((C.METRICS / "p3.json").read_text())
    # default: the loop's current champion, else Phase 3's best validation model
    model = a.model or ("champion" if (C.METRICS / "oos_champion.parquet").exists()
                        else p3["best_model_by_validation"])
    close, volume, market, fred, rets, rf = load_all()
    pred = load_preds(model)
    start = pred.index.get_level_values("date").min()

    strategies = {
        "Signal tilt": dict(mode="tilt", dd=None),
        "Signal tilt + vol target + DD stop": dict(mode="tilt_vt", dd=C.DD_LIMIT),
        "Half-Kelly + vol target + DD stop": dict(mode="kelly", dd=C.DD_LIMIT),
        "EW + vol target + DD stop": dict(mode="ew_vt", dd=C.DD_LIMIT),
    }
    bts = {}
    reb_m = backtest.rebalance_dates(rets.loc[start:].index, "ME")
    bts["Equal weight (current)"] = backtest.run(rets.loc[start:], backtest.equal_weight_targets(close, reb_m), rf=rf)
    for k, s in strategies.items():
        T = build_targets(pred, rets, rf, close, a.strength, s["mode"])
        bts[k] = backtest.run(rets.loc[start:], T, rf=rf, dd_limit=s["dd"])
    net = pd.DataFrame({k: v["net"] for k, v in bts.items()})
    net["VOO (S&P 500)"] = rets[C.BENCHMARK]
    net = net.dropna()
    tab = M.summary_table(net, rf, bench=net["VOO (S&P 500)"])
    yrs = len(net) / C.TRADING_DAYS
    for k, v in bts.items():
        v = v.loc[net.index]
        tab.loc[k, "Turnover (ann.)"] = v["turnover"].sum() / yrs
        tab.loc[k, "Cost drag (ann.)"] = v["cost"].sum() / yrs
        tab.loc[k, "Avg invested"] = v["invested"].mean()
        tab.loc[k, "Time de-risked"] = v["derisked"].mean()
    hold = net.index >= pd.Timestamp(C.HOLDOUT_START)
    tab["Sharpe (hold-out)"] = [M.sharpe(net.loc[hold, c], rf.loc[net.index[hold]]) for c in net.columns]
    cols = ["CAGR", "Volatility", "Sharpe", "Sortino", "Max Drawdown", "Calmar", "Beta", "Sharpe (hold-out)",
            "Turnover (ann.)", "Cost drag (ann.)", "Avg invested", "Time de-risked"]
    to_md(tab[cols], "p4_strategy_comparison")

    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    for k, c in zip(net.columns, [SERIES[1], SERIES[6], SERIES[2], SERIES[3], SERIES[4], SERIES[0]]):
        g = (1 + net[k]).cumprod()
        ax.plot(g.index, g, color=c, label=k, linewidth=1.7)
    ax.axvspan(pd.Timestamp(C.HOLDOUT_START), net.index[-1], color="#f0efec", zorder=0, label="Hold-out period")
    ax.set_title(f"Strategy backtests, net of trading costs (signal: {model})")
    ax.set_ylabel("Growth of $1")
    ax.legend(fontsize=8, loc="upper left")
    savefig(fig, "p4_growth")

    fig, ax = plt.subplots(figsize=(9.5, 3.3))
    for k, c in zip(["Equal weight (current)", "Signal tilt + vol target + DD stop", "VOO (S&P 500)"],
                    [SERIES[1], SERIES[2], SERIES[0]]):
        ax.plot(net.index, M.drawdown(net[k]) * 100, color=c, label=k, linewidth=1.5)
    ax.axhline(-C.DD_LIMIT * 100, color=MUTED, linestyle="--", linewidth=1, label=f"DD stop trigger (−{C.DD_LIMIT:.0%})")
    ax.set_ylabel("Drawdown (%)")
    ax.set_title("Drawdowns: does the risk overlay cap the downside?")
    ax.legend(fontsize=8, loc="lower left")
    savefig(fig, "p4_drawdown")

    # cost sensitivity: how fragile is the edge to trading costs?
    sens = {}
    T = build_targets(pred, rets, rf, close, a.strength, "tilt_vt")
    base = backtest.cost_vector(C.TICKERS)
    for mult in (0, 1, 2, 4):
        bt = backtest.run(rets.loc[start:], T, rf=rf, costs=base * mult, dd_limit=C.DD_LIMIT)
        sens[f"{mult}x costs"] = {"Sharpe": M.sharpe(bt["net"], rf), "CAGR": M.cagr(bt["net"])}
    to_md(pd.DataFrame(sens).T, "p4_cost_sensitivity")

    save_json({"model": model, "strength": a.strength, "table": tab[cols].to_dict(orient="index"),
               "cost_sensitivity": sens}, "p4")
    print(tab[["CAGR", "Volatility", "Sharpe", "Max Drawdown", "Sharpe (hold-out)", "Turnover (ann.)"]].round(3))


if __name__ == "__main__":
    main()
