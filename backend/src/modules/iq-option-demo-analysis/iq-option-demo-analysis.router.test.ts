import request from "supertest";
import { describe, expect, it, vi } from "vitest";

import { createApp } from "../../app";
import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoAnalysisClient,
} from "../market-analysis/python-quant-engine.client";
import type { IqOptionDemoAnalysisResponse } from "./iq-option-demo-analysis.schema";

const validIqOptionDemoAnalysisPayload: IqOptionDemoAnalysisResponse = {
  symbol: "EURUSD-OTC",
  timeframe: "1m",
  source: "iq_option_demo",
  accountMode: "PRACTICE",
  analysisAt: "2026-11-07T09:35:04+00:00",
  lastClosedCandle: {
    openTime: "2026-11-07T09:34:00+00:00",
    closeTime: "2026-11-07T09:35:00+00:00",
    ageSeconds: 4,
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
    entryTime: "2026-11-07T09:36:00+00:00",
    expirationTime: "2026-11-07T09:37:00+00:00",
  },
  reasons: ["EMA 9 is below EMA 21."],
  disclaimer: "Technical reference only. No IQ Option order was sent.",
};

describe("GET /api/v1/iq-option/demo/market-analysis", () => {
  it("returns the frontend signal contract directly", async () => {
    const analyzeIqOptionDemo = vi
      .fn()
      .mockResolvedValue(validIqOptionDemoAnalysisPayload);

    const app = createApp({
      quantEngineIqOptionDemoAnalysisClient: { analyzeIqOptionDemo },
    });

    const response = await request(app)
      .get("/api/v1/iq-option/demo/market-analysis")
      .query({ symbol: "EURUSD-OTC", timeframe: "1m", limit: 29 })
      .expect(200);

    expect(response.body).toEqual(validIqOptionDemoAnalysisPayload);

    expect(analyzeIqOptionDemo).toHaveBeenCalledWith({
      symbol: "EURUSD-OTC",
      timeframe: "1m",
      limit: 29,
    });
  });

  it("uses the default limit when it is not informed", async () => {
    const analyzeIqOptionDemo = vi
      .fn()
      .mockResolvedValue(validIqOptionDemoAnalysisPayload);

    const app = createApp({
      quantEngineIqOptionDemoAnalysisClient: { analyzeIqOptionDemo },
    });

    await request(app)
      .get("/api/v1/iq-option/demo/market-analysis")
      .query({ symbol: "EURUSD", timeframe: "5m" })
      .expect(200);

    expect(analyzeIqOptionDemo).toHaveBeenCalledWith({
      symbol: "EURUSD",
      timeframe: "5m",
      limit: 100,
    });
  });

  it("rejects an invalid request before calling the Quant Engine", async () => {
    const analyzeIqOptionDemo = vi.fn();

    const app = createApp({
      quantEngineIqOptionDemoAnalysisClient: { analyzeIqOptionDemo },
    });

    await request(app)
      .get("/api/v1/iq-option/demo/market-analysis")
      .query({ symbol: "BTC-USDT", timeframe: "3m", limit: 10 })
      .expect(400);

    expect(analyzeIqOptionDemo).not.toHaveBeenCalled();
  });

  it("returns a gateway error when the Quant Engine fails", async () => {
    const quantEngineIqOptionDemoAnalysisClient: QuantEngineIqOptionDemoAnalysisClient =
      {
        analyzeIqOptionDemo: vi
          .fn()
          .mockRejectedValue(
            new QuantEngineClientError(
              "IQ Option demo authentication failed.",
            ),
          ),
      };

    const app = createApp({ quantEngineIqOptionDemoAnalysisClient });

    await request(app)
      .get("/api/v1/iq-option/demo/market-analysis")
      .query({ symbol: "EURUSD-OTC", timeframe: "1m" })
      .expect(502);
  });
});