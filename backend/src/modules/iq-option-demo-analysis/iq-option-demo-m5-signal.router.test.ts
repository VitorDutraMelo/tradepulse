import express from "express";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";

import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoM5SignalClient,
} from "../market-analysis/python-quant-engine.client";
import { createIqOptionDemoM5SignalRouter } from "./iq-option-demo-m5-signal.router";

const validPayload = {
  source: "iq_option_demo" as const,
  venue: "iq" as const,
  accountMode: "PRACTICE" as const,
  symbol: "GBPUSD-OTC" as const,
  timeframe: "5m" as const,
  state: "UPDATED" as const,
  latestClosedCandle: {
    timestamp: "2026-11-14T01:40:00+00:00",
    open: 1.35,
    high: 1.351,
    low: 1.349,
    close: 1.3505,
    volume: 0,
    closed: true as const,
    closeTime: "2026-11-14T01:45:00+00:00",
  },
  expectedLatestCloseTime: "2026-11-14T01:45:00+00:00",
  indicators: {
    ema200: 1.349,
    rsi14: 60,
    macd: 0.001,
    macdSignal: 0.0005,
    macdHistogram: 0.0005,
    previousMacdHistogram: 0.0004,
    adx14: 24,
    atr14: 0.0008,
  },
  dataQuality: {
    requiredClosedCandles: 250 as const,
    receivedClosedCandles: 260,
    candlesContiguous: true,
  },
  decision: {
    action: "WAIT" as const,
    candidateAction: "CALL" as const,
    actionability: "NOT_ACTIONABLE_LATE" as const,
    theoreticalEntryTime: "2026-11-14T01:45:00+00:00",
    theoreticalExpirationTime: "2026-11-14T01:50:00+00:00",
    reasons: [
      "Candidate CALL met the configured M5 filters.",
      "The theoretical M5 entry time already passed; no order is executable.",
    ],
  },
  timing: {
    clockSource: "application_utc_clock" as const,
    iqCandleAvailabilityAt: null,
    iqCandleAvailabilityMeasurement:
      "NOT_AVAILABLE_FROM_IQ_OPTION_API" as const,
    sourceCandleCloseTime: "2026-11-14T01:45:00+00:00",
    observedClosedCandleAgeSeconds: 10,
    python: {
      analysisStartedAt: "2026-11-14T01:45:10+00:00",
      providerCallStartedAt: "2026-11-14T01:45:10+00:00",
      providerCallCompletedAt: "2026-11-14T01:45:11+00:00",
      payloadBuiltAt: "2026-11-14T01:45:11+00:00",
      providerCallDurationMs: 1000,
      payloadProcessingDurationMs: 0,
      totalDurationMs: 1000,
      providerCallScope:
        "IQ Option connection, candle retrieval and provider parsing" as const,
    },
  },
};

function createTestApp(client: QuantEngineIqOptionDemoM5SignalClient) {
  const app = express();

  app.use(
    "/api/v1/iq-option/demo/m5-signal",
    createIqOptionDemoM5SignalRouter(client),
  );

  return app;
}

describe("GET /api/v1/iq-option/demo/m5-signal", () => {
  it("returns the M5 candidate as non-actionable", async () => {
    const getIqOptionDemoM5Signal = vi.fn().mockResolvedValue(validPayload);

    const response = await request(
      createTestApp({ getIqOptionDemoM5Signal }),
    )
      .get("/api/v1/iq-option/demo/m5-signal")
      .query({ symbol: "GBPUSD-OTC" });

    expect(response.status).toBe(200);
    expect(response.body.data.decision.action).toBe("WAIT");
    expect(response.body.data.decision.candidateAction).toBe("CALL");
    expect(response.body.data.decision.actionability).toBe(
      "NOT_ACTIONABLE_LATE",
    );
  });

  it("rejects an unsupported symbol", async () => {
    const getIqOptionDemoM5Signal = vi.fn();

    const response = await request(
      createTestApp({ getIqOptionDemoM5Signal }),
    )
      .get("/api/v1/iq-option/demo/m5-signal")
      .query({ symbol: "EURUSD-OTC" });

    expect(response.status).toBe(400);
    expect(getIqOptionDemoM5Signal).not.toHaveBeenCalled();
  });

  it("returns 502 when IQ Option is unavailable", async () => {
    const response = await request(
      createTestApp({
        getIqOptionDemoM5Signal: vi
          .fn()
          .mockRejectedValue(
            new QuantEngineClientError("IQ Option unavailable"),
          ),
      }),
    )
      .get("/api/v1/iq-option/demo/m5-signal")
      .query({ symbol: "GBPUSD-OTC" });

    expect(response.status).toBe(502);
    expect(response.body.error.code).toBe(
      "IQ_OPTION_DEMO_M5_SIGNAL_UNAVAILABLE",
    );
  });
});