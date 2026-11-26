# Integridade dos dados

## Princípios aplicados

1. Dados simulados nunca são apresentados como reais. O código de produção **não tem transporte simulado**; os simuladores existem só nos testes.
2. Uma vela é "fechada" somente quando o seu horário de fechamento já passou no relógio de referência.
3. Uma análise antiga pode ser guardada, mas **nunca** é apresentada como atual.
4. Horários que a fonte não fornece ficam `null` e são marcados como tais.

## Velas abertas e fechadas

- A IQ Option devolve, em `get_candles`, as velas pedidas **incluindo a vela em formação**. O gateway separa:
  - **fechadas**: `to ≤ agora_referência`;
  - **em formação**: usada só como "preço observado" (`observedQuote`), nunca como dado de análise.
- Como a vela em formação conta dentro do limite pedido, o cache pede `N + 1` velas para entregar `N` fechadas (máximo 999).
- `agora_referência` é o **relógio do servidor IQ** quando a sessão já o recebeu (`get_server_timestamp`). Caso contrário, é o relógio UTC local. O campo `closedCandleClock` informa qual relógio foi usado.

## Cache de candles (worker)

- Chave: `ATIVO` + `timeframe`. Validade: enquanto a última vela fechada do cache for a vela mais nova possível (`latest_expected_close`).
- Ao passar uma fronteira de vela, a próxima leitura volta à IQ.
- Se a IQ ainda não publicou a vela recém-fechada, as novas leituras são **espaçadas por no mínimo 1 s** (`IQ_GATEWAY_MIN_REFETCH_SECONDS`). Cada resultado informa `freshness = CURRENT | AWAITING_CLOSE_PUBLICATION`.

## Atualidade no backend (calculada a cada leitura)

| `dataState` | Condição |
|---|---|
| `CURRENT` | Fechamento da vela publicada = fechamento mais recente possível |
| `AWAITING_NEW_CANDLE` | A vela publicada é exatamente a anterior (nova vela ainda não disponível) |
| `STALE` | Mais antiga que isso |
| `NO_DATA` | Nada publicado ainda |

O campo `state` do motor M5 (`UPDATED`, etc.) também é **recalculado na leitura**. Isso elimina o
defeito em que o cache anterior servia a vela anterior como `UPDATED` por 90 s.

A estratégia M1 considera os dados atuais por **um timeframe inteiro** (60 s no M1, 300 s no M5),
em vez do limite fixo de 120 s que transformava todo M5 em WAIT depois de 2 minutos.

## Horários registrados

| Campo | Tipo | Origem |
|---|---|---|
| `candleOpenTime` | observado | campo `from` da IQ |
| `candleCloseTime` | derivado | abertura + intervalo (`DERIVED_OPEN_PLUS_INTERVAL`) |
| `sourceCloseTime` | observado | campo `to` da IQ (nos metadados de coleta) |
| `dataRequestedAt` / `dataReceivedAt` | observado | relógio local do worker |
| `analysisStartedAt` / `analysisCompletedAt` | observado | relógio local do worker |
| `publishedAt` | observado | relógio local do backend |
| `observedQuote.sourceTimestamp` | observado (fonte) | campo `at` da vela em formação, quando presente |
| `iqCandleAvailabilityAt` | **indisponível** | a IQ não informa quando a vela fica disponível |
| `serverClockOffsetMs` | observado | diferença entre o relógio do servidor IQ e o local |

Latências: `collectionLatencyMs` (requisição → resposta da IQ), `processingLatencyMs` (análise no worker),
`gatewayRoundTripMs` e `totalLatencyFromCloseMs` (fechamento da vela → publicação).

## Identificador de vela

`ATIVO:TIMEFRAME:ABERTURA_EPOCH_SEGUNDOS`, por exemplo `GBPUSD-OTC:5m:1795694700`.

## Dados persistidos

| Local | Conteúdo | Git |
|---|---|---|
| `quant-engine/data/iq-option-demo-binary-signals/` | Referências CALL/PUT do M1 e liquidação | ignorado |
| `quant-engine/data/iq-option-demo-m5-validations/` | Candidatos M5 alinhados ao M15 | ignorado |
| `backend/data/runtime/publications.jsonl` | Uma linha por publicação (horários, latência, diagnóstico) | ignorado |
| `backend/data/validation/` | Relatórios do `npm run validate:live` | ignorado |

## Limitações conhecidas

- O M1 não verifica lacunas entre velas; o M5 e o M15 verificam (`candlesContiguous`).
- A EMA 200 usa 260 velas; a semente por média simples ainda pesa cerca de 55% (revisão matemática no próximo bloco).
- O gráfico M5 é agregado de 100 velas M1 no navegador (cerca de 20 velas M5).
- A IQ pode publicar a vela fechada com atraso; esse atraso aparece em `attempts` e na latência total, mas o instante exato de disponibilidade não é medido pela fonte.
