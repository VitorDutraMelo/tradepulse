# Segurança

## Regras permanentes

1. **Nenhuma ordem é executada.** Não existe executor de ordens no código.
2. **Somente PRACTICE.** Depois de cada login, o worker seleciona PRACTICE e **verifica** com
   `get_balance_mode()`. Se não for `PRACTICE`, a sessão é fechada e nenhuma leitura é feita
   (`IQ_OPTION_PRACTICE_NOT_CONFIRMED`).
3. **Credenciais só no backend**, por variáveis de ambiente (`IQ_OPTION_DEMO_EMAIL`, `IQ_OPTION_DEMO_PASSWORD`).
4. **Nada privado em logs ou respostas:** e-mails, senhas, tokens e ssid são removidos pelo redator
   (Python `app/gateway/redaction.py`, Node `modules/iq-gateway/logger.ts`). `/status` informa apenas se as
   credenciais existem (booleano).

## Isolamento da conta REAL

- O login PRACTICE da IQ Option é o **mesmo** da conta real. Por isso:
  - o transporte (`app/gateway/transport.py`) expõe apenas leitura: `connect`, `check_connect`,
    `change_balance("PRACTICE")`, `get_balance_mode`, `get_server_timestamp` e a requisição de candles. Não há
    `buy`, `sell` nem `close_position` (teste `test_transport_exposes_no_order_capability`);
  - o worker aceita apenas 6 comandos de leitura (teste `test_unknown_commands_are_rejected`).
- O antigo módulo `iq-option-real-trading` (preflight) **não está montado** na API (teste `app.security.test.ts`).
  Ele permanece no repositório, marcado como isolado, até a decisão N.2.

## Rede

- `HOST` aceita apenas `127.0.0.1`, `::1` ou `localhost`. Qualquer outro valor impede a API de iniciar.
- CORS: lista de origens (`FRONTEND_ORIGIN`, padrão `http://localhost:5173,http://127.0.0.1:5173`), somente `GET`.
- `helmet`, `x-powered-by` desativado, corpo JSON limitado a 16 KB.

### Acesso remoto (celular / PWA fora do computador) — **não implementado**

Antes de expor o backend, é necessária uma solução aprovada. Proposta para avaliação:

1. Manter a API em loopback e publicar um **túnel autenticado** (por exemplo Tailscale ou Cloudflare Access) com identidade do proprietário.
2. Ou: autenticação por token de sessão no backend, HTTPS obrigatório, limite de requisições e lista de dispositivos.

## Repositório

- `.gitignore` cobre `.env*`, chaves, credenciais, backups, `tsbuildinfo`, `egg-info`, caches, ambientes virtuais e dados gerados.
- Varredura feita antes da publicação dos blocos A.1/A.2: **nenhuma credencial real encontrada** no histórico
  conhecido nem nas mudanças (somente valores de teste como `pw-123456`).
- Dependência não oficial `iqoptionapi` fixada em um commit do GitHub. Risco: o protocolo da IQ pode mudar e a
  biblioteca não é mantida pela IQ. O código só usa as partes listadas acima.

## Riscos abertos

| Risco | Situação |
|---|---|
| Biblioteca não oficial | Aceito; isolado atrás do transporte somente-leitura |
| Mesmo login da conta real | Mitigado (PRACTICE verificado, sem métodos de ordem); depende de N.5 |
| Sem autenticação no backend | Mitigado por loopback obrigatório |
| `connect` da biblioteca pode travar | Mitigado: prazo de 30 s, worker reiniciado pelo backend |
