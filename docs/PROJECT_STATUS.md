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
- Validated internal Signal domain model.
- Market-data provider abstraction.
- MockMarketDataProvider for deterministic tests.
- BinanceMarketDataProvider using public Spot market data.
- Protection against incomplete Binance candles.
- EMA indicator.
- EMA 9/21 crossover strategy.
- Internal directions: LONG, SHORT, and NEUTRAL.
- MarketAnalysisService.
- JSON command-line interface:
  - python -m app.cli.analyze_market
  - JSON success payload on stdout.
  - Structured JSON error payload on stderr.
Backend API
- Node.js, TypeScript, Express, Helmet, CORS, and Zod.
- Environment validation.
- Health endpoint:
  GET /api/v1/health
- Real market-analysis endpoint:
  GET /api/v1/market-analysis?symbol=BTC-USDT&timeframe=1h&limit=100
- Safe Node → Python communication through execFile.
- Separate command arguments without shell-string concatenation.
- Configurable process timeout.
- Validation of request input and Python response output.
- Supports both BTC-USDT and BTC/USD input formats.
- Slash-separated symbols are normalized to the internal BASE-QUOTE format before reaching the Quant Engine.
Frontend
- Existing React dashboard preserved.
- Typed frontend client for the real market-analysis endpoint.
- Live analysis panel connected to the backend.
- Loading, retry, and API-error states.
- Displays real:
  - Asset.
  - Timeframe.
  - Internal direction.
  - Technical score.
  - Last closed-candle timestamp in UTC.
  - Data source.
  - Strategy.
  - EMA periods.
  - Decision reasons.
- The live panel explicitly states that LONG, SHORT, and NEUTRAL are internal analysis outcomes and do not automatically mean CALL, PUT, or WAIT.
Current API Contract
Successful responses use this format:
{
  "data": {
    "symbol": "BTC-USD",
    "timeframe": "1h",
    "timestamp": "2026-11-01T14:00:00+00:00",
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

score represents technical-rule confluence only. It is not a probability of success, expected profit, or recommendation to trade.
Validation Status
- Python: 51 automated tests passing.
- Python Ruff: passing.
- Node.js: 7 automated tests passing.
- Node.js typecheck: passing.
- Node.js build: passing.
- Frontend ESLint: passing.
- Frontend build: passing.
- Real end-to-end analysis verified through:
  - Frontend request format: BTC/USD.
  - Backend normalization: BTC/USD → BTC-USD.
  - Quant Engine.
  - Binance Spot public market data.
Current UI Data Boundary
Only the Análise atual panel consumes the real backend endpoint.

The following dashboard elements are still based on local demonstration data and must not be presented as live market data:
- Candlestick chart.
- RSI chart.
- MACD chart.
- Asset-strip prices and variations.
- Scanner signals and scores.
- Signal history.
- Backtest metrics and performance curve.
- Technical-indicator summary cards.
Product Direction
TradePulse is being prepared for multiple market-data providers:
- Cryptocurrency.
- Forex.
- Indices.
- Commodities.
- Platform-specific OTC assets, only when reliable and authorized data is available.
The current LONG, SHORT, and NEUTRAL values are internal market-analysis outcomes.

Future IQ Option-oriented signals will use a separate product layer with:
- CALL.
- PUT.
- WAIT.
- Platform-specific asset identification.
- Entry time.
- Expiration.
- Rationale.
- Risk controls.
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
- Real historical dashboard.
- Real market chart endpoint.
- Alerts.

`docs/ROADMAP.md`

```md
# TradePulse Roadmap

## Principles

- Build an analysis platform before considering automation.
- Keep data provenance explicit.
- Never present technical scores as win probabilities.
- Preserve separation between internal analysis directions and platform-specific trade actions.
- Validate strategies through backtesting and simulation before any real-operation discussion.
- Do not represent mock data as live market data.