import express from "express";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";

import { createIqOptionDemoM5SyncRouter } from "./iq-option-demo-m5-sync.router";
import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoM5SyncClient,
} from "../market-analysis/python-quant-engine.client";

const validPayload = {
  source: "iq_option_demo" as const,
  venue: "iq" as const,
  accountMode: "PRACTICE" as const,
  symbol: "GBPUSD-OTC" as const,
  timeframe: "5m" as const,
  state: "UPDATED" as const,
  latestClosedCandle: {
    timestamp: "2026-11-14T12:00:00+00:00",
    open: 1.25,
    high: 1.251,
    low: 1.249,
    close: 1.2505,
    volume: 0,
    closed: true as const,
    closeTime: "2026-11-14T12:05:00+00:00",
  },
  expectedLatestCloseTime: "2026-11-14T12:05:00+00:00",
  timing: {
    clockSource: "application_utc_clock" as const,
    iqCandleAvailabilityAt: null,
    iqCandleAvailabilityMeasurement:
      "NOT_AVAILABLE_FROM_IQ_OPTION_API" as const,
    sourceCandleCloseTime: "2026-11-14T12:05:00+00:00",
    observedClosedCandleAgeSeconds: 2,
    python: {
      analysisStartedAt: "2026-11-14T12:05:02+00:00",
      providerCallStartedAt: "2026-11-14T12:05:02+00:00",
      providerCallCompletedAt: "2026-11-14T12:05:02.500000+00:00",
      payloadBuiltAt: "2026-11-14T12:05:02.501000+00:00",
      providerCallDurationMs: 500,
      payloadProcessingDurationMs: 1,
      totalDurationMs: 501,
      providerCallScope:
        "IQ Option connection, candle retrieval and provider parsing" as const,
    },
  },
};

function createTestApp(client: QuantEngineIqOptionDemoM5SyncClient) {
  const app = express();

  app.use(
    "/api/v1/iq-option/demo/m5-sync",
    createIqOptionDemoM5SyncRouter(client),
  );

  return app;
}

describe("GET /api/v1/iq-option/demo/m5-sync", () => {
  it("returns the synchronized M5 demonstration payload", async () => {
    const getIqOptionDemoM5Sync = vi.fn().mockResolvedValue(validPayload);
    const response = await request(
      createTestApp({ getIqOptionDemoM5Sync }),
    )
      .get("/api/v1/iq-option/demo/m5-sync")
      .query({ symbol: "GBPUSD-OTC" });

    expect(response.status).toBe(200);
    expect(response.body.data.symbol).toBe("GBPUSD-OTC");
    expect(response.body.data.timeframe).toBe("5m");
    expect(response.body.data.state).toBe("UPDATED");
    expect(response.body.data.timing.iqCandleAvailabilityAt).toBeNull();
    expect(response.body.data.timing.nodeApi.durationMs).toEqual(
      expect.any(Number),
    );
    expect(getIqOptionDemoM5Sync).toHaveBeenCalledWith({
      symbol: "GBPUSD-OTC",
    });
  });

  it("rejects an unsupported M5 demonstration symbol", async () => {
    const getIqOptionDemoM5Sync = vi.fn();
    const response = await request(
      createTestApp({ getIqOptionDemoM5Sync }),
    )
      .get("/api/v1/iq-option/demo/m5-sync")
      .query({ symbol: "EURUSD-OTC" });

    expect(response.status).toBe(400);
    expect(response.body.error.code).toBe(
      "INVALID_IQ_OPTION_DEMO_M5_SYNC_REQUEST",
    );
    expect(getIqOptionDemoM5Sync).not.toHaveBeenCalled();
  });

  it("reports IQ Option unavailability without returning stale data", async () => {
    const response = await request(
      createTestApp({
        getIqOptionDemoM5Sync: vi
          .fn()
          .mockRejectedValue(new QuantEngineClientError("IQ Option unavailable")),
      }),
    )
      .get("/api/v1/iq-option/demo/m5-sync")
      .query({ symbol: "GBPUSD-OTC" });

    expect(response.status).toBe(502);
    expect(response.body.error.code).toBe(
      "IQ_OPTION_DEMO_M5_SYNC_UNAVAILABLE",
    );
  });
});