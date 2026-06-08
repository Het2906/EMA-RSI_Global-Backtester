# EMA + RSI Global Index Backtester

An algorithmic trading backtester implementing an **EMA crossover + RSI momentum strategy** across **10 global stock market indexes** with a **$10M virtual portfolio** ($1M per index).

---

## Indexes Traded

| Country | Index | Ticker |
|---|---|---|
| USA | S&P 500 | ^GSPC |
| India | BSE Sensex | ^BSESN |
| UK | FTSE 100 | ^FTSE |
| Germany | DAX | ^GDAXI |
| Japan | Nikkei 225 | ^N225 |
| France | CAC 40 | ^FCHI |
| Hong Kong | Hang Seng | ^HSI |
| Brazil | IBOVESPA | ^BVSP |
| Canada | S&P/TSX | ^GSPTSE |
| Australia | S&P/ASX 200 | ^AXJO |

---

## Strategy

### Indicators
- **EMA 9** — Fast exponential moving average (short-term trend)
- **EMA 21** — Slow exponential moving average (medium-term trend)
- **RSI 14** — Relative Strength Index (momentum, 0–100)

### Signal Rules

| Signal | Condition |
|---|---|
| **LONG** | EMA9 > EMA21 and RSI between 40–65 |
| **SHORT** | EMA9 < EMA21 and RSI > 70 (capped at 10% of portfolio) |
| **CASH** | All other conditions |

### Dynamic Position Sizing

Allocation scales down as RSI rises — reducing exposure at overheated levels.

| RSI Range | Allocation |
|---|---|
| RSI < 45 | 80% |
| RSI 45–55 | 60% |
| RSI 55–65 | 40% |
| RSI ≥ 65 | 20% |

Positions only rebalance when drift exceeds **1%** of portfolio value, minimising unnecessary churn.

---

## Risk Management

- Allocation always calculated as a percentage of **current** portfolio value — no over-investment
- Existing positions are closed before any new signal is entered
- Short positions are hard-capped at **10%** of portfolio
- Trading halts if portfolio value reaches **$0**
- Cash mode is forced if capital falls below **$100**
- Margin call protection triggers if short losses drive cash negative

---

## Results (2006–2025)

| Country | Total Return | Sharpe Ratio | Max Drawdown |
|---|---|---|---|
| Brazil | +150.2% | 1.21 | -7.5% |
| India | +138.9% | 1.13 | -9.3% |
| UK | +136.4% | 1.05 | -12.3% |
| Australia | +82.0% | 0.91 | -15.6% |
| Hong Kong | +77.7% | 0.70 | -18.5% |
| Canada | +58.4% | 0.65 | -12.7% |
| USA | +47.5% | 0.62 | -18.0% |
| France | +46.2% | 0.59 | -16.5% |
| Germany | +38.7% | 0.49 | -26.8% |
| Japan | +27.9% | 0.42 | -20.9% |

> **Sharpe > 1.0** achieved in Brazil, India, and UK — indicating strong risk-adjusted returns over the 19-year period.
---
*Built as a portfolio project demonstrating algorithmic strategy design, financial data analysis, risk management, and Python engineering.*