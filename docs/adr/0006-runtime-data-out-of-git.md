# ADR-0006 — Dados de execução fora do Git; persistência JSON mantida

- **Data:** 26/11/2026 · **Estado:** aceita (A.1). A migração para SQLite continua pendente (N.7).

## Contexto

O branch tinha 155 registros JSON gerados em execução, backups, `tsbuildinfo` e `egg-info` versionados.

## Decisão

- Remover do rastreamento com `git rm --cached` (cópias locais preservadas; histórico não reescrito).
- `.gitignore` abrangente; pastas de dados com `.gitignore` próprio.
- Manter a persistência em JSON neste bloco, para não ampliar o escopo; o log de publicações usa JSON-lines.

## Consequências

- Os registros históricos continuam apenas na máquina do proprietário. Para compartilhá-los, é preciso enviá-los explicitamente.
