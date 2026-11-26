import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GatewayError, type GatewayResponse, type GatewayWorker } from "./gateway-worker";
import { LiveAnalysisService, StrategyUnavailableError } from "./live-analysis.service";

const MINUTE = 60_000;

function m1Payload(closeMs: number, action: "CALL" | "PUT" | "WAIT" = "CALL") {
  const openMs = closeMs - MINUTE;

  return {
    symbol: "EURUSD-OTC",
    timeframe: "1m",
    source: "iq_option_demo",
    accountMode: "PRACTICE",
    analysisAt: new Date(closeMs + 1500).toISOString(),
    lastClosedCandle: {
      openTime: new Date(openMs).toISOString(),
      closeTime: new Date(closeMs).toISOString(),
      ageSeconds: 1.5,
    },
    indicators: { ema9: 1.1, ema21: 1.09, rsi14: 55, adx14: 25, atr14: 0.001 },
    action,
    reference: {
      price: action === "WAIT" ? null : 1.1,
      entryTime: new Date(closeMs).toISOString(),
      expirationTime: new Date(closeMs + MINUTE).toISOString(),
    },
    reasons: ["rule evaluation"],
    disclaimer: "Technical reference only.",
  };
}

function m5Payload(closeMs: number, candidate: "CALL" | "PUT" | "WAIT" = "WAIT") {
  const openMs = closeMs - 5 * MINUTE;
  const at = new Date(closeMs + 2000).toISOString();

  return {
    source: "iq_option_demo",
    venue: "iq",
    accountMode: "PRACTICE",
    symbol: "GBPUSD-OTC",
    timeframe: "5m",
    state: "UPDATED",
    latestClosedCandle: {
      timestamp: new Date(openMs).toISOString(),
      open: 1.3,
      high: 1.31,
      low: 1.29,
      close: 1.305,
      volume: 1,
      closed: true,
      closeTime: new Date(closeMs).toISOString(),
    },
    expectedLatestCloseTime: new Date(closeMs).toISOString(),
    indicators: {
      ema200: 1.2,
      rsi14: 50,
      macd: 0,
      macdSignal: 0,
      macdHistogram: 0,
      previousMacdHistogram: 0,
      adx14: 20,
      atr14: 0.001,
    },
    dataQuality: { requiredClosedCandles: 250, receivedClosedCandles: 260, candlesContiguous: true },
    decision: {
      action: "WAIT",
      candidateAction: candidate,
      actionability: candidate === "WAIT" ? "NO_CANDIDATE" : "NOT_ACTIONABLE_LATE",
      theoreticalEntryTime: new Date(closeMs).toISOString(),
      theoreticalExpirationTime: new Date(closeMs + 5 * MINUTE).toISOString(),
      reasons: ["rule evaluation"],
    },
    timing: {
      clockSource: "application_utc_clock",
      iqCandleAvailabilityAt: null,
      iqCandleAvailabilityMeasurement: "NOT_AVAILABLE_FROM_IQ_OPTION_API",
      sourceCandleCloseTime: new Date(closeMs).toISOString(),
      observedClosedCandleAgeSeconds: 2,
      python: {
        analysisStartedAt: at,
        providerCallStartedAt: at,
        providerCallCompletedAt: at,
        payloadBuiltAt: at,
        providerCallDurationMs: 1,
        payloadProcessingDurationMs: 1,
        totalDurationMs: 2,
        providerCallScope: "IQ Option connection, candle retrieval and provider parsing",
      },
    },
  };
}

type Responder = (command: string, call: number) => unknown;

class FakeGateway {
  calls: Array<{ command: string; at: number }> = [];

  constructor(public responder: Responder, private readonly latencyMs = 300) {}

  async request(command: string): Promise<GatewayResponse> {
    const call = this.calls.length;
    this.calls.push({ command, at: Date.now() });
    const dispatchedAt = Date.now();
    await new Promise((resolve) => setTimeout(resolve, this.latencyMs));
    const result = this.responder(command, call);

    if (result instanceof Error) {
      throw result;
    }

    return {
      result,
      meta: {
        analysisStartedAt: new Date(dispatchedAt).toISOString(),
        analysisCompletedAt: new Date(Date.now()).toISOString(),
        fetches: [
          {
            timeframe: command === "analyze_m5" ? "5m" : "1m",
            requestedAt: new Date(dispatchedAt).toISOString(),
            receivedAt: new Date(Date.now() - 50).toISOString(),
            collectionDurationMs: this.latencyMs - 50,
            cacheHit: false,
            observedQuote: { price: 1.1001, sourceTimestamp: null },
          },
        ],
        session: { state: "CONNECTED", accountMode: "PRACTICE", serverClockOffsetMs: 0 },
      },
      dispatchedAt,
      respondedAt: Date.now(),
    };
  }

  status() {
    return {
      workerState: "READY",
      session: { state: "CONNECTED", accountMode: "PRACTICE" },
      lastErrorCode: null,
      nextRestartAt: null,
    };
  }
}

function service(gateway: FakeGateway, overrides: Record<string, unknown> = {}) {
  return new LiveAnalysisService(gateway as unknown as GatewayWorker, {
    toleranceMs: { "1m": 10_000, "5m": 30_000 },
    publicationLogPath: null,
    ...overrides,
  });
}

const T0 = Date.parse("2026-11-26T12:00:00Z");

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("LiveAnalysisService", () => {
  it("publishes the analysis of the just-closed candle right after the boundary", async () => {
    vi.setSystemTime(T0 + 30_000);
    const gateway = new FakeGateway(() => m1Payload(Date.now() - (Date.now() % MINUTE)));
    const live = service(gateway);

    await live.getLive("EURUSD-OTC", "1m");
    await vi.advanceTimersByTimeAsync(500); // initial (mid-candle) analysis
    await vi.advanceTimersByTimeAsync(30_000 - 500 + 400); // reach 12:01:00 + 0.4 s

    const view = (await live.getLive("EURUSD-OTC", "1m")) as any;

    expect(view.dataState).toBe("CURRENT");
    expect(view.publication.candleCloseTime).toBe("2026-11-26T12:01:00.000Z");
    expect(view.publication.signal.timeliness).toBe("ON_TIME");
    expect(view.publication.signal.status).toBe("EXPERIMENTAL_CANDIDATE");
    expect(view.publication.signal.theoreticalEntryTime).toBe("2026-11-26T12:01:00.000Z");
    expect(view.publication.timing.totalLatencyFromCloseMs).toBeLessThan(1000);
    expect(view.publication.timing.dataReceivedAtKind).toBe("OBSERVED_LOCAL_CLOCK");
    // The cycle starts exactly at the boundary: no fixed waiting delay.
    expect(gateway.calls.at(-1)!.at).toBe(Date.parse("2026-11-26T12:01:00Z"));
  });

  it("retries in a controlled way until the source publishes the closed candle", async () => {
    vi.setSystemTime(T0 - 1);
    let publishedAt = Number.POSITIVE_INFINITY;
    const gateway = new FakeGateway(() =>
      m1Payload(Date.now() >= publishedAt ? T0 : T0 - MINUTE),
    );
    const live = service(gateway);

    await live.getLive("EURUSD-OTC", "1m");
    await vi.advanceTimersByTimeAsync(400);
    publishedAt = T0 + 3000; // IQ makes the 12:00 close available 3 s late
    await vi.advanceTimersByTimeAsync(10_000);

    const view = (await live.getLive("EURUSD-OTC", "1m")) as any;
    const afterBoundary = gateway.calls.filter((call) => call.at >= T0);

    expect(view.dataState).toBe("CURRENT");
    expect(view.publication.candleCloseTime).toBe("2026-11-26T12:00:00.000Z");
    expect(view.publication.timing.attempts).toBeGreaterThan(1);
    expect(afterBoundary.length).toBeGreaterThan(1);
    expect(afterBoundary.length).toBeLessThan(10); // paced, not hammering
    expect(view.publication.timing.totalLatencyFromCloseMs).toBeLessThan(10_000);
  });

  it("never presents the previous candle as current after a new boundary", async () => {
    vi.setSystemTime(T0 + 5_000);
    let available = T0;
    const gateway = new FakeGateway(() => m5Payload(available), 100);
    const live = service(gateway);

    await live.getLive("GBPUSD-OTC", "5m");
    await vi.advanceTimersByTimeAsync(200);
    // 12:05 boundary passes but the source still only has the 12:00 candle.
    await vi.advanceTimersByTimeAsync(5 * MINUTE);

    const view = (await live.getLive("GBPUSD-OTC", "5m")) as any;

    expect(view.dataState).toBe("AWAITING_NEW_CANDLE");
    expect(view.publication.candleCloseTime).toBe("2026-11-26T12:00:00.000Z");
    expect(view.publication.signal.status).toBe("NOT_CURRENT");
    expect(view.publication.analysis.state).toBe("AWAITING_CONFIRMATION");
    expect(view.publication.analysis.state).not.toBe("UPDATED");

    available = T0 + 5 * MINUTE;
    await vi.advanceTimersByTimeAsync(6_000);
    const updated = (await live.getLive("GBPUSD-OTC", "5m")) as any;
    expect(updated.dataState).toBe("CURRENT");
    expect(updated.publication.analysis.state).toBe("UPDATED");
  });

  it("marks a candidate published after the tolerance as late, never as available", async () => {
    vi.setSystemTime(T0 + 45_000); // subscribe 45 s into the M5 candle
    const gateway = new FakeGateway(() => m5Payload(T0, "CALL"), 100);
    const live = service(gateway);

    await live.getLive("GBPUSD-OTC", "5m");
    await vi.advanceTimersByTimeAsync(200);
    const view = (await live.getLive("GBPUSD-OTC", "5m")) as any;

    expect(view.publication.signal.action).toBe("CALL");
    expect(view.publication.signal.engineAction).toBe("WAIT");
    expect(view.publication.signal.timeliness).toBe("LATE");
    expect(view.publication.signal.status).toBe("LATE_NOT_ACTIONABLE");
    expect(view.publication.signal.operational).toBe(false);
    expect(view.strategy.experimentalEngine).toBe(true);
  });

  it("expires a candidate after its theoretical expiration", async () => {
    vi.setSystemTime(T0 + 500);
    const gateway = new FakeGateway(() => m1Payload(T0, "PUT"), 100);
    const live = service(gateway);

    await live.getLive("EURUSD-OTC", "1m");
    await vi.advanceTimersByTimeAsync(200);
    expect(((await live.getLive("EURUSD-OTC", "1m")) as any).publication.signal.status).toBe(
      "EXPERIMENTAL_CANDIDATE",
    );

    // At the theoretical expiration (12:01) the candle is no longer current:
    // the old candidate can never be shown as an opportunity again.
    await vi.advanceTimersByTimeAsync(MINUTE);
    const later = (await live.getLive("EURUSD-OTC", "1m")) as any;
    expect(later.publication.candleCloseTime).toBe("2026-11-26T12:00:00.000Z");
    expect(later.publication.signal.status).toBe("NOT_CURRENT");
    live.stop();
  });

  it("does not analyse the same candle twice for repeated reads", async () => {
    vi.setSystemTime(T0 + 2000);
    const gateway = new FakeGateway(() => m1Payload(T0, "WAIT"), 50);
    const live = service(gateway);

    for (let index = 0; index < 10; index += 1) {
      await live.getLive("EURUSD-OTC", "1m");
      await vi.advanceTimersByTimeAsync(100);
    }

    expect(gateway.calls).toHaveLength(1);
    expect(((await live.getLive("EURUSD-OTC", "1m")) as any).publication.signal.status).toBe(
      "WAIT",
    );
  });

  it("keeps M1 and M5 strategies separate and limits the M5 engine to GBPUSD-OTC", async () => {
    vi.setSystemTime(T0 + 2000);
    const live = service(new FakeGateway(() => m1Payload(T0)));

    expect(() => live.resolveStrategy("EURUSD-OTC", "1m").id).not.toThrow();
    expect(live.resolveStrategy("GBPUSD-OTC", "5m").id).toBe("m5-ema200-rsi14-macd-m15");
    expect(live.resolveStrategy("EURUSD-OTC", "1m").id).toBe("m1-trend-ema9-21-rsi-adx-atr");
    await expect(live.getLive("EURUSD-OTC", "5m")).rejects.toBeInstanceOf(StrategyUnavailableError);
  });

  it("stops retrying when credentials are missing and reports the reason", async () => {
    vi.setSystemTime(T0 + 2000);
    const gateway = new FakeGateway(
      () => new GatewayError("IQ_OPTION_CREDENTIALS_MISSING", "credentials missing"),
      50,
    );
    const live = service(gateway);

    await live.getLive("EURUSD-OTC", "1m");
    await vi.advanceTimersByTimeAsync(20_000);
    const view = (await live.getLive("EURUSD-OTC", "1m")) as any;

    expect(gateway.calls).toHaveLength(1);
    expect(view.dataState).toBe("NO_DATA");
    expect(view.lastError.code).toBe("IQ_OPTION_CREDENTIALS_MISSING");
  });

  it("reports IQ Option unavailability and honours the reconnect hint", async () => {
    vi.setSystemTime(T0 + 1000);
    const retryAt = new Date(T0 + 9000).toISOString();
    const gateway = new FakeGateway(
      () => new GatewayError("IQ_OPTION_RECONNECT_BACKOFF", "backoff", retryAt),
      10,
    );
    const live = service(gateway);

    await live.getLive("EURUSD-OTC", "1m");
    await vi.advanceTimersByTimeAsync(5000);
    const view = (await live.getLive("EURUSD-OTC", "1m")) as any;

    expect(view.lastError).toMatchObject({ code: "IQ_OPTION_RECONNECT_BACKOFF", retryAt });
    expect(gateway.calls).toHaveLength(1); // waits for the backoff instead of retrying
  });

  it("gives up on a candle at the next boundary", async () => {
    vi.setSystemTime(T0 + 1000);
    const gateway = new FakeGateway(() => m1Payload(T0 - MINUTE), 10);
    const live = service(gateway);

    await live.getLive("EURUSD-OTC", "1m");
    await vi.advanceTimersByTimeAsync(58_000);
    const view = (await live.getLive("EURUSD-OTC", "1m")) as any;

    expect(view.dataState).toBe("AWAITING_NEW_CANDLE");
    expect(view.cycle.running).toBe(false);
  });

  it("limits the number of followed pairs", async () => {
    vi.setSystemTime(T0 + 1000);
    const live = service(new FakeGateway(() => m1Payload(T0)), { maxSubscriptions: 1 });

    await live.getLive("EURUSD-OTC", "1m");
    await expect(live.getLive("GBPUSD-OTC", "1m")).rejects.toMatchObject({
      code: "LIVE_SUBSCRIPTION_LIMIT",
    });
    live.stop();
  });
});
