# TradePulse

Protótipo funcional de uma plataforma de análise de mercado. O frontend exibe candles, indicadores, sinais explicáveis, scanner, histórico, backtest e configurações visuais com dados totalmente demonstrativos. Não conecta a corretoras e não executa operações.

## Stack

- React 19 + TypeScript
- Vinext/Vite
- Recharts
- Lucide React
- CSS responsivo

## Executar

```bash
pnpm install
pnpm dev
```

Build de produção:

```bash
pnpm build
```

## Estrutura

- `app/`: interface principal e estilos
- `data/mockData.ts`: ativos, candles, sinais, histórico e backtest simulados
- `types/market.ts`: contratos TypeScript
- `services/`: camada de acesso aos mocks, pronta para ser substituída por HTTP

## Conexão futura com API

Substitua a implementação de `marketService`, `signalService` e `backtestService` por chamadas ao backend mantendo os mesmos tipos. Os componentes não precisam conhecer a origem dos dados.

> Todo score, resultado, win rate e P/L exibido é demonstrativo e não representa performance financeira real.
