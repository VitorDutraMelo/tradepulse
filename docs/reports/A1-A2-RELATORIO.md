# TradePulse — Relatório de conclusão dos blocos A.1 + A.2

**Coleta confiável e sincronizada**

- **Data:** 26/11/2026
- **Branch:** `feat/tradepulse-v2-frontend`
- **Base:** `9144f59` (confirmada: clone local = remoto = conteúdo do zip auditado)
- **Autorização:** desenvolvimento, commits e push nesta branch. Sem merge e sem deploy.

---

## 1. Resumo executivo

O TradePulse deixou de abrir um processo Python e fazer um login na IQ Option a cada consulta. Agora:

- um worker Python persistente mantém **uma** sessão PRACTICE verificada, reutilizada por todas as análises, gráficos e liquidações;
- o backend dispara cada análise **no fechamento da vela**, repete de forma controlada até a vela existir e publica uma vez por vela;
- o estado de atualidade e de validade é recalculado a cada leitura, então uma vela anterior **não pode** aparecer como atual;
- o atraso artificial de 90 s foi eliminado e nenhuma espera fixa o substituiu;
- o sinal M5 deixou de ser associado à vela seguinte, e o limite genérico de 120 s não se aplica mais ao M5;
- o backend só aceita conexões locais, as rotas da conta REAL foram retiradas da API e as credenciais nunca aparecem em logs ou respostas.

**Testes:** Python 247/247, ruff limpo, backend 71/71, typecheck e build do backend e do frontend.

**O que não foi feito:** a validação com a IQ Option real **não foi feita**. Não tenho as credenciais PRACTICE e não devo digitá-las.
- A latência real e a contagem real de logins **ainda não foram medidas**.
- Deixei um procedimento de um comando para o proprietário: `npm run validate:live`, descrito em `docs/TESTING.md`.

---

## 2. Problemas corrigidos e causas

| # | Problema | Causa comprovada | Correção |
|---|---|---|---|
| D1 | Sinal M5 associado à vela seguinte (+300 s) | Entrada = fronteira após o horário da análise | Entrada = fechamento da vela de referência (M1 e painel). O motor M5 já usava essa regra |
| D2 | Atraso de 60 a 120 s | Consulta a cada 60 s, sem alinhamento, mais o tempo do ciclo | Agendador no fechamento + leitura local a cada 2 s |
| D3 | M5 em WAIT depois de 2 min | Idade máxima fixa de 120 s | Idade máxima = 1 timeframe |
| D4 | Login a cada consulta | Um processo e um login por requisição | Sessão persistente única |
| D5 / R3 | Timeouts com consultas concorrentes | Duas filas, gráfico fora de fila, M5 com 3 logins | Uma fila, dedupe, limite, cancelamento, M5 com 2 leituras |
| D6 / R2 | Vela anterior apresentada como atual | Caches por tempo (55 s; fechamento + 5 min + 90 s) | Cache por vela e estado recalculado na leitura |
| D7 | Sem horário de recebimento, publicação ou latência | `analysisAt` capturado antes da coleta | Horários observados e derivados, latências de coleta, processamento e total |
| D8 | Somente relógio local | Horário do servidor não era usado | Relógio do servidor IQ, quando disponível, para velas fechadas e agendamento |
| R1 | Carência de 90 s | Constantes no coletor e no cache | Removidas |
| R4 | Timeout de 15 s para 3 logins | Executor CLI genérico | Timeout próprio do gateway (45 s) e reinício do worker travado |
| — | Biblioteca pode travar ou fazer login escondido | Espera infinita e reconexão dentro de `get_candles` | Espera própria com prazo; `connect` com prazo; nenhuma reconexão fora do controle da sessão |
| — | IQ conta a vela aberta no limite pedido | Pedir N velas devolvia N−1 fechadas | Cache pede N+1 (encontrado pelos novos testes) |
| — | 7 erros de lint | — | Corrigidos sem alterar texto nem regras |

---

## 3. Arquitetura implementada

Descrição completa em `docs/ARCHITECTURE.md`, com as decisões em `docs/adr/0001` a `0006`.

```
Frontend ──/live (2 s, só backend)──▶ LiveAnalysisService ──▶ GatewayWorker ──JSON-lines──▶ worker Python
                                      (fechamento da vela,       (fila 1-em-voo,              (IqSession 1 login,
                                       retentativas,              dedupe, limite,              PRACTICE verificado,
                                       publicação, validade)      cancelamento, timeout)       CandleCache, estratégias)
```

---

## 4. Arquivos alterados

70 arquivos no total desde `9144f59`, incluindo as remoções do rastreamento.

**Novos:**
- `backend/src/modules/iq-gateway/` (8 arquivos de código e 3 de teste)
- `backend/src/app.security.test.ts`
- `backend/scripts/validate-live.ts`
- `quant-engine/app/gateway/` (8 arquivos)
- `quant-engine/tests/gateway/` (4 arquivos)
- `frontend/src/live.ts`
- `docs/` (documentos, ADRs, auditorias, este relatório), `CHANGELOG.md`, `quant-engine/README.md`

**Alterados:**
- `backend/src/app.ts`, `server.ts`, `config/env.ts`, `.env.example`, `package.json`
- `quant-engine/app/strategies/iq_option_trend_strategy.py` (somente a parte temporal)
- `quant-engine/app/cli/analyze_iq_option_binary_signal.py`, `collect_iq_option_demo_m5_validation.py`
- 4 CLIs só com ajuste de lint
- `frontend/src/App.tsx`, `style.css`, `components/charts/CandlestickChart.tsx`, `iqHistory.ts`, `.env.example`
- `.gitignore`, `README.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`

**Removidos:**
- Os dois caches antigos e seus testes.
- Do rastreamento do Git (com cópias locais preservadas): 155 JSON, 10 `.bak`, 3 pastas de backup, `tsbuildinfo`, `egg-info`, 1 arquivo vazio e 1 teste duplicado.

---

## 5. Decisões técnicas tomadas

1. **Worker JSON-lines, não microserviço HTTP (ADR-0001):** sem nova dependência, sem nova porta, e o Node continua sendo a única API.
2. **Estratégias existentes reutilizadas por injeção de provedor:** nenhuma regra matemática foi reescrita.
3. **Agendamento no backend, não no navegador (ADR-0002):** o navegador só lê o resultado publicado.
4. **Regra provisória de entrada e tolerâncias de 10 s / 30 s (ADR-0003),** como autorizado. Tudo é marcado como experimental e não operacional.
5. **Loopback obrigatório e rotas REAL desmontadas (ADR-0004).** O módulo foi mantido isolado até a decisão N.2.
6. **Persistência JSON mantida (ADR-0006);** SQLite pendente (N.7).
7. **Motor M5:** `decision.action = "WAIT"` foi preservado. O painel mostra `candidateAction` com selo experimental, e o backend calcula a validade temporal.
8. **Gráfico M5 continua agregado de M1** (N.17 pendente). Só o intervalo de atualização (10 s) e a URL padrão foram ajustados.

---

## 6. Testes anteriores e atuais

| Verificação | Antes (`9144f59`) | Depois |
|---|---|---|
| Python pytest | 208/208 | **247/247** (39 novos) |
| Python ruff | 7 erros | **0** |
| Backend vitest | 51/51 | **71/71** (28 novos; 8 removidos junto com os caches eliminados) |
| Backend tsc + build | passa | passa |
| Frontend tsc + build | passa | passa |

Todos os 15 temas de cobertura pedidos estão mapeados em `docs/TESTING.md`.

---

## 7. Evidências de funcionamento

Todas sem credenciais.

1. **Integração real Node ↔ Python.** O teste `gateway-worker.integration.test.ts` inicia o worker Python verdadeiro.
   - O status inicial é `DISCONNECTED` e `credentialsConfigured: false`.
   - A análise M1 falha com `IQ_OPTION_CREDENTIALS_MISSING`.
   - O comando `buy` é rejeitado com `INVALID_GATEWAY_REQUEST`.
   - Houve 1 processo iniciado.
2. **API real iniciada a partir do build (`dist/server.js`):**
   - escuta em `127.0.0.1` apenas (`netstat`: `TCP 127.0.0.1:3999 LISTENING`);
   - `/api/v1/iq-option/real/status` → 404;
   - `/live` → `dataState: NO_DATA` com `lastError.code = IQ_OPTION_CREDENTIALS_MISSING`;
   - nenhum processo worker órfão depois do encerramento.
3. **Navegador (painel do app, 1280 px e 375 px):**
   - a sessão aparece como `CREDENTIALS_MISSING` e o ícone de conexão como desconectado;
   - o painel mostra "Sem dados" e "Credenciais PRACTICE não configuradas no backend";
   - o M5 aparece com selo "Motor experimental"; EURUSD M5 exibe "disponível apenas para GBPUSD-OTC";
   - console sem erros de JavaScript (apenas as respostas HTTP 502/422 esperadas);
   - sem rolagem horizontal a 375 px (um transbordo de 2 px foi encontrado e corrigido).
4. **Simulações de tempo:**
   - A análise começa exatamente na fronteira (12:01:00.000) e é publicada cerca de 0,3 s depois, com latência simulada.
   - Quando a IQ publica a vela 3 s depois, a análise faz poucas tentativas espaçadas.
   - A vela anterior aparece como `AWAITING_NEW_CANDLE` e `state: AWAITING_CONFIRMATION`, nunca como `UPDATED`.
   - Um candidato publicado 45 s depois do fechamento do M5 recebe `LATE_NOT_ACTIONABLE`.

---

## 8. Latência e logins

**Latência real observada:** **não disponível.** É necessária a validação do proprietário.
- Com o código novo, a latência total é: tempo até a IQ disponibilizar a vela + uma requisição pela sessão aberta + o cálculo.
- O tempo de login deixa de entrar no caminho de cada análise.

**Logins (4 painéis: 2 M1 + 2 M5 GBPUSD, com gráficos):**

| | Antes (A.0 rev. 1, derivado do código) | Depois |
|---|---|---|
| Por minuto | cerca de 8 a 11 | **0** (só o login inicial) |
| Por sessão do backend | ilimitado | **1** + reconexões após quedas |
| Medido | reprodução: 3 chamadas ao provedor por requisição M5 | testes: 1 login para 5 leituras; M5 + M15 com 0 logins extras e 2 leituras |

Os valores reais serão informados pelo relatório do `validate:live`.

---

## 9. Funcionalidades preservadas

- **Estratégia M1:** indicadores, limiares e lógica idênticos, com teste dedicado. Só a parte temporal mudou.
- **Motor M5 + contexto M15:** regras, contratos e persistência sem alteração. Apenas formatação de linhas longas foi ajustada.
- **Endpoints existentes:** mesmos contratos. O `/m5-signal` ganhou o campo `live`.
- **Interface:** design, gráfico de candles e PWA preservados.
- **Dados locais:** todos os registros históricos foram mantidos no disco.

---

## 10. Limitações

- Validação real ausente: latência, logins, reconexão real e comportamento da biblioteca diante da IQ real.
- O motor M5 continua sempre WAIT, só cobre GBPUSD-OTC, e a EMA 200 tem aquecimento curto (55% de peso da semente).
- O MACD não tem teste numérico.
- O M1 não detecta lacunas entre velas.
- Os registros persistidos não guardam versão da estratégia nem latência. WAIT não é registrado, e não existem os estados EXPIRED e NOT_EVALUABLE nos registros.
- O gráfico M5 é agregado de M1 (cerca de 20 velas).
- O estado `EXPIRED` não aparece na prática com expiração de 1 vela: na expiração a vela já deixou de ser atual e o estado é `NOT_CURRENT`.
- Não há acesso remoto: o backend aceita apenas loopback.

---

## 11. Bloqueios

1. **Credenciais PRACTICE** para a validação real (procedimento em `docs/TESTING.md`).
2. **Decisões N.1** (regra definitiva de entrada), **N.8** (regras M5/M15) e **N.10** (ativos M5) para os próximos blocos.

---

## 12. Pendências

- Executar `npm run validate:live` por 30 minutos ou mais e anexar o relatório.
- Decisões pendentes atualizadas em `docs/PROJECT_STATUS.md`.
- O arquivo `.env.local` do frontend aponta para `http://localhost:3001`. Ele funciona, mas `http://127.0.0.1:3001` evita ambiguidade IPv6. Não alterei esse arquivo porque é configuração local do proprietário.

---

## 13. Commits

| Commit | Conteúdo |
|---|---|
| `fe22233` | Higiene do repositório (`.gitignore`, arquivos gerados fora do Git) |
| `91456e3` | Worker Python persistente, correções temporais do M1, coletor sem carência e lint |
| `792aaa0` | Gateway no backend, agendador, API apenas em loopback e REAL isolado |
| `05c5045` | Frontend: estado ao vivo, latência e motor M5 real |
| `3fa3a9c` | Diagnóstico das causas de WAIT do motor M5 |
| *(commit de documentação)* | Documentação, ADRs, auditorias e este relatório |

**Branch publicada:** `origin/feat/tradepulse-v2-frontend`. O hash remoto final é confirmado no relatório de entrega.

---

## 14. Percentuais atualizados

Mesmo critério das auditorias: 22 itens, valendo 1, 0,5 ou 0.

| Valor | Qtd. | Itens |
|---|---|---|
| 1 | 11 | Coleta IQ · Estratégias por timeframe · Estratégia M1 · CALL/PUT/WAIT · Explicação · Horários e validade · Indisponibilidade · Sessão IQ · Responsividade · Documentação · Logs e health |
| 0,5 | 9 | Gráfico · Seleção de ativos · M5 · M15 · Histórico · Avaliação · Indicadores · Qualidade dos dados · PWA |
| 0 | 2 | Estatísticas · Backtesting |

Soma: 11 × 1 + 9 × 0,5 = 15,5. Itens que subiram desde a rev. 1 (+4,0): Sessão IQ (0 → 1), e
Coleta IQ, Estratégias por timeframe, Horários, Indisponibilidade, Documentação, Logs e health (0,5 → 1 cada).

**Resultado:**
- Implementação: **15,5 / 22 ≈ 70%** (era 52%).
- Validação funcional real: **≈ 5–10%** (sem mudança; nada validado com a IQ real nesta etapa).
- Validação estatística: **0%**.

---

## 15. Proposta para o próximo bloco

1. **Primeiro, validação real de A.1/A.2 pelo proprietário** (30 a 60 min). Ela aceita ou reabre este bloco com dados.
2. **Depois, bloco A.6 — Histórico e avaliação:**
   - registrar toda publicação, inclusive WAIT e os candidatos bloqueados pelo M15;
   - gravar versão da estratégia, latência e estado temporal no registro;
   - adicionar os estados EXPIRED e NOT_EVALUABLE;
   - liquidação feita por rotina do backend, sem depender de leituras;
   - migrar para SQLite (N.7);
   - estatísticas básicas com intervalo de confiança e tamanho de amostra.

   Isso cria a linha de base necessária antes de revisar a matemática do M5.
3. **Em paralelo, a engenharia decide** N.1, N.8 e N.10, usando os diagnósticos de WAIT coletados na validação real.
