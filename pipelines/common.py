"""Shared helpers for the phase pipelines: data loading, chart style, table export."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pa import config as C  # noqa: E402
from pa import data as D  # noqa: E402
from pa.metrics import simple_returns  # noqa: E402

# Validated categorical order (dataviz reference palette) — fixed, never cycled.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERGING = ["#184f95", "#3987e5", "#9ec5f4", "#f0efec", "#f4a5a4", "#e34948", "#a62b2b"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelsize": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "legend.frameon": False, "legend.fontsize": 9, "lines.linewidth": 2.0,
    "font.family": "sans-serif", "figure.dpi": 110, "savefig.dpi": 160,
    "axes.prop_cycle": matplotlib.cycler(color=SERIES),
})


def savefig(fig, name: str, source: str = "Source: Yahoo Finance, FRED; author calculations."):
    fig.text(0.01, 0.005, source, fontsize=7.5, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    path = C.FIG / f"{name}.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def pct(x, d=1):
    return "" if pd.isna(x) else f"{x * 100:.{d}f}%"


def num(x, d=2):
    return "" if pd.isna(x) else f"{x:.{d}f}"


PCT_COLS = {"CAGR", "Volatility", "Max Drawdown", "VaR 95% (1d)", "CVaR 95% (1d)", "Alpha (ann.)",
            "Tracking Error", "weight", "ret", "vol", "Turnover (ann.)", "Cost drag (ann.)",
            "Avg invested", "Time de-risked"}


def to_md(df: pd.DataFrame, name: str, pct_cols=PCT_COLS, digits=2, index=True) -> str:
    """Format a DataFrame as a Markdown table and save it to results/tables."""
    out = df.copy()
    for c in out.columns:
        if c in pct_cols:
            out[c] = out[c].map(lambda v: pct(v))
        elif pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].map(lambda v: num(v, digits))
    md = out.to_markdown(index=index)
    (C.TAB / f"{name}.md").write_text(md + "\n")
    out.to_csv(C.TAB / f"{name}.csv")
    return md


def save_json(obj, name):
    (C.METRICS / f"{name}.json").write_text(json.dumps(obj, indent=2, default=str))


def load_all(refresh: bool = False):
    close, volume = D.load_prices(refresh)
    try:
        market = D.load_market(refresh)
    except Exception as e:
        print("WARN market data unavailable:", e)
        market = pd.DataFrame(index=close.index)
    try:
        fred = D.load_fred(refresh)
    except Exception as e:
        print("WARN FRED unavailable:", e)
        fred = pd.DataFrame(index=close.index)
    rets = simple_returns(close)
    rf = D.risk_free_daily(close.index)
    return close, volume, market, fred, rets, rf
