"""Persistent, PRACTICE-only IQ Option data gateway (blocks A.1/A.2).

The gateway keeps one authenticated IQ Option session per worker process,
serves closed candles from a candle-keyed cache and runs the existing
TradePulse analyses on top of it. It never sends orders.
"""
