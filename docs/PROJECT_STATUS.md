# TradePulse Project Status

_Last updated: 2026-11-01_

## Purpose

TradePulse is a market-analysis platform designed to evolve into a multi-market signal product.

The current implementation focuses on analysis and manual decision support. It does not execute trades, connect to IQ Option accounts, or claim prediction accuracy.

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
- Deterministic MockMarketDataProvider.
- BinanceMarketDataProvider using public Spot market data.
- Protection against incomplete Binance candles.
- EMA indicator.
- EMA 9/21 crossover strategy.
- Internal directions: LONG, SHORT, and NEUTRAL.
- MarketAnalysisService.
- JSON command-line interfaces:
  - python -m app.cli.analyze_market
  - python -m app.cli.get_candles
- Structured JSON success output on stdout and error output on stderr.
- Product-level IQ Option signal foundation:
  - TradeSignal.
  - MarketCategory: CRYPTO, FOREX, INDEX, COMMODITY, and OTC.
  - TradeAction: CALL, PUT, and WAIT.
  - SignalPlatform.IQ_OPTION.
  - Entry and expiration validation for actionable signals.
  - IqOptionSignalService.
- The current IQ Option preparation service intentionally returns WAIT.
- No automatic mapping exists from LONG to CALL or from SHORT to PUT.
Backend API
- Node.js, TypeScript, Express, Helmet, CORS, and Zod.
- Environment validation.
- Health endpoint:
  GET /api/v1/health
- Real market-analysis endpoint:
  GET /api/v1/market-analysis?symbol=BTC-USDT&timeframe=1h&limit=100
- Real candle-data endpoint:
  GET /api/v1/market-data/candles?symbol=BTC-USD&timeframe=1h&limit=100
- Safe Node → Python communication through execFile.
- Separate command arguments without shell-string concatenation.
- Configurable process timeout.
- Validation of request input and Python response output.
- Supports BTC-USDT and BTC/USD input formats.
- Slash-separated symbols are normalized to the internal BASE-QUOTE format before reaching the Quant Engine.
Frontend
- Existing React dashboard preserved.
- Typed frontend client for the real market-analysis endpoint.
- Typed frontend client for the real candle-data endpoint.
- Live analysis panel connected to the backend.
- Live candlestick chart connected to the backend.
- Loading, retry, and API-error states.
- Displays real:
  - Asset.
  - Timeframe.
  - Closed candles.
  - Internal direction.
  - Technical score.
  - Last closed-candle timestamp in UTC.
  - Data source.
  - Strategy.
  - EMA periods.
  - Decision reasons.
- The live panel explicitly states that LONG, SHORT, and NEUTRAL are internal analysis outcomes and do not automatically mean CALL, PUT, or WAIT.
Current API Contracts
Market analysis
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

Market candles
{
  "data": {
    "symbol": "BTC-USD",
    "timeframe": "1h",
    "source": "binance_spot",
    "candles": [
      {
        "timestamp": "2026-11-01T14:00:00+00:00",
        "open": 78035.45,
        "high": 78123.52,
        "low": 77922.99,
        "close": 78055.84,
        "volume": 291.25664
      }
    ]
  }
}

A technical score represents rule confluence only. It is not a probability of success, expected profit, or recommendation to trade.
Current UI Data Boundary
The following dashboard elements consume real Binance Spot data through the backend:
- Live candlestick chart.
- Live market-analysis panel.
- Closed-candle timestamp.
- Data source.
- Internal EMA crossover result.
The following dashboard elements are still local demonstration data and must not be presented as live market data:
- RSI chart.
- MACD chart.
- Asset-strip prices and variations.
- Scanner signals and scores.
- Signal history.
- Backtest metrics and performance curve.
- Technical-indicator summary cards.
IQ Option Direction
TradePulse is being prepared for multiple market-data providers:
- Cryptocurrency.
- Forex.
- Indices.
- Commodities.
- Platform-specific OTC assets, only when reliable and authorized data is available.
The current LONG, SHORT, and NEUTRAL values are internal market-analysis outcomes.

The new product-level contract supports CALL, PUT, and WAIT, but the current service always emits WAIT because no IQ Option market policy has been implemented or validated.

A Binance LONG must never be treated automatically as an IQ Option CALL. A Binance SHORT must never be treated automatically as an IQ Option PUT. OTC prices must not be inferred from other markets.
Validation Status
- Python: 63 automated tests passing.
- Python Ruff: passing.
- Node.js: 12 automated tests passing.
- Node.js typecheck: passing.
- Node.js build: passing.
- Frontend ESLint: passing.
- Frontend build: passing.
- Real end-to-end market analysis verified through:
  - Frontend request format: BTC/USD.
  - Backend normalization: BTC/USD → BTC-USD.
  - Quant Engine.
  - Binance Spot public market data.
- Real end-to-end candle chart verified through:
  - Frontend.
  - Backend candle endpoint.
  - Quant Engine candle CLI.
  - Binance Spot public market data.
Explicitly Not Implemented
- IQ Option login or automation.
- Trade execution.
- CALL/PUT recommendation policy.
- Forex, indices, commodities, or OTC providers.
- Backtesting engine.
- Paper trading.
- PostgreSQL persistence.
- Authentication and user accounts.
- Real RSI, MACD, or technical-summary dashboard values.
- Alerts.

### `docs/ROADMAP.md`

```md
# TradePulse Roadmap

## Principles

- Build an analysis platform before considering automation.
- Keep data provenance explicit.
- Never present technical scores as win probabilities.
- Preserve separation between internal analysis directions and platform-specific trade actions.
- Validate strategies through backtesting and simulation before any real-operation discussion.
- Do not represent mock data as live market data.
- Do not infer OTC prices from a different market or provider.

## Phase 1 — Core Market Analysis

### Completed

- Candle and internal signal domain models.
- Provider abstraction and mock provider.
- Binance Spot provider.
- Closed-candle protection.
- EMA indicator.
- EMA 9/21 crossover strategy.
- Internal `LONG`, `SHORT`, and `NEUTRAL` outcomes.
- Python JSON market-analysis CLI.
- Python JSON candle-data CLI.
- Node.js API bootstrap.
- Secure Node → Python bridge.
- Real Binance analysis endpoint.
- Real Binance candle-data endpoint.
- Input validation and request normalization for `BTC-USDT` and `BTC/USD`.
- Frontend typed API clients.
- Frontend live-analysis panel.
- Frontend live candlestick chart.
- Frontend loading, retry, and error states.
- Display of source, timestamp, direction, score, reasons, strategy, EMA periods, and closed candles.

### Next

- Provider capability metadata and asset catalog.
- Explicit frontend status for supported and unsupported assets.
- Data freshness and stale-data handling.
- Replace mock dashboard indicators with real computed values or clearly hide them.
- Real asset-strip prices and variations.
- Frontend automated tests for API clients and live components.
- Shared frontend/backend contract package or generated contract.

## Phase 2 — Market Provider Expansion

- Provider capability metadata.
- Forex provider with authorized and reliable data.
- Indices provider.
- Commodities provider.
- Symbol normalization by provider and market.
- Market calendar and trading-session awareness where applicable.
- Data freshness monitoring.
- Platform-specific OTC provider only when trustworthy and authorized data exists.

## Phase 3 — IQ Option Signal Layer

### Completed

- Separate `TradeSignal` domain contract.
- `CALL`, `PUT`, and `WAIT` actions.
- Asset, market category, timeframe, timestamp, source, entry time, expiration time, and rationale fields.
- Explicit separation between internal analysis direction and product-level action.
- Validation that `WAIT` cannot define entry or expiration.
- Validation that `CALL` and `PUT` require valid entry and expiration times.
- Initial `IqOptionSignalService`.
- Safe default behavior: `WAIT`.
- Tests proving no automatic `LONG → CALL` or `SHORT → PUT` conversion.

### Next

- Define policy interfaces per market and provider.
- Define eligibility requirements for a manual signal.
- Define entry-time and expiration rules by timeframe.
- Add a manual-review workflow.
- Add source-specific constraints for IQ Option assets.
- Add audit fields and immutable signal identifiers.
- Keep OTC unavailable until a reliable and authorized OTC source exists.

## Phase 4 — Indicator and Strategy Library

- RSI.
- MACD.
- Bollinger Bands.
- Candlestick patterns.
- Support and resistance.
- Multi-timeframe context.
- Configurable strategies.
- Strategy confluence and explainability.

## Phase 5 — Backtesting and Evaluation

- Historical datasets.
- Event ordering without look-ahead bias.
- Transaction costs where applicable.
- Payout and expiration models for binary-option simulations.
- Out-of-sample validation.
- Performance metrics.
- Risk and drawdown metrics.
- Strategy comparison.

## Phase 6 — Paper Trading and Risk Controls

- Paper trading portfolio.
- Position-sizing simulation.
- Daily and weekly exposure limits.
- Cooldown rules.
- Loss limits.
- Audit trail.
- Alert simulation.

## Phase 7 — Platform Product Features

- PostgreSQL and Prisma persistence.
- Users and authentication.
- Signal history.
- Watchlists.
- Saved strategy configurations.
- Alerts and notifications.
- Dashboard analytics.
- Provider health monitoring.

## Phase 8 — Automation Assessment

Automation is not currently planned for implementation.

Before any discussion of order execution, the project must evaluate:

- Official platform permissions and API availability.
- Legal and regulatory requirements.
- Account and user authorization.
- Security model.
- Operational risk.
- Strategy validation results.
- Paper-trading results.