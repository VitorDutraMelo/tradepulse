import { describe, expect, it, vi } from "vitest";

import {
  PythonQuantEngineClient,
  type QuantEngineRunner,
} from "../market-analysis/python-quant-engine.client";

const validIqOptionSignalPayload = {
  platform: "IQ_OPTION",
  asset: "BTC-USD",
  market: "CRYPTO",
  timeframe: "1h",
  timestamp: "2026-11-01T16:00:00+00:00",
  dataSource: "binance_spot",
  analysisDirection: "NEUTRAL",
  action: "WAIT",
  entryTime: null,
  expirationTime: null,
  reasons: [
    "No EMA 9/21 crossover detected",
    "No IQ Option policy is configured for this market and data source; manual action remains WAIT.",
  ],
};

describe("PythonQuantEngineClient.prepareIqOptionSignal", () => {
  it("runs the IQ Option CLI with a fixed command and separate arguments", async () => {
    const runner: QuantEngineRunner = {
      run: vi.fn().mockResolvedValue({
        stdout: JSON.stringify(validIqOptionSignalPayload),
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

    const result = await client.prepareIqOptionSignal({
      symbol: "BTC-USD",
      timeframe: "1h",
      limit: 100,
      market: "CRYPTO",
    });

    expect(result).toEqual(validIqOptionSignalPayload);
    expect(runner.run).toHaveBeenCalledWith(
      "python.exe",
      [
        "-m",
        "app.cli.prepare_iq_option_signal",
        "--symbol",
        "BTC-USD",
        "--timeframe",
        "1h",
        "--limit",
        "100",
        "--market",
        "CRYPTO",
      ],
      {
        cwd: "C:/tradepulse/quant-engine",
        timeoutMs: 15000,
      },
    );
  });
});