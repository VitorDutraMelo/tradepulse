# Arquitetura

_Estado: blocos A.1 + A.2 (26/11/2026). Reflete o código da branch `feat/tradepulse-v2-frontend`._

## Visão geral

```
┌────────────────────────────┐   GET /api/v1/iq-option/demo/live (a cada 2 s, só leitura local)
│ Frontend React 18 + Vite 6 │──────────────────────────────────────────────┐
│ PWA (manifest + SW)        │   GET /api/v1/iq-option/demo/candles (10 s)  │
└────────────────────────────┘                                              ▼
                                         ┌──────────────────────────────────────────────────┐
                                         │ Backend Express 5 (127.0.0.1:3001, loopback)     │
                                         │                                                  │
                                         │  LiveAnalysisService                             │
                                         │   · inscrições (ativo + timeframe + estratégia)  │
                                         │   · dispara em cada fechamento de vela           │
                                         │   · retentativa controlada até a vela existir    │
                                         │   · 1 publicação por vela; estado na leitura     │
                                         │           │                                      │
                                         │  GatewayWorker (fila 1-em-voo, dedupe, limite,   │
                                         │   cancelamento, timeout → reinício com backoff)  │
                                         └───────────┼──────────────────────────────────────┘
                                                     │ JSON-lines (stdin/stdout)
                                         ┌───────────▼──────────────────────────────────────┐
                                         │ Worker Python persistente (app.gateway.worker)    │
                                         │  IqSession: 1 login, PRACTICE verificado,         │
                                         │   reconexão com backoff, relógio do servidor IQ   │
                                         │  CandleCache: chave = ativo/timeframe/última vela │
                                         │  SessionBackedProvider → estratégias existentes:  │
                                         │   M1 (IqOptionTrendStrategy) · M5+M15 · M5 sync   │
                                         │  Repositórios JSON (data/, fora do Git)           │
                                         └───────────┬──────────────────────────────────────┘
                                                     │ websocket (iqoptionapi, não oficial)
                                               IQ Option PRACTICE
```

## Componentes

### Frontend (`frontend/`)

- `src/App.tsx`: painéis (1, 2 ou 4). Cada painel lê `/live` e mostra o estado publicado pelo backend.
  **O frontend não decide se uma análise é atual**; ele exibe `dataState` e `signal.status`.
- `src/live.ts`: cliente tipado de `/live` e textos de estado.
- `src/components/charts/`: gráfico SVG. O M1 vem da IQ e o M5 é agregado de M1 no navegador (decisão N.17 pendente).
- `public/sw.js`: service worker que **não guarda respostas da API** em cache.

### Backend (`backend/`)

| Módulo | Função |
|---|---|
| `modules/iq-gateway/gateway-worker.ts` | Processo Python único; fila limitada; deduplicação por chave; cancelamento; timeout que reinicia o worker; logs redigidos |
| `modules/iq-gateway/live-analysis.service.ts` | Agendador por fechamento de vela; retentativas; publicação; atualidade e validade calculadas na leitura; log JSONL |
| `modules/iq-gateway/strategies.ts` | Registro de estratégias por timeframe (id, versão, comando, validação do contrato) |
| `modules/iq-gateway/gateway-analysis.client.ts` | Endpoints IQ existentes servidos pelo gateway |
| `modules/iq-gateway/iq-gateway.router.ts` | `/status` e `/live` |
| `modules/market-analysis/python-quant-engine.client.ts` | Executor CLI legado (Binance e leitura de históricos locais; **não faz login na IQ**) |
| `modules/iq-option-real-trading/` | **Isolado e não montado** (ver SECURITY.md) |

### Motor quantitativo (`quant-engine/`)

| Pacote | Função |
|---|---|
| `app/gateway/` | Worker, sessão, transporte somente-leitura, cache, provedor, redação |
| `app/strategies/iq_option_trend_strategy.py` | Estratégia M1 (regras preservadas) |
| `app/cli/get_iq_option_demo_m5_signal*.py`, `iq_option_demo_m15_context.py` | Motor M5 experimental e contexto M15 |
| `app/repositories/` | Persistência JSON de referências M1 e validações M5 |
| `app/indicators/` | EMA, RSI, ADX, ATR (o M5 ainda tem cópias próprias; consolidação no próximo bloco) |

## Fluxo de uma vela (M5, exemplo)

1. 12:05:00.000 (relógio local + desvio do servidor IQ): o agendador da inscrição `GBPUSD-OTC 5m` dispara.
2. Ele pede `analyze_m5` ao gateway. O worker lê M5 (260) e M15 (260) pela sessão aberta; a leitura M5 da liquidação vem do cache.
3. Se a vela das 12:05 ainda não existe na IQ, o resultado traz a vela anterior. O serviço tenta de novo em 0,5 s, 1 s, 1 s, 2 s, 3 s, 5 s… até a vela aparecer ou até 12:10.
4. Quando a vela existe, o resultado é publicado com horários observados e a latência.
5. Cada leitura de `/live` recalcula `dataState` e `signal.status` com o relógio atual.

## Concorrência e carga sobre a IQ Option

| Situação | Antes (A.0 rev. 1) | Agora |
|---|---|---|
| Logins por requisição M1 | 1 | 0 (sessão reutilizada) |
| Logins por requisição M5+M15 | 3 | 0 (2 leituras; a terceira vem do cache) |
| Gráfico | 1 login a cada 60 s por painel, fora de fila | Cache por vela; sem login |
| Requisições simultâneas à IQ | até 3 trilhas | 1 por vez, fila limitada |
| Repetição da mesma análise | a cada consulta | 1 por vela por inscrição |

Os números "antes" vêm da leitura do código e da reprodução da auditoria. Os números "agora" vêm dos
testes automatizados com transporte simulado. **A contagem real de logins depende da validação do proprietário.**

## Decisões

Ver [docs/adr/](adr/).
