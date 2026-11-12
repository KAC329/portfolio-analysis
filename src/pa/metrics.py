"""Performance and risk statistics.

Conventions (stated once so every table in the report is comparable):
* Daily simple returns in, annualised figures out, 252 trading days/year.
* Annual return is the *geometric* (compound) growth rate (CAGR).
* Sharpe and Sortino use excess returns over the 3-month T-bill.
* Max drawdown is measured on the compounded wealth curve.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .config import TRADING_DAYS as N


def log_returns(close: pd.DataFrame) -> pd.DataFrame:
    return np.log(close).diff()


def simple_returns(close: pd.DataFrame) -> pd.DataFrame:
    # fill_method=None: never manufacture a 0% return across a missing price
    return close.pct_change(fill_method=None)


def cagr(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) == 0:
        return np.nan
    return float((1 + r).prod() ** (N / len(r)) - 1)


def ann_vol(r: pd.Series) -> float:
    return float(r.dropna().std(ddof=1) * np.sqrt(N))


def sharpe(r: pd.Series, rf: pd.Series | float = 0.0) -> float:
    ex = (r - rf).dropna()
    sd = ex.std(ddof=1)
    return float(ex.mean() / sd * np.sqrt(N)) if sd > 0 else np.nan


def sortino(r: pd.Series, rf: pd.Series | float = 0.0) -> float:
    ex = (r - rf).dropna()
    downside = np.sqrt((np.minimum(ex, 0) ** 2).mean())
    return float(ex.mean() / downside * np.sqrt(N)) if downside > 0 else np.nan


def drawdown(r: pd.Series) -> pd.Series:
    w = (1 + r.fillna(0)).cumprod()
    return w / w.cummax() - 1


def max_drawdown(r: pd.Series) -> float:
    return float(drawdown(r.dropna()).min())


def calmar(r: pd.Series) -> float:
    mdd = max_drawdown(r)
    return float(cagr(r) / abs(mdd)) if mdd < 0 else np.nan


def var_cvar(r: pd.Series, level: float = 0.95) -> tuple[float, float]:
    """Historical 1-day Value-at-Risk and Conditional VaR (as positive losses)."""
    r = r.dropna()
    q = r.quantile(1 - level)
    return float(-q), float(-r[r <= q].mean())


def beta_alpha(r: pd.Series, bench: pd.Series, rf: pd.Series | float = 0.0) -> tuple[float, float]:
    """CAPM beta and annualised Jensen's alpha."""
    df = pd.concat([r - rf, bench - rf], axis=1).dropna()
    if len(df) < 20:
        return np.nan, np.nan
    b = np.cov(df.iloc[:, 0], df.iloc[:, 1])[0, 1] / df.iloc[:, 1].var()
    a = (df.iloc[:, 0].mean() - b * df.iloc[:, 1].mean()) * N
    return float(b), float(a)


def information_ratio(r: pd.Series, bench: pd.Series) -> tuple[float, float]:
    active = (r - bench).dropna()
    te = active.std(ddof=1) * np.sqrt(N)
    return float(te), float(active.mean() * N / te) if te > 0 else np.nan


def summary(r: pd.Series, rf: pd.Series | float = 0.0, bench: pd.Series | None = None) -> dict:
    r = r.dropna()
    out = {
        "start": r.index[0].date() if len(r) else None,
        "end": r.index[-1].date() if len(r) else None,
        "years": round(len(r) / N, 2),
        "CAGR": cagr(r),
        "Volatility": ann_vol(r),
        "Sharpe": sharpe(r, rf),
        "Sortino": sortino(r, rf),
        "Max Drawdown": max_drawdown(r),
        "Calmar": calmar(r),
        "VaR 95% (1d)": var_cvar(r)[0],
        "CVaR 95% (1d)": var_cvar(r)[1],
        "Skew": float(stats.skew(r)) if len(r) > 2 else np.nan,
        "Excess Kurtosis": float(stats.kurtosis(r)) if len(r) > 3 else np.nan,
    }
    if bench is not None:
        b, a = beta_alpha(r, bench, rf)
        te, ir = information_ratio(r, bench)
        out.update({"Beta": b, "Alpha (ann.)": a, "Tracking Error": te, "Info Ratio": ir})
    return out


def summary_table(returns: pd.DataFrame, rf=0.0, bench: pd.Series | None = None) -> pd.DataFrame:
    return pd.DataFrame({c: summary(returns[c], rf, bench) for c in returns.columns}).T


def adf_table(series: pd.DataFrame) -> pd.DataFrame:
    """Augmented Dickey-Fuller test per column (H0: unit root / non-stationary)."""
    from statsmodels.tsa.stattools import adfuller

    rows = {}
    for c in series.columns:
        s = series[c].dropna()
        if len(s) < 50:
            continue
        stat, p, lags, nobs, crit, _ = adfuller(s, autolag="AIC", result_object=False)
        rows[c] = {"ADF stat": stat, "p-value": p, "lags": lags, "n": nobs,
                   "crit 5%": crit["5%"], "stationary @5%": p < 0.05}
    return pd.DataFrame(rows).T
