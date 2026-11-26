# Registro de decisões arquiteturais (ADR)

| ADR | Título | Estado |
|---|---|---|
| [0001](0001-persistent-iq-gateway-worker.md) | Sessão IQ persistente em um worker Python JSON-lines | Aceita (A.1) |
| [0002](0002-candle-close-scheduling.md) | Agendamento por fechamento de vela, sem atraso fixo | Aceita (A.2) |
| [0003](0003-provisional-entry-and-tolerance.md) | Entrada no fechamento da vela de referência e tolerância de publicação | **Provisória** (A.2) |
| [0004](0004-loopback-only-and-real-account-isolation.md) | Backend apenas em loopback e isolamento da conta REAL | Aceita (A.1) |
| [0005](0005-candle-keyed-cache-and-read-time-freshness.md) | Cache por vela e atualidade calculada na leitura | Aceita (A.2) |
| [0006](0006-runtime-data-out-of-git.md) | Dados de execução fora do Git; persistência JSON mantida | Aceita (A.1); SQLite pendente (N.7) |
