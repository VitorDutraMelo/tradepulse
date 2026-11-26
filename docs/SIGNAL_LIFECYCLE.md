# Ciclo de vida dos sinais

> **Metodologia provisória e experimental.** Os parâmetros abaixo foram autorizados pela engenharia
> apenas para validação técnica. Nenhum resultado produzido com eles pode ser contabilizado como
> desempenho operacional comprovado.

## Linha do tempo (M5)

```
11:55 ─────────── 12:00 ─────────── 12:05 ─────────── 12:10
      vela de referência  │ vela de entrada  │
                          │◀─ tolerância 30 s│
                          ▲                  ▲
          fechamento = abertura teórica   expiração
                          │
                 publicação real (P)
```

| Conceito | Definição atual |
|---|---|
| Vela de referência | Última vela **fechada**, usada no cálculo |
| Abertura teórica (entrada) | Fechamento da vela de referência = abertura da vela seguinte |
| Preço teórico de referência | Fechamento da vela de referência |
| Preço observado na publicação | Último preço da vela em formação lido junto com os dados (quando disponível) |
| Expiração | Entrada + 1 vela |
| Publicação | Momento em que o backend tornou a análise disponível |
| Atraso de publicação | `publicação − fechamento da vela de referência` |
| Tolerância | M1: 10 s · M5: 30 s (`SIGNAL_TOLERANCE_M1_MS`, `SIGNAL_TOLERANCE_M5_MS`) |

**Mudança em relação ao código anterior (defeito D1):** a entrada era a fronteira seguinte ao **horário
da análise**. No M5 isso pulava uma vela inteira (+300 s). Agora a entrada é sempre o fechamento da vela
de referência. Um sinal publicado depois da abertura teórica **não é apresentado como disponível
antes**: ele recebe o rótulo de atraso.

## Estados do sinal (`publication.signal.status`)

Calculados pelo backend **a cada leitura**:

| Estado | Condição | Exibição |
|---|---|---|
| `NOT_CURRENT` | A vela publicada não é a mais recente possível | "Análise da vela anterior — não é atual"; nenhuma ação exibida |
| `WAIT` | A estratégia não encontrou condições | WAIT |
| `EXPIRED` | Agora ≥ expiração | "Expirado — não utilizar"; nenhuma ação exibida |
| `LATE_NOT_ACTIONABLE` | Atraso > tolerância | "Publicado após a tolerância — não utilizar"; nenhuma ação exibida |
| `EXPERIMENTAL_CANDIDATE` | Atual, dentro da tolerância, antes da expiração | Ação exibida com o rótulo "candidato experimental (não operacional)" |

`operational` é sempre `false` enquanto a metodologia não for aprovada.

## Motor M5

O motor M5 mantém `decision.action = "WAIT"` sempre: é uma regra do próprio motor e foi preservada.
O que o painel mostra como candidato é `decision.candidateAction` (já filtrado pelo M15), sempre com
o selo **experimental**. O rótulo do motor `NOT_ACTIONABLE_LATE` reflete a confirmação por vela fechada.
O estado de validade publicado pelo backend (`timeliness`, `status`) é quem decide a exibição.

## Avaliação de resultado

- **M1:** a liquidação compara o preço de referência (fechamento da vela de referência) com o
  fechamento da vela de entrada. Com a correção da entrada, o horizonte passa a ser **1 vela**
  (antes eram 2, com uma vela ignorada no meio).
- **M5:** o horizonte de 1 vela já estava correto.
- Ainda não implementado (bloco A.6): registro de WAIT, estados `EXPIRED` e `NOT_EVALUABLE` nos
  registros, latência gravada no registro persistido e liquidação independente das leituras.

## Prevenção de duplicidade

- Uma publicação por vela e por inscrição; leituras repetidas não disparam novas análises.
- Os repositórios deduplicam por ativo, ação e entrada.
