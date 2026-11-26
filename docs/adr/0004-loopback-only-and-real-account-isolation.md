# ADR-0004 — Backend apenas em loopback e isolamento da conta REAL

- **Data:** 26/11/2026 · **Estado:** aceita · **Bloco:** A.1

## Contexto

O backend escutava em todas as interfaces, sem autenticação, e mantinha rotas de "preflight" para a
conta real. O login PRACTICE é o mesmo da conta real.

## Decisão

- `HOST` aceita apenas loopback. Valores diferentes impedem o início da API.
- CORS com lista de origens, somente GET.
- Rotas `/api/v1/iq-option/real/*` removidas da API. O módulo fica isolado no repositório até a decisão N.2.
- Sessão com PRACTICE verificado; transporte e worker sem nenhuma operação de ordem.

## Consequências

- Acesso por celular ou remoto fica indisponível até uma solução aprovada (ver SECURITY.md).
