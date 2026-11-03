import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def synthetic():
    """Synthetic prices for unit tests ONLY — never used for any reported result."""
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2018-01-01", periods=1200)
    tick = ["VOO", "AAA", "BBB", "CCC", "DDD", "EEE"]
    mkt = rng.normal(0.0004, 0.01, len(idx))
    r = np.column_stack([mkt] + [0.8 * mkt + rng.normal(0, 0.015, len(idx)) for _ in tick[1:]])
    close = pd.DataFrame(100 * np.exp(np.cumsum(r, 0)), index=idx, columns=tick)
    close.iloc[:300, 3] = np.nan            # CCC lists later
    vol = pd.DataFrame(rng.integers(1e5, 1e6, close.shape), index=idx, columns=tick).astype(float)
    return close, vol
