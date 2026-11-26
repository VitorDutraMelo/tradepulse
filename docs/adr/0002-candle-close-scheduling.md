# ADR-0002 — Agendamento por fechamento de vela, sem atraso fixo

- **Data:** 26/11/2026 · **Estado:** aceita · **Bloco:** A.2

## Contexto

O frontend consultava a cada 60 s, sem alinhamento com as velas, e o M5 usava uma carência fixa de
90 s (coletor e cache). As diretrizes proíbem o atraso artificial e qualquer espera fixa substituta.

## Decisão

- O backend mantém inscrições (ativo + timeframe + estratégia) criadas pela leitura de `/live` e expiradas sem uso (10 min).
- Em cada fronteira de vela (relógio local ajustado pelo desvio do servidor IQ), a análise é disparada imediatamente.
- Se a IQ ainda não publicou a vela, novas tentativas em 0,5 s, 1 s, 1 s, 2 s, 3 s e depois 5 s, até a vela existir ou até a próxima fronteira. Um `retryAt` informado pela sessão é respeitado.
- Uma publicação por vela; leituras não disparam novas análises da mesma vela.
- O coletor CLI do M5 também dispara na fronteira e repete até a vela ser publicada.

## Consequências

- A latência medida passa a ser "tempo até a IQ disponibilizar a vela + leitura + cálculo".
- O frontend pode consultar o backend a cada 2 s sem gerar requisições à IQ.
- Credenciais ausentes, PRACTICE não confirmado e pedidos inválidos não são repetidos.
