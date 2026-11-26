import { describe, expect, it, vi } from "vitest";

import type {
  QuantEngineIqOptionDemoM5SignalClient,
} from "../market-analysis/python-quant-engine.client";
import type {
  IqOptionDemoM5SignalResponse,
} from "./iq-option-demo-m5-signal.schema";
import { CachedIqOptionDemoM5SignalClient } from "./iq-option-demo-m5-signal-cache";

function createResponse(
  closeTime = "2026-11-21T16:15:00+00:00",
): IqOptionDemoM5SignalResponse {
  return {
    source: "iq_option_demo",
    venue: "iq",
    accountMode: "PRACTICE",
    symbol: "GBPUSD-OTC",
    timeframe: "5m",
    state: "UPDATED",
    latestClosedCandle: {
      timestamp: "2026-11-21T16:10:00+00:00",
      open: 1.31,
      high: 1.32,
      low: 1.3,
      close: 1.315,
      volume: 0,
      closed: true,
      closeTime,
    },
    expectedLatestCloseTime: closeTime,
    indicators: {
      ema200: 1.31,
      rsi14: 50,
      macd: 0,
      macdSignal: 0,
      macdHistogram: 0,
      previousMacdHistogram: 0,
      adx14: 20,
      atr14: 0.001,
    },
    dataQuality: {
      requiredClosedCandles: 250,
      receivedClosedCandles: 259,
      candlesContiguous: true,
    },
    decision: {
      action: "WAIT",
      candidateAction: "WAIT",
      m5CandidateAction: "WAIT",
      actionability: "NO_CANDIDATE",
      theoreticalEntryTime: "2026-11-21T16:15:00+00:00",
      theoreticalExpirationTime: "2026-11-21T16:20:00+00:00",
      reasons: ["No candidate."],
    },
    contextM15: {
      state: "UPDATED",
      trend: "NEUTRAL",
      timeframe: "15m",
      latestClosedCandle: {
        timestamp: "2026-11-21T16:00:00+00:00",
        open: 1.31,
        high: 1.32,
        low: 1.3,
        close: 1.315,
        volume: 0,
        closed: true,
        closeTime,
      },
      expectedLatestCloseTime: closeTime,
      ema200: 1.31,
      ema200ThreeCandlesAgo: 1.31,
      structure: "MIXED",
      dataQuality: {
        requiredClosedCandles: 250,
        receivedClosedCandles: 259,
        candlesContiguous: true,
      },
      reasons: ["Neutral context."],
      timing: {
        sourceCandleCloseTime: closeTime,
        observedClosedCandleAgeSeconds: 60,
        providerCallStartedAt: "2026-11-21T16:16:00+00:00",
        providerCallCompletedAt: "2026-11-21T16:16:01+00:00",
        providerCallDurationMs: 1000,
        providerCallScope: "IQ Option connection, M15 candle retrieval and provider parsing",
      },
    },
    tracking: {
      recordId: null,
      status: "NOT_APPLICABLE",
      settledAt: null,
      settlementPrice: null,
    },
    timing: {
      clockSource: "application_utc_clock",
      iqCandleAvailabilityAt: null,
      iqCandleAvailabilityMeasurement:
        "NOT_AVAILABLE_FROM_IQ_OPTION_API",
      sourceCandleCloseTime: closeTime,
      observedClosedCandleAgeSeconds: 60,
      python: {
        analysisStartedAt: "2026-11-21T16:16:00+00:00",
        providerCallStartedAt: "2026-11-21T16:16:00+00:00",
        providerCallCompletedAt: "2026-11-21T16:16:01+00:00",
        payloadBuiltAt: "2026-11-21T16:16:01+00:00",
        providerCallDurationMs: 1000,
        payloadProcessingDurationMs: 1,
        totalDurationMs: 1001,
        providerCallScope: "IQ Option connection, candle retrieval and provider parsing",
      },
    },
  };
}

describe("Cached IQ Option DEMO M5 signal client", () => {
  it("reuses one M5 result until the next close plus grace", async () => {
    let currentTime = Date.parse("2026-11-21T16:16:00+00:00");

    const client: QuantEngineIqOptionDemoM5SignalClient = {
      getIqOptionDemoM5Signal: vi
        .fn()
        .mockResolvedValue(createResponse()),
    };

    const cached = new CachedIqOptionDemoM5SignalClient(client, {
      now: () => currentTime,
    });

    await cached.getIqOptionDemoM5Signal({
      symbol: "GBPUSD-OTC",
    });

    currentTime = Date.parse("2026-11-21T16:21:29+00:00");

    await cached.getIqOptionDemoM5Signal({
      symbol: "GBPUSD-OTC",
    });

    expect(client.getIqOptionDemoM5Signal).toHaveBeenCalledTimes(1);
  });

  it("refreshes only after the next collection window", async () => {
    let currentTime = Date.parse("2026-11-21T16:16:00+00:00");

    const client: QuantEngineIqOptionDemoM5SignalClient = {
      getIqOptionDemoM5Signal: vi
        .fn()
        .mockResolvedValue(createResponse()),
    };

    const cached = new CachedIqOptionDemoM5SignalClient(client, {
      now: () => currentTime,
    });

    await cached.getIqOptionDemoM5Signal({
      symbol: "GBPUSD-OTC",
    });

    currentTime = Date.parse("2026-11-21T16:21:30+00:00");

    await cached.getIqOptionDemoM5Signal({
      symbol: "GBPUSD-OTC",
    });

    expect(client.getIqOptionDemoM5Signal).toHaveBeenCalledTimes(2);
  });

  it("shares equal active requests", async () => {
    let releaseRequest!: () => void;

    const pendingResponse = new Promise<IqOptionDemoM5SignalResponse>(
      (resolve) => {
        releaseRequest = () => resolve(createResponse());
      },
    );

    const client: QuantEngineIqOptionDemoM5SignalClient = {
      getIqOptionDemoM5Signal: vi
        .fn()
        .mockReturnValue(pendingResponse),
    };

    const cached = new CachedIqOptionDemoM5SignalClient(client);

    const first = cached.getIqOptionDemoM5Signal({
      symbol: "GBPUSD-OTC",
    });

    const second = cached.getIqOptionDemoM5Signal({
      symbol: "GBPUSD-OTC",
    });

    releaseRequest();

    await Promise.all([first, second]);

    expect(client.getIqOptionDemoM5Signal).toHaveBeenCalledTimes(1);
  });

  it("does not cache a failed IQ Option request", async () => {
    const client: QuantEngineIqOptionDemoM5SignalClient = {
      getIqOptionDemoM5Signal: vi
        .fn()
        .mockRejectedValueOnce(new Error("IQ Option unavailable"))
        .mockResolvedValueOnce(createResponse()),
    };

    const cached = new CachedIqOptionDemoM5SignalClient(client);

    await expect(
      cached.getIqOptionDemoM5Signal({
        symbol: "GBPUSD-OTC",
      }),
    ).rejects.toThrow("IQ Option unavailable");

    await cached.getIqOptionDemoM5Signal({
      symbol: "GBPUSD-OTC",
    });

    expect(client.getIqOptionDemoM5Signal).toHaveBeenCalledTimes(2);
  });
});
