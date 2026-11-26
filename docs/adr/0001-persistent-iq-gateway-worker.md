# ADR-0001 — Sessão IQ persistente em um worker Python JSON-lines

- **Data:** 26/11/2026 · **Estado:** aceita · **Bloco:** A.1

## Contexto

Cada requisição HTTP abria um processo Python e fazia um novo login na IQ Option. O M5 fazia 3 logins
por requisição e o gráfico fazia 1 login por minuto fora de qualquer fila. Isso causava latência,
timeouts e risco de bloqueio da conta.

## Decisão

Um único processo Python de longa duração (`python -m app.gateway.worker`), gerenciado pelo Node, mantém
**uma** sessão IQ. Comunicação por JSON em linhas (stdin/stdout). O Node continua sendo a única API pública.

## Alternativas consideradas

- **Microserviço HTTP em Python:** exigiria nova dependência, outra porta e outra superfície de rede.
- **Reescrever a integração em Node:** descartaria código Python testado.

## Consequências

- Sem novas dependências. As estratégias existentes rodam sem alteração, com um provedor injetável.
- O worker é serial: 1 requisição por vez, o que evita logins simultâneos.
- A biblioteca pode travar; o backend aplica timeout e reinicia o worker com backoff progressivo.
- Se o backend morrer, o worker termina ao receber EOF em stdin (verificado: nenhum processo órfão).
