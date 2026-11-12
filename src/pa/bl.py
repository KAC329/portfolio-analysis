"""Phase 5: Black-Litterman (1992) with model-generated views.

Plain-English version
---------------------
1. *Prior*: assume the market is in equilibrium; back out the returns that
   would make the reference weights optimal: π = δ Σ w_ref.
2. *Views*: our models say asset i will beat the average by some amount.
   Convert the forecast z-score into an expected excess return with Grinold's
   rule α_i = IC × σ_i × z_i (the forecast is only worth its skill, the IC).
3. *Blend*: the posterior is a precision-weighted average of prior and views.
   Ω (view uncertainty) controls how far we move from the prior.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from . import config as C


def implied_returns(cov: pd.DataFrame, w_ref: pd.Series, delta: float = C.RISK_AVERSION) -> pd.Series:
    return delta * cov @ w_ref.reindex(cov.index).fillna(0)


def grinold_alpha(pred: pd.Series, cov: pd.DataFrame, ic: float) -> pd.Series:
    """α_i = IC · σ_i · z_i (annualised), z = cross-sectional z-score of forecast."""
    z = (pred - pred.mean()) / (pred.std() or 1.0)
    sigma = np.sqrt(np.diag(cov.loc[pred.index, pred.index]))
    return pd.Series(ic * sigma * z.to_numpy(), index=pred.index)


def posterior(pi: pd.Series, cov: pd.DataFrame, Q: pd.Series, omega_scale: float = 1.0,
              tau: float = C.TAU) -> tuple[pd.Series, pd.DataFrame]:
    """Absolute views on each asset in Q (P = identity on those assets)."""
    names = cov.index
    P = np.zeros((len(Q), len(names)))
    for k, t in enumerate(Q.index):
        P[k, names.get_loc(t)] = 1.0
    S = cov.to_numpy()
    tS = tau * S
    Omega = np.diag(np.diag(P @ tS @ P.T)) * omega_scale
    A = np.linalg.inv(tS) + P.T @ np.linalg.inv(Omega) @ P
    b = np.linalg.inv(tS) @ pi.to_numpy() + P.T @ np.linalg.inv(Omega) @ Q.to_numpy()
    M = np.linalg.inv(A)
    mu = M @ b
    cov_post = S + M
    return pd.Series(mu, index=names), pd.DataFrame(cov_post, index=names, columns=names)


def optimal_weights(mu: pd.Series, cov: pd.DataFrame, delta: float = C.RISK_AVERSION,
                    cap: float = C.MAX_WEIGHT) -> pd.Series:
    """Maximise w'μ − (δ/2) w'Σw, long-only, fully invested, capped."""
    m, S = mu.to_numpy(), cov.to_numpy()
    n = len(m)
    cap = max(cap, 1 / n)
    res = minimize(lambda w: -(w @ m - delta / 2 * w @ S @ w), np.full(n, 1 / n),
                   method="SLSQP", bounds=[(0, cap)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
                   options={"maxiter": 500, "ftol": 1e-12})
    w = np.clip(res.x, 0, None)
    return pd.Series(w / w.sum(), index=mu.index)
