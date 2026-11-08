# TradePulse — Guia para rodar no seu computador (Windows)

Este guia é para testar **localmente** o dashboard TradePulse com **IQ Option PRACTICE/DEMO**, sem enviar ordens.

## 1. O que instalar

- **Git** — para baixar o repositório.
- **Node.js e npm** — para backend e frontend.
- **Python** — para o Quant Engine.
- **VS Code** — opcional, mas recomendado.

No PowerShell, confirme:

```powershell
git --version
node --version
npm --version
python --version
```

> As versões mínimas exatas e a instalação Python dependem dos arquivos atuais do repositório (`package.json`, arquivos de dependências Python e scripts). Não escolha uma versão aleatória da `iqoptionapi` se o projeto já fixar uma.

## 2. Baixar o projeto

```powershell
cd $HOME\Documents
git clone https://github.com/VitorDutraMelo/tradepulse.git
cd tradepulse
```

Se a pasta já existir:

```powershell
cd $HOME\Documents\tradepulse
git pull origin main
```

## 3. Instalar dependências Node.js

```powershell
cd backend
npm install
cd ..\frontend
npm install
cd ..
```

## 4. Preparar o Python

Na raiz `tradepulse`:

```powershell
cd quant-engine
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

**IMPORTANTE:** agora inspecione os arquivos de dependências do `quant-engine` e siga o método de instalação previsto pelo projeto. Por exemplo, se existir `requirements.txt`:

```powershell
if (Test-Path requirements.txt) { python -m pip install -r requirements.txt }
```

Se houver `pyproject.toml`, siga as instruções desse projeto; não instale pacotes duplicados por tentativa. A biblioteca `iqoptionapi` pode exigir versão ou origem específica.

Se o PowerShell bloquear a ativação do ambiente virtual, execute no terminal atual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## 5. Configurar acesso PRACTICE

O TradePulse usa uma integração **não oficial** com a IQ Option. O responsável pelo repositório deve confirmar os nomes exatos das variáveis de ambiente e o procedimento de autenticação **já implementado**.

- Use somente credenciais de uma conta autorizada em modo PRACTICE.
- Digite segredos apenas localmente, conforme o procedimento do projeto.
- **Não envie credenciais por WhatsApp, GitHub ou chat.**
- Não coloque segredos no frontend ou em arquivos versionados.
- Não execute nenhuma função de compra ou venda.

**Pendente de confirmar no código:** nomes das variáveis, comando de inicialização da integração Python e eventuais passos de autenticação. Sem isso, não é possível garantir que a instalação nova se conectará.

## 6. Iniciar o backend

Abra um novo PowerShell:

```powershell
cd $HOME\Documents\tradepulse\backend
npm run dev
```

A API deverá responder em `http://localhost:3001`.

Em outro PowerShell, teste:

```powershell
Invoke-RestMethod "http://localhost:3001/api/v1/health"
```

## 7. Iniciar o frontend

Abra outro PowerShell:

```powershell
cd $HOME\Documents\tradepulse\frontend
npm run dev
```

Abra no navegador **http://localhost:5173**.

Não use `http://127.0.0.1:5173`: a configuração CORS informada aceita `localhost`.

## 8. Fazer o primeiro teste

1. Selecione `EURUSD-OTC` no topo do dashboard.
2. Clique em **Atualizar análise**.
3. Confira o sinal **CALL**, **PUT** ou **WAIT**, os indicadores e os horários.
4. Troque para `GBPUSD-OTC` e faça outra consulta.
5. Aguarde 60 segundos para observar a atualização automática.

Para consultar a API diretamente:

```powershell
Invoke-RestMethod "http://localhost:3001/api/v1/iq-option/demo/market-analysis?symbol=GBPUSD-OTC&timeframe=1m&limit=120" | ConvertTo-Json -Depth 10
```

Oito símbolos estão configurados no seletor, mas **não há consulta automática de mercado aberto**; um símbolo pode falhar ou estar indisponível.

## 9. Problemas comuns

| Problema | O que verificar |
|---|---|
| `npm` não reconhecido | Instalação do Node.js e terminal reiniciado |
| `python` não reconhecido | Instalação/PATH do Python |
| Erro de CORS | Abrir `localhost:5173`, não `127.0.0.1:5173` |
| Frontend sem dados | Backend iniciado e `/api/v1/health` acessível |
| Erro em um ativo | Disponibilidade do ativo, rede, integração e logs sem segredos |
| Timeout da `iqoptionapi` | Conectividade e endpoints usados pela biblioteca; não contornar restrições |
| Falha no Quant Engine | Ambiente virtual, dependências e comando de integração definidos no projeto |

## 10. Segurança e limitações

Este dashboard **não executa operações**, não utiliza conta REAL e não comprova rentabilidade. A `iqoptionapi` é comunitária e não oficial. Use somente se o acesso for permitido pela plataforma e pelas regras aplicáveis à sua localização.

**Antes de compartilhar o repositório**, o mantenedor deve confirmar os comandos Python e as variáveis de ambiente com base no código atual, e verificar que nenhum segredo foi enviado ao GitHub.
