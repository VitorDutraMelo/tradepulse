# Roadmap

Cada bloco termina com relatório, aprovação da engenharia e publicação. Nenhum bloco começa sem aprovação.

| Bloco | Objetivo | Estado |
|---|---|---|
| A.0 | Auditoria e recuperação | **Concluído** (rev. 1 em `docs/audits/`) |
| A.0.1 | Higiene do repositório | **Concluído** dentro de A.1/A.2 |
| A.1 + A.2 | Coleta confiável e sincronizada (sessão persistente, agendamento, horários, cache, segurança) | **Implementado e testado**; validação real pendente |
| A.5 | Ciclo de vida dos sinais (regra definitiva de entrada e expiração) | Parcial: infraestrutura pronta e regra provisória; depende de N.1 |
| A.6 | Histórico e avaliação (WAIT registrado, EXPIRED/NOT_EVALUABLE, liquidação autônoma, versão no registro, SQLite) | Próximo candidato |
| A.3 + A.4 | Revisão matemática do M5/M15 (indicadores no módulo comum, testes numéricos, aquecimento da EMA 200, ADX/ATR, outros ativos) | Depende de N.8 e N.10 |
| A.7 | Backtesting com separação cronológica e comparação com o M1 | Depende de A.6 |
| A.9 | Frontend completo (histórico, estatísticas, gráfico M5 nativo, indicadores no gráfico) | |
| A.8 | Revisão do M1 | |
| A.10 | Estabilização, PWA (ícones PNG, instalação) e acesso remoto seguro | Depende de N.13 |
| A.11 | Documentação final e lançamento | |

## Ordem recomendada a partir daqui

1. **Validação real de A.1/A.2** pelo proprietário (TESTING.md), 30 minutos ou mais.
2. **A.6**: sem histórico completo e sem avaliação confiável, nenhuma comparação de estratégia é possível.
3. **A.3/A.4** com as regras M5/M15 aprovadas (N.8), usando os diagnósticos de WAIT coletados.
4. A.7 → A.9 → A.8 → A.10 → A.11.
