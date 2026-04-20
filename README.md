# portfolio-analysis
 Quantitative portfolio analysis with ARIMA baselines and deep learning (LSTM/Transformer) trading signals — built on Shumway &amp; Stoffer time series foundations

# Quantitative Portfolio Analysis & Deep Learning Trading Signals

A end-to-end quantitative finance project that analyzes a real stock portfolio,
optimizes asset allocation, and applies deep learning models to generate
buy/sell signals — built as an extension of classical time series analysis
(Shumway & Stoffer, Chapters 1–3).

---

## Project Overview

This project is structured in three phases:

### Phase 1 — Buy & Hold Portfolio Analysis
- Log return computation and stationarity testing (ADF test)
- Portfolio performance metrics: CAGR, Sharpe Ratio, Sortino Ratio, Max Drawdown
- Correlation matrix and diversification analysis
- Benchmark comparison against S&P 500 (VOO)

### Phase 2 — Portfolio Optimization
- Mean-variance optimization (Markowitz Efficient Frontier)
- Risk-minimizing and return-maximizing portfolio construction
- Comparison of current holdings vs. optimized weights

### Phase 3 — Deep Learning for Market Timing
- ARIMA baseline models (direct application of Shumway & Stoffer Ch. 3)
- LSTM (Long Short-Term Memory) model for return forecasting
- Transformer-based attention model for sequence modeling
- Buy/sell signal generation with backtesting

---

## Motivation

This project bridges classical time series econometrics and modern deep learning.
ARIMA models from Ch. 3 of *Time Series Analysis and Its Applications*
(Shumway & Stoffer) serve as interpretable baselines, while LSTM and Transformer
architectures are explored as nonlinear extensions capable of capturing
complex temporal dependencies in financial data.

---

## Tech Stack

- **Python 3.10+**
- `yfinance` — historical price data
- `pandas`, `numpy` — data manipulation
- `matplotlib`, `seaborn` — visualization
- `statsmodels` — ARIMA, ADF testing, ACF/PACF
- `scipy` — portfolio optimization
- `PyTorch` — LSTM and Transformer models
- `scikit-learn` — preprocessing, evaluation metrics

---

## Portfolio

The portfolio analyzed consists of 23 real holdings spanning:
- High-growth speculative tech (QBTS, OKLO, PLTR, SOLS)
- Blue-chip equities (HON, IBM, NVDA, MSFT, META, AMZN)
- Diversified ETFs (VOO, VTI, VEA, VB, VO, VWO, VCIT)
- Sector-specific plays (QTUM, SKYT, JD, WDAY, PSKY)

---

## Repository Structure
quantitative-portfolio-analysis/
│
├── notebooks/
│   ├── 01_portfolio_analysis.ipynb       # Phase 1
│   ├── 02_portfolio_optimization.ipynb   # Phase 2
│   └── 03_deep_learning_signals.ipynb    # Phase 3
│
├── data/                                 # Cached price data (auto-downloaded)
├── models/                               # Saved PyTorch model weights
├── results/                              # Charts, tables, backtest results
├── requirements.txt
└── README.md

---

## Getting Started

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/quantitative-portfolio-analysis.git
cd quantitative-portfolio-analysis

# Install dependencies
pip install -r requirements.txt

# Launch Jupyter
jupyter notebook notebooks/
```

---

## References

- Shumway, R.H. & Stoffer, D.S. (2017). *Time Series Analysis and Its Applications*. Springer.
- Markowitz, H. (1952). Portfolio Selection. *Journal of Finance*.
- Hochreiter, S. & Schmidhuber, J. (1997). Long Short-Term Memory. *Neural Computation*.
- Vaswani et al. (2017). Attention Is All You Need. *NeurIPS*.
