import request from "supertest";
import { describe, expect, it, vi } from "vitest";

import { createApp } from "../../app";
import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoCandleClient,
} from "../market-analysis/python-quant-engine.client";

const validPayload = {
  source: "iq_option_demo" as const,
  venue: "iq" as const,
  accountMode: "PRACTICE" as const,
  symbol: "GBPUSD-OTC" as const,
  timeframe: "1m" as const,
  candles: [
    {
      timestamp: "2026-11-12T16:20:00+00:00",
      open: 1.2345,
      high: 1.235,
      low: 1.234,
      close: 1.2348,
      volume: 0,
      closed: true as const,
    },
  ],
};

describe("GET /api/v1/iq-option/demo/candles", () => {
  it("returns validated closed IQ Option PRACTICE candles", async () => {
    const getIqOptionDemoCandles = vi.fn().mockResolvedValue(validPayload);

    const client: QuantEngineIqOptionDemoCandleClient = {
      getIqOptionDemoCandles,
    };

    const app = createApp({
      quantEngineIqOptionDemoCandleClient: client,
    });

    const response = await request(app)
      .get("/api/v1/iq-option/demo/candles")
      .query({
        symbol: "GBPUSD-OTC",
        timeframe: "1m",
        limit: 100,
      })
      .expect(200);

    expect(response.body).toEqual({
      data: validPayload,
    });

    expect(getIqOptionDemoCandles).toHaveBeenCalledWith({
      symbol: "GBPUSD-OTC",
      timeframe: "1m",
      limit: 100,
    });
  });

  it("rejects assets outside the approved OTC list", async () => {
    const getIqOptionDemoCandles = vi.fn();

    const app = createApp({
      quantEngineIqOptionDemoCandleClient: {
        getIqOptionDemoCandles,
      },
    });

    const response = await request(app)
      .get("/api/v1/iq-option/demo/candles")
      .query({
        symbol: "BTC-USD",
        timeframe: "1m",
        limit: 100,
      })
      .expect(400);

    expect(response.body).toEqual({
      error: {
        code: "INVALID_IQ_OPTION_DEMO_CANDLES_REQUEST",
        message:
          "A supported OTC symbol, timeframe 1m and limit between 1 and 1000 are required.",
      },
    });

    expect(getIqOptionDemoCandles).not.toHaveBeenCalled();
  });

  it("returns a gateway error when IQ Option candles are unavailable", async () => {
    const app = createApp({
      quantEngineIqOptionDemoCandleClient: {
        getIqOptionDemoCandles: vi
          .fn()
          .mockRejectedValue(
            new QuantEngineClientError(
              "IQ Option reports GBPUSD-OTC is currently unavailable on PRACTICE",
            ),
          ),
      },
    });

    const response = await request(app)
      .get("/api/v1/iq-option/demo/candles")
      .query({
        symbol: "GBPUSD-OTC",
        timeframe: "1m",
        limit: 100,
      })
      .expect(502);

    expect(response.body.error.code).toBe(
      "IQ_OPTION_DEMO_CANDLES_UNAVAILABLE",
    );
  });
});
