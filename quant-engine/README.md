# TradePulse Quant Engine

Motor quantitativo em Python 3.14 do TradePulse. Lê somente a conta **PRACTICE** da IQ Option e
**nunca envia ordens**.

- `app/gateway/`: worker persistente (`python -m app.gateway.worker`) com uma sessão IQ, cache de candles e protocolo JSON-lines usado pelo backend.
- `app/strategies/`, `app/cli/`: estratégia M1 e motor M5 + contexto M15 (experimental).
- `app/indicators/`: EMA, RSI, ADX, ATR.
- `app/repositories/`: registros locais em `data/` (fora do Git).

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Documentação completa em [`../docs`](../docs).
