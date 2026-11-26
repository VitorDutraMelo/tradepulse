# Estado do projeto

_Atualizado em 26/11/2026, ao final dos blocos A.1 + A.2._

Legenda: **Validado** = comprovado com a IQ Option real · **Testado** = testes automatizados ·
**Implementado** = código existe sem teste específico · **Parcial** · **Ausente** · **Bloqueado**.

## Matriz de funcionalidades

| Funcionalidade | Estado | Observação |
|---|---|---|
| Sessão IQ persistente (1 login, PRACTICE verificado, backoff) | **Testado** | Validação real bloqueada (credenciais) |
| Fila, deduplicação, limite, cancelamento, timeout com reinício | **Testado** | |
| Coleta de velas fechadas com relógio do servidor IQ | **Testado** | |
| Cache de candles por vela | **Testado** | |
| Agendamento por fechamento de vela, sem atraso fixo | **Testado** | |
| Horários observados/derivados e latências | **Testado** | Latência real ainda não medida |
| Atualidade e validade calculadas na leitura | **Testado** | |
| Tolerância provisória M1 10 s / M5 30 s | **Testado** | Metodologia não aprovada |
| Estratégia M1 (EMA 9/21, RSI, ADX, ATR) | **Testado** | Regras preservadas; sem validação estatística |
| Motor M5 (EMA 200, RSI, MACD) + contexto M15 | **Parcial** | Experimental; somente GBPUSD-OTC; ação final sempre WAIT; EMA 200 com aquecimento curto |
| Separação de estratégias por timeframe (registro + painel) | **Testado** | Versão ainda não gravada nos registros persistidos |
| Indicadores EMA, RSI, ADX, ATR | **Testado** | |
| MACD / EMA 200 | **Implementado** | Sem teste numérico; duplicados no M5 |
| Histórico CALL/PUT (M1) e validações M5 | **Parcial** | WAIT não registrado; fora da interface |
| Avaliação WIN/LOSS/DRAW | **Parcial** | Horizonte de 1 vela; sem EXPIRED/NOT_EVALUABLE; liquidação depende de leituras |
| Estatísticas de desempenho | **Ausente** | |
| Backtesting | **Ausente** | |
| Frontend: estado da conexão, atualidade, latência, estratégia | **Testado (visual)** | Verificado no navegador sem credenciais |
| Frontend: gráfico de candles | **Parcial** | M1 da IQ; M5 agregado de 100 M1 |
| Frontend: histórico e estatísticas | **Ausente** | |
| Responsividade | **Implementado** | Sem rolagem horizontal a 375 px |
| PWA | **Parcial** | Manifest e service worker; somente ícone SVG; instalação não validada |
| Segurança: loopback, CORS, REAL isolado, redação | **Testado** | Acesso remoto não disponível |
| Documentação permanente | **Implementado** | Este conjunto de documentos |
| Validação real com IQ Option PRACTICE | **Bloqueado** | Requer o procedimento em TESTING.md |

## Percentuais (critério da auditoria A.0: 22 itens, 1 / 0,5 / 0)

| Medida | A.0 rev. 1 | Agora |
|---|---|---|
| Implementação | 11,5 / 22 ≈ **52%** | 15,5 / 22 ≈ **70%** |
| Validação funcional real | ≈ 5–10% | ≈ 5–10% (nenhuma validação real neste bloco) |
| Validação estatística | 0% | 0% |

Itens que mudaram: coleta IQ (0,5 → 1), estratégias por timeframe (0,5 → 1), horários (0,5 → 1),
indisponibilidade (0,5 → 1), sessão IQ (0 → 1), documentação (0,5 → 1), logs/health (0,5 → 1).
Cálculo detalhado em [reports/A1-A2-RELATORIO.md](reports/A1-A2-RELATORIO.md).

## Decisões pendentes

As 18 decisões da auditoria A.0 rev. 1 continuam registradas em
[audits/A0-auditoria-rev1.md](audits/A0-auditoria-rev1.md#n-decisões-pendentes).
Situação após A.1/A.2:

| # | Decisão | Situação |
|---|---|---|
| N.1 | Regra de entrada e tolerância | **Provisória** aplicada (ADR-0003); falta a aprovação definitiva |
| N.2 | Módulo de trading real | Isolado e desmontado; falta decidir a remoção |
| N.3 | Binance legado / OTCharts | Inalterados |
| N.4 | Estado do Git | **Resolvido**: clone local em `9144f59` = remoto |
| N.5 | Uso do login da conta real | Pendente (mitigado: PRACTICE verificado) |
| N.6 | Arquitetura da conexão | **Resolvido**: worker JSON-lines (ADR-0001) |
| N.7 | SQLite | Pendente (ADR-0006) |
| N.8 | Regras M5/M15 (ADX, ATR, faixas de RSI, MACD, M15, aquecimento) | Pendente: próximo bloco |
| N.9 | Expiração | 1 vela mantida (provisória) |
| N.10 | Outros ativos no M5 | Pendente (somente GBPUSD-OTC) |
| N.11 | Payout | Pendente |
| N.12 | Idioma dos motivos | Pendente (motor em inglês; interface em PT-BR) |
| N.13 | Acesso remoto / celular | Pendente (proposta em SECURITY.md) |
| N.14 | npm ou pnpm | npm mantido (lockfiles do npm) |
| N.15 | Remover a carência de 90 s | **Resolvido** |
| N.16 | Painel M5 com o motor novo | **Resolvido** (rotulado experimental) |
| N.17 | Gráfico M5 nativo | Pendente |
| N.18 | Coletor CLI | Mantido sem carência; o agendador do backend é a fonte principal |
