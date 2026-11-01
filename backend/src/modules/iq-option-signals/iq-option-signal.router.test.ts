import request from "supertest";
import { describe, expect, it, vi } from "vitest";

import { createApp } from "../../app";
import {
  QuantEngineClientError,
  type QuantEngineIqOptionSignalClient,
} from "../market-analysis/python-quant-engine.client";

const validIqOptionSignalPayload = {
  platform: "IQ_OPTION" as const,
  asset: "BTC-USD",
  market: "CRYPTO" as const,
  timeframe: "1h",
  timestamp: "2026-11-01T16:00:00+00:00",
  dataSource: "binance_spot",
  analysisDirection: "NEUTRAL" as const,
  action: "WAIT" as const,
  entryTime: null,
  expirationTime: null,
  reasons: [
    "No EMA 9/21 crossover detected",
    "No IQ Option policy is configured for this market and data source; manual action remains WAIT.",
  ],
};

describe("GET /api/v1/iq-option/signals/prepare", () => {
  it("returns a validated IQ Option signal response", async () => {
    const prepareIqOptionSignal = vi
      .fn()
      .mockResolvedValue(validIqOptionSignalPayload);
    const quantEngineIqOptionSignalClient: QuantEngineIqOptionSignalClient = {
      prepareIqOptionSignal,
    };
    const app = createApp({ quantEngineIqOptionSignalClient });

    const response = await request(app)
      .get("/api/v1/iq-option/signals/prepare")
      .query({
        symbol: "BTC-USDT",
        timeframe: "1h",
      })
      .expect(200);

    expect(response.body).toEqual({
      data: validIqOptionSignalPayload,
    });
    expect(prepareIqOptionSignal).toHaveBeenCalledWith({
      symbol: "BTC-USDT",
      timeframe: "1h",
      limit: 100,
      market: "CRYPTO",
    });
  });

  it("accepts a slash-separated symbol and normalizes it", async () => {
    const prepareIqOptionSignal = vi
      .fn()
      .mockResolvedValue(validIqOptionSignalPayload);
    const quantEngineIqOptionSignalClient: QuantEngineIqOptionSignalClient = {
      prepareIqOptionSignal,
    };
    const app = createApp({ quantEngineIqOptionSignalClient });

    await request(app)
      .get("/api/v1/iq-option/signals/prepare")
      .query({
        symbol: "BTC/USD",
        timeframe: "1h",
      })
      .expect(200);

    expect(prepareIqOptionSignal).toHaveBeenCalledWith({
      symbol: "BTC-USD",
      timeframe: "1h",
      limit: 100,
      market: "CRYPTO",
    });
  });

  it("rejects an invalid request before calling the Quant Engine", async () => {
    const prepareIqOptionSignal = vi.fn();
    const quantEngineIqOptionSignalClient: QuantEngineIqOptionSignalClient = {
      prepareIqOptionSignal,
    };
    const app = createApp({ quantEngineIqOptionSignalClient });

    const response = await request(app)
      .get("/api/v1/iq-option/signals/prepare")
      .query({
        symbol: "BTC-USDT",
        timeframe: "1h",
        limit: 10,
      })
      .expect(400);

    expect(response.body).toEqual({
      error: {
        code: "INVALID_IQ_OPTION_SIGNAL_REQUEST",
        message: "The IQ Option signal request is invalid.",
      },
    });
    expect(prepareIqOptionSignal).not.toHaveBeenCalled();
  });

  it("returns a gateway error when the Quant Engine fails", async () => {
    const quantEngineIqOptionSignalClient: QuantEngineIqOptionSignalClient = {
      prepareIqOptionSignal: vi
        .fn()
        .mockRejectedValue(
          new QuantEngineClientError("could not retrieve candles from Binance"),
        ),
    };
    const app = createApp({ quantEngineIqOptionSignalClient });

    const response = await request(app)
      .get("/api/v1/iq-option/signals/prepare")
      .query({
        symbol: "BTC-USDT",
        timeframe: "1h",
      })
      .expect(502);

    expect(response.body).toEqual({
      error: {
        code: "IQ_OPTION_SIGNAL_PREPARATION_UNAVAILABLE",
        message: "could not retrieve candles from Binance",
      },
    });
  });
});