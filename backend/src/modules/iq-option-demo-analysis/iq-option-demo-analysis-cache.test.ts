import { describe, expect, it, vi } from "vitest";

import type {
  QuantEngineIqOptionDemoAnalysisClient,
} from "../market-analysis/python-quant-engine.client";
import type {
  IqOptionDemoAnalysisRequest,
  IqOptionDemoAnalysisResponse,
} from "./iq-option-demo-analysis.schema";
import { CachedIqOptionDemoAnalysisClient } from "./iq-option-demo-analysis-cache";

const input: IqOptionDemoAnalysisRequest = {
  symbol: "EURUSD-OTC",
  timeframe: "1m",
  limit: 120,
};

const analysis: IqOptionDemoAnalysisResponse = {
  symbol: "EURUSD-OTC",
  timeframe: "1m",
  source: "iq_option_demo",
  accountMode: "PRACTICE",
  analysisAt: "2026-11-09T23:00:05+00:00",
  lastClosedCandle: {
    openTime: "2026-11-09T22:59:00+00:00",
    closeTime: "2026-11-09T23:00:00+00:00",
    ageSeconds: 5,
  },
  indicators: {
    ema9: 1.105945,
    ema21: 1.106373,
    rsi14: 41.68,
    adx14: 25.2,
    atr14: 0.000614,
  },
  action: "PUT",
  reference: {
    price: 1.105895,
    entryTime: "2026-11-09T23:01:00+00:00",
    expirationTime: "2026-11-09T23:02:00+00:00",
  },
  reasons: ["EMA 9 is below EMA 21."],
  disclaimer: "Technical reference only. No IQ Option order was sent.",
};

describe("CachedIqOptionDemoAnalysisClient", () => {
  it("caches a successful analysis for the configured interval", async () => {
    let currentTime = 1_000;

    const client: QuantEngineIqOptionDemoAnalysisClient = {
      analyzeIqOptionDemo: vi.fn().mockResolvedValue(analysis),
    };

    const cachedClient = new CachedIqOptionDemoAnalysisClient(
      client,
      {
        cacheTtlMs: 55_000,
        now: () => currentTime,
      },
    );

    await expect(
      cachedClient.analyzeIqOptionDemo(input),
    ).resolves.toEqual(analysis);

    currentTime += 54_999;

    await expect(
      cachedClient.analyzeIqOptionDemo(input),
    ).resolves.toEqual(analysis);

    expect(client.analyzeIqOptionDemo).toHaveBeenCalledTimes(1);

    currentTime += 1;

    await expect(
      cachedClient.analyzeIqOptionDemo(input),
    ).resolves.toEqual(analysis);

    expect(client.analyzeIqOptionDemo).toHaveBeenCalledTimes(2);
  });

  it("shares one in-flight request for equal analyses", async () => {
    let resolveAnalysis!: (
      value: IqOptionDemoAnalysisResponse,
    ) => void;

    const pendingAnalysis = new Promise<IqOptionDemoAnalysisResponse>(
      (resolve) => {
        resolveAnalysis = resolve;
      },
    );

    const client: QuantEngineIqOptionDemoAnalysisClient = {
      analyzeIqOptionDemo: vi.fn().mockReturnValue(pendingAnalysis),
    };

    const cachedClient = new CachedIqOptionDemoAnalysisClient(client);

    const firstRequest = cachedClient.analyzeIqOptionDemo(input);
    const secondRequest = cachedClient.analyzeIqOptionDemo(input);

    await Promise.resolve();

    expect(client.analyzeIqOptionDemo).toHaveBeenCalledTimes(1);

    resolveAnalysis(analysis);

    await expect(firstRequest).resolves.toEqual(analysis);
    await expect(secondRequest).resolves.toEqual(analysis);
  });

  it("runs different IQ Option analyses one at a time", async () => {
    let resolveFirst!: (
      value: IqOptionDemoAnalysisResponse,
    ) => void;

    const firstAnalysis = new Promise<IqOptionDemoAnalysisResponse>(
      (resolve) => {
        resolveFirst = resolve;
      },
    );

    const analyzeIqOptionDemo = vi
      .fn()
      .mockReturnValueOnce(firstAnalysis)
      .mockResolvedValueOnce({
        ...analysis,
        symbol: "GBPUSD-OTC",
      });

    const client: QuantEngineIqOptionDemoAnalysisClient = {
      analyzeIqOptionDemo,
    };

    const cachedClient = new CachedIqOptionDemoAnalysisClient(client);

    const firstRequest = cachedClient.analyzeIqOptionDemo(input);

    const secondRequest = cachedClient.analyzeIqOptionDemo({
      ...input,
      symbol: "GBPUSD-OTC",
    });

    await Promise.resolve();

    expect(analyzeIqOptionDemo).toHaveBeenCalledTimes(1);

    resolveFirst(analysis);

    await expect(firstRequest).resolves.toEqual(analysis);

    await expect(secondRequest).resolves.toEqual({
      ...analysis,
      symbol: "GBPUSD-OTC",
    });

    expect(analyzeIqOptionDemo).toHaveBeenCalledTimes(2);
  });

  it("does not cache a failed IQ Option analysis", async () => {
    const client: QuantEngineIqOptionDemoAnalysisClient = {
      analyzeIqOptionDemo: vi
        .fn()
        .mockRejectedValue(new Error("IQ Option unavailable")),
    };

    const cachedClient = new CachedIqOptionDemoAnalysisClient(client);

    await expect(
      cachedClient.analyzeIqOptionDemo(input),
    ).rejects.toThrow("IQ Option unavailable");

    await expect(
      cachedClient.analyzeIqOptionDemo(input),
    ).rejects.toThrow("IQ Option unavailable");

    expect(client.analyzeIqOptionDemo).toHaveBeenCalledTimes(2);
  });
});