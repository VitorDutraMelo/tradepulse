import { describe, expect, it, vi } from "vitest";

import {
  PythonQuantEngineClient,
  type QuantEngineRunner,
} from "./python-quant-engine.client";

const validAnalysisPayload = {
  symbol: "BTC-USDT",
  timeframe: "1h",
  timestamp: "2026-11-01T12:00:00+00:00",
  direction: "NEUTRAL",
  score: 20,
  reasons: ["No EMA 9/21 crossover detected"],
  source: "binance_spot",
  strategy: "ema_crossover",
  indicators: {
    fastEmaPeriod: 9,
    slowEmaPeriod: 21,
  },
};

const validCandlesPayload = {
  symbol: "BTC-USDT",
  timeframe: "1h",
  source: "binance_spot",
  candles: [
    {
      timestamp: "2026-11-01T12:00:00+00:00",
      open: 77962.63,
      high: 78025.53,
      low: 77749.09,
      close: 77890.02,
      volume: 408.2493,
    },
  ],
};

const validIqOptionDemoAnalysisPayload = {
  symbol: "EURUSD-OTC",
  timeframe: "1m",
  source: "iq_option_demo",
  accountMode: "PRACTICE",
  analysisAt: "2026-11-08T12:07:04.914171+00:00",
  lastClosedCandle: {
    openTime: "2026-11-08T12:06:00+00:00",
    closeTime: "2026-11-08T12:07:00+00:00",
    ageSeconds: 4.914171,
  },
  indicators: {
    ema9: 1.1059452456282621,
    ema21: 1.1063734732262245,
    rsi14: 41.67946301547834,
    adx14: 25.200070442490915,
    atr14: 0.000613654856663767,
  },
  action: "PUT",
  reference: {
    price: 1.105895,
    entryTime: "2026-11-08T12:08:00+00:00",
    expirationTime: "2026-11-08T12:09:00+00:00",
  },
  reasons: ["EMA 9 is below EMA 21."],
  disclaimer: "Technical reference only. No IQ Option order was sent.",
};

describe("PythonQuantEngineClient", () => {
  it("runs the analysis CLI with fixed command arguments", async () => {
    const runner: QuantEngineRunner = {
      run: vi.fn().mockResolvedValue({
        stdout: JSON.stringify(validAnalysisPayload),
        stderr: "",
      }),
    };

    const client = new PythonQuantEngineClient(
      {
        pythonExecutable: "python.exe",
        workingDirectory: "C:/tradepulse/quant-engine",
        timeoutMs: 15000,
      },
      runner,
    );

    const result = await client.analyze({
      symbol: "BTC-USDT",
      timeframe: "1h",
      limit: 100,
    });

    expect(result).toEqual(validAnalysisPayload);

    expect(runner.run).toHaveBeenCalledWith(
      "python.exe",
      [
        "-m",
        "app.cli.analyze_market",
        "--symbol",
        "BTC-USDT",
        "--timeframe",
        "1h",
        "--limit",
        "100",
      ],
      {
        cwd: "C:/tradepulse/quant-engine",
        timeoutMs: 15000,
      },
    );
  });

  it("runs the market-candles CLI with fixed command arguments", async () => {
    const runner: QuantEngineRunner = {
      run: vi.fn().mockResolvedValue({
        stdout: JSON.stringify(validCandlesPayload),
        stderr: "",
      }),
    };

    const client = new PythonQuantEngineClient(
      {
        pythonExecutable: "python.exe",
        workingDirectory: "C:/tradepulse/quant-engine",
        timeoutMs: 15000,
      },
      runner,
    );

    const result = await client.getCandles({
      symbol: "BTC-USDT",
      timeframe: "1h",
      limit: 100,
    });

    expect(result).toEqual(validCandlesPayload);

    expect(runner.run).toHaveBeenCalledWith(
      "python.exe",
      [
        "-m",
        "app.cli.get_candles",
        "--symbol",
        "BTC-USDT",
        "--timeframe",
        "1h",
        "--limit",
        "100",
      ],
      {
        cwd: "C:/tradepulse/quant-engine",
        timeoutMs: 15000,
      },
    );
  });

  it("runs the read-only IQ Option binary analysis CLI", async () => {
    const runner: QuantEngineRunner = {
      run: vi.fn().mockResolvedValue({
        stdout: JSON.stringify(validIqOptionDemoAnalysisPayload),
        stderr: "",
      }),
    };

    const client = new PythonQuantEngineClient(
      {
        pythonExecutable: "python.exe",
        workingDirectory: "C:/tradepulse/quant-engine",
        timeoutMs: 15000,
      },
      runner,
    );

    const result = await client.analyzeIqOptionDemo({
      symbol: "EURUSD-OTC",
      timeframe: "1m",
      limit: 100,
    });

    expect(result).toEqual(validIqOptionDemoAnalysisPayload);

    expect(runner.run).toHaveBeenCalledWith(
      "python.exe",
      [
        "-m",
        "app.cli.analyze_iq_option_binary_signal",
        "--symbol",
        "EURUSD-OTC",
        "--timeframe",
        "1m",
        "--limit",
        "100",
      ],
      {
        cwd: "C:/tradepulse/quant-engine",
        timeoutMs: 15000,
      },
    );
  });

  it("rejects invalid JSON returned by the CLI", async () => {
    const runner: QuantEngineRunner = {
      run: vi.fn().mockResolvedValue({
        stdout: "not-json",
        stderr: "",
      }),
    };

    const client = new PythonQuantEngineClient(
      {
        pythonExecutable: "python.exe",
        workingDirectory: "C:/tradepulse/quant-engine",
        timeoutMs: 15000,
      },
      runner,
    );

    await expect(
      client.analyze({
        symbol: "BTC-USDT",
        timeframe: "1h",
        limit: 100,
      }),
    ).rejects.toThrow("The Quant Engine returned invalid JSON.");
  });

  it("uses the structured message returned by a failing CLI process", async () => {
    const runner: QuantEngineRunner = {
      run: vi.fn().mockRejectedValue(
        Object.assign(new Error("Command failed"), {
          stderr: JSON.stringify({
            error: {
              code: "MARKET_DATA_UNAVAILABLE",
              message: "could not retrieve candles from Binance",
            },
          }),
        }),
      ),
    };

    const client = new PythonQuantEngineClient(
      {
        pythonExecutable: "python.exe",
        workingDirectory: "C:/tradepulse/quant-engine",
        timeoutMs: 15000,
      },
      runner,
    );

    await expect(
      client.getCandles({
        symbol: "BTC-USDT",
        timeframe: "1h",
        limit: 100,
      }),
    ).rejects.toThrow("could not retrieve candles from Binance");
  });
});