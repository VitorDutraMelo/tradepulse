# ADR-0005 — Cache por vela e atualidade calculada na leitura

- **Data:** 26/11/2026 · **Estado:** aceita · **Bloco:** A.2

## Contexto

O cache M1 durava 55 s sem considerar a vela. O cache M5 durava até "fechamento + 5 min + 90 s" e
devolvia a vela anterior marcada como `UPDATED`.

## Decisão

- **Worker:** cache de candles com chave ativo/timeframe, válido enquanto a última vela fechada for a mais nova possível. Leituras compartilhadas entre análise, gráfico e liquidação.
- **Backend:** publicação com chave estratégia/ativo/timeframe/vela. `dataState`, `signal.status` e o `state` do M5 são **recalculados em cada leitura**.
- Os caches antigos foram removidos.

## Consequências

- Nenhum dado antigo pode ser apresentado como atual, mesmo se a IQ atrasar.
- A versão da estratégia faz parte da publicação (`strategyVersion`), mas ainda não dos registros persistidos.
