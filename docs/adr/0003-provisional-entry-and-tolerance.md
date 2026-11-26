# ADR-0003 — Entrada no fechamento da vela de referência e tolerância de publicação

- **Data:** 26/11/2026 · **Estado:** **provisória** (autorizada para validação técnica; não é regra financeira aprovada) · **Bloco:** A.2

## Contexto

A estratégia M1 calculava a entrada como "fronteira seguinte ao horário da análise". No M5 isso
associava o sinal à vela errada (+300 s). A engenharia autorizou parâmetros provisórios: tolerância
de publicação de 10 s no M1 e de 30 s no M5.

## Decisão

- Abertura teórica (entrada) = fechamento da vela de referência. Expiração = entrada + 1 vela.
- Preço teórico = fechamento da vela de referência. O preço observado na publicação é registrado à parte.
- Uma publicação com atraso acima da tolerância recebe `LATE_NOT_ACTIONABLE` e não é exibida como ação.
- Tudo é marcado `methodology: PROVISIONAL_NOT_APPROVED`, `operational: false`.
- Tolerâncias configuráveis: `SIGNAL_TOLERANCE_M1_MS` e `SIGNAL_TOLERANCE_M5_MS`.

## Consequências

- A liquidação do M1 passa a usar horizonte de 1 vela (antes 2).
- A regra definitiva de entrada e avaliação continua pendente (decisão N.1).
- Os registros persistidos ainda não guardam a latência de publicação (bloco A.6).
