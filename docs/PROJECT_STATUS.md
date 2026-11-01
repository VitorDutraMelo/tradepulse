# TradePulse Project Status

_Last updated: 2026-11-01_

## Purpose

TradePulse is a market-analysis platform designed to evolve into a multi-market signal product.

The current implementation focuses on analysis and manual decision support. It does not execute trades, connect to IQ Option accounts, or claim any prediction accuracy.

## Current Architecture

```text
Frontend React/TypeScript
        ↓
Backend Node.js/TypeScript/Express
        ↓
Quant Engine Python
        ↓
Market Data Providers
        ↓
Binance Spot public market data

Implemented
Quant Engine
- Validated Candle domain model.
- Validated internal Signal model.
- Market data provider abstraction.
- MockMarketDataProvider for deterministic tests.
- BinanceMarketDataProvider using public Spot market data.
- Protection against using incomplete Binance candles.
- EMA indicator.
- EMA 9/21 crossover strategy.
- Internal directions: LONG, SHORT, and NEUTRAL.
- MarketAnalysisService.
- JSON command-line interface:
  - python -m app.cli.analyze_market
  - JSON success payload on stdout.
  - Structured JSON error payload on stderr.
Backend API
- Node.js, TypeScript, Express, Helmet, CORS, Zod.
- Environment validation.
- Health endpoint:
  GET /api/v1/health
- Real market analysis endpoint:
  GET /api/v1/market-analysis?symbol=BTC-USDT&timeframe=1h&limit=100
- Secure Node → Python communication through execFile.
- Separate command arguments without shell string concatenation.
- Configurable process timeout.
- Validation of both request input and Python response output.
Current API Contract
Successful responses use this format:
{
  "data": {
    "symbol": "BTC-USDT",
    "timeframe": "1h",
    "timestamp": "2026-11-01T12:00:00+00:00",
    "direction": "NEUTRAL",
    "score": 20,
    "reasons": [
      "No EMA 9/21 crossover detected"
    ],
    "source": "binance_spot",
    "strategy": "ema_crossover",
    "indicators": {
      "fastEmaPeriod": 9,
      "slowEmaPeriod": 21
    }
  }
}

score represents technical-rule confluence only. It is not a probability of success or expected profit.
Validation Status
- Python: 51 automated tests passing.
- Python Ruff: passing.
- Node.js: 6 automated tests passing.
- Node.js typecheck: passing.
- Node.js build: passing.
- Real end-to-end analysis verified through the Node API and Binance Spot data.
Product Direction
TradePulse is being prepared for multiple market-data providers:
- Cryptocurrency
- Forex
- Indices
- Commodities
- Platform-specific OTC assets, only when reliable and authorized data is available
The current LONG, SHORT, and NEUTRAL values are internal market-analysis outcomes.

Future IQ Option-oriented signals will use a separate product layer with:
- CALL
- PUT
- WAIT
- Platform-specific asset identification
- Entry time
- Expiration
- Rationale
- Risk controls
A Binance LONG must never be treated automatically as an IQ Option CALL. OTC prices must not be inferred from other markets.
Explicitly Not Implemented
- IQ Option login or automation.
- Trade execution.
- CALL/PUT recommendation engine.
- Forex, indices, commodities, or OTC providers.
- Backtesting engine.
- Paper trading.
- PostgreSQL persistence.
- Authentication and user accounts.
- Alerts and historical dashboard.

`docs/ROADMAP.md`

```md
# TradePulse Roadmap

## Principles

- Build an analysis platform before considering automation.
- Keep data provenance explicit.
- Never present technical scores as win probabilities.
- Preserve separation between internal analysis directions and platform-specific trade actions.
- Validate strategies through backtesting and simulation before any