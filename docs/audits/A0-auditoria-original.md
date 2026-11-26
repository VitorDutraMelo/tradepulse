# TradePulse — Relatório de Auditoria (Bloco A.0)

- Data da auditoria: 26/11/2026
- Material auditado: `tradepulse-main.zip` (355 KB), um arquivo do GitHub sem a pasta `.git`.
- Método: leitura integral do código-fonte. Testes executados em uma cópia isolada, sem nenhuma alteração nos arquivos-fonte.
- Reprodução: um script externo executou o código real da estratégia e da liquidação em cenários de tempo controlados.
- Escopo da autorização: somente auditoria. Nenhuma correção foi feita.

---

## A. Resumo executivo

O TradePulse tem uma base técnica sólida, mas ainda é um produto incompleto.

**O que existe e funciona tecnicamente:**

- Pipeline completo: frontend React → backend Express → motor Python → IQ Option PRACTICE, pela biblioteca `iqoptionapi`.
- Validação forte de contratos com Zod e dataclasses.
- Indicadores EMA, RSI, ADX e ATR corretos e testados.
- Sinais CALL, PUT e WAIT com motivos.
- Registro em JSON dos sinais CALL/PUT e liquidação técnica.
- Proteção contra concorrência no backend.

Todos os testes existentes passam: backend 34/34, Python 172/172, typecheck e build do frontend.

**O que impede o produto de funcionar como esperado (comprovado):**

1. **O sinal M5 aponta para a vela errada.** A entrada de referência é a próxima fronteira depois do horário da análise. Uma análise feita às 17:45:00,5 sobre a vela que fechou às 17:45 recebe entrada às **17:50** e vencimento às 17:55. Isso aparece em um registro real versionado e foi reproduzido no código.
2. **A atualização não acompanha o fechamento das velas.** O frontend consulta 60 s *depois do fim* de cada ciclo, que analisa os painéis em fila. Os registros reais mostram ciclos de cerca de 65 s, com 2 painéis. O fechamento de uma vela pode ser percebido de 60 a mais de 120 s depois, conforme o número de painéis e a latência do login. Esta é a explicação mais provável para o atraso de 90 a 120 s relatado.
3. **O M5 "encerra" a análise depois de 2 minutos.** O limite de idade da vela é fixo em 120 s para todos os timeframes. No M5, toda análise feita mais de 120 s depois do fechamento vira WAIT. Isso foi reproduzido.
4. **Cada análise faz um novo login na IQ Option.** Cada análise abre um novo processo Python e uma nova autenticação. Não existe sessão persistente. Isso gera latência e risco de bloqueio, e explica parte da instabilidade.
5. **A metodologia de avaliação está errada.** A liquidação compara o fechamento da vela de referência com o fechamento da vela de entrada. Isso é um horizonte de 2 velas, com uma vela intermediária ignorada. Sinais podem ficar em PENDING para sempre.

**O que não existe:**

- Estratégia M5 (EMA 200, RSI e MACD) e contexto M15.
- Separação das estratégias por timeframe. Hoje uma única estratégia, a do M1, roda em todos os timeframes.
- Gráfico de candles.
- Histórico e estatísticas no frontend.
- Backtesting.
- PWA.

**Conflitos com os princípios:**

- Existe um módulo `iq-option-real-trading`: endpoint de *preflight* e variáveis para stake e perda diária. Ele não executa ordens, mas prepara o caminho para operações reais. Ver N.2.
- Backups `.bak` e registros JSON estão versionados no branch **main**, não só em um branch de desenvolvimento.

**Estimativa (ver M):** cerca de 41% do escopo implementado e menos de 10% validado funcionalmente. Não há nenhuma validação estatística.

---

## B. Arquitetura atual

```
Navegador (React 18 + Vite 6, :5173, host 127.0.0.1)
   │  GET a cada 60 s após o fim do ciclo; fila serial; timeout de 15 s
   ▼
Backend Express 5 + Zod (:3001; escuta em TODAS as interfaces; sem autenticação)
   │  CachedIqOptionDemoAnalysisClient: fila global serial, de-dup e cache de 55 s
   │  execFile(python -m app.cli.<comando>)  ← 1 processo por requisição
   ▼
Quant Engine Python 3.14 (CLIs que imprimem JSON)
   │  IqOptionMarketDataProvider → IQ_Option(email, senha).connect() a cada chamada
   │  change_balance("PRACTICE") → get_candles(ativo, intervalo, limite, agora_local)
   ▼
IQ Option (iqoptionapi não oficial, fixada no commit 8a903cc)
   Persistência: arquivos JSON em quant-engine/data/iq-option-demo-binary-signals/
```

**Endpoints do backend:**

| Endpoint | Fonte de dados | Usado pelo frontend? |
|---|---|---|
| `GET /api/v1/health` | estático (não verifica o Python nem a IQ) | não |
| `GET /api/v1/iq-option/demo/market-analysis` | IQ PRACTICE, `IqOptionTrendStrategy` | **sim (único)** |
| `GET /api/v1/iq-option/demo/binary-signals[/:id]` | JSON local (CALL/PUT) | não |
| `GET /api/v1/iq-option/demo/analyses[/:id]` | JSON gerado por uma CLI que nenhum endpoint chama | não (órfão) |
| `GET /api/v1/market-analysis` | **Binance** (EMA 9/21, legado) | não |
| `GET /api/v1/market-data/candles` | **Binance** (legado) | não |
| `GET /api/v1/iq-option/signals` | **Binance** → sempre WAIT (legado) | não |
| `GET /api/v1/iq-option/real/status`, `POST /preflight` | política de trading real (sempre `allowed:false`) | não |

**Componentes Python sem uso pelo backend:**

- `OtchartsIqOptionMarketDataProvider` e o stream SSE do OTCharts: um terceiro pago, que exige `OTCHARTS_API_KEY`.
- `IqOptionStreamCaptureService`, `OneMinuteCandleBuilder` e `IqOptionSessionRepository`.
- `EmaCrossoverStrategy` (LONG/SHORT/NEUTRAL), `BinanceMarketDataProvider` e `MockMarketDataProvider`.

---

## C. Inventário de funcionalidades

**Existentes e funcionais (tecnicamente):**

- Análise IQ PRACTICE por ativo e timeframe, com CALL/PUT/WAIT e motivos em inglês.
- Indicadores EMA 9/21, RSI 14, ADX 14 e ATR 14.
- Filtro de velas fechadas.
- Validação de contratos ponta a ponta.
- Erros exibidos como erro, nunca como WAIT.
- Interface com 1, 2 ou 4 painéis, 8 ativos OTC fixos e M1/M5.
- Fase da referência no frontend ("aguardando", "em andamento", "expirado").
- Detecção de dados desatualizados no frontend.
- Registro JSON dos CALL/PUT, com deduplicação por entrada, e liquidação WIN/LOSS/DRAW.
- Fila serial, deduplicação de requisições e cache no backend.
- Layout responsivo por media queries.

**Parcialmente implementadas:**

- Histórico: existe no backend, mas não registra WAIT e não aparece no frontend.
- Avaliação de resultados: a metodologia está errada e não há EXPIRED nem NOT_EVALUABLE.
- Seleção de ativos: a lista é fixa, não vem da IQ.
- Tratamento de indisponibilidade: retorna 502 com a mensagem do Python, mas o health check é falso.
- Qualidade dos dados: há idade da vela e filtro de fechadas, mas não há detecção de lacunas no fluxo principal.

**Ausentes:**

- Estratégia M5 (EMA 200, RSI, MACD 12/26/9) e contexto M15.
- MACD (o indicador não existe).
- Registro de estratégias por timeframe e versão da estratégia nos registros.
- Gráfico de candles e endpoint de candles da IQ.
- Estatísticas e intervalos de confiança.
- Backtesting.
- Sessão persistente com a IQ e horário do servidor da IQ.
- Agendamento alinhado ao fechamento das velas.
- Timestamps de recebimento, conclusão e publicação, e latência.
- PWA (manifest e service worker).
- Logs estruturados.
- Testes de frontend.

**Não verificadas:**

- Conexão real com a IQ Option nesta auditoria. Não há credenciais e não devo inseri-las.
- Disponibilidade dos 6 ativos além de EURUSD-OTC e GBPUSD-OTC.
- Comportamento no celular.

---

## D. Diagnóstico dos problemas

Legenda: **[C]** causa comprovada (código, reprodução ou dado real) · **[H]** hipótese.

| # | Problema relatado | Achado | Evidência |
|---|---|---|---|
| D1 | Sinais em horários incorretos ou vela errada | **[C]** `_next_reference_entry_time` usa o horário da análise, não o fechamento da vela de referência. Resultado: a entrada é sempre a fronteira seguinte (M1: +60 s; **M5: +300 s**). | `iq_option_trend_strategy.py:316-326`. Registro real `…174500…eurjpy-otc…json`: análise às 17:45:00,5, entrada às 17:50:00. A reprodução mostrou `gap=300s` no M5. |
| D2 | Atraso de 90 a 120 s | **[C]** O próximo ciclo do frontend só começa 60 s depois que o ciclo anterior *termina* (`App.tsx:684-691`). A consulta não é alinhada ao fechamento. **[C]** Os registros reais estão espaçados em cerca de 65 s (17:41:41 → 17:42:47 → 17:43:52 → 17:44:57). **[H]** Com 4 painéis e logins mais lentos, o ciclo passa de 80 a 120 s, e o fechamento é percebido no fim de um ciclo inteiro. | Código + dados reais |
| D3 | "Encerramento prematuro" das análises M5 | **[C]** `max_candle_age_seconds=120` vale para todos os timeframes. No M5, depois de 120 s do fechamento, o resultado é sempre WAIT ("candle is Xs old"). O frontend considera o M5 desatualizado só depois de 600 s, o que é incoerente. | Reprodução: 119 s → CALL; 121 s → WAIT. `api.ts:339-342` |
| D4 | Instabilidade com a IQ Option | **[C]** Um login completo (`connect` + `change_balance`) por requisição, em um processo Python novo, sem reutilização de sessão. **[H]** Logins repetidos provocam limitação ou bloqueio pela IQ e lentidão variável. | `iq_option_market_data_provider.py:142-186`, `python-quant-engine.client.ts:342` |
| D5 | Timeouts com consultas concorrentes | **[C]** A fila global do backend é serial e sem limite. O tempo de espera na fila não tem timeout. O frontend aborta em 15 s, mas o processo Python continua (não há cancelamento). Várias abas ou dispositivos acumulam trabalho. | `iq-option-demo-analysis-cache.ts:122-138` |
| D6 | Análise antiga apresentada como atual | **[C]** O cache de 55 s usa `ativo:tf:limite` como chave, não a última vela fechada. Uma atualização manual feita pouco depois de um fechamento pode devolver a análise da vela anterior. O `analysisAt` antigo é exibido, mas o painel mostra "Dados recebidos". | `iq-option-demo-analysis-cache.ts:48,143` |
| D7 | Horário da análise impreciso | **[C]** `analysisAt` é capturado *antes* do login e da coleta. A latência da IQ fica oculta e a idade da vela é subestimada. Não existem horários de recebimento, conclusão ou publicação. | `analyze_iq_option_binary_signal.py:109` |
| D8 | Relógio | **[H]** O relógio local decide quais velas estão fechadas e qual é a entrada. O horário do servidor da IQ não é usado. Um relógio adiantado incluiria a vela em formação como fechada; um atrasado atrasaria uma vela. | `iq_option_market_data_provider.py:107,129-133` |
| D9 | M1 e M5 não são independentes | **[C]** Uma única `IqOptionTrendStrategy` (EMA 9/21 + RSI + ADX + ATR) com os mesmos limiares para 1m, 5m, 15m e 1h. | `analyze_iq_option_binary_signal.py:124` |
| D10 | Sem comprovação estatística | **[C]** A avaliação compara `close(vela de referência)` com `close(vela de entrada)`, um horizonte de 2 velas. WAIT não é registrado. A liquidação só ocorre quando alguém consulta o mesmo ativo e timeframe e a vela de entrada ainda está entre as 120 retornadas; senão fica PENDING para sempre. Não há estatísticas. | Reprodução, seção 2. `iq_option_demo_binary_signal_repository.py:131-160` |
| D11 | Falhas de integração | **[C]** O frontend rejeita um WAIT legítimo sem velas, porque exige `lastClosedCandle.openTime` válido, enquanto o backend aceita `null`. **[C]** O endpoint `/demo/analyses` lê dados que nenhum fluxo grava. **[C]** O Vite escuta em `127.0.0.1` e o CORS libera `localhost:5173`, então abrir pelo IP bloqueia por CORS. | `api.ts:113-121`, `iq-option-demo-analysis.schema.ts:41-45` |
| D12 | Código diferente do que rodou | **[C]** Os JSON versionados têm campos (`analysis.lastClosedCandle`, `analysis.indicators`) e um texto de aviso que o repositório atual **não** produz. Os registros vieram de uma versão do código que não está neste zip. | Comparação entre o JSON e `save_pending()` |

---

## E. Estado da integração IQ Option

**Biblioteca:** `iqoptionapi` comunitária, instalada do Git e fixada no commit `8a903cc…`. Ela não é oficial e é pouco mantida. Há risco de quebra quando a IQ muda o protocolo, e risco de cadeia de suprimentos.

**Conexão:**

- Credenciais vêm de `IQ_OPTION_DEMO_EMAIL` e `IQ_OPTION_DEMO_PASSWORD`, herdadas do ambiente do Node. Elas não estão documentadas no `.env.example` do backend.
- Login a cada requisição.
- `change_balance("PRACTICE")` é chamado sempre (correto).

**Coleta:**

- `get_candles(ativo, intervalo, limite, agora_local)`.
- O fechamento é calculado pelo campo `to`, e o filtro aceita `to ≤ agora`.
- O limite é 1000 velas por chamada, sem paginação.

**Disponibilidade:**

- `get_all_open_time` existe no provedor, mas não é exposto ao frontend.
- Dados reais já foram obtidos antes: há registros de 10/11 para EURUSD-OTC e EURJPY-OTC.
- **Bloqueio desta auditoria:** a conexão real não foi testada. Faltam credenciais e não devo digitá-las.

**Segurança:**

- A conta PRACTICE da IQ usa **o mesmo login da conta real**. Quem tem essas credenciais tem acesso à conta com dinheiro real.
- Isso aumenta a importância de o backend não ficar exposto na rede. Hoje ele escuta em todas as interfaces, sem autenticação.

**Fontes alternativas:** OTCharts (terceiro pago) existe no código e só em CLIs isoladas, sem mistura silenciosa. A Binance está nos endpoints legados. Nenhuma das duas alimenta o painel IQ.

---

## F. Estado das estratégias M1 e M5

**Estratégia atual** (`IqOptionTrendStrategy`, usada em todos os timeframes):

| Regra | Valor |
|---|---|
| Velas mínimas | 29 (o frontend pede 120) |
| Idade máxima da vela | 120 s, igual para todos os timeframes |
| Distância entre as EMAs | `|EMA9−EMA21| / ATR14 ≥ 0,15`; senão WAIT |
| Força da tendência | `ADX14 ≥ 20`; senão WAIT |
| CALL | `EMA9 > EMA21` e `52 ≤ RSI14 ≤ 68` |
| PUT | `EMA9 ≤ EMA21` e `32 ≤ RSI14 ≤ 48` |
| Expiração | 1 vela |
| Versão da estratégia | não registrada |

Isso confirma os indicadores do M1 (EMA 9, EMA 21, RSI 14, ADX 14 e ATR 14). O ATR **é usado** como filtro de distância entre as EMAs. O README diz que talvez não seja, o que está desatualizado.

**Detalhe de borda:** `EMA9 == EMA21` cai no ramo do PUT. Na prática isso é bloqueado pelo filtro ATR quando o ATR é maior que zero. Se o ATR for zero, a razão vale 0 e o resultado é WAIT, o que está correto.

**Indicadores** (fórmulas conferidas):

- EMA com semente por média simples (SMA): padrão.
- RSI, ATR e ADX de Wilder: padrão, com testes.
- Ressalva: o RSI devolve 100 quando não há ganho nem perda (mercado parado). O mais comum é 50 ou indefinido. O impacto é baixo.

**M5 (EMA 200, RSI 14, MACD 12/26/9):**

- Não implementado. MACD não existe.
- A função EMA suporta o período 200, mas o pedido de 120 velas é insuficiente. A EMA 200 exige pelo menos 200 velas e, idealmente, um aquecimento de 400 a 600.

**M15:** não implementado.

**Separação:** nenhuma. Qualquer mudança hoje afetaria o M1 e o M5 juntos. É preciso um registro de estratégias por timeframe, com versão.

---

## G. Estado da sincronização

**Linha do tempo real de um sinal M5** (registro de 10/11, EURJPY-OTC):

```
17:40:00  abertura da vela de referência
17:45:00  fechamento da vela de referência  ← dado disponível
17:45:00,5  análise (login + coleta + cálculo ≈ 2,7 s no ciclo observado)
17:50:00  "entrada de referência"           ← 5 min depois do dado
17:55:00  vencimento
```

**Timestamps registrados hoje:**

| Timestamp | Situação |
|---|---|
| Abertura da vela | sim |
| Fechamento da vela | calculado como abertura + timeframe; o campo `to` da IQ é usado só no filtro |
| `analysisAt` | sim, mas é o *início* do processo |
| Entrada e expiração | sim |
| Recebimento dos dados, conclusão, publicação e latência | não |

**Componentes que somam atraso:**

1. Consulta do frontend não alinhada: período = 60 s + duração do ciclo.
2. Processamento por painel: login e coleta em fila serial no frontend e no backend.
3. Cache de 55 s, que não sabe que uma vela nova fechou.
4. Regra de entrada que empurra para a fronteira seguinte.

**Validade:**

- O frontend marca como expirado depois do vencimento: correto.
- Mas um CALL M5 do item 4 fica "aguardando" por até 5 minutos e entra em uma vela que nenhum dado confirmou.

**Proposta para a "regra dos 90 segundos"** (requer aprovação, ver N.1):

- **Opção 1 — manter "próxima vela completa":** corrigir só a coerência. A entrada passa a ser a fronteira seguinte ao **fechamento da vela de referência**. Hoje é a fronteira seguinte ao horário da análise. O sinal publicado em T+latência vale para a vela T→T+tf, que já começou. Por isso essa opção exige a tolerância da Opção 2.
- **Opção 2 — recomendada: vela corrente com janela de tolerância W.**
  - A vela de referência fecha em T. A análise é disparada por um agendador alinhado em T + ε. A publicação ocorre em P.
  - A entrada de referência é T, com preço de referência = abertura da vela T (próxima do fechamento de T−1). O vencimento é T + tf.
  - Se P − T ≤ W (proposta: M1 W = 10 s; M5 W = 30 s), o sinal é publicado como acionável, com a latência visível.
  - Se P − T > W, o sinal é registrado como `EXPIRED` (não acionável) e contado à parte nas estatísticas.
  - Nenhum sinal é apresentado como disponível antes de P. A latência fica registrada.
  - A avaliação usa a abertura de T contra o fechamento de T + tf: horizonte de 1 vela, sem vela ignorada.
- **Opção 3 — complemento: pré-análise.** Em T − k s, calcular uma prévia com a vela em formação, marcada como PROVISÓRIA e nunca exibida como sinal. Isso só serve para ter os dados prontos e encurtar P − T. A confirmação continua exigindo a vela fechada.

---

## H. Estado do frontend

**Real e funcional:**

- Consome apenas o endpoint de análise da IQ.
- Valida o JSON.
- Mostra sinal, motivos, indicadores, horários em UTC, JSON bruto e fase da referência.
- Bloqueia CALL/PUT depois da expiração.
- Tema escuro e visual tecnológico, com 1, 2 ou 4 painéis.
- Media queries até 650 px.

**Ausente:**

- **Gráfico de candles.** A especificação pede que ele seja o elemento principal. Também não existe endpoint de candles da IQ no backend.
- Histórico, estatísticas e estado de conexão real (o rótulo "Dados recebidos" não prova a conexão).
- Lista dinâmica de ativos.
- PWA.
- Testes automatizados.

**Defeitos:** D2, D3, D11 e a ausência do indicador de latência. Os motivos aparecem em inglês, porque vêm do Python.

**Repositório do frontend:**

- 6 arquivos `.bak` em `src/`.
- `frontend/services/marketAnalysisService.ts` vazio, fora de `src`.
- `tsconfig.tsbuildinfo` (585 KB) versionado, com caminhos do pnpm, enquanto o lockfile é do npm.

**Responsividade no celular:** não validada visualmente nesta auditoria.

---

## I. Testes e qualidade

**Resultados obtidos nesta auditoria** (cópia isolada, Node 24.21, Python 3.14.8):

| Verificação | Resultado |
|---|---|
| Backend `vitest run src` | **34/34 passaram** (9 arquivos) |
| Backend `tsc --noEmit` | passou |
| Python `pytest` (`quant-engine/tests`) | **172/172 passaram** |
| Python `ruff check` | **1 erro** (E501 em `get_iq_option_demo_binary_signal_history.py:11`) |
| Frontend `tsc --noEmit` | passou |
| Frontend `vite build` | passou (165,7 KB de JS) |
| Frontend: testes automatizados | não existem |
| `tests/repositories/…` na raiz | não é coletado pelo pytest; é uma cópia divergente da versão em `quant-engine/tests` |

**Limitações da validação:**

- Todos os testes são unitários, com dados simulados (mocks).
- Nenhum teste cobre: a defasagem de entrada no M5, o horizonte da liquidação, o cache atravessando um fechamento, o limite de idade por timeframe ou o atraso da consulta.
- Por isso os defeitos D1 a D6 passam com todos os testes verdes. É exatamente o ciclo descrito na seção 3 das diretrizes.
- Não há teste de integração com a IQ real.
- O README cita "27/27" testes e o PROJECT_STATUS cita "63 Python / 12 Node": números desatualizados.

**Script de reprodução:** fica fora do projeto (`scratchpad/scripts/repro_timing.py`) e executa o código real com velas sintéticas e relógio controlado.

---

## J. Segurança e GitHub

**Estado do Git:** não verificável.

- O zip não contém `.git` e o `gh` não está instalado nesta máquina.
- Branch atual, commit, alterações locais e outros branches **continuam sem verificação**.
- O nome `tradepulse-main` indica o branch **main**.

**Problemas no branch main (confirmados no conteúdo do zip):**

- **Backups versionados:**
  - `frontend/src/App.tsx.20261110-005831.bak`, `App.tsx.20261110-011558.bak`, `App.tsx.bak`
  - `api.ts.20261110-005831.bak`
  - `style.css.20261110-011558/011916/012117.bak`
  - `quant-engine/app/repositories/iq_option_demo_analysis_repository.py.before-restore-20261110-190120.bak`
- **Registros JSON do motor versionados:** 5 arquivos em `quant-engine/data/iq-option-demo-binary-signals/`. Essa pasta não tem `.gitignore`, ao contrário das pastas vizinhas `iq-option-demo-analyses` e `iq-option-sessions`. **O problema relatado continua, agora no main.**
- **Arquivos gerados versionados:**
  - `frontend/tsconfig.tsbuildinfo`, apesar de o `.gitignore` incluir `*.tsbuildinfo`; foi versionado antes da regra.
  - `quant-engine/tradepulse_quant_engine.egg-info/`, desatualizado: não lista o `iqoptionapi`.
- **Arquivos vazios:** `quant-engine/README.md`, embora o `pyproject.toml` o use como `readme`, e `frontend/services/marketAnalysisService.ts`.

**Credenciais:** nenhuma credencial real encontrada (varredura de e-mail, senha, chave e token). Só aparecem valores de teste. O `.gitignore` cobre `.env` e `.env.*`.

**Riscos:**

1. O backend escuta em todas as interfaces, sem autenticação. Qualquer pessoa na rede local pode disparar logins na conta IQ.
2. A conta PRACTICE usa o mesmo login da conta real.
3. Existe o módulo de *real trading*, ainda que bloqueado.
4. Mensagens de erro do Python chegam ao cliente.
5. Dependência não oficial instalada direto do Git.

**Documentação:**

- `docs/PROJECT_STATUS.md` (01/11) descreve a arquitetura Binance, que está desatualizada, e contém uma cópia embutida do ROADMAP.
- `README.md` cita `docs/images/tradepulse-candles.svg`, mas o arquivo está na raiz.
- `docs/GUIA_INSTALACAO_AMIGO.md` existe.

---

## K. Matriz de desenvolvimento

| Funcionalidade | Classificação |
|---|---|
| Coleta de velas IQ PRACTICE | Implementada, mas não validada (houve uso real em 10/11, não reverificado) |
| Sessão, reconexão e reutilização da conexão IQ | Não implementada |
| Horário do servidor e relógio | Não implementado |
| Indicadores EMA, RSI, ADX e ATR | Concluídos e validados (testes matemáticos) |
| Indicadores MACD e EMA 200 com aquecimento | Não implementados |
| Estratégia M1 (atual) | Implementada, mas não validada (sem estatística; afetada por D1 a D3) |
| Estratégia M5 (EMA 200, RSI, MACD) | Não implementada |
| Contexto M15 | Não implementado |
| Separação das estratégias por timeframe e versão | Não implementada |
| CALL, PUT e WAIT com motivos | Implementado, mas não validado |
| Horários de entrada, expiração e validade | **Com defeito** (D1, D3, D7) |
| Agendamento alinhado aos fechamentos e latência | Não implementado (atual com defeito, D2) |
| Cache e concorrência | Parcialmente implementado (D5, D6) |
| Histórico de análises | Parcialmente implementado |
| Avaliação de resultados | **Com defeito** (D10) |
| Estatísticas de desempenho | Não implementadas |
| Backtesting | Não implementado |
| Monitoramento da qualidade dos dados | Parcialmente implementado |
| Tratamento de indisponibilidade e health check | Parcialmente implementado |
| Frontend: painel de sinal | Implementado, mas não validado |
| Frontend: gráfico de candles | Não implementado |
| Frontend: histórico e estatísticas | Não implementados |
| Responsividade | Implementada, mas não validada |
| PWA | Não implementado |
| Documentação | Parcial e desatualizada |
| Conexão real IQ nesta auditoria | **Bloqueada** (sem credenciais) |
| Estado do Git e dos branches | **Bloqueado** (sem `.git` e sem `gh`) |

---

## L. Roadmap revisado

Esta ordem segue as dependências reais.

1. **A.0.1 — Higiene do repositório** (pequeno; precisa de aprovação):
   - Tirar do versionamento os `.bak`, os JSON de dados, o `tsbuildinfo` e o `egg-info`, usando `git rm --cached`. Isso não apaga nenhum arquivo local.
   - Adicionar `.gitignore` na pasta de dados.
   - Apagar o teste solto e o arquivo vazio.
   - Corrigir o erro do ruff.
   - Atualizar o PROJECT_STATUS para refletir o estado real.
2. **A.1 + A.2 juntos — Coleta confiável e sincronizada.** As causas de D1 a D8 estão entrelaçadas. Corrigir uma sem as outras repete o ciclo anterior.
3. **A.5 — Ciclo de vida do sinal**, com a regra de entrada aprovada em N.1. Inclui estados e validade. Pode entrar no mesmo bloco de A.2, se aprovado.
4. **A.6 — Histórico e avaliação:**
   - Registrar todas as análises, incluindo WAIT.
   - Corrigir a metodologia.
   - Adicionar EXPIRED e NOT_EVALUABLE.
   - Liquidar por uma rotina do backend, sem depender de uma visita na tela.
   - Gravar a versão da estratégia.
   - Isso cria a *linha de base* do M1 atual, necessária para comparar com o M5.
5. **A.3 + A.4 — Motor M5 e contexto M15:** registro de estratégias por timeframe; o M1 fica intacto e protegido por testes de regressão. As regras exatas precisam ser aprovadas.
6. **A.7 — Backtesting:** histórico IQ paginado, separação cronológica, comparação M5 contra o M1 e contra uma linha de base aleatória ou ingênua, e cálculo do ponto de equilíbrio pelo payout.
7. **A.9 — Integração do frontend:** endpoint de candles IQ, gráfico, histórico, estatísticas e estado da conexão.
8. **A.8 — Revisão do M1.**
9. **A.10 — Estabilização e PWA** (inclui bind em localhost e autenticação, se houver acesso pelo celular).
10. **A.11 — Documentação e lançamento.**

---

## M. Percentual de desenvolvimento

**Critério:** 22 itens do escopo final (seção 5 das diretrizes mais a infraestrutura das seções 9 a 14), com peso igual. Implementação: 1 = completo, 0,5 = parcial ou com defeito, 0 = ausente.

**Itens com 1 (4 itens = 4,0):**

- Estratégia M1
- CALL/PUT/WAIT
- Explicação dos sinais
- Responsividade

**Itens com 0,5 (10 itens = 5,0):**

- Coleta IQ
- Seleção de ativos
- Horários
- Histórico
- Avaliação
- Qualidade dos dados
- Indisponibilidade
- Documentação
- Indicadores (EMA, RSI, ADX e ATR completos; faltam MACD e EMA 200 com aquecimento)
- Logs e health check

**Itens com 0 (8 itens):**

- Gráfico
- Estratégias por timeframe
- M5
- M15
- Estatísticas
- Sessão e conexão IQ
- PWA
- Backtesting

**Resultado:** 9,0 / 22 ≈ **41% de implementação**.

**Validação funcional** (comprovada em uso real, por critério de aceitação): nenhum item foi validado nesta auditoria. Os registros reais de 10/11 dão evidência parcial para a coleta e para CALL/PUT. Estimativa: **< 10% validado**. Validação estatística: **0%**.

---

## N. Dúvidas e decisões necessárias

1. **Regra de entrada:** escolher entre as Opções 1, 2 e 3 da seção G e definir a tolerância W por timeframe. Recomendação: Opção 2 + Opção 3, com W = 10 s no M1 e 30 s no M5.
2. **Módulo `iq-option-real-trading`:** remover, manter desativado ou mover para um branch separado? Ele contraria o princípio 1. Recomendação: remover do main.
3. **Endpoints Binance legados e código do OTCharts:** desativar, arquivar ou manter isolados? O OTCharts (pago) está em uso?
4. **Git:** o zip corresponde ao main atual? Qual branch estava rodando? Os JSON mostram código diferente. Preciso do caminho do clone local ou do `gh`/`git` com acesso para auditar branches, commits e alterações locais.
5. **Credenciais IQ:** confirmar que é aceitável usar o login que também dá acesso à conta real. Para a validação real, o proprietário define as variáveis de ambiente localmente; eu não digito credenciais.
6. **Arquitetura da conexão** (mudança estrutural): sessão IQ persistente. Recomendação: um processo Python de longa duração, com mensagens JSON por linha via stdin/stdout, gerenciado pelo Node. Não exige dependência nova, e o Node continua sendo a única API pública. Alternativa: um microserviço HTTP em Python.
7. **Persistência:** manter arquivos JSON ou migrar para SQLite (biblioteca padrão)? Recomendação: SQLite para histórico e estatísticas.
8. **Regras exatas do M5 e do M15:** quem especifica, a engenharia (ChatGPT) ou eu proponho um rascunho? Pontos em aberto:
   - Cruzamento do MACD ou sinal e inclinação do histograma.
   - Faixas de RSI.
   - Distância mínima da EMA 200.
   - Classificação do M15 em BULLISH, BEARISH ou NEUTRAL.
   - Aquecimento da EMA 200: quantas velas buscar.
9. **Expiração:** 1 vela no M1 e no M5?
10. **Ativos:** lista dinâmica vinda da IQ (abertos agora) ou lista fixa curada?
11. **Payout para o ponto de equilíbrio:** ler da IQ ou configurar manualmente?
12. **Idioma dos motivos:** PT-BR no backend?
13. **Acesso pelo celular / PWA:** só na rede local ou remoto? Isso define o bind e a autenticação.
14. **Gerenciador de pacotes:** npm (lockfile atual) ou pnpm (usado localmente)?

---

## O. Próxima entrega funcional proposta

**Bloco A.1 + A.2 — "Coleta confiável e sincronizada"**, precedido do A.0.1 se aprovado.

**Problemas resolvidos:** D1 a D8, ou seja, atraso, vela errada, encerramento prematuro do M5, logins repetidos, timeouts e análise antiga exibida como atual.

**Escopo:**

- Sessão IQ persistente e única, com reconexão controlada e limite de requisições. Depende de N.6.
- Horário do servidor IQ e desvio do relógio local registrados.
- Agendador no backend, disparado no fechamento de cada vela de cada ativo e timeframe ativo. O frontend passa a só ler o resultado publicado, sem disparar análises.
- Cache com a chave "última vela fechada".
- Timestamps completos: abertura e fechamento da vela, recebimento, início, conclusão, publicação e latência.
- Regra de entrada aprovada em N.1. Idade máxima proporcional ao timeframe.
- **Regras de decisão do M1 inalteradas**, protegidas por testes de regressão.
- Testes novos para cada defeito D1 a D8, que falham no código atual e passam depois da correção.

**Critérios de aceitação:**

- Em 30 minutos de DEMO real, com M1 e M5 em 2 ou mais ativos:
  - Mediana de publicação ≤ 5 s depois do fechamento da vela.
  - Nenhum sinal com entrada fora da regra aprovada.
  - 1 login por sessão (comprovado em log).
  - 0 timeouts sem explicação.
- Relatório com o log real.

**Como o proprietário verifica:**

1. Abrir o painel M5 e observar os horários :00, :05, :10.
2. O painel deve atualizar segundos depois do fechamento e mostrar, por exemplo: "Vela 12:00–12:05 · recebida 12:05:01,8 · publicada 12:05:02,3 · latência 2,3 s · entrada 12:05 · vence 12:10".
3. Desligar a internet: o painel deve mostrar "IQ Option indisponível" e nunca exibir o sinal anterior como atual.

Aguardo a aprovação e as respostas da seção N antes de iniciar qualquer implementação.
