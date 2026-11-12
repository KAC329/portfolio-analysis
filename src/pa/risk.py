"""Phase 4: turn forecasts into position sizes, with risk controls.

Pipeline per rebalance date t (all inputs known at t's close):
1. ``signal_tilt`` or ``kelly`` → raw long-only weights from model forecasts.
2. ``vol_target`` → scale total exposure so *predicted* portfolio volatility
   equals ``TARGET_VOL`` (never above ``MAX_LEVERAGE``).
3. Drawdown stop is applied inside the backtest engine (``backtest.run``).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def ewma_cov(returns: pd.DataFrame, t: pd.Timestamp, halflife: int = 42, window: int = 252) -> pd.DataFrame:
    """Exponentially weighted covariance using data up to and including ``t``."""
    r = returns.loc[:t].iloc[-window:]
    r = r.loc[:, r.notna().sum() > 60].fillna(0.0)
    w = 0.5 ** (np.arange(len(r))[::-1] / halflife)
    w /= w.sum()
    x = r - (w[:, None] * r.to_numpy()).sum(0)
    cov = (x.to_numpy() * w[:, None]).T @ x.to_numpy() * C.TRADING_DAYS
    return pd.DataFrame(cov, index=r.columns, columns=r.columns)


def _cap(w: pd.Series, cap: float) -> pd.Series:
    """Iteratively cap weights and redistribute the excess pro-rata."""
    w = w.clip(lower=0)
    total = w.sum()
    if total <= 0:
        return w
    w = w / total * min(total, 1.0)
    budget = w.sum()
    for _ in range(50):
        over = w > cap
        if not over.any():
            break
        excess = (w[over] - cap).sum()
        w[over] = cap
        free = ~over & (w > 0)
        if not free.any():
            break
        w[free] += excess * w[free] / w[free].sum()
    return w * budget / w.sum() if w.sum() > 0 else w


def signal_tilt(pred: pd.Series, strength: float = 0.5, cap: float = C.MAX_WEIGHT) -> pd.Series:
    """Equal weight tilted by the cross-sectional z-score of the forecast.

    w_i ∝ max(0, 1 + strength · z_i). strength=0 recovers equal weight, so the
    signal's contribution is easy to isolate.
    """
    z = (pred - pred.mean()) / (pred.std() or 1.0)
    raw = (1 + strength * z.clip(-3, 3)).clip(lower=0)
    return _cap(raw / raw.sum(), cap)


def kelly(mu_ann: pd.Series, cov: pd.DataFrame, fraction: float = C.KELLY_FRACTION,
          cap: float = C.MAX_WEIGHT) -> pd.Series:
    """Fractional multivariate Kelly, long-only and capped.

    Full Kelly f* = Σ⁻¹ μ maximises long-run log growth *if μ and Σ are known*.
    They are not, so practitioners use a fraction (half-Kelly gives ~75% of the
    growth with ~50% of the volatility).
    """
    names = mu_ann.index.intersection(cov.index)
    S = cov.loc[names, names].to_numpy() + np.eye(len(names)) * 1e-4
    f = np.linalg.solve(S, mu_ann.loc[names].to_numpy()) * fraction
    w = pd.Series(f, index=names).clip(lower=0)
    if w.sum() > C.MAX_LEVERAGE:
        w *= C.MAX_LEVERAGE / w.sum()
    return _cap(w, cap)


def vol_target(w: pd.Series, cov: pd.DataFrame, target: float = C.TARGET_VOL,
               max_lev: float = C.MAX_LEVERAGE) -> pd.Series:
    names = w.index.intersection(cov.index)
    w = w.loc[names]
    vol = float(np.sqrt(w @ cov.loc[names, names] @ w))
    if vol <= 0:
        return w
    scale = min(target / vol, max_lev / max(w.sum(), 1e-12))
    return w * scale


def kelly_inputs(pred_xs: pd.Series, returns: pd.DataFrame, t: pd.Timestamp, rf_ann: float) -> pd.Series:
    """Absolute annualised excess-return forecast from a relative (xs) forecast.

    μ_i = (expected average-holding return over the next H days) + pred_xs_i,
    where the first term is the trailing 1-year mean of the equal-weight basket,
    shrunk 50% toward zero (a deliberately humble market forecast).
    """
    hist = returns.loc[:t].iloc[-252:].mean(axis=1).mean() * C.TRADING_DAYS
    mkt = 0.5 * hist
    return mkt - rf_ann + pred_xs * (C.TRADING_DAYS / C.HORIZON)
