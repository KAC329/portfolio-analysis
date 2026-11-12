"""Phase 3 — Signal research: feature ICs, decay, regimes, walk-forward models.

Usage:
    python p3_signal_research.py                 # all models, default settings
    python p3_signal_research.py --models xgb    # subset
    python p3_signal_research.py --tag exp42 --params '{"xgb": {"max_depth": 4}}'

Every run appends to results/metrics/scoreboard.jsonl so the improvement loop
(and the report) can track accuracy over time.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from common import C, INK2, MUTED, SERIES, load_all, save_json, savefig, to_md, plt
from pa.features import FEATURE_GROUPS, build_panel, eligible
from pa.metrics import log_returns
from pa.models import (WFConfig, daily_ic, feature_ic_table, log_scoreboard, score,
                       split_scores, walk_forward)

DEFAULT_MODELS = ["momentum", "ar", "ridge", "xgb", "lstm"]
RETRAIN = {"lstm": 126, "ar": 63}   # slower models refit less often


def build(close, volume, market, fred):
    panel = build_panel(close, volume, market, fred)
    return eligible(panel, close)


def feature_research(panel, market):
    ic_tab = feature_ic_table(panel)
    to_md(ic_tab, "p3_feature_ic", pct_cols=set(), digits=3)

    # decay chart for the 6 strongest features
    top = ic_tab.index[:6]
    lags = [c for c in ic_tab.columns if c.startswith("IC lag")]
    fig, ax = plt.subplots(figsize=(8, 4))
    x = [int(c.replace("IC lag", "")) * C.HORIZON for c in lags]
    for f, c in zip(top, SERIES):
        ax.plot(x, ic_tab.loc[f, lags].to_numpy(dtype=float) * 100, marker="o", markersize=5, color=c, label=f)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_xlabel("Days between signal and start of the 5-day return window")
    ax.set_ylabel("Mean rank IC (%)")
    ax.set_title("Signal decay — how fast predictive power fades")
    ax.legend(ncol=2, loc="upper right")
    savefig(fig, "p3_signal_decay")

    # regime split: high vs low VIX (median split, pre-holdout only)
    pre = panel[panel.index.get_level_values("date") < pd.Timestamp(C.HOLDOUT_START)]
    if pre["vix"].notna().any():
        vix_by_date = pre["vix"].groupby(level="date").first()
        hi = vix_by_date > vix_by_date.median()
        rows = {}
        for f in top:
            ic = daily_ic(pd.DataFrame({"pred": pre[f], "target_xs": pre["target_xs"]}))
            rows[f] = {"IC low VIX": ic[~hi.reindex(ic.index).fillna(False)].mean(),
                       "IC high VIX": ic[hi.reindex(ic.index).fillna(False)].mean()}
        to_md(pd.DataFrame(rows).T, "p3_regime_ic", pct_cols=set(), digits=3)
    return ic_tab


def run_models(panel, rets_log, models, params, tag):
    results, oos_all = {}, {}
    for m in models:
        cfg = WFConfig(m, params.get(m, {}), retrain_every=RETRAIN.get(m, C.RETRAIN_EVERY))
        print(f"walk-forward: {m} {cfg.params}")
        oos = walk_forward(panel, cfg, raw_returns=rets_log, verbose=True)
        oos.to_parquet(C.METRICS / f"oos_{m}.parquet")
        sc = split_scores(oos)
        results[m] = sc
        oos_all[m] = oos
        log_scoreboard({"tag": tag, "model": m, "params": cfg.params, "horizon": C.HORIZON, **{
            f"{k}_{s}": v for s, d in sc.items() for k, v in d.items()}})
    # ensemble: average of per-date ranks of the learned models
    learned = [m for m in ("ridge", "xgb", "lstm") if m in oos_all]
    if len(learned) >= 2:
        ranks = pd.concat({m: oos_all[m]["pred"].groupby(level="date").rank(pct=True) for m in learned}, axis=1)
        ens = ranks.mean(axis=1).to_frame("pred").join(oos_all[learned[0]][["target", "target_xs"]])
        ens.to_parquet(C.METRICS / "oos_ensemble.parquet")
        results["ensemble"] = split_scores(ens)
        oos_all["ensemble"] = ens
        log_scoreboard({"tag": tag, "model": "ensemble", "params": {"members": learned}, "horizon": C.HORIZON,
                        **{f"{k}_{s}": v for s, d in results["ensemble"].items() for k, v in d.items()}})
    return results, oos_all


def report_models(results, oos_all):
    rows = []
    for m, sc in results.items():
        for split in ("validation", "holdout"):
            d = sc.get(split, {})
            rows.append({"model": m, "split": split, **d})
    tab = pd.DataFrame(rows).set_index(["model", "split"])
    cols = ["n_dates", "mean_IC", "IC_tstat", "ICIR_ann", "IC_pos_share", "hit_rate", "top_minus_bottom_ann", "tmb_sharpe"]
    to_md(tab[cols], "p3_model_scores", pct_cols={"IC_pos_share", "hit_rate", "top_minus_bottom_ann"}, digits=3)

    # rolling 126-day IC for each model (validation + holdout, holdout shaded)
    fig, ax = plt.subplots(figsize=(9, 4))
    for (m, oos), c in zip(oos_all.items(), SERIES):
        ic = daily_ic(oos).rolling(126, min_periods=60).mean()
        ax.plot(ic.index, ic * 100, color=c, label=m, linewidth=1.6)
    last = max(o.index.get_level_values("date").max() for o in oos_all.values())
    ax.axvspan(pd.Timestamp(C.HOLDOUT_START), last, color="#f0efec", zorder=0, label="Hold-out period")
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_ylabel("Rolling 6-month mean IC (%)")
    ax.set_title("Out-of-sample information coefficient by model")
    ax.legend(ncol=3, loc="upper left")
    savefig(fig, "p3_rolling_ic")
    return tab


def xgb_importance(panel, params):
    """Fit once on all pre-holdout data to show what the model relies on."""
    from pa.models import XGBModel, prep
    pre = panel[panel.index.get_level_values("date") < pd.Timestamp(C.HOLDOUT_START)].dropna(subset=["target_xs"])
    X = prep(pre)
    m = XGBModel(**params.get("xgb", {})).fit(X, pre["target_xs"].to_numpy())
    imp = pd.Series(m.m.get_booster().get_score(importance_type="gain")).reindex(X.columns).fillna(0)
    imp = (imp / imp.sum()).sort_values()
    group = {f: g for g, fs in FEATURE_GROUPS.items() for f in fs}
    fig, ax = plt.subplots(figsize=(7, 6))
    gcol = {g: SERIES[i] for i, g in enumerate(FEATURE_GROUPS)}
    ax.barh(imp.index, imp * 100, color=[gcol[group[f]] for f in imp.index], height=0.65)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=c, label=g) for g, c in gcol.items()], loc="lower right")
    ax.set_xlabel("Share of total split gain (%)")
    ax.set_title("XGBoost feature importance (pre-holdout fit)")
    ax.grid(axis="y", visible=False)
    savefig(fig, "p3_xgb_importance")
    return imp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    ap.add_argument("--params", default="{}")
    ap.add_argument("--tag", default="baseline")
    ap.add_argument("--skip-research", action="store_true")
    a = ap.parse_args()
    params = json.loads(a.params)

    close, volume, market, fred, rets, rf = load_all()
    panel = build(close, volume, market, fred)
    print(f"panel: {len(panel):,} rows, {panel.index.get_level_values('ticker').nunique()} assets, "
          f"{panel.index.get_level_values('date').min().date()} → {panel.index.get_level_values('date').max().date()}")
    res = {"panel_rows": len(panel)}
    if not a.skip_research:
        ic_tab = feature_research(panel, market)
        res["top_features"] = ic_tab.head(8)[["IC lag0", "t-stat"]].to_dict(orient="index")
    results, oos_all = run_models(panel, log_returns(close), a.models, params, a.tag)
    report_models(results, oos_all)
    if "xgb" in a.models:
        res["xgb_importance_top"] = xgb_importance(panel, params).sort_values(ascending=False).head(8).to_dict()
    res["scores"] = results
    # the zero-parameter baseline competes too: a model must earn its complexity
    best = max(results,
               key=lambda m: results[m]["validation"].get("ICIR_ann", -np.inf))
    res["best_model_by_validation"] = best
    save_json(res, "p3" if a.tag == "baseline" else f"p3_{a.tag}")
    print("best (validation ICIR):", best)
    for m, s in results.items():
        v, h = s["validation"], s["holdout"]
        print(f"  {m:9s} val IC {v.get('mean_IC', np.nan):+.4f} (t {v.get('IC_tstat', np.nan):+.2f}) hit {v.get('hit_rate', np.nan):.3f} | "
              f"hold IC {h.get('mean_IC', np.nan):+.4f} hit {h.get('hit_rate', np.nan):.3f}")


if __name__ == "__main__":
    main()
