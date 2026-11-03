"""Phase 3 feature library.

Every feature at date ``t`` uses only data observed at or before the close of
``t``. The target is the *forward* log return from ``t`` to ``t+HORIZON``.
Macro series from FRED are lagged one extra day to respect publication timing.

Output is a long "panel": one row per (date, ticker).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

FEATURE_GROUPS = {
    "momentum": ["r_1", "r_5", "r_21", "mom_63", "mom_12_1", "ma_gap_50_200", "dist_52w_high"],
    "reversal/oscillator": ["rsi_14"],
    "volatility": ["vol_21", "vol_63", "vol_ratio", "skew_63", "idio_vol_63"],
    "market-relative": ["beta_63", "rel_r_21"],
    "volume": ["volume_z", "dollar_vol_trend"],
    "cross-sectional rank": ["cs_rank_r_21", "cs_rank_mom_12_1", "cs_rank_vol_21"],
    "macro": ["mkt_r_21", "vix", "vix_chg_5", "term_spread", "credit_spread", "ust10y_chg_21"],
}
FEATURES = [f for g in FEATURE_GROUPS.values() for f in g]


def _rsi(close: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)


def build_panel(close: pd.DataFrame, volume: pd.DataFrame, market: pd.DataFrame | None,
                fred: pd.DataFrame | None, horizon: int = C.HORIZON) -> pd.DataFrame:
    lr = np.log(close).diff()
    bench = lr[C.BENCHMARK]
    f: dict[str, pd.DataFrame] = {}

    f["r_1"] = lr
    f["r_5"] = lr.rolling(5).sum()
    f["r_21"] = lr.rolling(21).sum()
    f["mom_63"] = lr.rolling(63).sum()
    f["mom_12_1"] = lr.rolling(252).sum() - f["r_21"]
    f["ma_gap_50_200"] = close.rolling(50).mean() / close.rolling(200).mean() - 1
    f["dist_52w_high"] = close / close.rolling(252, min_periods=126).max() - 1
    f["rsi_14"] = _rsi(close)
    f["vol_21"] = lr.rolling(21).std() * np.sqrt(C.TRADING_DAYS)
    f["vol_63"] = lr.rolling(63).std() * np.sqrt(C.TRADING_DAYS)
    f["vol_ratio"] = f["vol_21"] / f["vol_63"]
    f["skew_63"] = lr.rolling(63).skew()

    cov = lr.rolling(63).cov(bench)
    var = bench.rolling(63).var()
    f["beta_63"] = cov.div(var, axis=0)
    resid = lr - f["beta_63"].mul(bench, axis=0)
    f["idio_vol_63"] = resid.rolling(63).std() * np.sqrt(C.TRADING_DAYS)
    f["rel_r_21"] = f["r_21"].sub(bench.rolling(21).sum(), axis=0)

    lv = np.log(volume.replace(0, np.nan))
    f["volume_z"] = (lv - lv.rolling(63).mean()) / lv.rolling(63).std()
    dv = (close * volume).replace(0, np.nan)
    f["dollar_vol_trend"] = np.log(dv.rolling(21).mean() / dv.rolling(126).mean())

    for k in ["r_21", "mom_12_1", "vol_21"]:
        f[f"cs_rank_{k}"] = f[k].rank(axis=1, pct=True)

    # target: forward H-day log return, aligned to the decision date
    fwd = lr.rolling(horizon).sum().shift(-horizon)

    panel = pd.concat({k: v.stack(future_stack=True) for k, v in f.items()}, axis=1)
    panel["target"] = fwd.stack(future_stack=True)
    panel.index.names = ["date", "ticker"]

    # macro / market context (same value for every ticker on a date)
    macro = pd.DataFrame(index=close.index)
    macro["mkt_r_21"] = bench.rolling(21).sum()
    if market is not None and not market.empty:
        m = market.reindex(close.index).ffill()
        macro["vix"] = m["vix"]
        macro["vix_chg_5"] = np.log(m["vix"]).diff(5)
        macro["ust10y_chg_21"] = m["ust10y"].diff(21)
    if fred is not None and not fred.empty:
        fr = fred.reindex(close.index.union(fred.index)).ffill().reindex(close.index).shift(1)
        for col in ["term_spread", "credit_spread"]:
            if col in fr:
                macro[col] = fr[col]
    for col in FEATURE_GROUPS["macro"]:
        if col not in macro:
            macro[col] = np.nan
    panel = panel.join(macro, on="date")

    # cross-sectionally demeaned target: "did this asset beat the average holding?"
    panel["target_xs"] = panel["target"] - panel.groupby(level="date")["target"].transform("mean")
    return panel


def eligible(panel: pd.DataFrame, close: pd.DataFrame, min_history: int = C.MIN_ASSET_HISTORY) -> pd.DataFrame:
    """Keep rows where the asset has traded ``min_history`` days and core features exist."""
    age = close.notna().cumsum().stack(future_stack=True)
    age.index.names = ["date", "ticker"]
    ok = age.reindex(panel.index) >= min_history
    core = ["r_21", "vol_21", "mom_63"]
    return panel[ok & panel[core].notna().all(axis=1)]
