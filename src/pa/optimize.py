"""Mean-variance optimisation (Markowitz 1952) with practical safeguards.

Safeguards vs. the textbook version:
* Covariance is shrunk toward a structured target (Ledoit-Wolf 2004), which
  makes the inverse far more stable when assets >> years of data.
* Weights are long-only and capped (``MAX_WEIGHT``) so the optimiser cannot
  put the whole portfolio in last year's winner.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

from .config import MAX_WEIGHT, TRADING_DAYS as N


def estimate(returns: pd.DataFrame, shrink: bool = True) -> tuple[pd.Series, pd.DataFrame]:
    """Annualised expected returns (arithmetic mean) and covariance."""
    r = returns.dropna()
    mu = r.mean() * N
    if shrink:
        cov = LedoitWolf().fit(r.to_numpy()).covariance_ * N
        cov = pd.DataFrame(cov, index=r.columns, columns=r.columns)
    else:
        cov = r.cov() * N
    return mu, cov


def port_stats(w, mu, cov, rf=0.0):
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ cov @ w))
    return ret, vol, (ret - rf) / vol if vol > 0 else np.nan


def monte_carlo(mu, cov, n: int, rf=0.0, seed: int = 42) -> pd.DataFrame:
    """Random long-only portfolios drawn uniformly from the simplex (Dirichlet(1))."""
    rng = np.random.default_rng(seed)
    W = rng.dirichlet(np.ones(len(mu)), size=n)
    rets = W @ mu.to_numpy()
    vols = np.sqrt(np.einsum("ij,jk,ik->i", W, cov.to_numpy(), W))
    return pd.DataFrame({"ret": rets, "vol": vols, "sharpe": (rets - rf) / vols})


def _solve(objective, n, bounds, extra_cons=()):
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}, *extra_cons]
    w0 = np.full(n, 1 / n)
    res = minimize(objective, w0, method="SLSQP", bounds=bounds, constraints=cons,
                   options={"maxiter": 1000, "ftol": 1e-12})
    if not res.success:
        raise RuntimeError(res.message)
    w = np.clip(res.x, 0, None)
    return w / w.sum()


def max_sharpe(mu, cov, rf=0.0, cap: float = MAX_WEIGHT) -> pd.Series:
    """Tangency portfolio. If no holding is expected to beat cash (the Sharpe
    ratio is negative everywhere) or the solver fails, fall back to min-vol."""
    m, S = mu.to_numpy(), cov.to_numpy()
    if (m - rf).max() <= 0:
        return min_vol(mu, cov, cap)
    cap = max(cap, 1 / len(m))
    try:
        w = _solve(lambda w: -(w @ m - rf) / np.sqrt(w @ S @ w), len(m), [(0, cap)] * len(m))
    except RuntimeError:
        return min_vol(mu, cov, cap)
    return pd.Series(w, index=mu.index)


def min_vol(mu, cov, cap: float = MAX_WEIGHT) -> pd.Series:
    S = cov.to_numpy()
    cap = max(cap, 1 / len(mu))
    w = _solve(lambda w: w @ S @ w, len(mu), [(0, cap)] * len(mu))
    return pd.Series(w, index=mu.index)


def frontier(mu, cov, points: int = 40, cap: float = MAX_WEIGHT) -> pd.DataFrame:
    m, S = mu.to_numpy(), cov.to_numpy()
    cap = max(cap, 1 / len(m))
    wmin = min_vol(mu, cov, cap).to_numpy()
    lo = float(wmin @ m)
    # highest return achievable under the cap: fill best assets up to the cap
    order = np.argsort(-m)
    w_hi, left = np.zeros_like(m), 1.0
    for j in order:
        w_hi[j] = min(cap, left)
        left -= w_hi[j]
        if left <= 0:
            break
    hi = float(w_hi @ m)
    rows = []
    for target in np.linspace(lo, hi * 0.999, points):
        try:
            w = _solve(lambda w: w @ S @ w, len(m), [(0, cap)] * len(m),
                       ({"type": "eq", "fun": lambda w, t=target: w @ m - t},))
            rows.append({"ret": target, "vol": float(np.sqrt(w @ S @ w))})
        except RuntimeError:
            continue
    return pd.DataFrame(rows)
