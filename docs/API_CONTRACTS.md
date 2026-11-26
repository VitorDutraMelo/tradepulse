# Contratos da API

Base: `http://127.0.0.1:3001` (somente loopback). Somente `GET` é aceito pelo CORS.
Erros seguem `{ "error": { "code": string, "message": string } }`.

## Novos (A.1/A.2)

### `GET /api/v1/iq-option/demo/live?symbol=&timeframe=`

- `symbol`: um dos 8 ativos OTC; `timeframe`: `1m` ou `5m` (M5 apenas `GBPUSD-OTC`).
- A primeira leitura cria a inscrição; o backend passa a analisar cada fechamento de vela desse par.
- A leitura **nunca** espera uma análise e nunca chama a IQ diretamente.

```jsonc
{
  "data": {
    "strategy": { "id": "m1-trend-ema9-21-rsi-adx-atr", "version": "1.1.0", "label": "…",
                  "timeframe": "1m", "experimentalEngine": false,
                  "methodology": "PROVISIONAL_NOT_APPROVED", "operational": false },
    "symbol": "EURUSD-OTC", "timeframe": "1m",
    "observedAt": "…", "expectedLatestCloseTime": "…", "nextCloseTime": "…",
    "dataState": "CURRENT | AWAITING_NEW_CANDLE | STALE | NO_DATA",
    "cycle": { "running": false, "forCandleClose": null, "attempts": 0, "lastAttemptAt": null },
    "lastError": null | { "code": "IQ_OPTION_RECONNECT_BACKOFF", "message": "…", "at": "…", "retryAt": "…" },
    "gateway": { "workerState": "READY", "sessionState": "CONNECTED", "accountMode": "PRACTICE",
                 "lastErrorCode": null, "nextReconnectAt": null },
    "publication": null | {
      "candleId": "EURUSD-OTC:1m:1795694520",
      "candleOpenTime": "…", "candleCloseTime": "…", "publishedAt": "…",
      "timing": { "clock": "LOCAL_UTC_CLOCK", "serverClockOffsetMs": 0,
                  "candleCloseTimeKind": "DERIVED_OPEN_PLUS_INTERVAL", "scheduledFor": "…",
                  "dataRequestedAt": "…", "dataReceivedAt": "…", "dataReceivedAtKind": "OBSERVED_LOCAL_CLOCK",
                  "analysisStartedAt": "…", "analysisCompletedAt": "…", "publishedAt": "…",
                  "collectionLatencyMs": 0, "processingLatencyMs": 0, "gatewayRoundTripMs": 0,
                  "totalLatencyFromCloseMs": 0, "attempts": 1, "cacheHit": false,
                  "iqCandleAvailabilityAt": null, "iqCandleAvailabilityKind": "NOT_AVAILABLE_FROM_IQ_OPTION_API" },
      "signal": { "action": "CALL|PUT|WAIT", "engineAction": "CALL|PUT|WAIT",
                  "status": "WAIT|EXPERIMENTAL_CANDIDATE|LATE_NOT_ACTIONABLE|EXPIRED|NOT_CURRENT",
                  "operational": false, "timeliness": "ON_TIME|LATE",
                  "publicationDelayMs": 0, "toleranceMs": 10000, "toleranceKind": "PROVISIONAL_EXPERIMENTAL",
                  "theoreticalEntryTime": "…", "theoreticalEntryKind": "REFERENCE_CANDLE_CLOSE",
                  "theoreticalExpirationTime": "…", "theoreticalReferencePrice": 1.1,
                  "theoreticalReferencePriceKind": "REFERENCE_CANDLE_CLOSE",
                  "observedQuoteAtPublication": { "price": 1.1, "sourceTimestamp": "…", "sourceTimestampKind": "OBSERVED_SOURCE", "observedAt": "…" },
                  "reasons": ["…"] },
      "analysis": { /* payload original da estratégia (contratos abaixo) */ }
    }
  }
}
```

Códigos HTTP: `400` (parâmetros), `422` (`STRATEGY_NOT_AVAILABLE_FOR_SYMBOL|TIMEFRAME`),
`429` (`LIVE_SUBSCRIPTION_LIMIT`), `503` (gateway parado).

### `GET /api/v1/iq-option/demo/status`

`{ data: { gateway: {workerState, workerPid, workerStarts, workerCrashes, queue, requests, lastErrorCode, session, nextRestartAt}, clockOffsetMs, publications, subscriptions[] } }`.
`session` contém `state`, `accountMode`, `credentialsConfigured` (booleano), contadores de login e
reconexão e o desvio do relógio. **Nunca contém e-mail, senha, token ou ssid.**

### `GET /api/v1/health`

`{ status: "ok", service, iqGateway: { workerState, sessionState } }`. Indica a API viva, não que a IQ está disponível.

## Existentes (agora servidos pelo gateway)

| Endpoint | Mudança |
|---|---|
| `GET /demo/market-analysis` | Mesmo contrato; usa a sessão persistente. `entryTime` = fechamento da vela de referência |
| `GET /demo/candles` | Mesmo contrato; servido pelo cache de candles |
| `GET /demo/m5-sync` | Mesmo contrato; usa a sessão persistente |
| `GET /demo/m5-signal` | Contrato original **mais** o campo `live` (dataState, strategy, publication). `state` é recalculado na leitura; aguarda até 20 s pela análise em andamento |
| `GET /demo/m5-validations`, `/demo/binary-signals`, `/demo/analyses` | Sem mudança (leitura de arquivos locais) |
| `/api/v1/market-analysis`, `/market-data`, `/iq-option/signals` | Sem mudança (Binance, legado) |
| `/api/v1/iq-option/real/*` | **Removido da API** (módulo isolado, não montado) |

## Protocolo do worker (interno)

JSON por linha em stdin/stdout de `python -m app.gateway.worker`. Comandos permitidos:
`status`, `candles`, `analyze_m1`, `analyze_m5`, `m5_sync`, `shutdown`. Qualquer outro comando é rejeitado com
`INVALID_GATEWAY_REQUEST`. Códigos de erro: `IQ_OPTION_CREDENTIALS_MISSING`, `IQ_OPTION_AUTH_FAILED`,
`IQ_OPTION_PRACTICE_NOT_CONFIRMED`, `IQ_OPTION_RECONNECT_BACKOFF` (com `retryAt`), `IQ_OPTION_UNAVAILABLE`,
`IQ_OPTION_TIMEOUT`, `IQ_OPTION_CONNECT_HUNG`, `IQ_OPTION_DATA_NOT_FOUND`, `GATEWAY_INTERNAL_ERROR`. No
backend: `GATEWAY_QUEUE_FULL`, `GATEWAY_REQUEST_CANCELLED`, `GATEWAY_RESTART_BACKOFF`, `GATEWAY_WORKER_EXITED`, `GATEWAY_STOPPED`.
