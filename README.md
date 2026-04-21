# Quantitative Portfolio Analysis & Deep Learning Trading Signals

An end-to-end quantitative finance project analyzing a real 22-asset 
portfolio through classical time series methods, mean-variance optimization, 
and deep learning-based trading signal generation — built as a direct 
extension of Shumway & Stoffer's Time Series Analysis and Its Applications 
(Chapters 1-3). Data sourced from Yahoo Finance, WRDS/OptionMetrics, 
LSEG Machine Readable News, and Bloomberg Terminal.

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

### Phase 3 — Quant-Grade Signal Research (In Progress)
- Feature library construction: price, volume, options, sentiment, macro
- Information coefficient (IC) analysis at multiple lags
- Signal decay and regime analysis
- XGBoost as primary model for tabular financial features
- LSTM and Transformer for sequential price modeling
- Walk-forward validation — no single train/test split
- Data sources: OptionMetrics via WRDS, LSEG Machine Readable News, 
  Bloomberg Terminal exports

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

## Tech Stack

- **Python 3.10+**
- `yfinance` — baseline price and volume data
- `pandas`, `numpy` — data manipulation
- `matplotlib`, `seaborn` — visualization
- `statsmodels` — ARIMA, ADF testing, ACF/PACF
- `scipy` — portfolio optimization
- `PyTorch` — LSTM and Transformer models
- `xgboost` — gradient boosted trees for tabular signal modeling
- `scikit-learn` — preprocessing, evaluation, walk-forward validation
- **WRDS/OptionMetrics** — historical options data (IV, put/call ratio, skew)
- **LSEG Machine Readable News** — professional news sentiment scores
- **Bloomberg Terminal** — implied volatility history, options flow

---

## Repository Structure

'''
quantitative-portfolio-analysis/
│
├── notebooks/
│   ├── 01_portfolio_analysis.ipynb         # Phase 1
│   ├── 02_portfolio_optimization.ipynb     # Phase 2
│   ├── 03_deep_learning_signals.ipynb      # Phase 3 (prototype)
│   ├── 04_qbts_feature_study.ipynb         # Phase 3 feature research
│   ├── 05_quant_signal_research.ipynb      # Phase 3 redesign (in progress)
│   ├── 06_risk_management.ipynb            # Phase 4 (planned)
│   └── 07_black_litterman.ipynb            # Phase 5 (planned)
│
├── data/                                   # Cached and exported data
├── models/                                 # Saved model weights
├── results/                                # Charts, tables, backtest results
├── requirements.txt
└── README.md
---

## Data Sources

| Source | Access | Data |
|---|---|---|
| Yahoo Finance | Free, remote | Price, volume |
| WRDS/OptionMetrics | Stevens HFSC | Historical options, IV, put/call |
| LSEG Machine Readable News | Stevens HFSC | News sentiment scores |
| Bloomberg Terminal | Stevens HFSC (on-site) | IV history, options flow |
| S&P Capital IQ | Stevens HFSC | Earnings surprise, short interest |

---

## Current Status

| Phase | Status |
|---|---|
| Phase 1 — Portfolio Analysis | Complete |
| Phase 2 — Portfolio Optimization | Complete |
| Phase 3 — Signal Research | In Progress — awaiting WRDS access |
| Phase 4 — Risk Management | Planned |
| Phase 5 — Black-Litterman | Planned |

---

## Getting Started

```bash
git clone https://github.com/YOUR_USERNAME/quantitative-portfolio-analysis.git
cd quantitative-portfolio-analysis
pip install -r requirements.txt
jupyter notebook notebooks/
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
