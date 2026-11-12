"""Phase 1 — Buy & hold portfolio analysis.

Outputs (results/): data-quality table, per-asset risk/return table, portfolio
vs benchmark table, growth/drawdown/correlation/ACF charts, ADF & Ljung-Box tests.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.stats.diagnostic import acorr_ljungbox

from common import C, GRID, INK2, MUTED, SERIES, DIVERGING, load_all, save_json, savefig, to_md, plt
from pa import backtest, metrics as M
from pa.data import quality_report


def main():
    close, volume, market, fred, rets, rf = load_all()
    res = {}

    # 1. Data quality --------------------------------------------------------
    from pa.data import load_prices
    raw_close, raw_vol = load_prices(raw=True)
    q = quality_report(raw_close, raw_vol)
    q["treatment"] = ""
    for t, d in C.TRADING_START.items():
        q.loc[t, "treatment"] = f"history starts {d} (pre-merger SPAC removed)"
    for t, why in C.EXCLUDE.items():
        q.loc[t, "treatment"] = f"EXCLUDED: {why}"
    to_md(q, "p1_data_quality", pct_cols=set())
    res["data_quality_flags"] = q[q["flag"] != ""]["flag"].to_dict()

    # 2. Per-asset statistics over each asset's own history --------------------
    tab = M.summary_table(rets, rf, bench=rets[C.BENCHMARK])
    group = {t: g for g, ts in C.GROUPS.items() for t in ts}
    tab.insert(0, "group", tab.index.map(group))
    cols = ["group", "start", "years", "CAGR", "Volatility", "Sharpe", "Sortino", "Max Drawdown",
            "Beta", "CVaR 95% (1d)"]
    to_md(tab[cols].sort_values(["group", "Sharpe"], ascending=[True, False]), "p1_asset_stats")

    # 3. Common 3-year window (apples-to-apples) -------------------------------
    end = rets.index[-1]
    w3 = rets.loc[end - pd.DateOffset(years=3):]
    full3 = w3.columns[w3.notna().mean() > 0.98]
    tab3 = M.summary_table(w3[full3], rf, bench=w3[C.BENCHMARK])
    to_md(tab3[["CAGR", "Volatility", "Sharpe", "Max Drawdown", "Beta"]].sort_values("Sharpe", ascending=False),
          "p1_asset_stats_3y")
    res["assets_full_3y"] = list(full3)

    # 4. Portfolio: equal weight, monthly rebalance, new listings join next month
    reb = backtest.rebalance_dates(close.index, "ME")
    tgt = backtest.equal_weight_targets(close, reb)
    port = backtest.run(rets, tgt, rf=rf)["net"]
    start = max(port.index[0], pd.Timestamp("2016-01-01"))
    perf = pd.DataFrame({"Portfolio (EW)": port, "VOO (S&P 500)": rets[C.BENCHMARK]}).loc[start:]
    ptab = M.summary_table(perf, rf, bench=perf["VOO (S&P 500)"])
    to_md(ptab.drop(columns=["start", "end"]), "p1_portfolio_vs_benchmark")
    res["portfolio_vs_benchmark"] = ptab.to_dict(orient="index")
    # same window for last 3y
    p3 = perf.loc[end - pd.DateOffset(years=3):]
    to_md(M.summary_table(p3, rf, bench=p3["VOO (S&P 500)"]).drop(columns=["start", "end"]),
          "p1_portfolio_vs_benchmark_3y")
    perf.to_csv(C.TAB / "p1_portfolio_daily_returns.csv")

    # Growth of $10,000 (log scale) + drawdown — two charts, never a dual axis
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for k, c in zip(perf.columns, SERIES):
        g = 10_000 * (1 + perf[k].fillna(0)).cumprod()
        ax.plot(g.index, g, color=c, label=k)
        ax.annotate(f"${g.iloc[-1]:,.0f}", (g.index[-1], g.iloc[-1]), xytext=(4, 0),
                    textcoords="offset points", fontsize=8.5, color=INK2, va="center")
    ax.set_yscale("log")
    from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
    ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_title("Growth of $10,000 — equal-weight portfolio vs S&P 500")
    ax.set_ylabel("Portfolio value (log scale, USD)")
    ax.legend(loc="upper left")
    savefig(fig, "p1_growth")

    fig, ax = plt.subplots(figsize=(9, 3.2))
    for k, c in zip(perf.columns, SERIES):
        dd = M.drawdown(perf[k])
        ax.plot(dd.index, dd * 100, color=c, label=k, linewidth=1.5)
    ax.set_title("Drawdown from previous peak")
    ax.set_ylabel("Drawdown (%)")
    ax.legend(loc="lower left")
    savefig(fig, "p1_drawdown")

    # Contribution: which holdings drove the result (3y window, EW)
    contrib = (w3[full3].mean() * C.TRADING_DAYS / len(full3)).sort_values()
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.barh(contrib.index, contrib * 100, color=[SERIES[0] if v >= 0 else SERIES[7] for v in contrib], height=0.6)
    ax.axvline(0, color=MUTED, linewidth=0.8)
    ax.set_title("Return contribution by holding (last 3y, EW)")
    ax.set_xlabel("Contribution to annual arithmetic return (pp)")
    ax.grid(axis="y", visible=False)
    savefig(fig, "p1_contribution")

    # 5. Correlation & diversification (3y window) ------------------------------
    corr = w3[full3].corr()
    order = corr.mean().sort_values(ascending=False).index
    corr = corr.loc[order, order]
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("div", DIVERGING)
    fig, ax = plt.subplots(figsize=(8.5, 7))
    im = ax.imshow(corr, cmap=cmap, vmin=-1, vmax=1)
    ax.set_xticks(range(len(order)), order, rotation=90, fontsize=8)
    ax.set_yticks(range(len(order)), order, fontsize=8)
    ax.grid(False)
    for i in range(len(order)):
        for j in range(len(order)):
            ax.text(j, i, f"{corr.iloc[i, j]:.1f}", ha="center", va="center", fontsize=6,
                    color="white" if abs(corr.iloc[i, j]) > 0.6 else INK2)
    fig.colorbar(im, ax=ax, shrink=0.75, label="Correlation of daily returns")
    ax.set_title("Correlation matrix (last 3 years)")
    savefig(fig, "p1_correlation")

    vols = w3[full3].std() * np.sqrt(C.TRADING_DAYS)
    w = pd.Series(1 / len(full3), index=full3)
    cov = w3[full3].cov() * C.TRADING_DAYS
    port_vol = float(np.sqrt(w @ cov @ w))
    off = corr.where(~np.eye(len(corr), dtype=bool)).stack()
    res["diversification"] = {
        "avg_pairwise_corr": float(off.mean()),
        "diversification_ratio": float((w @ vols) / port_vol),
        "effective_n_bets": float(((w @ vols) / port_vol) ** 2),
        "most_correlated_pair": [list(off.idxmax()), float(off.max())],
        "least_correlated_pair": [list(off.idxmin()), float(off.min())],
    }

    # 6. Stationarity (ADF) on log prices vs log returns ------------------------
    lp, lr = np.log(close), M.log_returns(close)
    adf_p = M.adf_table(lp)[["ADF stat", "p-value", "stationary @5%"]].add_prefix("price ")
    adf_r = M.adf_table(lr)[["ADF stat", "p-value", "stationary @5%"]].add_prefix("return ")
    adf = adf_p.join(adf_r)
    to_md(adf, "p1_adf", pct_cols=set(), digits=3)
    res["adf"] = {"prices_stationary": int(adf["price stationary @5%"].sum()),
                  "returns_stationary": int(adf["return stationary @5%"].sum()), "n": len(adf)}

    # 7. ACF/PACF (Shumway & Stoffer ch. 1-3): returns vs squared returns ------
    r = lr[C.BENCHMARK].dropna()
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.4))
    plot_acf(r, lags=30, ax=axes[0], zero=False, color=SERIES[0], vlines_kwargs={"colors": SERIES[0]})
    axes[0].set_title("ACF of VOO daily log returns")
    plot_pacf(r, lags=30, ax=axes[1], zero=False, method="ywm", color=SERIES[0], vlines_kwargs={"colors": SERIES[0]})
    axes[1].set_title("PACF of VOO daily log returns")
    plot_acf(r ** 2, lags=30, ax=axes[2], zero=False, color=SERIES[1], vlines_kwargs={"colors": SERIES[1]})
    axes[2].set_title("ACF of squared returns (volatility)")
    for a in axes:
        a.set_xlabel("Lag (trading days)")
        from matplotlib.collections import PolyCollection
        for coll in a.collections:
            if isinstance(coll, PolyCollection):          # the 95% confidence band
                coll.set_facecolor("#cde2fb")
                coll.set_alpha(0.8)
        a.set_ylim(-0.3, 0.6)
    savefig(fig, "p1_acf_pacf", source="Shaded band = 95% confidence interval; bars outside it are statistically significant. Source: Yahoo Finance; author calculations.")

    lb = []
    for t in full3:
        s = lr[t].dropna()
        lb.append({"ticker": t,
                   "LB p (returns, 10 lags)": float(acorr_ljungbox(s, lags=[10])["lb_pvalue"].iloc[0]),
                   "LB p (squared, 10 lags)": float(acorr_ljungbox(s ** 2, lags=[10])["lb_pvalue"].iloc[0])})
    lb = pd.DataFrame(lb).set_index("ticker")
    to_md(lb, "p1_ljung_box", pct_cols=set(), digits=4)
    res["ljung_box"] = {"returns_autocorrelated": int((lb.iloc[:, 0] < 0.05).sum()),
                        "vol_clustering": int((lb.iloc[:, 1] < 0.05).sum()), "n": len(lb)}

    save_json(res, "p1")
    print("Phase 1 complete:", {k: v for k, v in res.items() if k != "portfolio_vs_benchmark"})


if __name__ == "__main__":
    main()
