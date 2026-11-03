import pytest

from pa import config as C
from pa.features import build_panel, eligible
from pa.models import WFConfig, split_scores, walk_forward
from pa.metrics import log_returns


@pytest.mark.parametrize("name,kw", [("momentum", {}), ("xgb", {"n_estimators": 20}),
                                     ("ar", {}), ("lstm", {"epochs": 1, "hidden": 8})])
def test_models_run(synthetic, monkeypatch, name, kw):
    monkeypatch.setattr(C, "MIN_TRAIN_DAYS", 400)
    close, vol = synthetic
    p = eligible(build_panel(close, vol, None, None), close)
    out = walk_forward(p, WFConfig(name, kw, retrain_every=200), raw_returns=log_returns(close))
    assert out["pred"].notna().all() and len(out) > 1000
    assert "validation" in split_scores(out)
