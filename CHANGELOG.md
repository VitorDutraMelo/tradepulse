# Changelog

Formato inspirado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Datas em UTC.

## [Blocos A.1 + A.2] — 2026-11-26 — branch `feat/tradepulse-v2-frontend`

### Adicionado
- Worker Python persistente (`app.gateway.worker`) com **uma** sessão IQ Option PRACTICE: PRACTICE verificado
  após o login, reconexão com backoff progressivo, espera de candles com prazo, relógio do servidor IQ,
  logs estruturados com redação de credenciais.
- Cache de candles por vela (ativo/timeframe/última vela fechada), compartilhado por análise, gráfico e liquidação.
- `GatewayWorker` no backend: fila limitada, deduplicação, cancelamento, timeout com reinício do worker.
- `LiveAnalysisService`: análise disparada em cada fechamento de vela, retentativas controladas, uma publicação
  por vela, atualidade e validade calculadas na leitura, log JSON-lines de publicações com diagnóstico de WAIT.
- Endpoints `GET /api/v1/iq-option/demo/live` e `/status`; `/health` informa o estado do gateway.
- Painel: estado da sessão, atualidade, estratégia e versão, selos "experimental" e "não operacional",
  abertura teórica, expiração, preço teórico × observado, atraso × tolerância, latências e tentativas.
- `npm run validate:live`: procedimento de validação real para o proprietário.
- Documentação permanente (`docs/`), ADRs 0001–0006, auditorias A.0 como referência histórica.

### Alterado
- M1: a entrada passa a ser o fechamento da vela de referência (antes: fronteira após o horário da análise).
  A atualidade passa a ser 1 timeframe (antes: 120 s fixos). Regras de decisão inalteradas (versão 1.1.0).
- Painel M5 usa o motor M5 + M15 (experimental, somente GBPUSD-OTC), nunca mais a estratégia M1.
- `/demo/m5-signal` serve a publicação do agendador; o campo `state` é recalculado na leitura.
- Coletor M5: dispara na fronteira e repete até a vela ser publicada.
- Backend aceita apenas `HOST` de loopback; CORS com lista de origens, somente GET.

### Removido
- Carência artificial de 90 s (coletor e cache M5) e o cache M1 de 55 s.
- Rotas `/api/v1/iq-option/real/*` da API (módulo isolado, não montado).
- Do Git (cópias locais preservadas): 155 registros JSON, backups, `tsbuildinfo`, `egg-info`, arquivo vazio
  e teste duplicado.

### Corrigido
- D1 (vela errada no M5), D2 (consulta desalinhada), D3 (limite de 120 s no M5), D4/D5 (logins repetidos e
  concorrentes), D6/R2 (vela anterior apresentada como atual), D7 (horários e latência), D8 (relógio local
  apenas), R1 (atraso de 90 s), R3/R4 (pressão de logins e timeout), 7 erros do ruff.

## [9144f59] — 2026-11-21
- Motor M5, contexto M15, cache M5, histórico de validações (estado auditado em `docs/audits/A0-auditoria-rev1.md`).
