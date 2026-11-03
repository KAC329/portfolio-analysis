"""Project-wide configuration.

Every tunable assumption lives here so the report can cite one place and the
self-improvement loop can change parameters without touching analysis code.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Env overrides exist ONLY so the pipelines can be dry-run on synthetic data
# in a scratch folder; reported results always use the defaults below.
DATA_RAW = Path(os.environ.get("PA_DATA_DIR", ROOT / "data" / "raw"))
DATA_SNAP = ROOT / "data" / "snapshots"
RESULTS = Path(os.environ.get("PA_RESULTS_DIR", ROOT / "results"))
FIG = RESULTS / "figures"
TAB = RESULTS / "tables"
METRICS = RESULTS / "metrics"
for _p in (DATA_RAW, DATA_SNAP, FIG, TAB, METRICS):
    _p.mkdir(parents=True, exist_ok=True)

# --- Universe -------------------------------------------------------------
# The 22 holdings listed in the README. Grouping is used for reporting only.
GROUPS: dict[str, list[str]] = {
    "Speculative tech": ["QBTS", "OKLO", "PLTR", "SOLS"],
    "Blue chip": ["HON", "IBM", "NVDA", "MSFT", "META", "AMZN"],
    "Diversified ETF": ["VOO", "VTI", "VEA", "VB", "VO", "VWO", "VCIT"],
    "Sector-specific": ["QTUM", "SKYT", "JD", "WDAY", "PSKY"],
}
TICKERS: list[str] = [t for g in GROUPS.values() for t in g]
ETFS = {"VOO", "VTI", "VEA", "VB", "VO", "VWO", "VCIT", "QTUM"}
BENCHMARK = "VOO"

# Actual position sizes are unknown (only the README survives), so the
# "current portfolio" is assumed EQUAL-WEIGHT across the holdings that are
# trading on each date. Replace with real weights here if they become known.
CURRENT_WEIGHTS: dict[str, float] | None = None

# Market-context series (features + risk-free rate).
MARKET_TICKERS = ["^VIX", "^TNX", "^IRX"]          # Yahoo symbols
FRED_SERIES = {
    "DGS3MO": "rf_3m",          # 3-month T-bill (risk-free proxy), % p.a.
    "T10Y2Y": "term_spread",    # 10y minus 2y Treasury, %
    "BAA10Y": "credit_spread",  # Moody's Baa minus 10y Treasury, %
}

START = "2015-01-01"
TRADING_DAYS = 252

# --- Phase 2 --------------------------------------------------------------
OPT_LOOKBACK_YEARS = 3       # estimation window for mean/covariance
MC_PORTFOLIOS = 10_000
MAX_WEIGHT = 0.25            # single-name cap in the optimiser
RANDOM_SEED = 42

# --- Phase 3 --------------------------------------------------------------
HORIZON = 5                  # forecast horizon in trading days
MIN_TRAIN_DAYS = 504         # ~2 years before the first prediction
RETRAIN_EVERY = 21           # refit monthly
HOLDOUT_START = "2025-11-01" # final 12 months are NEVER used for tuning
MIN_ASSET_HISTORY = 252      # assets need 1y of data to enter the panel

# --- Phase 4 --------------------------------------------------------------
TARGET_VOL = 0.15            # annualised portfolio volatility target
COST_BPS_ETF = 2.0           # one-way trading cost, basis points
COST_BPS_LARGE = 5.0
COST_BPS_SMALL = 20.0        # small/speculative names: wider spreads
SMALL_CAPS = {"QBTS", "OKLO", "SOLS", "SKYT", "PSKY"}
KELLY_FRACTION = 0.5         # half-Kelly: standard practitioner haircut
MAX_LEVERAGE = 1.0           # long-only, fully invested at most
DD_LIMIT = 0.20              # de-risk when drawdown exceeds 20%

# --- Phase 5 --------------------------------------------------------------
RISK_AVERSION = 2.5          # delta in Black-Litterman (He & Litterman 1999)
TAU = 0.05
