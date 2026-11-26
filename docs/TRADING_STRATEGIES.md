# Estratégias

> Nenhuma estratégia abaixo tem validação estatística. CALL e PUT são **cenários técnicos**, não
> recomendações, probabilidades ou promessas de resultado.

## Separação por timeframe

O backend tem um registro de estratégias (`backend/src/modules/iq-gateway/strategies.ts`):

| Id | Versão | Timeframe | Ativos | Comando do worker |
|---|---|---|---|---|
| `m1-trend-ema9-21-rsi-adx-atr` | 1.1.0 | 1m | 8 OTC | `analyze_m1` |
| `m5-ema200-rsi14-macd-m15` | 0.1.0-experimental | 5m | GBPUSD-OTC | `analyze_m5` |

O painel M5 usa **somente** o motor M5. A estratégia M1 não é mais apresentada como "M5". O endpoint
legado `/demo/market-analysis?timeframe=5m` ainda aplica a estratégia M1 em 5m e existe apenas por
compatibilidade.

## M1 — `IqOptionTrendStrategy` (regras preservadas)

| Regra | Valor |
|---|---|
| Velas mínimas | 29 fechadas (o gateway lê 120) |
| Atualidade | idade da última vela ≤ 1 timeframe (**alterado em A.2**; antes 120 s fixos) |
| Separação das EMAs | `|EMA9 − EMA21| / ATR14 ≥ 0,15`, senão WAIT |
| Força | `ADX14 ≥ 20`, senão WAIT |
| CALL | `EMA9 > EMA21` e `52 ≤ RSI14 ≤ 68` |
| PUT | `EMA9 ≤ EMA21` e `32 ≤ RSI14 ≤ 48` |
| Entrada / expiração | fechamento da vela de referência / +1 vela (**alterado em A.2**, ver SIGNAL_LIFECYCLE.md) |

Versão 1.0.0 → 1.1.0: muda só a parte temporal (entrada e atualidade). Os indicadores, os limiares e
a lógica de decisão são idênticos; o teste `test_m1_decision_rules_are_unchanged` protege esses valores.

## M5 — motor experimental (preservado sem alterações de regra)

Arquivo: `quant-engine/app/cli/get_iq_option_demo_m5_signal.py`.

| Componente | Regra |
|---|---|
| Dados | 250 velas M5 fechadas, contíguas, estado `UPDATED` (lê 260) |
| ATR 14 | > 0; distância `|close − EMA200| / ATR14 ≥ 0,20` |
| ADX 14 | ≥ 20 |
| CALL | close > EMA 200; 55 ≤ RSI ≤ 68; MACD > sinal; histograma > 0 e subindo |
| PUT | close < EMA 200; 32 ≤ RSI ≤ 45; MACD < sinal; histograma < 0 e caindo |
| Saída | `decision.action = "WAIT"` sempre; candidato em `candidateAction` |

ADX e ATR **não fazem parte** do conjunto aprovado (EMA 200, RSI 14, MACD + M15). Eles foram mantidos
porque as diretrizes proíbem remover filtros sem aprovação (decisão N.8).

## M15 — contexto (preservado)

Arquivo: `quant-engine/app/cli/iq_option_demo_m15_context.py`.

- **BULLISH:** close > EMA 200 (M15), EMA 200 maior que 3 velas antes, e estrutura "topos e fundos ascendentes" (swings estritos com raio 2).
- **BEARISH:** o simétrico.
- **NEUTRAL:** qualquer outro caso, ou dados insuficientes, com lacuna, ou não atualizados.
- Usa apenas velas M15 fechadas. Não há informação futura: um swing só é confirmado 2 velas depois.
- CALL exige BULLISH; PUT exige BEARISH; caso contrário o candidato vira WAIT.

## Por que o motor M5 fica em WAIT (investigação A.2)

Nenhuma regra foi flexibilizada. Causas identificadas:

| # | Causa | Tipo | Evidência |
|---|---|---|---|
| 1 | `decision.action` é fixo em `"WAIT"` no código do motor | **Comprovada** (por projeto) | `get_iq_option_demo_m5_signal.py`, campo `action: "WAIT"` |
| 2 | O candidato precisa de cerca de 10 condições simultâneas (dados, ADX, distância ATR, RSI, MACD triplo, M15 triplo) | **Comprovada** (leitura do código) | `evaluate_candidate` e `apply_m15_confirmation` |
| 3 | O M15 exige 250 velas M15 **contíguas** (cerca de 62 h). Uma única lacuna na série OTC transforma o contexto em NEUTRAL e bloqueia todo candidato | **Hipótese** | precisa de dados reais (`candlesContiguous` do M15) |
| 4 | O M5 exige 250 velas contíguas (cerca de 21 h) | **Hipótese** | idem |
| 5 | Antes de A.1/A.2: 3 logins por requisição, timeout de 15 s e cache com carência de 90 s geravam erros 502 e estados não atualizados | **Comprovada e corrigida** | auditoria A.0 rev. 1, R1–R4 |

**Como medir com dados reais:** cada publicação grava `diagnostics.actionability`, a tendência e
estrutura do M15 e a contiguidade em `backend/data/runtime/publications.jsonl`. O relatório do
`npm run validate:live` resume as causas (`m5WaitCauses`). A revisão matemática fica para o próximo bloco.

## Indicadores

| Indicador | Implementação | Teste numérico |
|---|---|---|
| EMA (semente SMA) | `app/indicators/ema.py` e cópia no M5 | sim (módulo) / não (cópia) |
| RSI de Wilder | `app/indicators/rsi.py` e cópia no M5 | sim / não |
| ADX e ATR de Wilder | `app/indicators/adx.py`, `atr.py` e cópia no M5 | sim / não |
| MACD 12/26/9 | somente no M5 | **não** |
| EMA 200 | `ema_series` no M5, com 260 velas | **não**; aquecimento insuficiente |
