# Quantitative Portfolio Analysis — Research Report

| | |
|---|---|
| **Portfolio** | 22 holdings (stocks + ETFs), see §1 |
| **Benchmark** | Vanguard S&P 500 ETF (VOO) |
| **Report status** | 🟡 **Draft — pipeline built and tested; awaiting market-data access to populate results** |
| **Last updated** | 2026-11-03 |
| **Data as of** | Snapshot data: 2026-11-03 (Bigdata.com). Price history: *pending* |
| **Code** | `run_all.sh` rebuilds every table and chart in this report |

> **How to read this report.** Each phase follows the same layout used in
> professional investment research: **Objective → Method → Results →
> Interpretation → Caveats**. Boxes marked **📘 Concept** explain the finance or
> statistics idea in plain English for readers new to the topic; experienced
> readers can skip them.

---

## Executive summary

**Status today.** Everything needed to run the analysis has been built and tested:
the data layer, all five phases, the backtest engine, and the model
self-improvement loop (11 automated tests pass, including two that prove the
models cannot "see the future"). **No price history has been downloaded yet**
because this cloud session's network policy blocks Yahoo Finance and FRED (see
*What is still needed*). No results have been estimated or invented to fill the
gaps; every result section below says *pending* until real data arrives.

**What we already know (from the Bigdata.com snapshot, 3 Nov 2026):**

1. **The portfolio is very top-heavy in market value but spread evenly in
   count.** NVDA ($4.87T), MSFT ($3.77T) and AMZN ($2.65T) are each more than
   1,000× the size of QBTS ($3.8B) or SKYT ($1.6B). An equal-weight portfolio
   therefore holds far more small, speculative risk than the market does.
   Phase 5 uses that gap directly.
2. **Three holdings have data problems that must be fixed before trading
   decisions:** SOLS (last price is 29 Oct 2025, under a when-issued ticker),
   SKYT (no price update since 31 Jul 2026; Bigdata.com classifies it as
   *private*, which suggests it may have been acquired or delisted — verify), and
   PSKY (could not be matched to a security). See §1.3.
3. **The sell-side is constructive on the speculative names but sentiment is
   weak.** Mean analyst targets imply large upside for QBTS (+250%) and OKLO
   (+173%), but both missed the most recent earnings-per-share (EPS) estimate
   (−18% and −71% surprise). News sentiment is negative for META (−0.53),
   QBTS (−0.38) and AMZN (−0.34).

**What still needs to be done:** see the checklist at the end of this section.
Each phase's conclusions will be written here once its results exist.

### What is still needed

| # | Item | Owner | Why |
|---|---|---|---|
| 1 | Allow `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `fc.yahoo.com`, `guce.yahoo.com`, `fred.stlouisfed.org` in the cloud environment's **Network access** settings | You | Price, volume and interest-rate history for every phase |
| 2 | Install the Claude GitHub App on `KAC329/portfolio-analysis` (or reconnect GitHub in claude.ai settings) | You | So work can be pushed to GitHub automatically |
| 3 | *(Optional)* Real position sizes | You | The analysis currently assumes **equal weights** (§1.2) |
| 4 | Verify SKYT and PSKY tickers / corporate actions | You or Claude, once web access is allowed | Data quality (§1.3) |

---

## 1. Portfolio, data and assumptions

### 1.1 Holdings

| Group | Holdings |
|---|---|
| Speculative tech | QBTS (D-Wave Quantum), OKLO (Oklo), PLTR (Palantir), SOLS (Solstice Advanced Materials) |
| Blue chip | HON, IBM, NVDA, MSFT, META, AMZN |
| Diversified ETFs | VOO (S&P 500), VTI (total US), VEA (developed ex-US), VB (small cap), VO (mid cap), VWO (emerging), VCIT (investment-grade corporate bonds) |
| Sector-specific | QTUM (quantum ETF), SKYT (SkyWater), JD (JD.com), WDAY (Workday), PSKY (Paramount Skydance) |

### 1.2 Key assumptions

| Assumption | Value | Why / effect |
|---|---|---|
| Current weights | **Equal weight** across holdings trading on each date, rebalanced monthly | Real position sizes are unknown. New listings join at the next month-end |
| Risk-free rate | 3-month T-bill (FRED `DGS3MO`) | Standard for Sharpe/Sortino |
| Trading costs (one-way) | ETFs 2 bp · large caps 5 bp · small/speculative 20 bp | Conservative retail estimates. Phase 4 tests 0×–4× these costs |
| Return convention | Daily total return (prices adjusted for splits and dividends); annualised with 252 days | — |
| Hold-out period | 2025-11-01 → today | **Never used to tune any model.** Reported separately as the honest test |

All parameters live in [`src/pa/config.py`](../src/pa/config.py).

> **📘 Concept — why a hold-out period?** If you try 100 model settings and
> keep the best one, part of its "skill" is luck. Setting the last 12 months
> aside, and looking at them only *after* every choice is made, gives an
> unbiased estimate of how the strategy would have done in real life.

### 1.3 Data sources and data quality

| Source | Used for | Access | Status |
|---|---|---|---|
| Yahoo Finance (`yfinance`) | Adjusted daily close & volume; VIX; Treasury yields | Free | ⛔ Blocked by session network policy |
| FRED (St. Louis Fed) | T-bill rate, 10y–2y term spread, Baa credit spread | Free, no key | ⛔ Blocked by session network policy |
| [Bigdata.com](https://bigdata.com) (plugin) | Market caps, ETF AUM, analyst targets, EPS surprises, news sentiment | Plugin | ✅ Snapshot saved: `data/snapshots/bigdata_snapshot_2026-11-03.csv` |

**Snapshot (Bigdata.com, 3 Nov 2026, 17:00 UTC):**

| Ticker | Size (USD) | Price | Mean analyst target | Implied upside | Last EPS surprise | News sentiment | Flag |
|---|---:|---:|---:|---:|---:|---:|---|
| NVDA | 4.87T cap | 208.54 | 339.17 | +62.6% | +6.2% | −0.02 | |
| MSFT | 3.77T cap | 516.22 | 611.74 | +18.5% | +3.6% | −0.21 | |
| AMZN | 2.65T cap | 248.00 | 328.48 | +32.5% | −4.1% | −0.34 | |
| META | 1.34T cap | 621.46 | 834.36 | +34.3% | +13.1% | −0.53 | |
| PLTR | 410B cap | 173.12 | 216.61 | +25.1% | +8.3% | −0.07 | |
| IBM | 239B cap | 250.26 | 271.07 | +8.3% | +3.5% | −0.11 | |
| HON | 70.9B cap | 223.89 | 256.92 | +14.8% | +4.6% | +0.20 | |
| WDAY | 47.7B cap | 198.95 | 201.85 | +1.5% | +5.4% | −0.16 | |
| JD | ≈31.5B cap | HK$107.30 | — | — | +13.0% | +0.02 | Quoted in Hong Kong (9618.HK); market cap converted at 7.78 HKD/USD |
| SOLS | 7.8B cap | 49.25 | — | — | — | +0.15 | ⚠️ Stale price (29 Oct 2025, when-issued ticker) |
| OKLO | 4.38B cap | 23.16 | 63.33 | +173% | −70.9% | +0.02 | |
| QBTS | 3.80B cap | 10.33 | 36.14 | +250% | −18.1% | −0.38 | |
| SKYT | 1.60B cap | 32.46 | 29.00 | −10.7% | — | +0.54 | ⚠️ Stale since 31 Jul 2026; listed as private, so verify |
| PSKY | — | — | — | — | — | — | ⚠️ Not resolved |
| VOO | 1,000B AUM | 694.23 | | | | | |
| VTI | 689B AUM | 371.81 | | | | | |
| VEA | 232B AUM | 69.45 | | | | | |
| VWO | 125B AUM | 55.45 | | | | | |
| VB | 76.9B AUM | 293.87 | | | | | |
| VCIT | 66.6B AUM | 79.14 | | | | | |
| QTUM | 5.06B AUM | 132.71 | | | | | |
| VO | — | — | | | | | ⚠️ ETF data not available |

*Sentiment is Bigdata.com's recent-window news score (−1 to +1). "Implied upside" =
mean analyst target ÷ price − 1. It is a cross-check, not an input to any model.*

**Automated price-history checks** (run as soon as data loads; table →
`results/tables/p1_data_quality.md`): coverage dates, missing days inside the
trading history, runs of unchanged prices (a stale-feed symptom), extreme daily
moves (>50% log return), and holdings that stopped trading. *Pending.*

---

## 2. Phase 1 — Buy-and-hold analysis

**Objective.** Describe how the current portfolio has behaved in risk and return,
whether it is actually diversified, and what the return series look like
statistically, as a foundation for later modelling.

**Method.**
- Per-holding statistics over each holding's full history, plus a common
  3-year window (fair like-for-like comparison).
- Portfolio = equal weight, monthly rebalance, vs VOO.
- Correlation matrix; diversification ratio; effective number of independent bets.
- Augmented Dickey-Fuller (ADF) test on log prices vs log returns; ACF/PACF
  and Ljung-Box tests (Shumway & Stoffer ch. 1–3).

> **📘 Concept — the risk/return metrics in one place.**
> - **CAGR** (compound annual growth rate): the steady yearly rate that would turn your start value into your end value.
> - **Volatility**: how much returns swing (standard deviation, annualised). About ⅔ of years land within ±1 volatility of the average.
> - **Sharpe ratio**: return above the risk-free rate per unit of volatility. Roughly: < 0.5 weak, ~1 good, > 1.5 rare for long periods.
> - **Sortino ratio**: like Sharpe, but only counts *downside* swings as risk.
> - **Max drawdown**: the worst fall from a previous peak. It tells you what you would have had to sit through.
> - **Beta**: sensitivity to the market. A beta of 1.5 tends to move 1.5% when the S&P moves 1%.
> - **CVaR 95%**: the average loss on the worst 5% of days.

> **📘 Concept — stationarity.** Prices wander (they "remember" where they
> were), so their average and spread change over time. That makes them
> *non-stationary*, and most statistical models give misleading answers on
> them. Returns usually *are* stationary. The ADF test checks this formally
> (p < 0.05 means "stationary"). This is why every model here uses returns.

**Results.** *Pending price data.* Will include: `p1_asset_stats`,
`p1_portfolio_vs_benchmark` (full period and 3 years), growth and drawdown
charts, return-contribution chart, correlation heatmap, ADF table,
ACF/PACF figure, Ljung-Box table.

**Interpretation.** *Pending.*

**Caveats.** Equal weight is an assumption, not your actual allocation. Holdings
with less than 3 years of history (OKLO, SOLS, PSKY) are excluded from the
3-year comparison and the correlation matrix.

---

## 3. Phase 2 — Portfolio optimisation

**Objective.** Find the weights that would have given the best risk-adjusted
return, and test whether that advantage survives when weights are chosen
*without hindsight*.

**Method.**
- **A. In-sample (textbook):** estimate expected returns and the covariance
  matrix on the last 3 years; 10,000 random portfolios; exact max-Sharpe and
  min-volatility solutions (SLSQP solver); efficient frontier. Long-only, with
  at most 25% in any single holding.
- **B. Out-of-sample (realistic):** every month, re-optimise using only the
  trailing 3 years, hold for a month, and charge trading costs.
- Covariance uses **Ledoit-Wolf shrinkage**, which pulls extreme correlation
  estimates toward a sensible average.

> **📘 Concept — why the in-sample answer flatters itself.** The optimiser
> treats historical average returns as known truths. They are very noisy
> estimates (a 3-year average return has a standard error of about ±15–20 percentage points
> for a typical stock). It will over-weight whatever happened to do well. Part B
> measures how much of the promised improvement is real.

**Results.** *Pending.* Tables `p2_insample_portfolios`, `p2_weights`,
`p2_oos_backtest`; charts `p2_frontier`, `p2_weights`, `p2_oos_growth`.

**Interpretation.** *Pending.*

---

## 4. Phase 3 — Signal research

**Objective.** Test whether any combination of free data predicts which
holdings will beat the portfolio average over the next 5 trading days.

**Method.**
- **25 features in 7 families:** momentum (1d–12m), oscillator (RSI), volatility,
  market-relative (beta, relative strength), volume, cross-sectional ranks,
  macro (VIX, term and credit spreads, rate changes). Definitions:
  [`src/pa/features.py`](../src/pa/features.py).
- **Target:** 5-day forward log return *minus the average holding's*. The
  question is which holdings to overweight, not where the market goes.
- **Models:** 12-1 momentum (no fitting; the baseline), AR(p) per asset
  (Shumway & Stoffer ch. 3), Ridge regression, XGBoost, LSTM, and a rank-average
  ensemble.
- **Walk-forward validation:** refit monthly on an expanding window. Training
  stops 5 days before each refit so no future returns leak in (purging). Two
  automated tests verify that changing future prices never changes any past
  prediction.

> **📘 Concept — the information coefficient (IC).** Each day, rank the
> holdings by the model's forecast and by what actually happened, then
> correlate the two rankings. IC = 0 is a coin flip; IC = 1 is perfect. In
> professional equity research **an IC of 0.02–0.05 that holds up out of sample
> is considered useful**, because small edges add up across many bets. We also
> report the **t-stat** (computed on non-overlapping 5-day periods; above ~2
> is unlikely to be luck) and the **hit rate** (share of correct
> beat-or-lag-the-average calls; 50% = no skill).

**Results.** *Pending.* Tables `p3_feature_ic` (with decay at 0–40 days),
`p3_regime_ic` (high vs low VIX), `p3_model_scores` (validation vs hold-out);
charts `p3_signal_decay`, `p3_rolling_ic`, `p3_xgb_importance`.

**Interpretation.** *Pending.*

**Caveats.** With 22 assets, the daily cross-section is small, so ICs are
noisy. That is why t-stats and the hold-out matter more than any single number.
Free data excludes the options, news-sentiment and short-interest features
originally planned with WRDS, LSEG and Bloomberg (§9).

---

## 5. Phase 4 — Risk management and position sizing

**Objective.** Turn forecasts into position sizes that survive trading costs
and bad periods.

**Method** (weekly rebalance; strategies compared on the same dates):
1. **Signal tilt:** start at equal weight; overweight holdings the model
   likes, underweight ones it dislikes (w ∝ 1 + 0.5·z-score).
2. **Volatility targeting:** scale total exposure so predicted portfolio
   volatility is 15%, using an exponentially weighted covariance matrix (recent
   data counts more). The rest sits in T-bills.
3. **Drawdown stop:** if the portfolio is down more than 20% from its peak,
   halve risk until the loss recovers to 10%.
4. **Half-Kelly sizing** as an alternative to (1).
5. Costs: see §1.2. Sensitivity at 0×, 1×, 2× and 4× costs.

> **📘 Concept — the Kelly criterion.** Kelly sizing grows wealth fastest *if
> you know your true edge*. You never do, and over-betting is far worse than
> under-betting. Practitioners therefore bet a fraction: **half-Kelly** keeps
> about ¾ of the growth with about ½ the volatility.

**Results.** *Pending.* Tables `p4_strategy_comparison`, `p4_cost_sensitivity`;
charts `p4_growth`, `p4_drawdown`.

---

## 6. Phase 5 — Black-Litterman with model views

**Objective.** Combine a neutral starting point with the model's views, in
proportion to how much the model has earned trust.

**Method.**
- **Prior:** the returns that would make the reference weights optimal
  (π = δΣw, δ = 2.5). The backtest uses equal weight as the reference, so no
  look-ahead from current market caps. Today's recommendation also shows the
  market-cap/AUM prior from Bigdata.com.
- **Views:** Grinold's rule α = IC × volatility × forecast z-score, using the
  model's **own trailing 1-year realised IC**. If the model has had no skill
  lately, α ≈ 0 and the allocation stays at the prior.
- **Blend** with τ = 0.05; Ω proportional to τΣ; mean-variance weights capped
  at 25% per holding.

> **📘 Concept — Black-Litterman in one sentence.** Start from "the market
> knows best", then tilt only as far as your evidence justifies. That avoids
> the extreme, unstable weights in Phase 2.

**Results.** *Pending.* Tables `p5_backtest`, `p5_recommendation`; charts
`p5_growth`, `p5_weights`.

---

## 7. Model governance and the self-improvement loop

| Control | Implementation |
|---|---|
| No look-ahead | Purged walk-forward; tests `test_features_have_no_lookahead`, `test_walk_forward_has_no_lookahead` |
| Hold-out discipline | Data from 2025-11-01 is never used for selection; it is reported at every check-in |
| Promotion rule | A challenger replaces the champion only if validation ICIR (IC information ratio: average IC divided by its volatility, annualised) improves by ≥ 0.05 |
| Multiple-testing awareness | Every experiment is logged in `results/metrics/scoreboard.jsonl`; total count reported at each check-in |
| Reproducibility | Fixed seeds; `run_all.sh`; parameters in `config.py` |

**Check-in log** (`results/metrics/checkins.md`) — appended automatically when
the champion model improves. *None yet.*

---

## 8. Limitations and disclosures

- **Educational research, not investment advice.** Backtests are hypothetical
  and benefit from hindsight in the choice of holdings (survivorship bias:
  today's holdings were chosen knowing they still exist).
- Equal-weight assumption (§1.2); trading costs are estimates; no taxes.
- Several holdings have short histories (OKLO since 2024, SOLS and PSKY since
  2025), which limits what can be estimated for them.
- Free data only. Options-implied volatility, professional news sentiment and
  short interest were not available (§9).

## 9. Changes from the original plan

| Original (README) | Now | Reason |
|---|---|---|
| WRDS/OptionMetrics, LSEG news, Bloomberg, Capital IQ | Yahoo Finance, FRED, Bigdata.com snapshot | Institutional access ended at graduation |
| Options & sentiment features | Price/volume/macro features; sentiment snapshot as a cross-check only | Free historical sentiment/options data is not available |
| Jupyter notebooks | Python pipelines + this report (charts in `results/figures`) | Reproducible end to end, testable, and runnable by the automated improvement loop |

## Glossary

**Basis point (bp):** 0.01%. **Covariance matrix:** how every pair of holdings
moves together. **Efficient frontier:** the best possible return for each level
of risk. **Ledoit-Wolf shrinkage:** blending a noisy estimate toward a simple,
stable one. **Look-ahead bias:** accidentally using information that was not
yet known at decision time. **Turnover:** share of the portfolio traded per year
(100% = the whole portfolio replaced once). **Walk-forward:** repeatedly
train on the past and test on the period just after it, like trading in real
time.

## References

Black & Litterman (1992), *FAJ*; Grinold & Kahn (2000), *Active Portfolio
Management*; He & Litterman (1999); Ledoit & Wolf (2004), *J. Multivariate
Analysis*; López de Prado (2018), *Advances in Financial Machine Learning*;
Markowitz (1952), *J. Finance*; Shumway & Stoffer (2017), *Time Series
Analysis and Its Applications*; Chen & Guestrin (2016), *KDD*; Hochreiter &
Schmidhuber (1997), *Neural Computation*.

*Market snapshot data from [Bigdata.com](https://bigdata.com) (underlying
providers include FMP).*
