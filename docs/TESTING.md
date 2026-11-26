# Testes e validação

> Testes automatizados **não substituem** a validação com a IQ Option real. Os resultados abaixo
> provam a lógica com dados simulados; o comportamento com a fonte real ainda precisa ser
> comprovado pelo procedimento ao final deste documento.

## Resultados atuais (26/11/2026, Node 24.21, Python 3.14.8)

| Verificação | Antes de A.1/A.2 (9144f59) | Depois |
|---|---|---|
| Python `pytest` | 208/208 | **247/247** |
| Python `ruff check` | 7 erros | **0 erros** |
| Backend `vitest` | 51/51 (14 arquivos) | **71/71 (16 arquivos)** |
| Backend `tsc --noEmit` e `build` | passa | passa |
| Frontend `tsc --noEmit` e `vite build` | passa | passa |
| Frontend: testes automatizados | nenhum | nenhum (verificação visual no navegador) |
| Validação real IQ Option PRACTICE | não | **não (bloqueada: credenciais)** |

Removidos: 8 testes dos dois caches eliminados (TTL de 55 s e carência de 90 s), substituídos pelos
testes do cache por vela e do serviço de publicação.

## Cobertura pedida para A.1/A.2

| Tema | Testes |
|---|---|
| Reutilização de sessão | `test_reuses_one_login_for_many_candle_requests`, `reuses one worker process` |
| Reconexão | `test_reconnects_after_the_websocket_drops`, backoff progressivo e limite |
| Concorrência | `never sends two requests to the session at the same time`, deduplicação por chave |
| Timeout | `times out, replaces a stuck worker and restarts with backoff`, `test_candle_timeout_drops_the_session…` |
| Cancelamento | `drops a cancelled request before it reaches IQ Option` |
| Limite de fila | `rejects requests beyond the queue limit` |
| Fechamento M1/M5/M15 | `test_candle_close_identification_per_timeframe`, `test_open_candle_is_never_returned_as_closed` |
| Mudança de vela | `test_a_new_candle_boundary_forces_a_new_request`, `publishes the analysis of the just-closed candle…` |
| Dados atrasados | `retries in a controlled way until the source publishes…`, `gives up on a candle at the next boundary` |
| Cache desatualizado | `test_old_series_is_reported_as_awaiting_never_as_current`, `never presents the previous candle as current…` |
| Análises duplicadas | `does not analyse the same candle twice…`, deduplicação dos repositórios |
| Validade temporal | `marks a candidate published after the tolerance as late…`, expiração, entrada M1/M5 |
| Falhas da fonte | credenciais ausentes, autenticação, PRACTICE não confirmado, indisponibilidade com `retryAt` |
| Preservação do M1 | `test_m1_decision_rules_are_unchanged` + testes antigos da estratégia |
| Motor M5/M15 preservado | testes existentes do M5/M15 + `test_m5_engine_with_m15_uses_one_login…` |
| Proteção contra operações reais | transporte sem métodos de ordem, comandos rejeitados, rotas REAL 404, PRACTICE obrigatório |
| Sem atraso fixo de 90 s | `test_watch_never_waits_a_fixed_ninety_seconds`, coletor dispara na fronteira |
| Integração real Node ↔ Python | `gateway-worker.integration.test.ts` (processo Python real, sem login) |

## Como executar

```powershell
cd quant-engine; .\.venv\Scripts\python.exe -m pytest; .\.venv\Scripts\python.exe -m ruff check .
cd ..\backend;  npm test; npm run typecheck; npm run build
cd ..\frontend; npm run typecheck; npm run build
```

## Validação real pelo proprietário

Pré-requisito: conta IQ Option com saldo PRACTICE. O TradePulse **não executa ordens**.

1. Terminal 1 (backend), com credenciais **apenas nesta sessão do terminal**:

   ```powershell
   cd backend
   $env:IQ_OPTION_DEMO_EMAIL = "seu-email"
   $env:IQ_OPTION_DEMO_PASSWORD = "sua-senha"
   npm run dev
   ```

2. Terminal 2 (frontend): `cd frontend; npm run dev` e abrir `http://127.0.0.1:5173`.
   Configurar 2 painéis: `EURUSD-OTC M1` e `GBPUSD-OTC M5 (experimental)`.
3. Terminal 3 (medição automática, 30 minutos, 2 pares M1 + 1 M5):

   ```powershell
   cd backend
   npm run validate:live -- --minutes 30 --pairs EURUSD-OTC:1m,GBPUSD-OTC:1m,GBPUSD-OTC:5m
   ```

4. O script grava `backend/data/validation/live-validation-*.md` e `.json` com:
   - cada publicação (vela, horário de publicação, latência desde o fechamento, tentativas, estado);
   - mediana, p95 e máximo da latência;
   - logins antes e depois (o esperado é **1 login** para toda a sessão);
   - erros e quantidade de "vela anterior mostrada como atual" (o esperado é **0**);
   - causas do WAIT do motor M5.
5. Também é possível conferir no painel, a cada fechamento (:00, :05, :10…): o estado volta a
   "Atualizado" segundos depois do fechamento, e "Dados, horários e latência" mostra a vela nova.
6. Teste de indisponibilidade: desligar a internet. O painel deve mostrar "Aguardando nova vela" ou o erro da IQ,
   **nunca** a vela anterior como atual. Ao religar, a sessão reconecta com backoff progressivo.
7. Enviar à engenharia o arquivo `.md` gerado e `backend/data/runtime/publications.jsonl`
   (não contêm credenciais; conferir antes de enviar).

Critérios de aceitação propostos: mediana ≤ 5 s, p95 ≤ 15 s, 1 login por sessão, 0 velas antigas
mostradas como atuais, 0 timeouts sem explicação.
