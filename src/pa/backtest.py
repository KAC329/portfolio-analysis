"""A small, explicit portfolio backtest engine.

Timing convention (the most common source of look-ahead bias, so spelled out):
target weights dated ``t`` are computed from information available at the
close of day ``t`` and are traded at that close. They therefore earn the
returns of day ``t+1`` onward. Between rebalances weights drift with prices.
Any weight not allocated to assets sits in cash earning the risk-free rate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def cost_vector(columns) -> pd.Series:
    def bps(t):
        if t in C.ETFS:
            return C.COST_BPS_ETF
        if t in C.SMALL_CAPS:
            return C.COST_BPS_SMALL
        return C.COST_BPS_LARGE
    return pd.Series({t: bps(t) for t in columns}) / 1e4


def rebalance_dates(index: pd.DatetimeIndex, freq: str = "ME") -> pd.DatetimeIndex:
    """Last trading day of each period ("ME" month, "W-FRI" week, "QE" quarter)."""
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby(pd.Grouper(freq=freq)).last().dropna().values)


def equal_weight_targets(close: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Equal weight across assets with a valid price on each rebalance date."""
    live = close.reindex(dates).notna()
    return live.div(live.sum(axis=1), axis=0).fillna(0.0)


def run(returns: pd.DataFrame, targets: pd.DataFrame, rf: pd.Series | None = None,
        costs: pd.Series | None = None, dd_limit: float | None = None,
        dd_scale: float = 0.5) -> pd.DataFrame:
    """Simulate a long-only portfolio.

    ``dd_limit`` adds a portfolio-level stop: when the strategy's drawdown from
    its running peak exceeds ``dd_limit`` at a rebalance, the risky targets are
    multiplied by ``dd_scale`` (rest to cash) until drawdown recovers to half
    the limit. It only uses the realised equity curve, so it is not look-ahead.

    Returns a frame with columns ``gross``, ``cost``, ``net``, ``turnover``,
    ``invested`` (sum of risky weights) indexed by trading day.
    """
    returns = returns.reindex(columns=targets.columns)
    r = returns.fillna(0.0).to_numpy()
    idx = returns.index
    rf_arr = (rf.reindex(idx).fillna(0.0).to_numpy() if rf is not None
              else np.zeros(len(idx)))
    c = (costs if costs is not None else cost_vector(targets.columns)).reindex(targets.columns).fillna(0).to_numpy()
    tgt = targets.reindex(columns=returns.columns).fillna(0.0)
    tgt_pos = {idx.get_loc(d): tgt.loc[d].to_numpy() for d in tgt.index if d in idx}

    w = np.zeros(r.shape[1])
    out = np.zeros((len(idx), 6))
    wealth = peak = 1.0
    derisked = False
    for i in range(len(idx)):
        # 1) earn today's return with yesterday's post-trade weights
        cash = 1.0 - w.sum()
        gross = float(w @ r[i] + cash * rf_arr[i])
        if i > 0:
            growth = 1.0 + gross
            w = w * (1.0 + r[i]) / growth if growth > 0 else w * 0
        if i > 0:
            wealth *= 1.0 + gross
            peak = max(peak, wealth)
        dd = wealth / peak - 1.0
        # 2) trade at today's close if a target is dated today
        cost = turn = 0.0
        if i in tgt_pos:
            new = tgt_pos[i]
            if dd_limit is not None:
                if dd < -dd_limit:
                    derisked = True
                elif dd > -dd_limit / 2:
                    derisked = False
                if derisked:
                    new = new * dd_scale
            trade = np.abs(new - w)
            turn = float(trade.sum() / 2)
            cost = float(trade @ c)
            w = new.copy()
            wealth *= 1.0 - cost
        out[i] = (gross if i > 0 else 0.0, cost, (gross if i > 0 else 0.0) - cost, turn, w.sum(), float(derisked))
    res = pd.DataFrame(out, index=idx, columns=["gross", "cost", "net", "turnover", "invested", "derisked"])
    first = min(tgt_pos) if tgt_pos else 0
    return res.iloc[first + 1:]
