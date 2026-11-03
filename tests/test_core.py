import numpy as np
import pandas as pd
import pytest

from pa import backtest, bl, metrics, optimize
from pa import config as C
from pa.features import build_panel, eligible
from pa.models import WFConfig, walk_forward


def test_cagr_and_drawdown():
    idx = pd.bdate_range("2020-01-01", periods=252)
    r = pd.Series(0.001, index=idx)
    assert metrics.cagr(r) == pytest.approx(1.001 ** 252 - 1)
    r2 = pd.Series([0.1, -0.5, 0.2], index=idx[:3])
    assert metrics.max_drawdown(r2) == pytest.approx(-0.5)


def test_backtest_single_asset_matches_returns():
    idx = pd.bdate_range("2020-01-01", periods=50)
    rets = pd.DataFrame({"A": np.linspace(-0.01, 0.01, 50)}, index=idx)
    tgt = pd.DataFrame({"A": [1.0]}, index=[idx[0]])
    res = backtest.run(rets, tgt, costs=pd.Series({"A": 0.0}))
    assert np.allclose(res["net"].to_numpy(), rets["A"].iloc[1:].to_numpy())


def test_backtest_costs_charged_on_turnover():
    idx = pd.bdate_range("2020-01-01", periods=5)
    rets = pd.DataFrame(0.0, index=idx, columns=["A", "B"])
    tgt = pd.DataFrame([[1.0, 0.0], [0.0, 1.0]], index=[idx[0], idx[2]], columns=["A", "B"])
    res = backtest.run(rets, tgt, costs=pd.Series({"A": 0.001, "B": 0.001}))
    assert res.loc[idx[2], "cost"] == pytest.approx(0.002)
    assert res.loc[idx[2], "turnover"] == pytest.approx(1.0)


def test_min_vol_two_identical_uncorrelated_assets():
    mu = pd.Series([0.1, 0.1], index=["A", "B"])
    cov = pd.DataFrame(np.eye(2) * 0.04, index=mu.index, columns=mu.index)
    w = optimize.min_vol(mu, cov, cap=1.0)
    assert w.to_numpy() == pytest.approx([0.5, 0.5], abs=1e-4)
    ws = optimize.max_sharpe(mu, cov, cap=0.6)
    assert ws.sum() == pytest.approx(1) and ws.max() <= 0.6 + 1e-6


def test_bl_huge_uncertainty_returns_prior():
    cov = pd.DataFrame([[0.04, 0.01], [0.01, 0.09]], index=["A", "B"], columns=["A", "B"])
    pi = bl.implied_returns(cov, pd.Series([0.5, 0.5], index=["A", "B"]))
    mu, _ = bl.posterior(pi, cov, Q=pd.Series([1.0, -1.0], index=["A", "B"]), omega_scale=1e9)
    assert mu.to_numpy() == pytest.approx(pi.to_numpy(), abs=1e-6)


def test_features_have_no_lookahead(synthetic):
    close, vol = synthetic
    cut = close.index[800]
    p1 = build_panel(close, vol, None, None)
    close2 = close.copy()
    close2.loc[close2.index > cut] *= 1.5          # change the future only
    p2 = build_panel(close2, vol, None, None)
    feats = [c for c in p1.columns if not c.startswith("target")]
    a = p1.loc[p1.index.get_level_values("date") <= cut, feats]
    b = p2.loc[p2.index.get_level_values("date") <= cut, feats]
    pd.testing.assert_frame_equal(a, b)


def test_walk_forward_has_no_lookahead(synthetic, monkeypatch):
    monkeypatch.setattr(C, "MIN_TRAIN_DAYS", 400)
    close, vol = synthetic
    cut = close.index[900]

    def oos(cl):
        p = eligible(build_panel(cl, vol, None, None), cl)
        return walk_forward(p, WFConfig("ridge", retrain_every=50))["pred"]

    p1 = oos(close)
    close2 = close.copy()
    close2.loc[close2.index > cut] *= np.exp(np.linspace(0, 1, (close2.index > cut).sum()))[:, None]
    p2 = oos(close2)
    d = p1.index.get_level_values("date") <= cut
    pd.testing.assert_series_equal(p1[d], p2.reindex(p1.index)[d])


def test_daily_ic_matches_scipy_spearman():
    from scipy import stats
    from pa.models import daily_ic
    rng = np.random.default_rng(1)
    idx = pd.MultiIndex.from_product([pd.bdate_range("2020-01-01", periods=30), list("ABCDEFGH")],
                                     names=["date", "ticker"])
    df = pd.DataFrame({"pred": rng.normal(size=len(idx)), "target_xs": rng.normal(size=len(idx))}, index=idx)
    df.iloc[3, 0] = np.nan
    ic = daily_ic(df)
    ref = df.dropna().groupby(level="date").apply(lambda g: stats.spearmanr(g.pred, g.target_xs).statistic)
    assert np.allclose(ic.to_numpy(), ref.to_numpy())


def test_max_sharpe_falls_back_when_nothing_beats_cash():
    mu = pd.Series([0.01, 0.02], index=["A", "B"])
    cov = pd.DataFrame([[0.04, 0.0], [0.0, 0.09]], index=mu.index, columns=mu.index)
    w = optimize.max_sharpe(mu, cov, rf=0.05, cap=1.0)
    assert w.to_numpy() == pytest.approx(optimize.min_vol(mu, cov, cap=1.0).to_numpy())
