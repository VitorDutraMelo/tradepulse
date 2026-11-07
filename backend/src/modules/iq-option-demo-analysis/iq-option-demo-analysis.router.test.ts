import request from "supertest";
import { describe, expect, it, vi } from "vitest";

import { createApp } from "../../app";
import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoAnalysisClient,
} from "../market-analysis/python-quant-engine.client";
import type { IqOptionDemoAnalysisResponse } from "./iq-option-demo-analysis.schema";

const validIqOptionDemoAnalysisPayload: IqOptionDemoAnalysisResponse = {
  recordId: "iq-demo-20261107-093608-218988-eurusd-otc-ffdccba1f5",
  symbol: "EURUSD-OTC",
  timeframe: "1m",
  timestamp: "2026-11-07T09:35:00+00:00",
  direction: "NEUTRAL",
  score: 20,
  reasons: ["No EMA 9/21 crossover detected"],
  source: "iq_option_demo",
  venue: "iq",
  accountMode: "PRACTICE",
  strategy: "ema_crossover",
  indicators: {
    fastEmaPeriod: 9,
    slowEmaPeriod: 21,
  },
  disclaimer:
    "Technical analysis only. LONG, SHORT and NEUTRAL are not automatic CALL, PUT or WAIT instructions.",
};

describe("GET /api/v1/iq-option/demo/market-analysis", () => {
  it("returns a validated IQ Option practice analysis", async () => {
    const analyzeIqOptionDemo = vi
      .fn()
      .mockResolvedValue(validIqOptionDemoAnalysisPayload);

    const quantEngineIqOptionDemoAnalysisClient: QuantEngineIqOptionDemoAnalysisClient =
      {
        analyzeIqOptionDemo,
      };

    const app = createApp({ quantEngineIqOptionDemoAnalysisClient });

    const response = await request(app)
      .get("/api/v1/iq-option/demo/market-analysis")
      .query({
        symbol: "EURUSD-OTC",
        timeframe: "1m",
        limit: 30,
      })
      .expect(200);

    expect(response.body).toEqual({
      data: validIqOptionDemoAnalysisPayload,
    });

    expect(analyzeIqOptionDemo).toHaveBeenCalledWith({
      symbol: "EURUSD-OTC",
      timeframe: "1m",
      limit: 30,
    });
  });

  it("uses the default limit when it is not informed", async () => {
    const analyzeIqOptionDemo = vi
      .fn()
      .mockResolvedValue(validIqOptionDemoAnalysisPayload);

    const quantEngineIqOptionDemoAnalysisClient: QuantEngineIqOptionDemoAnalysisClient =
      {
        analyzeIqOptionDemo,
      };

    const app = createApp({ quantEngineIqOptionDemoAnalysisClient });

    await request(app)
      .get("/api/v1/iq-option/demo/market-analysis")
      .query({
        symbol: "EURUSD",
        timeframe: "5m",
      })
      .expect(200);

    expect(analyzeIqOptionDemo).toHaveBeenCalledWith({
      symbol: "EURUSD",
      timeframe: "5m",
      limit: 100,
    });
  });

  it("rejects an invalid request before calling the Quant Engine", async () => {
    const analyzeIqOptionDemo = vi.fn();

    const quantEngineIqOptionDemoAnalysisClient: QuantEngineIqOptionDemoAnalysisClient =
      {
        analyzeIqOptionDemo,
      };

    const app = createApp({ quantEngineIqOptionDemoAnalysisClient });

    const response = await request(app)
      .get("/api/v1/iq-option/demo/market-analysis")
      .query({
        symbol: "BTC-USDT",
        timeframe: "3m",
        limit: 10,
      })
      .expect(400);

    expect(response.body).toEqual({
      error: {
        code: "INVALID_IQ_OPTION_DEMO_ANALYSIS_REQUEST",
        message: "The IQ Option demo analysis request is invalid.",
      },
    });

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

    const response = await request(app)
      .get("/api/v1/iq-option/demo/market-analysis")
      .query({
        symbol: "EURUSD-OTC",
        timeframe: "1m",
      })
      .expect(502);

    expect(response.body).toEqual({
      error: {
        code: "IQ_OPTION_DEMO_ANALYSIS_UNAVAILABLE",
        message: "IQ Option demo authentication failed.",
      },
    });
  });
});