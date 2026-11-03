"""Phase 2 — Mean-variance optimisation.

Two views of the same question:
A. *In-sample* (the textbook picture): estimate μ, Σ on the last 3 years, draw
   10,000 random portfolios, solve max-Sharpe and min-volatility exactly.
B. *Out-of-sample* (the honest picture): re-optimise every month using only
   the trailing 3 years, hold for a month, repeat. This shows how much of the
   in-sample "improvement" survives estimation error.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import C, INK2, MUTED, SERIES, load_all, save_json, savefig, to_md, plt
from pa import backtest, metrics as M, optimize as O


def universe(rets: pd.DataFrame, end: pd.Timestamp, years: int) -> list[str]:
    w = rets.loc[end - pd.DateOffset(years=years):end]
    return list(w.columns[w.notna().mean() > 0.98])


def main():
    close, volume, market, fred, rets, rf = load_all()
    end = rets.index[-1]
    names = universe(rets, end, C.OPT_LOOKBACK_YEARS)
    excluded = sorted(set(C.TICKERS) - set(names))
    win = rets.loc[end - pd.DateOffset(years=C.OPT_LOOKBACK_YEARS):, names].dropna()
    rf_ann = float(rf.loc[win.index].mean() * C.TRADING_DAYS)
    mu, cov = O.estimate(win)
    res = {"universe": names, "excluded_short_history": excluded, "rf_ann": rf_ann,
           "window": [str(win.index[0].date()), str(win.index[-1].date())]}

    # --- A. In-sample ------------------------------------------------------
    mc = O.monte_carlo(mu, cov, C.MC_PORTFOLIOS, rf_ann, C.RANDOM_SEED)
    w_ms = O.max_sharpe(mu, cov, rf_ann)
    w_mv = O.min_vol(mu, cov)
    w_ew = pd.Series(1 / len(names), index=names)
    front = O.frontier(mu, cov)
    pts = {}
    for k, w in {"Current (equal weight)": w_ew, "Max Sharpe": w_ms, "Min volatility": w_mv}.items():
        r, v, s = O.port_stats(w.to_numpy(), mu.to_numpy(), cov.to_numpy(), rf_ann)
        pts[k] = {"ret": r, "vol": v, "Sharpe": s, "largest": f"{w.idxmax()} {w.max():.0%}",
                  "n_holdings>1%": int((w > 0.01).sum())}
    mc_best = mc.loc[mc["sharpe"].idxmax()]
    pts["Best of 10,000 random"] = {"ret": mc_best.ret, "vol": mc_best.vol, "Sharpe": mc_best.sharpe,
                                    "largest": "", "n_holdings>1%": np.nan}
    to_md(pd.DataFrame(pts).T, "p2_insample_portfolios")
    res["insample"] = pts

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    sc = ax.scatter(mc.vol * 100, mc.ret * 100, c=mc.sharpe, cmap="Blues", s=4, alpha=0.6, linewidths=0,
                    label="10,000 random portfolios (uncapped)")
    fig.colorbar(sc, ax=ax, label="Sharpe ratio")
    ax.plot(front.vol * 100, front.ret * 100, color=INK2, linewidth=2, label="Efficient frontier (max 25% per holding)")
    marks = {"Current (equal weight)": ("o", SERIES[1]), "Max Sharpe": ("*", SERIES[7]), "Min volatility": ("D", SERIES[2])}
    for k, (mk, c) in marks.items():
        ax.scatter(pts[k]["vol"] * 100, pts[k]["ret"] * 100, marker=mk, s=380 if mk == "*" else 140, color=c,
                   edgecolor="white", linewidth=1.5, zorder=5, label=k)
    ax.set_xlabel("Expected volatility (annualised, %)")
    ax.set_ylabel("Expected return (annualised, %)")
    ax.set_title(f"Efficient frontier — {len(names)} holdings, {res['window'][0]} to {res['window'][1]}")
    ax.legend(loc="lower right")
    savefig(fig, "p2_frontier")

    wt = pd.DataFrame({"Current (EW)": w_ew, "Max Sharpe": w_ms, "Min vol": w_mv}).sort_values("Max Sharpe")
    to_md(wt.sort_values("Max Sharpe", ascending=False), "p2_weights", pct_cols=set(wt.columns))
    fig, ax = plt.subplots(figsize=(8, 6.5))
    y = np.arange(len(wt))
    h = 0.27
    for k, (col, c) in enumerate(zip(wt.columns, [SERIES[1], SERIES[7], SERIES[2]])):
        ax.barh(y + (k - 1) * h, wt[col] * 100, height=h - 0.03, color=c, label=col)
    ax.set_yticks(y, wt.index)
    ax.set_xlabel("Portfolio weight (%)")
    ax.set_title("Current vs optimised weights")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    savefig(fig, "p2_weights")

    # --- B. Out-of-sample rolling re-optimisation -------------------------------
    reb = backtest.rebalance_dates(rets.index, "ME")
    reb = reb[reb >= rets.index[0] + pd.DateOffset(years=C.OPT_LOOKBACK_YEARS)]
    tg = {"Max Sharpe (rolling)": {}, "Min vol (rolling)": {}, "Equal weight": {}}
    for d in reb:
        nm = universe(rets, d, C.OPT_LOOKBACK_YEARS)
        wd = rets.loc[d - pd.DateOffset(years=C.OPT_LOOKBACK_YEARS):d, nm].dropna()
        if len(nm) < 3 or len(wd) < 250:
            continue
        m_, S_ = O.estimate(wd)
        r_ = float(rf.loc[wd.index].mean() * C.TRADING_DAYS)
        try:
            tg["Max Sharpe (rolling)"][d] = O.max_sharpe(m_, S_, r_)
        except RuntimeError:
            tg["Max Sharpe (rolling)"][d] = pd.Series(1 / len(nm), index=nm)
        tg["Min vol (rolling)"][d] = O.min_vol(m_, S_)
        live = close.loc[d].dropna().index
        tg["Equal weight"][d] = pd.Series(1 / len(live), index=live)
    perf = {}
    turnover = {}
    for k, dct in tg.items():
        T = pd.DataFrame(dct).T.reindex(columns=C.TICKERS).fillna(0.0)
        bt = backtest.run(rets, T, rf=rf)
        perf[k] = bt["net"]
        turnover[k] = bt["turnover"].sum() / (len(bt) / C.TRADING_DAYS)
    perf["VOO (S&P 500)"] = rets[C.BENCHMARK]
    P = pd.DataFrame(perf).dropna()
    oos = M.summary_table(P, rf, bench=P["VOO (S&P 500)"])
    oos["Turnover (ann.)"] = pd.Series(turnover)
    cols = ["start", "years", "CAGR", "Volatility", "Sharpe", "Max Drawdown", "Beta", "Turnover (ann.)"]
    to_md(oos[cols], "p2_oos_backtest")
    res["oos"] = oos[cols].to_dict(orient="index")

    fig, ax = plt.subplots(figsize=(9, 4.2))
    for k, c in zip(P.columns, [SERIES[7], SERIES[2], SERIES[1], SERIES[0]]):
        g = (1 + P[k]).cumprod()
        ax.plot(g.index, g, color=c, label=k, linewidth=1.8)
    ax.set_title("Out-of-sample: monthly re-optimised portfolios (net of costs)")
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="upper left")
    savefig(fig, "p2_oos_growth")

    save_json(res, "p2")
    print("Phase 2 complete. In-sample:", {k: round(v["Sharpe"], 2) for k, v in pts.items()})
    print(oos[cols])


if __name__ == "__main__":
    main()
