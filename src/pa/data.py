"""Data layer: download, cache, and quality-check all free data sources.

Sources
-------
* Yahoo Finance (via ``yfinance``): split/dividend-adjusted daily close and
  volume for the 22 holdings plus VIX and Treasury yield indices.
* FRED (St. Louis Fed): risk-free rate and macro spreads, via the public
  ``fredgraph.csv`` endpoint (no API key needed).

Everything is cached to ``data/raw`` so analysis is reproducible offline and
re-runs never hit the network unless ``refresh=True``.
"""
from __future__ import annotations

import io
import logging
import urllib.request

import numpy as np
import pandas as pd

from . import config as C

log = logging.getLogger(__name__)

_PRICE_FILE = C.DATA_RAW / "close.csv"
_VOLUME_FILE = C.DATA_RAW / "volume.csv"
_MARKET_FILE = C.DATA_RAW / "market.csv"
_FRED_FILE = C.DATA_RAW / "fred.csv"


# ---------------------------------------------------------------- download
def _download_yahoo(tickers: list[str], start: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    import yfinance as yf

    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False,
                      group_by="column", threads=True)
    if raw.empty:
        raise RuntimeError(
            "Yahoo Finance returned no data. If running in a sandbox, allow "
            "*.finance.yahoo.com, fc.yahoo.com and guce.yahoo.com.")
    close = raw["Close"].reindex(columns=tickers)
    volume = raw["Volume"].reindex(columns=tickers)
    return close, volume


def _download_fred(series: list[str], start: str) -> pd.DataFrame:
    frames = []
    for sid in series:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"
        with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 (fixed host)
            df = pd.read_csv(io.BytesIO(r.read()), index_col=0, parse_dates=True,
                             na_values=".")
        df.columns = [sid]
        frames.append(df)
    return pd.concat(frames, axis=1).astype(float)


# ---------------------------------------------------------------- loaders
def load_prices(refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Adjusted close and volume, one column per holding (NaN before listing)."""
    if refresh or not _PRICE_FILE.exists():
        close, volume = _download_yahoo(C.TICKERS, C.START)
        close.to_csv(_PRICE_FILE)
        volume.to_csv(_VOLUME_FILE)
    close = pd.read_csv(_PRICE_FILE, index_col=0, parse_dates=True)
    volume = pd.read_csv(_VOLUME_FILE, index_col=0, parse_dates=True)
    return clean_prices(close), volume.reindex_like(close)


def load_market(refresh: bool = False) -> pd.DataFrame:
    """VIX level, 10y and 13-week Treasury yields from Yahoo."""
    if refresh or not _MARKET_FILE.exists():
        close, _ = _download_yahoo(C.MARKET_TICKERS, C.START)
        close.columns = ["vix", "ust10y", "tbill13w"]
        close.to_csv(_MARKET_FILE)
    return pd.read_csv(_MARKET_FILE, index_col=0, parse_dates=True)


def load_fred(refresh: bool = False) -> pd.DataFrame:
    if refresh or not _FRED_FILE.exists():
        df = _download_fred(list(C.FRED_SERIES), C.START)
        df.to_csv(_FRED_FILE)
    df = pd.read_csv(_FRED_FILE, index_col=0, parse_dates=True)
    return df.rename(columns=C.FRED_SERIES)


def risk_free_daily(index: pd.DatetimeIndex) -> pd.Series:
    """Daily risk-free return aligned to ``index``.

    Uses FRED DGS3MO; falls back to Yahoo ^IRX; last resort is 0 (flagged).
    Yields are quoted in % p.a., converted with simple 252-day compounding.
    """
    rf = None
    try:
        rf = load_fred()["rf_3m"]
    except Exception as e:  # pragma: no cover - network dependent
        log.warning("FRED unavailable (%s); trying ^IRX", e)
        try:
            rf = load_market()["tbill13w"]
        except Exception as e2:
            log.warning("No risk-free source (%s); using 0", e2)
    if rf is None:
        return pd.Series(0.0, index=index, name="rf")
    rf = rf.reindex(index.union(rf.index)).ffill().reindex(index).fillna(0.0)
    return ((1 + rf / 100) ** (1 / C.TRADING_DAYS) - 1).rename("rf")


# ---------------------------------------------------------------- quality
def clean_prices(close: pd.DataFrame) -> pd.DataFrame:
    """Remove obviously bad prints; never forward-fill across listing gaps."""
    close = close.sort_index()
    close = close[~close.index.duplicated(keep="last")]
    close = close.where(close > 0)
    # Drop calendar rows where *nothing* traded (holidays in the union index).
    return close.dropna(how="all")


def quality_report(close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    """One row per ticker: coverage, gaps, stale runs, extreme moves."""
    r = np.log(close).diff()
    rows = []
    for t in close.columns:
        s = close[t]
        first, last = s.first_valid_index(), s.last_valid_index()
        live = s.loc[first:last] if first is not None else s.iloc[:0]
        stale = (live.diff() == 0).astype(int)
        # longest run of unchanged prices
        runs = stale.groupby((stale != stale.shift()).cumsum()).cumsum().max() if len(live) else 0
        rows.append({
            "ticker": t,
            "first_date": first.date() if first is not None else None,
            "last_date": last.date() if last is not None else None,
            "n_obs": int(live.notna().sum()),
            "years": round(live.notna().sum() / C.TRADING_DAYS, 2),
            "missing_inside": int(live.isna().sum()),
            "longest_flat_run": int(runs or 0),
            "max_abs_daily_logret": round(float(r[t].abs().max()), 3) if len(live) else np.nan,
            "zero_volume_days": int((volume[t].loc[first:last] == 0).sum()) if first is not None else 0,
        })
    q = pd.DataFrame(rows).set_index("ticker")
    q["flag"] = ""
    q.loc[q["years"] < 1, "flag"] += "SHORT_HISTORY;"
    q.loc[q["longest_flat_run"] >= 5, "flag"] += "STALE_RUN;"
    q.loc[q["max_abs_daily_logret"] > 0.5, "flag"] += "EXTREME_MOVE;"
    last_common = q["last_date"].dropna().max()
    q.loc[q["last_date"] < last_common, "flag"] += "STOPPED_TRADING;"
    return q
