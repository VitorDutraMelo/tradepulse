# TradePulse — Dashboard IQ Option DEMO

Frontend independente em React + TypeScript + Vite. **Não executa operações.**

## Instalação (PowerShell)

```powershell
cd C:\Users\vitor\OneDrive\Documents\GitHub\tradepulse\frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Abra http://localhost:5173

Inicie o backend existente separadamente na porta 3001, com o Quant Engine conforme sua configuração atual. Endpoint usado:
`GET /api/v1/iq-option/demo/market-analysis?symbol=EURUSD-OTC&timeframe=1m&limit=120`.

Se a API rejeitar `limit=120`, confirme no backend o limite aceito e altere `VITE_CANDLE_LIMIT` no `.env.local`.

## Segurança e atualização

O frontend usa apenas HTTP GET e não recebe credenciais. Revalida a cada 60 segundos, bloqueia consultas simultâneas, aplica timeout de 15 segundos e não apresenta CALL/PUT depois do horário de entrada ou vencimento. Erros da API são mostrados como erros, nunca como WAIT.

O campo `reasons` é exibido exatamente como retornado pelo backend; para motivos em português, padronize no backend.

O indicador MA50 só aparece quando o JSON contém `indicators.ma50` numérico. A origem do backend deve autorizar CORS para `http://localhost:5173` se necessário.

O status "Dados recebidos" significa apenas que o endpoint respondeu com uma análise válida e recente; não certifica uma conexão persistente à IQ Option. A detecção de frescor é uma proteção de interface, não uma garantia de qualidade do feed.

## Validação

```powershell
npm run typecheck
npm run build
```

Verifique manualmente CALL, PUT, WAIT, falha de rede, JSON inválido, candle antigo, horário expirado, indicador ausente e layout mobile. Não há testes automatizados incluídos neste pacote.
