# TradePulse — Relatório de Auditoria A.0 (Revisão 1)

- **Data:** 26/11/2026.
- **Base anterior:** `tradepulse-main.zip`, branch main. Relatório A.0 original.
- **Base atual:** `tradepulse-main (1).zip`, informado como branch `feat/tradepulse-v2-frontend`, commit `9144f59`.
- **Método:** leitura integral do código novo e do código alterado, e comparação arquivo a arquivo com a versão anterior.
- **Testes:** todas as suítes foram executadas numa cópia isolada. Dois scripts de reprodução externos rodaram o código real com um relógio controlado.
- **Nenhum arquivo-fonte foi modificado.** Não houve merge, push nem deploy.

> **Nota sobre a identificação da versão.** Não foi possível confirmar que o zip corresponde ao commit `9144f59`.
> - O zip não tem a pasta `.git`.
> - A pasta interna se chama `tradepulse-main`. Um zip de branch gerado pelo GitHub se chamaria `tradepulse-feat-tradepulse-v2-frontend`.
> - A diferença em relação ao zip anterior é de 45 caminhos de código (36 novos e 9 alterados) mais 150 registros JSON novos. O informado foi "20 arquivos, +2.937/−10".
> - Hipóteses: o zip inclui commits anteriores do branch, ou foi gerado a partir da pasta local.
> - Os números deste relatório se referem ao **conteúdo do zip**, não ao commit.

---

## A. Resumo executivo

A nova versão trouxe avanços reais. Os três principais:

1. **Um motor M5 separado**, com EMA 200, RSI 14 e MACD 12/26/9, filtrado por um **contexto M15**: EMA 200, inclinação e estrutura de topos e fundos. Ele usa um caminho de código próprio, e o M1 não foi alterado.
2. **A metodologia de entrada e avaliação do M5 foi corrigida.**
   - A entrada é o fechamento da vela de referência.
   - A avaliação compara o fechamento de T−1 com o fechamento de T. É um horizonte de 1 vela, coerente.
   - O motor declara honestamente que o candidato chega tarde ("NOT_ACTIONABLE_LATE").
3. **Gráfico de candles reais da IQ**, timestamps de latência no M5, um repositório de validações M5 separado do M1 e um PWA básico.

**Os problemas centrais continuam, e alguns pioraram:**

- **O frontend não usa o novo motor M5.** O painel "M5" continua chamando o endpoint antigo, ou seja, a estratégia EMA 9/21 do M1 rodando em 5 minutos. Os defeitos D1 (vela errada, +300 s) e D3 (WAIT depois de 120 s) **continuam visíveis para o usuário**. O novo motor só é acessível pela API e por uma CLI.
- **O motor M5 nunca emite sinal acionável.** `decision.action` é fixo em `"WAIT"`. Os candidatos CALL/PUT só servem para validação teórica.
- **O motor M5 está limitado a um ativo**, GBPUSD-OTC, fixo no código.
- **Foi introduzido um atraso artificial de 90 s:**
  - na carência do coletor (`DEFAULT_GRACE_SECONDS = 90`);
  - no cache do backend (`gracePeriodMs = 90_000`).

  As diretrizes proíbem isso explicitamente.
- **O cache M5 do backend devolve análise antiga como atual.** Entre T+0 e T+90 s depois de cada fechamento, ele entrega a análise da vela anterior, ainda marcada como `state: "UPDATED"`.
- **A pressão sobre a IQ Option aumentou.** Cada requisição M5 faz **3 logins**. Cada gráfico faz 1 login por minuto, fora de qualquer fila. A fila do M1 e a do M5 são independentes, então há logins simultâneos. A sessão IQ persistente continua inexistente.
- **A EMA 200 é calculada com 260 velas.** A semente por média simples ainda pesa cerca de 55% no valor final. Ela diverge da EMA 200 de uma plataforma de gráficos (reproduzido: 7,2 pips de diferença num exemplo sintético).
- **Mais arquivos indevidos versionados:** 155 registros JSON (eram 5), 3 pastas de backup no frontend e 2 arquivos `.bak` novos.

**Testes:** backend 51/51 (eram 34), Python 208/208 (eram 172), typecheck e build do frontend passam. O ruff encontra **7 erros** (era 1). Não existe nenhum teste matemático para MACD e EMA 200, e nenhum teste de frontend.

**Estimativa (ver M):** cerca de **52% implementado** (era 41%). **Menos de 10% validado** funcionalmente. **0% validado estatisticamente.** O motor M5 não tem nenhuma evidência de execução real no zip: não há registros de validação M5.

---

## B. Comparação entre a versão anterior e a atual

### B.1 Problemas da auditoria anterior

| # | Problema (A.0 original) | Situação atual | Evidência |
|---|---|---|---|
| D1 | Entrada M5 na fronteira seguinte (+300 s) | **Corrigido apenas no motor M5 novo**: entrada = fechamento da vela (T). **Continua no painel**, que usa a estratégia antiga. | `get_iq_option_demo_m5_signal.py:354`. Reprodução: `gap=300s` continua em `IqOptionTrendStrategy` |
| D2 | Consulta não alinhada ao fechamento (60 s + ciclo) | **Continua.** Agora é `setInterval` de 60 s, e um tick é descartado se o ciclo ainda estiver rodando. O coletor CLI alinha às fronteiras do M5, **mas com 90 s de carência**. | `App.tsx:157-166`, `collect_iq_option_demo_m5_validation.py:17` |
| D3 | Idade máxima de 120 s igual para todos os timeframes | **Continua no painel.** O motor M5 novo usa estados UPDATED, AWAITING_CONFIRMATION e STALE: corrigido nesse caminho. | Reprodução: M5 a 121 s → WAIT |
| D4 | Login IQ a cada requisição | **Piorou.** Requisição M5 = 3 logins. Gráfico = 1 login por minuto por painel. | Reprodução: `[('5m',260),('15m',260),('5m',260)]` |
| D5 | Fila sem limite e sem cancelamento | **Piorou.** Agora há duas filas independentes (M1 e M5) e o endpoint de candles fica fora de qualquer fila, o que gera logins concorrentes. O timeout de 15 s é o mesmo para uma operação 3 vezes maior. | `app.ts`, `iq-option-demo-m5-signal-cache.ts` |
| D6 | Cache de 55 s sem a chave da vela | **Continua no M1.** **Novo defeito no M5**: o cache dura até fechamento + 5 min + 90 s e devolve a vela anterior como UPDATED. | `iq-option-demo-m5-signal-cache.ts:136-155` |
| D7 | `analysisAt` antes da coleta; sem latência | **Melhorou no M5**: análise, início e fim da chamada ao provedor, montagem do payload e durações; `iqCandleAvailabilityAt: null` declarado honestamente. **Continua no M1.** O horário de publicação não é gravado nos registros M5. | `get_iq_option_demo_m5_signal.py:451-480` |
| D8 | Relógio local, sem horário do servidor IQ | **Continua** (`clockSource: application_utc_clock`). | — |
| D9 | M1 e M5 não independentes | **Parcial.** O motor M5 é independente no backend, mas o painel M5 ainda usa as regras do M1. Não há registro de estratégias nem versão. | `api.ts:153-170` (sem alteração) |
| D10 | Avaliação em 2 velas; WAIT não registrado; PENDING eterno | **Corrigido no M5** (1 vela). **Continua no M1.** WAIT não é registrado em nenhum dos dois. Não há EXPIRED nem NOT_EVALUABLE. Há 11 registros M1 em PENDING para sempre no repositório. | `iq_option_demo_m5_validation_repository.py:153-182`, dados versionados |
| D11 | Integração: WAIT nulo rejeitado; endpoint órfão; CORS | **Continua.** Novo: `iqHistory.ts` usa `VITE_API_BASE_URL ?? ""`, então sem `.env.local` o gráfico consulta o próprio Vite e falha. `api.ts` usa `localhost:3001` como padrão. | `iqHistory.ts:60-62` |
| D12 | Código diferente do que rodou | **Continua parcialmente.** O zip não corresponde ao "20 arquivos" informado. Não há registros M5, então o motor M5 não aparece executado em nenhum dado do zip. | ver nota inicial |

### B.2 Funcionalidades novas

| Funcionalidade | Onde |
|---|---|
| Motor M5: EMA 200, RSI 14, MACD 12/26/9, mais ADX 14 e ATR 14 | `quant-engine/app/cli/get_iq_option_demo_m5_signal.py` |
| Contexto M15: EMA 200, inclinação em 3 velas, estrutura de swings | `quant-engine/app/cli/iq_option_demo_m15_context.py` |
| Combinação M5 + M15, liquidação e persistência | `get_iq_option_demo_m5_signal_with_m15.py` |
| Snapshot de sincronização M5 (3 velas e timings) | `get_iq_option_demo_m5_sync.py`, `GET /api/v1/iq-option/demo/m5-sync` |
| Endpoint do sinal M5 com cache | `GET /api/v1/iq-option/demo/m5-signal` |
| Repositório e histórico de validações M5 | `iq_option_demo_m5_validation_repository.py`, `GET /api/v1/iq-option/demo/m5-validations[/:id]` |
| Coletor agendado (CLI) que chama o backend a cada M5 | `collect_iq_option_demo_m5_validation.py` |
| Endpoint de candles IQ (somente M1, 8 ativos) | `GET /api/v1/iq-option/demo/candles` |
| Gráfico de candles em SVG (M1 real; M5 agregado de 100 M1) | `frontend/src/components/charts/` |
| PWA: manifest, service worker (não guarda dados da API em cache) e ícone SVG | `frontend/public/`, `registerPwa.ts` |
| Novo layout do frontend ("TradePulse 2.0") | `App.tsx`, `style.css` |

### B.3 Regressões

1. **R1 — Atraso artificial de 90 s** no coletor e no cache do backend. Viola a regra dos 90 segundos.
2. **R2 — Cache M5 serve a vela anterior como UPDATED** por 90 s depois de cada fechamento.
3. **R3 — Mais logins por minuto e logins concorrentes:** M1, M5 e gráficos.
4. **R4 — Timeout de 15 s compartilhado** com uma requisição M5 que faz 3 logins e baixa 780 velas. O risco de 502 por timeout aumenta.
5. **R5 — O ruff passou de 1 para 7 erros.**
6. **R6 — Lixo no repositório:** de 5 para 155 JSON, mais 7 arquivos de backup em pastas ocultas e mais 2 `.bak`.
7. **R7 — Indicadores duplicados.** O motor M5 reimplementa EMA, RSI, ADX e ATR dentro da CLI, em vez de usar `app/indicators`. Passam a existir duas implementações que podem divergir. O MACD também ficou dentro da CLI.

O módulo de trading real e os endpoints Binance continuam iguais. Não foram encontradas regressões nas funcionalidades M1 que existiam: os testes antigos passam e `IqOptionTrendStrategy` não mudou.

---

## C. Arquitetura atual

```
Navegador (React 18 + Vite 6, PWA básico)
 ├─ Painéis: GET /demo/market-analysis (estratégia ANTIGA, M1 e "M5"), setInterval 60 s, fila serial
 └─ Gráfico (por painel): GET /demo/candles (M1, 100 velas) a cada 60 s; o M5 é agregado no navegador
        │
Backend Express 5 (:3001, todas as interfaces, sem autenticação)
 ├─ /demo/market-analysis → CachedIqOptionDemoAnalysisClient (fila 1, cache 55 s)
 ├─ /demo/m5-signal       → CachedIqOptionDemoM5SignalClient (fila 2, cache até fechamento + 5 min + 90 s)
 ├─ /demo/candles, /demo/m5-sync, históricos → sem fila e sem cache
 └─ Binance legado, trading real (preflight)
        │ execFile: 1 processo Python por requisição
Quant Engine (Python 3.14)
 ├─ IqOptionTrendStrategy (M1; inalterada)
 ├─ CLIs M5/M15 (lógica e indicadores próprios; somente GBPUSD-OTC)
 └─ Repositórios JSON: binary-signals (M1; versionado) e m5-validations (sem .gitignore)
        │ IQ_Option(email, senha).connect() a cada chamada ao provedor
IQ Option PRACTICE (iqoptionapi não oficial)

CLI externa opcional: collect_iq_option_demo_m5_validation --watch
  → chama /m5-signal em fronteira do M5 + 90 s
```

---

## D. Inventário de funcionalidades

**Funcionais (tecnicamente, comprovado por testes ou código):**

- Tudo o que já estava listado no relatório anterior para o M1.
- Motor M5 + M15 via API.
- Validação teórica M5 com horizonte correto.
- Gráfico M1 com dados reais da IQ.
- Timings do M5.
- Shell PWA.

**Parciais:**

- Gráfico M5: agregado de apenas 100 velas M1, o que dá cerca de 20 velas M5. Sem indicadores sobrepostos.
- Histórico: M5 tem API, mas não aparece no frontend; WAIT não é registrado.
- Separação M1/M5: existe no backend, não no painel.
- PWA: só ícone SVG, sem PNG 192/512. Instalação não validada.
- Qualidade dos dados: o M5 verifica contiguidade e estado; o M1, não.

**Ausentes:**

- Sinal M5 acionável.
- Motor M5 para outros ativos.
- Registro de estratégias e versão.
- Estatísticas e intervalos de confiança.
- Backtesting.
- Sessão IQ persistente e horário do servidor.
- Agendador no backend.
- Estados EXPIRED e NOT_EVALUABLE.
- Testes matemáticos de MACD e EMA 200.
- Testes de frontend.
- Atualização da documentação. `README.md`, `PROJECT_STATUS.md` e `ROADMAP.md` são idênticos aos da versão anterior.

**Não verificadas:**

- Conexão real com a IQ: não há credenciais, e não devo digitá-las.
- Execução real do motor M5: não há registros no zip.
- Instalação do PWA e uso no celular.

---

## E. Diagnóstico detalhado

Legenda: **[C]** comprovado · **[H]** hipótese.

### E.1 Motor M5 (item 4 da solicitação)

**[C] Regras implementadas** (`evaluate_candidate`):

| Componente | Regra |
|---|---|
| Velas | 250 fechadas, contíguas, estado `UPDATED` (busca 260) |
| ATR 14 | > 0; distância `|close − EMA200| / ATR14 ≥ 0,20` |
| ADX 14 | ≥ 20 |
| CALL | close > EMA 200; 55 ≤ RSI ≤ 68; MACD > sinal; histograma > 0 e subindo |
| PUT | close < EMA 200; 32 ≤ RSI ≤ 45; MACD < sinal; histograma < 0 e caindo |
| M15 | CALL exige BULLISH; PUT exige BEARISH; M15 precisa estar UPDATED |
| Saída | `decision.action = "WAIT"` **sempre**; o candidato vai para `candidateAction` com `actionability = NOT_ACTIONABLE_LATE` |

**Observações:**

- **[C]** ADX e ATR **não fazem parte do conjunto aprovado** (EMA 200, RSI 14, MACD + M15). Foram adicionados sem aprovação registrada. Ver N.8.
- **[C]** As faixas de RSI do CALL (55–68) e do PUT (32–45) são assimétricas. Não há justificativa documentada.
- **[C]** Limitado a GBPUSD-OTC no Python, nos schemas Zod e na mensagem de erro.
- **[C]** A EMA 200 usa uma semente por média simples com 260 velas. Depois de 60 atualizações, a semente ainda pesa 54,9%; com 500 velas pesaria 5%, e com 1000, cerca de 0%. O valor diverge do gráfico da plataforma.
- **[C]** A EMA, o RSI e o ADX/ATR foram duplicados dentro da CLI. O cálculo do RSI dá 100 quando não há perdas, igual ao módulo original.
- **[C]** Não há teste numérico de MACD nem de EMA 200 contra valores de referência. Os testes do M5 cobrem só a lógica de decisão: 3 testes do M5, 3 do M15 e 8 da combinação.

### E.2 Contexto M15 (item 5)

**[C] Classificação:**

- **BULLISH:** close > EMA 200(M15), EMA 200 maior que 3 velas antes, e estrutura "topos e fundos ascendentes".
- **BEARISH:** o simétrico.
- **NEUTRAL:** qualquer outro caso.

**[C] Swings:** topo ou fundo estrito, com raio de 2 velas para cada lado. A estrutura compara os dois últimos topos e os dois últimos fundos.

**[C] Disponibilidade temporal:**

- Usa somente velas M15 fechadas (filtro `to ≤ agora`) e exige estado UPDATED.
- Exemplo: numa decisão M5 às 12:05, a última M15 válida é a de 11:45–12:00.
- **Não há uso de vela M15 aberta.** Um swing só é confirmado 2 velas M15 (30 min) depois. Isso é correto: não há informação futura.

**[H]** O critério de 3 condições simultâneas é muito restritivo. Na reprodução sintética, o M15 ficou NEUTRAL/UNCONFIRMED. Na prática, isso deve produzir **quase sempre WAIT**. Só a medição em dados reais confirma.

**Os critérios matemáticos não foram apresentados para aprovação antes da implementação**, como pede a seção 8 das diretrizes. Ver N.8.

### E.3 Indicadores EMA 200, RSI 14 e MACD (item 6)

| Indicador | Fórmula | Situação |
|---|---|---|
| EMA 200 | semente SMA(200) + EMA padrão | Correta matematicamente; **aquecimento insuficiente** (260 velas) |
| RSI 14 | Wilder | Correto; RSI = 100 com mercado parado |
| MACD 12/26/9 | EMA12 − EMA26; sinal = EMA9 do MACD; histograma = MACD − sinal | Correto (alinhamento das séries verificado); **sem teste numérico**; dentro da CLI |
| ADX/ATR 14 (no M5) | Wilder (cópia) | Correto; duplicado |

### E.4 Sincronização dos candles (item 7)

**Motor M5 (caminho novo):**

- **[C]** Os estados UPDATED, AWAITING_CONFIRMATION e STALE são calculados contra o relógio local.
- **[C]** A contiguidade é verificada.
- **[C]** O instante em que a IQ disponibiliza a vela é declarado como `null` (correto: a fonte não informa).

**Painel e M1:**

- Sem mudança: D2, D3, D6, D7 e D8 continuam.

**Coletor e cache (regressão R1/R2):**

- **[C]** O coletor dispara em fronteira M5 + 90 s (permitido entre 15 e 240 s).
- **[C]** O cache do backend só recalcula depois de fechamento + 5 min + 90 s.
- Resultado: a análise de uma vela fica disponível **90 s depois do fechamento, na melhor hipótese**. Entre T e T+90 s, a resposta é a da vela anterior, marcada UPDATED (o estado não é recalculado na leitura do cache).

**Gráfico:**

- **[C]** O M5 é agregado de M1 no navegador, descartando baldes incompletos.
- **[H]** Pode divergir das velas M5 nativas da IQ, por diferença de volume e de arredondamento.
- Com 100 velas M1, o gráfico mostra cerca de 20 velas M5.

### E.5 Ciclo de vida e validade (item 8)

- **[C]** No M5, a entrada é T e a expiração é T+5 min. O sinal é rotulado NOT_ACTIONABLE_LATE, porque é confirmado depois de T. Isso é honesto: não apresenta o sinal como oportunidade atual.
- **[C]** Com o atraso de 90 s, cerca de 30% da vela de entrada já passou antes da publicação.
- **[C]** O registro M5 não tem campo de horário de publicação nem de latência. `recordedAt` é o início da análise, não a publicação.
- **[C]** As estatísticas futuras contariam o sinal "como se tivesse sido recebido em T". Isso contraria a regra da seção 12: "um sinal atrasado não poderá ser contabilizado como se tivesse sido recebido no momento ideal". Hoje isso é atenuado pelo rótulo NOT_ACTIONABLE_LATE, que precisa ser obrigatório em qualquer estatística.
- **[C]** O M1 continua igual: entrada na fronteira seguinte, idade máxima de 120 s.
- A decisão sobre a regra de entrada (N.1) **continua pendente**. A implementação atual equivale à Opção 2 do relatório anterior, mas **sem a janela de tolerância W**: nunca é acionável.

### E.6 Avaliação WIN/LOSS e demais estados (item 9)

**M5:**

- **[C]** A avaliação usa o preço de referência (fechamento de T−1, aproximadamente a abertura de T) contra o fechamento da vela que abre em T. A metodologia está correta.
- **[C]** A liquidação ocorre só quando chega uma nova requisição M5, e só se a vela de entrada estiver entre as 260 últimas (cerca de 21 horas). Depois disso, o registro fica PENDING para sempre.
- **[C]** A deduplicação usa ativo + ação + entrada.
- **[C]** Só são persistidos os candidatos CALL/PUT alinhados ao M15. O WAIT e os candidatos M5 bloqueados pelo M15 **não são registrados**, então não dá para medir a frequência de WAIT nem o efeito do filtro M15.

**M1:** inalterado (2 velas, PENDING eterno).

**Estados ausentes:** EXPIRED, NOT_EVALUABLE e WAIT como registro. A metodologia não está documentada em `docs/`.

**Dados reais versionados** (M1, estratégia antiga, 10 a 14/11):

- 155 registros: 147 M1 e 8 M5.
- M1 liquidados: 73 WIN, 64 LOSS. São 53,3% em n = 137, com intervalo de 95% de aproximadamente [45%, 62%]. Há 10 registros PENDING eternos.
- Isso **não é evidência** de vantagem estatística, por três motivos:
  - o intervalo inclui o ponto de equilíbrio típico de 54–56% com payout de 80–87%;
  - a metodologia de 2 velas está errada;
  - a amostra é pequena.

### E.7 Cache, concorrência e conexão (item 10)

**[C] Logins IQ por minuto** com 4 painéis (2 em M1 e 2 em M5):

| Origem | Logins |
|---|---|
| Painéis | 4 |
| Gráficos | 4 |
| Requisição M5 via `/m5-signal` | +3 (se chamada) |

Isso dá **de 8 a 11 logins por minuto**, em até 3 trilhas simultâneas: fila M1, fila M5 e gráficos sem fila.

- **[H]** Esse volume tende a provocar limitação pela IQ e é a causa mais provável da instabilidade remanescente.
- **[C]** Não há reconexão, reutilização, limite de requisições, health check real nem logs estruturados.
- **[C]** O frontend aborta em 15 s, mas o processo Python continua rodando.

### E.8 Frontend e gráficos (item 11)

- **[C]** Novo layout "TradePulse 2.0": tema escuro, 1, 2 ou 4 painéis, media queries em 1250, 950 e 550 px.
- **[C]** Gráfico de candles em SVG próprio, sem biblioteca. Dados reais M1 da IQ e M5 agregado. Sem indicadores sobrepostos e sem marcação de entrada e expiração.
- **[C]** O painel de sinal **continua consumindo apenas o endpoint antigo**. O motor M5 + M15, os timings, o histórico de validações e o estado M15 **não aparecem na interface**.
- **[C]** PWA: manifest, service worker (rede primeiro na navegação; não guarda API em cache, o que é correto) e ícone SVG.
  - **[H]** Sem ícones PNG de 192 e 512 px, a instalação pode falhar em alguns navegadores e no iOS.
  - O `<meta theme-color>` aparece duplicado em `index.html`.
- Testes de frontend: inexistentes.

### E.9 Segurança e versionamento (item 12)

**Novos arquivos indevidos:**

- `quant-engine/data/iq-option-demo-binary-signals/`: **155 JSON** (eram 5).
- `frontend/.backup-candles-20261112-173053/` (2 arquivos), `frontend/.backup-chart-pwa-20261112-163601/` (3) e `frontend/.tradepulse-v2-backup-20261112-162634/` (2).
- `frontend/src/App.tsx.20261112-163040.bak` e `frontend/src/components/charts/iqHistory.ts.bak-20261112-171234`.
- **Continuam:** os 8 `.bak` anteriores, `tsconfig.tsbuildinfo`, `egg-info`, os arquivos vazios e o teste solto na raiz.

**Ignore ausente:** `quant-engine/data/iq-option-demo-m5-validations/` não tem `.gitignore`. Os registros M5, quando existirem, serão versionados.

**Credenciais:** nenhuma credencial real encontrada.

**Riscos que continuam:**

- O backend escuta em todas as interfaces, sem autenticação.
- O login da conta PRACTICE é o mesmo da conta real.
- O módulo de trading real (preflight) continua.
- A biblioteca não oficial é instalada direto do Git.

**Novo risco:** o volume de logins aumenta a chance de bloqueio da conta pela IQ.

**Git:** branch, commits, alterações locais e o estado do commit `9144f59` **continuam sem verificação**, porque não há `.git` e o `gh` não está instalado.

---

## F. Estado da integração IQ Option

Não houve mudança estrutural desde o relatório anterior. Mesma biblioteca, mesmo login por chamada ao provedor, mesmo relógio local.

**Novo:**

- Endpoint de candles M1 para 8 ativos.
- Chamadas M15.
- Volume de logins maior (E.7).

**Evidência de uso real:** os registros M1 de 10 a 14/11 mostram EURUSD, GBPUSD, USDJPY, EURJPY e EURGBP.

**Bloqueio desta auditoria:** a conexão real não foi testada (sem credenciais).

---

## G. Estado das estratégias M1 e M5

| | M1 | M5 (novo) |
|---|---|---|
| Código | `IqOptionTrendStrategy` (inalterada) | CLIs `get_iq_option_demo_m5_signal*` |
| Indicadores | EMA 9/21, RSI 14, ADX 14, ATR 14 | EMA 200, RSI 14, MACD 12/26/9, **ADX 14, ATR 14** (não aprovados) + M15 |
| Ativos | 8 OTC | **somente GBPUSD-OTC** |
| Saída | CALL/PUT/WAIT acionável | **sempre WAIT**; candidato teórico |
| Entrada | fronteira seguinte à análise (defeito) | fechamento da vela T (coerente, mas tardio) |
| Avaliação | 2 velas (defeito) | 1 vela (correta) |
| Usada no painel | **sim, também para "M5"** | **não** |
| Versão da estratégia | não | não |
| Independência | não afetada pelo M5 | independente do M1 |

---

## H. Estado da sincronização

Resumo do que foi descrito em E.4 e E.5:

- **Motor M5:** sincronização correta em relação ao fechamento (entrada = T, estados de atualidade, timings). Porém o caminho de entrega (coletor e cache) **adiciona 90 s artificiais**, e o cache serve a vela anterior como UPDATED.
- **Painel:** inalterado. O atraso varia entre 60 s e 120 s ou mais, a vela fica errada no "M5" e o WAIT aparece depois de 120 s.
- A proposta da seção G do relatório anterior (agendador no backend, sem carência fixa, janela de tolerância W) **continua válida e necessária**.

---

## I. Testes e qualidade (item 13)

| Verificação | Versão anterior | Versão atual |
|---|---|---|
| Backend vitest | 34/34 (9 arquivos) | **51/51 (14 arquivos)** |
| Backend `tsc --noEmit` | passou | passou |
| Python pytest | 172/172 | **208/208** |
| Python ruff | 1 erro | **7 erros** (3 de imports desordenados ou sem uso, 4 de linha longa) |
| Frontend `tsc --noEmit` | passou | passou |
| Frontend `vite build` | passou (165,7 KB) | passou (169,2 KB) |
| Testes de frontend | nenhum | nenhum |
| Teste numérico de MACD/EMA 200 | — | **nenhum** |
| Teste de integração com IQ real | nenhum | nenhum |

**Reproduções desta revisão** (scripts externos, sem alterar o código):

- `repro_timing.py` sobre o código novo: o painel continua com `gap=300s` no M5 e com WAIT depois de 121 s.
- `repro_m5.py`:
  - 3 chamadas ao provedor (3 logins) por requisição M5;
  - entrada = 17:05:00 para uma análise às 17:05:04;
  - peso da semente da EMA 200 de 54,9% com 260 velas;
  - cache reutilizado até 17:11:30 para a vela fechada às 17:05.

**Limitação:** todos os testes usam dados simulados. Nenhum teste cobre a carência de 90 s, o estado UPDATED servido do cache, o número de logins ou a integração do painel com o motor M5.

---

## J. Segurança e GitHub

Ver E.9. Itens que exigem aprovação para correção:

1. Remover do versionamento (com `git rm --cached`, preservando os arquivos locais):
   - os 155 JSON;
   - os 10 `.bak`;
   - as 3 pastas de backup;
   - o `tsbuildinfo` e o `egg-info`.
2. Adicionar `.gitignore` em `data/iq-option-demo-binary-signals/` e `data/iq-option-demo-m5-validations/`.
3. Ligar o backend apenas em `127.0.0.1`, se não houver acesso pela rede.
4. Decidir o destino do módulo de trading real (N.2).

---

## K. Matriz atualizada de funcionalidades

| Funcionalidade | Anterior | Atual |
|---|---|---|
| Coleta de velas IQ PRACTICE | Implementada, não validada | Implementada, não validada |
| Sessão, reconexão e reutilização IQ | Não implementada | **Não implementada (pressão maior)** |
| Horário do servidor e relógio | Não implementado | Não implementado |
| Indicadores EMA, RSI, ADX, ATR | Concluídos e validados (testes) | Concluídos e validados (testes); **duplicados** no M5 |
| MACD | Não implementado | **Implementado, não validado** (sem teste numérico) |
| EMA 200 com aquecimento adequado | Não implementada | **Parcial** (260 velas; semente pesa 55%) |
| Estratégia M1 | Implementada, não validada | Implementada, não validada (inalterada) |
| Estratégia M5 | Não implementada | **Parcial**: backend completo, somente GBPUSD, sempre WAIT, fora do painel, ADX/ATR não aprovados |
| Contexto M15 | Não implementado | **Implementado, não validado** (somente GBPUSD; critérios não aprovados) |
| Separação por timeframe e versão | Não implementada | **Parcial** (backend sim; painel não; sem versão) |
| CALL/PUT/WAIT com motivos | Implementado, não validado | Implementado, não validado |
| Horários de entrada, expiração e validade | Com defeito | **Parcial**: correto no M5; com defeito no M1 e no painel |
| Agendamento alinhado e latência | Não implementado | **Com defeito**: coletor CLI com +90 s; timings só no M5 |
| Cache e concorrência | Parcial | **Com defeito** (R2, R3, R4) |
| Histórico de análises | Parcial | Parcial (M5 por API; sem WAIT; fora do frontend) |
| Avaliação de resultados | Com defeito | **Parcial**: M5 correto; M1 com defeito; sem EXPIRED/NOT_EVALUABLE |
| Estatísticas de desempenho | Não implementadas | Não implementadas |
| Backtesting | Não implementado | Não implementado |
| Monitoramento da qualidade dos dados | Parcial | Parcial (melhor no M5) |
| Indisponibilidade e health check | Parcial | Parcial |
| Frontend: painel de sinal | Implementado, não validado | Implementado, não validado (**não usa o M5 novo**) |
| Frontend: gráfico de candles | Não implementado | **Parcial** (M1 real; M5 com cerca de 20 velas; sem indicadores) |
| Frontend: histórico e estatísticas | Não implementados | Não implementados |
| Responsividade | Implementada, não validada | Implementada, não validada |
| PWA | Não implementado | **Parcial** (manifest + SW; ícone só SVG; não validado) |
| Documentação | Parcial e desatualizada | Parcial e desatualizada (**sem alterações**) |
| Conexão real IQ nesta auditoria | Bloqueada | Bloqueada |
| Estado do Git | Bloqueado | Bloqueado |

---

## L. Percentual de implementação e de validação

Mesmo critério do relatório anterior: 22 itens com peso igual; 1 = completo, 0,5 = parcial ou com defeito, 0 = ausente.

| Valor | Qtd. | Itens |
|---|---|---|
| **1** | 4 | Estratégia M1 · CALL/PUT/WAIT · Explicação · Responsividade |
| **0,5** | 15 | Coleta IQ · **Gráfico (0 → 0,5)** · Seleção de ativos · **Estratégias por timeframe (0 → 0,5)** · **M5 (0 → 0,5)** · **M15 (0 → 0,5)** · Horários · Histórico · Avaliação · Indicadores (continua 0,5: MACD sem teste, EMA 200 sem aquecimento) · Qualidade dos dados · Indisponibilidade · **PWA (0 → 0,5)** · Documentação · Logs e timings |
| **0** | 3 | Estatísticas · Sessão IQ · Backtesting |

Nenhum item subiu para 1. Os itens em negrito saíram de 0 para 0,5 nesta versão.

**Soma:**

- Itens com 1: M1, CALL/PUT/WAIT, Explicação e Responsividade = **4,0**.
- Itens com 0,5: Coleta, Gráfico, Ativos, Estratégias por timeframe, M5, M15, Horários, Histórico, Avaliação, Indicadores, Qualidade, Indisponibilidade, PWA, Documentação e Logs = 15 itens = **7,5**.
- Itens com 0: Estatísticas, Sessão IQ e Backtesting = **0**.
- Total: 4,0 + 7,5 = **11,5 / 22 ≈ 52% de implementação**. Eram 41%.

**Validação funcional** (uso real comprovado, contra critérios de aceitação):

- Só a coleta M1 e o fluxo CALL/PUT M1 têm evidência real parcial (147 registros, 10 a 14/11).
- O motor M5 e o M15 têm **zero evidência real** no zip.
- Estimativa: **cerca de 5% a 10% validado.**

**Validação estatística: 0%.** Não há amostra válida nem metodologia correta no M1, e não há registros M5.

---

## M. Roadmap revisado

Mantém a lógica do relatório anterior, ajustada ao que já existe. **Não reimplementar** o motor M5, o M15 e a metodologia de avaliação do M5: eles serão **consolidados e integrados**.

1. **A.0.1 — Higiene do repositório** (pequeno; aprovação em J):
   - tirar do versionamento os JSON, os backups, o `tsbuildinfo` e o `egg-info`;
   - criar os `.gitignore` da pasta de dados;
   - corrigir os 7 erros do ruff;
   - atualizar o PROJECT_STATUS.
2. **A.1 + A.2 — Coleta confiável e sincronizada:**
   - sessão IQ persistente única, com limite de requisições, fila única e cancelamento;
   - agendador no backend disparado no fechamento, **sem carência fixa de 90 s**;
   - cache com a chave "última vela fechada" e estado recalculado na leitura;
   - endpoint de candles passando pela mesma sessão e pelo mesmo cache;
   - timestamps de publicação e latência para M1 e M5;
   - horário do servidor IQ, se a biblioteca permitir.
3. **A.5 — Ciclo de vida:** aplicar a regra aprovada em N.1 (janela W) a M1 e M5; estados ACTIONABLE, EXPIRED e NOT_ACTIONABLE_LATE.
4. **A.6 — Histórico e avaliação:**
   - registrar todas as análises, inclusive WAIT e os candidatos bloqueados pelo M15;
   - corrigir a metodologia do M1, reaproveitando a do M5;
   - adicionar EXPIRED e NOT_EVALUABLE;
   - liquidação independente das visitas na tela;
   - versão da estratégia;
   - persistência (N.7).
5. **A.3 + A.4 — Consolidação do M5 e do M15:**
   - mover os indicadores para `app/indicators`, com testes numéricos;
   - aquecimento da EMA 200 com 1000 velas (ou paginação);
   - decisão sobre ADX/ATR e sobre as faixas de RSI (N.8);
   - outros ativos (N.10);
   - registro de estratégias versionado.
6. **A.9 — Integração do frontend:** o painel M5 passa a usar o motor M5 + M15; histórico e estatísticas; indicadores e marcação de entrada e expiração no gráfico; estado real da conexão.
7. **A.7 — Backtesting.**
8. **A.8 — Revisão do M1.**
9. **A.10 — Estabilização e PWA:** ícones PNG, validação de instalação, autenticação e bind.
10. **A.11 — Documentação e lançamento.**

---

## N. Decisões pendentes

As decisões 1 a 14 do relatório anterior **continuam todas pendentes**. As novas são a 15 a 18.

1. **Regra de entrada e janela de tolerância W.** Hoje o M5 equivale à "Opção 2 sem W", portanto nunca é acionável. Recomendação: Opção 2 + 3, com W = 10 s no M1 e 30 s no M5.
2. **Módulo de trading real:** remover, manter desativado ou mover para outro branch? Recomendação: remover do branch principal.
3. **Endpoints Binance legados e OTCharts:** desativar, arquivar ou manter isolados?
4. **Git:** confirmar se o zip é o commit `9144f59` (a contagem de arquivos não bate). Fornecer o clone local ou o acesso via `git`/`gh` para auditar branches e alterações locais.
5. **Credenciais IQ:** confirmar que é aceitável usar o login que também dá acesso à conta real. A validação real deve ser feita pelo proprietário, com as variáveis de ambiente locais.
6. **Arquitetura da conexão:** processo Python persistente (JSON por linha via stdin/stdout, gerenciado pelo Node), que é a recomendação, ou microserviço HTTP em Python.
7. **Persistência:** arquivos JSON ou SQLite? Recomendação: SQLite.
8. **Regras exatas do M5 e do M15.** Precisam de aprovação formal, porque já foram implementadas sem ela:
   - manter ou remover o **ADX ≥ 20** e a **distância mínima de 0,20 ATR** até a EMA 200;
   - faixas de RSI: CALL 55–68 e PUT 32–45 (assimétricas). Manter?
   - MACD: exigir linha > sinal, histograma > 0 **e** subindo (as três condições), ou menos?
   - M15: exigir as 3 condições (posição, inclinação em 3 velas e estrutura com raio 2)? A suspeita é que isso dê WAIT quase sempre.
   - aquecimento da EMA 200: 1000 velas?
9. **Expiração:** 1 vela no M1 e no M5?
10. **Ativos:** expandir o M5 além de GBPUSD-OTC? Lista dinâmica vinda da IQ ou lista curada?
11. **Payout para o ponto de equilíbrio:** ler da IQ ou configurar manualmente?
12. **Idioma dos motivos:** PT-BR no backend?
13. **Acesso pelo celular / PWA:** só rede local ou remoto? Define o bind e a autenticação.
14. **Gerenciador de pacotes:** npm ou pnpm?
15. **(Nova) Carência de 90 s** no coletor e no cache: confirmar a remoção. Ela contraria a regra das diretrizes.
16. **(Nova) Painel M5:** confirmar que ele deve passar a consumir o motor M5 + M15. Ficaria sem sinal acionável até a decisão 1.
17. **(Nova) Gráfico M5:** usar velas M5 nativas da IQ (recomendado; o backend já suporta 5m no provedor) ou manter a agregação de M1 no navegador?
18. **(Nova) Coletor CLI:** manter como ferramenta de validação ou substituí-lo pelo agendador do backend (A.2)? Recomendação: substituir.

---

## O. Proposta para o próximo bloco

**Bloco A.1 + A.2 — "Coleta confiável e sincronizada"**, precedido do A.0.1 se aprovado. A proposta é a mesma do relatório anterior, ajustada à nova versão.

**Problemas resolvidos:**

- D2, D4, D5, D6, D7 e D8;
- as regressões R1 a R4;
- D1 e D3 no M1, depois de aplicada a regra N.1.

**Escopo:**

1. Uma sessão IQ persistente e única para análise M1, motor M5 + M15, gráficos e sincronização. Um login por sessão, reconexão controlada, limite de requisições, fila única com timeout de espera e cancelamento.
2. Um agendador no backend, disparado no fechamento de cada vela de cada combinação ativa de ativo e timeframe, **sem carência fixa**. O frontend e o coletor apenas leem o resultado publicado.
3. Cache com a chave da última vela fechada. O estado de atualidade é recalculado em cada resposta. Nada antigo é marcado como UPDATED.
4. Timestamps completos e latência em M1 e M5, inclusive no registro persistido. Horário do servidor IQ, se disponível.
5. **Regras de decisão do M1 e do M5 + M15 sem nenhuma alteração** neste bloco, protegidas por testes de regressão.
6. Testes novos para cada defeito listado. Eles devem falhar no código atual e passar depois da correção.

**Critérios de aceitação:**

- 30 minutos de DEMO real, M1 (2 ativos) + M5 GBPUSD-OTC com M15:
  - mediana entre o fechamento da vela e a publicação ≤ 5 s;
  - p95 ≤ 15 s;
  - 1 login por sessão, comprovado em log;
  - 0 respostas antigas marcadas UPDATED;
  - 0 timeouts sem explicação.
- Relatório com o log real.

**Como o proprietário verifica:**

1. Rodar `/m5-signal` nos horários :00, :05 e :10. A resposta deve trazer a vela recém-fechada em poucos segundos, com `publishedAt` e `latencyMs`.
2. Deixar o painel aberto: ele deve atualizar logo depois de cada fechamento, não 60 a 90 s depois.
3. Desligar a internet: o painel deve mostrar indisponibilidade, nunca um sinal antigo apresentado como atual.

**Fora do escopo deste bloco** (dependem de decisões): ligar o painel ao motor M5 (N.16), as regras de M5/M15 (N.8) e a janela W (N.1).

Aguardo a aprovação da engenharia e as respostas da seção N antes de iniciar os blocos A.1 e A.2.
