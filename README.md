# Quantitative Portfolio Analysis & Deep Learning Trading Signals

An end-to-end quantitative finance project analyzing a real 22-asset 
portfolio through classical time series methods, mean-variance optimization, 
and deep learning-based trading signal generation — built as a direct 
extension of Shumway & Stoffer's Time Series Analysis and Its Applications 
(Chapters 1-3). Built entirely on free data: Yahoo Finance, FRED and a 
Bigdata.com market snapshot.

---

## Project Overview

### Phase 1 — Buy & Hold Portfolio Analysis
- Log return computation and stationarity testing (ADF test)
- Annualized return, volatility, Sharpe ratio, Sortino ratio, max drawdown
- Correlation matrix and diversification analysis
- Benchmark comparison against S&P 500 (VOO)
- ACF/PACF analysis connecting to Shumway & Stoffer Ch. 1-3

### Phase 2 — Portfolio Optimization
- Monte Carlo simulation of 10,000 random portfolios
- Analytical mean-variance optimization via scipy (SLSQP)
- Efficient frontier visualization
- Maximum Sharpe and minimum volatility portfolio construction
- Current vs optimized weight comparison

### Phase 3 — Quant-Grade Signal Research
- Feature library construction: price, volume, options, sentiment, macro
- Information coefficient (IC) analysis at multiple lags
- Signal decay and regime analysis
- XGBoost as primary model for tabular financial features
- LSTM and Transformer for sequential price modeling
- Walk-forward validation — no single train/test split
- Free data only: Yahoo Finance price/volume, FRED macro series

### Phase 4 — Risk Management & Position Sizing
- Kelly criterion for optimal position sizing based on model edge
- Volatility targeting — scale positions by predicted volatility
- Maximum drawdown constraints and stop-loss framework
- Walk-forward backtest with explicit transaction cost modeling

### Phase 5 — Black-Litterman Optimization with Deep Learning Views
- Market equilibrium prior from market cap weights
- Deep learning return forecasts as quantitative investor views
- Confidence intervals derived from model validation error
- Black-Litterman adjusted expected returns fed into mean-variance optimizer
- Dynamic portfolio rebalancing pipeline

---

## Motivation

This project bridges classical time series econometrics and modern 
quantitative finance. ARIMA models from Shumway & Stoffer Ch. 3 serve 
as interpretable baselines, while XGBoost and deep learning architectures 
(LSTM, Transformer) extend the analysis into nonlinear territory. The 
ultimate goal is a fully data-driven portfolio management pipeline — from 
raw price data through signal research, deep learning forecasting, and 
Bayesian portfolio optimization — consistent with industry-standard 
quantitative research practice.

---

## Portfolio

22 real holdings spanning:
- High-growth speculative tech (QBTS, OKLO, PLTR, SOLS)
- Blue-chip equities (HON, IBM, NVDA, MSFT, META, AMZN)
- Diversified ETFs (VOO, VTI, VEA, VB, VO, VWO, VCIT)
- Sector-specific plays (QTUM, SKYT, JD, WDAY, PSKY)

---

## Report

📄 **[docs/REPORT.md](docs/REPORT.md)** is the full research write-up (executive summary, method,
results, interpretation and caveats for each phase, with plain-English explainers).

---

## Tech Stack

- **Python 3.10+** · `pandas`, `numpy`, `scipy`, `statsmodels`, `scikit-learn`, `xgboost`, `PyTorch`, `matplotlib`
- **Data (free):** Yahoo Finance via `yfinance` (prices, volume, VIX, Treasury yields), FRED (T-bill, term and credit spreads),
  [Bigdata.com](https://bigdata.com) snapshot (market caps, ETF AUM, analyst targets, sentiment)

---

## Repository Structure

```
portfolio-analysis/
├── src/pa/                     # Library: config, data, metrics, backtest, optimize,
│                               #   features, models, risk, bl (Black-Litterman)
├── pipelines/
│   ├── p1_portfolio_analysis.py   # Phase 1
│   ├── p2_optimization.py         # Phase 2
│   ├── p3_signal_research.py      # Phase 3 (walk-forward models)
│   ├── p4_risk_management.py      # Phase 4
│   ├── p5_black_litterman.py      # Phase 5
│   └── improve.py                 # Self-improvement loop (champion/challenger)
├── tests/                      # Unit tests incl. look-ahead-bias tests
├── data/snapshots/             # Point-in-time snapshots (Bigdata.com)
├── results/{figures,tables,metrics}/
├── docs/REPORT.md
├── run_all.sh
└── requirements.txt
```

---

## Data Sources

| Source | Access | Data |
|---|---|---|
| Yahoo Finance (`yfinance`) | Free | Adjusted prices, volume, VIX, Treasury yields |
| FRED | Free, no key | 3-month T-bill, 10y–2y spread, Baa credit spread |
| Bigdata.com (plugin) | Plugin | Market caps, ETF AUM, analyst targets, EPS surprises, news sentiment (snapshot) |

Institutional sources from the original plan (WRDS/OptionMetrics, LSEG, Bloomberg, Capital IQ) are no longer
available, so Phase 3 uses price, volume and macro features only.

---

## Current Status

| Phase | Status |
|---|---|
| Pipeline, tests, report framework | ✅ 13 tests passing |
| Phase 1 — Portfolio Analysis | ✅ Complete (real data, Jan 2015 – Nov 2026) |
| Phase 2 — Portfolio Optimization | ✅ Complete |
| Phase 3 — Signal Research | ✅ Complete: momentum is the champion; ML models under improvement |
| Phase 4 — Risk Management | ✅ Complete |
| Phase 5 — Black-Litterman | ✅ Complete |
| Self-improvement loop | 🔄 Running (see `results/metrics/checkins.md`) |

---

## Getting Started

```bash
git clone https://github.com/KAC329/portfolio-analysis.git
cd portfolio-analysis
pip install -r requirements.txt
./run_all.sh --refresh      # download data, run tests, run all five phases
python pipelines/improve.py --trials 3   # one self-improvement iteration
```

---

## References

- Shumway, R.H. & Stoffer, D.S. (2017). Time Series Analysis and Its 
  Applications. Springer.
- Markowitz, H. (1952). Portfolio Selection. Journal of Finance.
- Black, F. & Litterman, R. (1992). Global Portfolio Optimization. 
  Financial Analysts Journal.
- Hochreiter, S. & Schmidhuber, J. (1997). Long Short-Term Memory. 
  Neural Computation.
- Vaswani et al. (2017). Attention Is All You Need. NeurIPS.
- Chen, T. & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting 
  System. KDD.
