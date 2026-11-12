"""Phase 5 — Black-Litterman with model views.

A. Backtest (monthly): prior = current equal-weight portfolio (no historical
   market caps are needed, so no look-ahead), Σ = Ledoit-Wolf on trailing year,
   views = Grinold alpha from the model forecast scaled by the model's OWN
   trailing realised IC (if the model has had no skill lately, views ≈ 0 and
   the portfolio stays at the prior — a built-in safety valve).
B. Today's recommendation: prior = market-cap/AUM weights (Bigdata.com
   snapshot), same view machinery on the latest forecasts.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from common import C, SERIES, load_all, save_json, savefig, to_md, plt
from pa import backtest, bl, metrics as M, optimize as O
from pa.models import daily_ic


def trailing_ic(oos: pd.DataFrame, d: pd.Timestamp, window: int = 252) -> float:
    """Mean daily IC over the past year using only labels known at d."""
    dates = oos.index.get_level_values("date").unique().sort_values()
    pos = dates.searchsorted(d)
    known = dates[max(0, pos - C.HORIZON - window): max(0, pos - C.HORIZON)]
    if len(known) < 60:
        return 0.0
    sub = oos[oos.index.get_level_values("date").isin(known)]
    return float(daily_ic(sub).mean())


def bl_weights(pred_d, cov, w_ref, ic, omega_scale):
    pi = bl.implied_returns(cov, w_ref)
    alpha = bl.grinold_alpha(pred_d, cov, max(ic, 0.0))
    Q = pi.loc[pred_d.index] + alpha
    mu, cov_post = bl.posterior(pi, cov, Q, omega_scale=omega_scale)
    return bl.optimal_weights(mu, cov_post), pi, alpha, mu


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--omega", type=float, default=1.0)
    a = ap.parse_args()
    p3 = json.loads((C.METRICS / "p3.json").read_text())
    # default: the loop's current champion, else Phase 3's best validation model
    model = a.model or ("champion" if (C.METRICS / "oos_champion.parquet").exists()
                        else p3["best_model_by_validation"])
    oos = pd.read_parquet(C.METRICS / f"oos_{model}.parquet")
    close, volume, market, fred, rets, rf = load_all()
    start = oos.index.get_level_values("date").min() + pd.DateOffset(years=1)

    # --- A. Backtest ------------------------------------------------------------
    reb = backtest.rebalance_dates(rets.loc[start:].index, "ME")
    T_bl, T_mvo, ics = {}, {}, {}
    for d in reb:
        if d not in oos.index.get_level_values("date"):
            continue
        p = oos["pred"].xs(d, level="date").dropna()
        win = rets.loc[:d].iloc[-252:]
        names = [t for t in p.index if win[t].notna().mean() > 0.95]
        if len(names) < 5:
            continue
        mu_h, cov = O.estimate(win[names].dropna())
        w_ref = pd.Series(1 / len(names), index=names)
        ic = trailing_ic(oos, d)
        ics[d] = ic
        T_bl[d] = bl_weights(p[names], cov, w_ref, ic, a.omega)[0]
        T_mvo[d] = O.max_sharpe(mu_h, cov, float(rf.loc[:d].iloc[-1] * C.TRADING_DAYS))
    res = {}
    net = {}
    for k, T in {"Black-Litterman (model views)": T_bl, "Max Sharpe on historical means": T_mvo}.items():
        Td = pd.DataFrame(T).T.reindex(columns=C.TICKERS).fillna(0)
        net[k] = backtest.run(rets.loc[start:], Td, rf=rf)["net"]
    net["Equal weight (current)"] = backtest.run(
        rets.loc[start:], backtest.equal_weight_targets(close, reb), rf=rf)["net"]
    net["VOO (S&P 500)"] = rets[C.BENCHMARK]
    net = pd.DataFrame(net).dropna()
    tab = M.summary_table(net, rf, bench=net["VOO (S&P 500)"])
    hold = net.index >= pd.Timestamp(C.HOLDOUT_START)
    tab["Sharpe (hold-out)"] = [M.sharpe(net.loc[hold, c], rf.loc[net.index[hold]]) for c in net.columns]
    cols = ["CAGR", "Volatility", "Sharpe", "Max Drawdown", "Beta", "Info Ratio", "Sharpe (hold-out)"]
    to_md(tab[cols], "p5_backtest")
    res["backtest"] = tab[cols].to_dict(orient="index")
    res["avg_trailing_ic_used"] = float(np.mean(list(ics.values()))) if ics else None

    fig, ax = plt.subplots(figsize=(9, 4.2))
    for k, c in zip(net.columns, [SERIES[6], SERIES[7], SERIES[1], SERIES[0]]):
        ax.plot(net.index, (1 + net[k]).cumprod(), color=c, label=k, linewidth=1.7)
    ax.axvspan(pd.Timestamp(C.HOLDOUT_START), net.index[-1], color="#f0efec", zorder=0, label="Hold-out period")
    ax.set_title("Black-Litterman vs alternatives (monthly rebalance, net of costs)")
    ax.set_ylabel("Growth of $1")
    ax.legend(fontsize=8, loc="upper left")
    savefig(fig, "p5_growth")

    # --- B. Today's recommendation ----------------------------------------------
    snap = pd.read_csv(sorted(C.DATA_SNAP.glob("bigdata_snapshot_*.csv"))[-1]).set_index("ticker")
    last = oos.index.get_level_values("date").max()
    p = oos["pred"].xs(last, level="date").dropna()
    win = rets.loc[:last].iloc[-252:]
    names = [t for t in p.index if win[t].notna().mean() > 0.95 and pd.notna(snap.loc[t, "market_cap_or_aum_usd"])]
    mu_h, cov = O.estimate(win[names].dropna())
    caps = snap.loc[names, "market_cap_or_aum_usd"].astype(float)
    w_cap = caps / caps.sum()
    ic = trailing_ic(oos, last)
    w_bl, pi, alpha, mu_post = bl_weights(p[names], cov, w_cap, ic, a.omega)
    w_bl_ew, *_ = bl_weights(p[names], cov, pd.Series(1 / len(names), index=names), ic, a.omega)
    px = snap.loc[names, "price"].astype(float)
    upside = snap.loc[names, "analyst_target_mean"].astype(float) / px - 1
    rec = pd.DataFrame({
        "Current (EW)": 1 / len(names), "Market-cap prior": w_cap, "Implied return π": pi,
        "Model view α": alpha, "Posterior return": mu_post, "BL weight (cap prior)": w_bl,
        "BL weight (EW prior)": w_bl_ew, "Analyst target upside": upside,
    }).sort_values("BL weight (EW prior)", ascending=False)
    to_md(rec, "p5_recommendation", pct_cols=set(rec.columns))
    res.update({"model": model, "as_of": str(last.date()), "trailing_ic": ic, "omega_scale": a.omega,
                "excluded_from_recommendation": sorted(set(C.TICKERS) - set(names))})

    fig, ax = plt.subplots(figsize=(8, 6.5))
    r2 = rec.sort_values("BL weight (EW prior)")
    y = np.arange(len(r2))
    for k, (col, c) in enumerate(zip(["Current (EW)", "BL weight (EW prior)", "BL weight (cap prior)"],
                                     [SERIES[1], SERIES[6], SERIES[0]])):
        ax.barh(y + (k - 1) * 0.27, r2[col] * 100, height=0.24, color=c, label=col)
    ax.set_yticks(y, r2.index)
    ax.set_xlabel("Weight (%)")
    ax.set_title(f"Black-Litterman allocation as of {last.date()}")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    savefig(fig, "p5_weights", source="Source: Yahoo Finance, FRED, Bigdata.com (market caps/AUM); author calculations.")

    save_json(res, "p5")
    print(tab[cols].round(3))
    print(rec.round(3))


if __name__ == "__main__":
    main()
