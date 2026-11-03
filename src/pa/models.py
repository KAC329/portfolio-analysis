"""Phase 3 models and walk-forward evaluation.

Walk-forward protocol (no single train/test split)
-------------------------------------------------
* Start predicting once ``MIN_TRAIN_DAYS`` of history exist.
* Every ``retrain_every`` trading days, refit on all rows whose *label is
  already known*: a label for date d needs prices up to d+H, so at refit date
  T we only train on d <= T - H (the "purge"). Skipping this leaks the future.
* Predict each following day until the next refit.
* Data from ``HOLDOUT_START`` onward is scored separately and is never used to
  choose models or hyper-parameters (that includes the self-improvement loop).

Models
------
* ``momentum``: the 12-1 momentum factor itself (a zero-parameter baseline).
* ``ar``: per-asset autoregressive model, AR(p) with p by AIC (Shumway &
  Stoffer ch. 3), forecasting the H-day return.
* ``ridge``: linear regression with L2 penalty on all features.
* ``xgb``: gradient-boosted trees (primary tabular model).
* ``lstm``: recurrent network on each asset's last ``SEQ_LEN`` days of features.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from . import config as C
from .features import FEATURE_GROUPS, FEATURES

MACRO = FEATURE_GROUPS["macro"]
CS_FEATURES = [f for f in FEATURES if f not in MACRO]


# ------------------------------------------------------------- preprocessing
def prep(panel: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score per date (uses same-date data only), clipped."""
    X = panel[FEATURES].copy()
    g = X[CS_FEATURES].groupby(level="date")
    z = (X[CS_FEATURES] - g.transform("mean")) / g.transform("std").replace(0, np.nan)
    X[CS_FEATURES] = z.clip(-3, 3)
    return X


# ------------------------------------------------------------- model zoo
class MomentumBaseline:
    name = "momentum"

    def fit(self, X, y):
        return self

    def predict(self, X):
        return X["mom_12_1"].fillna(0).to_numpy()


class RidgeModel:
    name = "ridge"

    def __init__(self, alpha: float = 10.0):
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        self.m = make_pipeline(StandardScaler(), Ridge(alpha=alpha))

    def fit(self, X, y):
        self.m.fit(X.fillna(0), y)
        return self

    def predict(self, X):
        return self.m.predict(X.fillna(0))


class XGBModel:
    name = "xgb"

    def __init__(self, **params):
        import xgboost as xgb
        p = dict(n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8,
                 colsample_bytree=0.7, min_child_weight=50, reg_lambda=5.0,
                 objective="reg:pseudohubererror", n_jobs=4, random_state=C.RANDOM_SEED)
        p.update(params)
        self.m = xgb.XGBRegressor(**p)

    def fit(self, X, y):
        self.m.fit(X, y)
        return self

    def predict(self, X):
        return self.m.predict(X)


class ARModel:
    """Per-asset AR(p) on daily log returns; H-step forecast summed."""
    name = "ar"

    def __init__(self, max_p: int = 5, window: int = 504):
        self.max_p, self.window = max_p, window
        self.params: dict[str, tuple[float, np.ndarray]] = {}

    def fit(self, X, y):
        from statsmodels.tsa.ar_model import AutoReg, ar_select_order
        r = self._raw.loc[: X.index.get_level_values("date").max()]
        for t in r.columns:
            s = r[t].dropna().iloc[-self.window:]
            if len(s) < 100:
                continue
            try:
                sel = ar_select_order(s.to_numpy(), maxlag=self.max_p, ic="aic", trend="c")
                lags = sel.ar_lags or []
                p = max(lags) if lags else 0
                res = AutoReg(s.to_numpy(), lags=p, trend="c").fit()
                self.params[t] = (float(res.params[0]), np.asarray(res.params[1:]))
            except Exception:
                continue
        return self

    def predict(self, X):
        out = np.zeros(len(X))
        dates = X.index.get_level_values("date")
        tick = X.index.get_level_values("ticker")
        for i, (d, t) in enumerate(zip(dates, tick)):
            if t not in self.params:
                continue
            c, phi = self.params[t]
            p = len(phi)
            hist = list(self._raw[t].loc[:d].dropna().iloc[-p:][::-1]) if p else []
            tot = 0.0
            for _ in range(C.HORIZON):
                f = c + (float(np.dot(phi, hist[:p])) if p else 0.0)
                tot += f
                hist = [f] + hist
            out[i] = tot
        return out


class LSTMModel:
    """Small LSTM on each asset's recent feature history (sequence model)."""
    name = "lstm"
    SEQ_LEN = 20

    def __init__(self, hidden: int = 32, epochs: int = 8, lr: float = 1e-3, seed: int = C.RANDOM_SEED):
        self.hidden, self.epochs, self.lr, self.seed = hidden, epochs, lr, seed

    def _seq(self, idx: pd.MultiIndex) -> np.ndarray:
        L = self.SEQ_LEN
        out = np.zeros((len(idx), L, self._F.shape[2]), dtype=np.float32)
        di = self._date_pos.get_indexer(idx.get_level_values("date"))
        ti = self._tick_pos.get_indexer(idx.get_level_values("ticker"))
        for k, (d, t) in enumerate(zip(di, ti)):
            lo = max(0, d - L + 1)
            w = self._F[lo:d + 1, t]
            out[k, L - len(w):] = w
        return out

    def attach(self, X_all: pd.DataFrame):
        """Pre-build a dense (date, ticker, feature) cube from the full prepped panel."""
        dates = X_all.index.get_level_values("date").unique().sort_values()
        ticks = X_all.index.get_level_values("ticker").unique()
        self._date_pos, self._tick_pos = pd.Index(dates), pd.Index(ticks)
        F = np.zeros((len(dates), len(ticks), X_all.shape[1]), dtype=np.float32)
        di = self._date_pos.get_indexer(X_all.index.get_level_values("date"))
        ti = self._tick_pos.get_indexer(X_all.index.get_level_values("ticker"))
        F[di, ti] = X_all.fillna(0).to_numpy(dtype=np.float32)
        # scaling stats from the initial training block only (no look-ahead)
        base = F[:C.MIN_TRAIN_DAYS].reshape(-1, F.shape[2])
        mu, sd = base.mean(0), base.std(0) + 1e-6
        self._F = np.clip((F - mu) / sd, -5, 5)
        return self

    def fit(self, X, y):
        import torch
        from torch import nn
        torch.manual_seed(self.seed)
        torch.set_num_threads(4)
        Xs = torch.from_numpy(self._seq(X.index))
        ys = torch.from_numpy(np.asarray(y, dtype=np.float32))
        self.y_scale = float(ys.std()) or 1.0
        ys = ys / self.y_scale

        class Net(nn.Module):
            def __init__(s, f, h):
                super().__init__()
                s.lstm = nn.LSTM(f, h, batch_first=True)
                s.drop = nn.Dropout(0.2)
                s.head = nn.Linear(h, 1)

            def forward(s, x):
                o, _ = s.lstm(x)
                return s.head(s.drop(o[:, -1])).squeeze(-1)

        self.net = Net(Xs.shape[2], self.hidden)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr, weight_decay=1e-4)
        loss_fn = nn.HuberLoss()
        n = len(Xs)
        for _ in range(self.epochs):
            self.net.train()
            perm = torch.randperm(n)
            for b in range(0, n, 512):
                j = perm[b:b + 512]
                opt.zero_grad()
                loss = loss_fn(self.net(Xs[j]), ys[j])
                loss.backward()
                opt.step()
        return self

    def predict(self, X):
        import torch
        self.net.eval()
        with torch.no_grad():
            return self.net(torch.from_numpy(self._seq(X.index))).numpy() * self.y_scale


def make_model(name: str, **kw):
    return {"momentum": MomentumBaseline, "ridge": RidgeModel, "xgb": XGBModel,
            "ar": ARModel, "lstm": LSTMModel}[name](**kw)


# ------------------------------------------------------------- walk-forward
@dataclass
class WFConfig:
    model: str
    params: dict = field(default_factory=dict)
    retrain_every: int = C.RETRAIN_EVERY
    target: str = "target_xs"
    train_window: int | None = None   # None = expanding window


def walk_forward(panel: pd.DataFrame, cfg: WFConfig, raw_returns: pd.DataFrame | None = None,
                 verbose: bool = False) -> pd.DataFrame:
    """Return out-of-sample predictions: columns pred, target, target_xs."""
    X_all = prep(panel)
    dates = panel.index.get_level_values("date").unique().sort_values()
    if len(dates) <= C.MIN_TRAIN_DAYS + C.HORIZON:
        raise ValueError("Not enough history for walk-forward")
    model_proto = make_model(cfg.model, **cfg.params)
    if cfg.model == "ar":
        model_proto._raw = raw_returns
    if cfg.model == "lstm":
        model_proto.attach(X_all)
    refits = dates[C.MIN_TRAIN_DAYS::cfg.retrain_every]
    preds = []
    t0 = time.time()
    for k, T in enumerate(refits):
        nxt = refits[k + 1] if k + 1 < len(refits) else dates[-1] + pd.Timedelta(days=1)
        cutoff_pos = dates.get_loc(T) - C.HORIZON          # purge: labels must be known at T
        if cutoff_pos <= 0:
            continue
        cutoff = dates[cutoff_pos]
        tr_dates = dates[dates <= cutoff]
        if cfg.train_window:
            tr_dates = tr_dates[-cfg.train_window:]
        tr_mask = X_all.index.get_level_values("date").isin(tr_dates)
        y_tr = panel.loc[tr_mask, cfg.target]
        ok = y_tr.notna().to_numpy()
        te_mask = (X_all.index.get_level_values("date") > T) & (X_all.index.get_level_values("date") <= nxt)
        if k == 0:  # first block also predicts T itself
            te_mask |= X_all.index.get_level_values("date") == T
        if not te_mask.any():
            continue
        m = model_proto if cfg.model in ("ar", "lstm") else make_model(cfg.model, **cfg.params)
        m.fit(X_all[tr_mask][ok], y_tr[ok].to_numpy())
        p = m.predict(X_all[te_mask])
        preds.append(pd.DataFrame({"pred": p}, index=X_all.index[te_mask]))
        if verbose and k % 10 == 0:
            print(f"  [{cfg.model}] refit {k + 1}/{len(refits)} at {T.date()} ({time.time() - t0:.0f}s)")
    out = pd.concat(preds)
    out = out[~out.index.duplicated(keep="last")]
    return out.join(panel[["target", "target_xs"]])


# ------------------------------------------------------------- scoring
def daily_ic(df: pd.DataFrame, pred: str = "pred", target: str = "target_xs") -> pd.Series:
    def _ic(g):
        g = g[[pred, target]].dropna()
        if len(g) < 5 or g[pred].nunique() < 2:
            return np.nan
        return stats.spearmanr(g[pred], g[target]).statistic
    return df.groupby(level="date").apply(_ic).dropna()


def score(df: pd.DataFrame, pred: str = "pred", target: str = "target_xs") -> dict:
    """Signal-quality metrics. Non-overlapping dates are used for t-stats."""
    df = df.dropna(subset=[pred, target])
    if df.empty:
        return {}
    ic = daily_ic(df, pred, target)
    ic_nov = ic.iloc[::C.HORIZON]                       # non-overlapping sample
    t_stat = ic_nov.mean() / ic_nov.std(ddof=1) * np.sqrt(len(ic_nov)) if len(ic_nov) > 2 else np.nan
    hit = float((np.sign(df[pred]) == np.sign(df[target])).mean())

    def spread(g):
        if len(g) < 6:
            return np.nan
        q = g[pred].rank(pct=True)
        return g.loc[q >= 2 / 3, target].mean() - g.loc[q <= 1 / 3, target].mean()

    sp = df.groupby(level="date").apply(spread).dropna().iloc[::C.HORIZON]
    periods = C.TRADING_DAYS / C.HORIZON
    return {
        "n_dates": int(ic.size),
        "mean_IC": float(ic.mean()),
        "IC_std": float(ic.std()),
        "ICIR_ann": float(ic.mean() / ic.std() * np.sqrt(periods)) if ic.std() > 0 else np.nan,
        "IC_tstat": float(t_stat),
        "IC_pos_share": float((ic > 0).mean()),
        "hit_rate": hit,
        "top_minus_bottom_ann": float(sp.mean() * periods),
        "tmb_sharpe": float(sp.mean() / sp.std() * np.sqrt(periods)) if sp.std() > 0 else np.nan,
    }


def split_scores(oos: pd.DataFrame) -> dict:
    d = oos.index.get_level_values("date")
    hold = d >= pd.Timestamp(C.HOLDOUT_START)
    return {"validation": score(oos[~hold]), "holdout": score(oos[hold])}


def feature_ic_table(panel: pd.DataFrame, lags=(0, 1, 2, 4, 8)) -> pd.DataFrame:
    """IC of each raw feature vs the forward return k*H days later (signal decay)."""
    pre = panel[panel.index.get_level_values("date") < pd.Timestamp(C.HOLDOUT_START)]
    rows = {}
    for f in CS_FEATURES:
        row = {}
        for k in lags:
            tgt = pre.groupby(level="ticker")["target_xs"].shift(-k * C.HORIZON)
            tmp = pd.DataFrame({"pred": pre[f], "target_xs": tgt})
            ic = daily_ic(tmp)
            ic_nov = ic.iloc[::C.HORIZON]
            row[f"IC lag{k}"] = ic.mean()
            if k == 0:
                row["t-stat"] = ic_nov.mean() / ic_nov.std() * np.sqrt(len(ic_nov))
        rows[f] = row
    return pd.DataFrame(rows).T.sort_values("IC lag0", key=np.abs, ascending=False)


def log_scoreboard(entry: dict, path=C.METRICS / "scoreboard.jsonl") -> None:
    entry = {"timestamp": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), **entry}
    with open(path, "a") as fh:
        fh.write(json.dumps(entry, default=float) + "\n")
