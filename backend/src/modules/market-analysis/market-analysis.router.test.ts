import request from "supertest";
import { describe, expect, it, vi } from "vitest";

import { createApp } from "../../app";
import {
  QuantEngineClientError,
  type QuantEngineClient,
} from "./python-quant-engine.client";

const validAnalysisPayload = {
  symbol: "BTC-USDT",
  timeframe: "1h",
  timestamp: "2026-11-01T12:00:00+00:00",
  direction: "NEUTRAL" as const,
  score: 20,
  reasons: ["No EMA 9/21 crossover detected"],
  source: "binance_spot",
  strategy: "ema_crossover",
  indicators: {
    fastEmaPeriod: 9,
    slowEmaPeriod: 21,
  },
};

describe("GET /api/v1/market-analysis", () => {
  it("returns a validated analysis response", async () => {
    const analyze = vi.fn().mockResolvedValue(validAnalysisPayload);
    const quantEngineClient: QuantEngineClient = { analyze };
    const app = createApp({ quantEngineClient });

    const response = await request(app)
      .get("/api/v1/market-analysis")
      .query({
        symbol: "BTC-USDT",
        timeframe: "1h",
      })
      .expect(200);

    expect(response.body).toEqual({
      data: validAnalysisPayload,
    });
    expect(analyze).toHaveBeenCalledWith({
      symbol: "BTC-USDT",
      timeframe: "1h",
      limit: 100,
    });
  });

  it("rejects an invalid request before calling the Quant Engine", async () => {
    const analyze = vi.fn();
    const quantEngineClient: QuantEngineClient = { analyze };
    const app = createApp({ quantEngineClient });

    const response = await request(app)
      .get("/api/v1/market-analysis")
      .query({
        symbol: "BTC-USDT",
        timeframe: "1h",
        limit: 10,
      })
      .expect(400);

    expect(response.body).toEqual({
      error: {
        code: "INVALID_ANALYSIS_REQUEST",
        message: "The market analysis request is invalid.",
      },
    });
    expect(analyze).not.toHaveBeenCalled();
  });

  it("returns a gateway error when the Quant Engine fails", async () => {
    const quantEngineClient: QuantEngineClient = {
      analyze: vi
        .fn()
        .mockRejectedValue(
          new QuantEngineClientError("could not retrieve candles from Binance"),
        ),
    };
    const app = createApp({ quantEngineClient });

    const response = await request(app)
      .get("/api/v1/market-analysis")
      .query({
        symbol: "BTC-USDT",
        timeframe: "1h",
      })
      .expect(502);

    expect(response.body).toEqual({
      error: {
        code: "QUANT_ENGINE_UNAVAILABLE",
        message: "could not retrieve candles from Binance",
      },
    });
  });
});