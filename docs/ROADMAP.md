# TradePulse Roadmap

## Principles

- Build an analysis platform before considering automation.
- Keep data provenance explicit.
- Never present technical scores as win probabilities.
- Preserve separation between internal analysis directions and platform-specific trade actions.
- Validate strategies through backtesting and simulation before any real-operation discussion.

## Phase 1 — Core Market Analysis

### Completed

- Candle and signal domain models.
- Provider abstraction and mock provider.
- Binance Spot provider.
- Closed-candle protection.
- EMA indicator.
- EMA 9/21 crossover strategy.
- Internal LONG, SHORT, and NEUTRAL outcomes.
- Python CLI with JSON output.
- Node.js API bootstrap.
- Secure Node → Python bridge.
- Real Binance analysis endpoint.
- Input validation and request normalization for BTC-USDT and BTC/USD.
- Frontend typed API client.
- Frontend live-analysis panel.
- Frontend loading, retry, and error states.
- Display of source, timestamp, direction, score, reasons, strategy, and EMA periods.

### Next

- Real candle-data endpoint for the frontend chart.
- Provider capability metadata and asset catalog.
- Explicit frontend status for supported and unsupported assets.
- Replace mock chart values with data from the selected provider.
- Data freshness and stale-data handling.
- Frontend automated tests for the API client and live-analysis panel.
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

- Separate CALL, PUT, and WAIT domain contract.
- Asset, market, entry time, expiration, and rationale.
- Explicit mapping rules evaluated per provider and market.
- No automatic LONG → CALL or SHORT → PUT conversion.
- No substitute external data for platform-specific OTC prices.
- Manual-use workflows and simulation first.

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
- Position sizing simulation.
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

