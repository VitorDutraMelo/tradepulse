import request from "supertest";
import { describe, expect, it, vi } from "vitest";

import { createApp } from "../../app";
import {
  QuantEngineClientError,
  type QuantEngineMarketDataClient,
} from "../market-analysis/python-quant-engine.client";

const validCandlesPayload = {
  symbol: "BTC-USD",
  timeframe: "1h",
  source: "binance_spot",
  candles: [
    {
      timestamp: "2026-11-01T12:00:00+00:00",
      open: 77962.63,
      high: 78025.53,
      low: 77749.09,
      close: 77890.02,
      volume: 408.2493,
    },
  ],
};

describe("GET /api/v1/market-data/candles", () => {
  it("returns validated real-market candle data", async () => {
    const getCandles = vi.fn().mockResolvedValue(validCandlesPayload);
    const quantEngineMarketDataClient: QuantEngineMarketDataClient = {
      getCandles,
    };
    const app = createApp({ quantEngineMarketDataClient });

    const response = await request(app)
      .get("/api/v1/market-data/candles")
      .query({
        symbol: "BTC-USDT",
        timeframe: "1h",
      })
      .expect(200);

    expect(response.body).toEqual({
      data: validCandlesPayload,
    });
    expect(getCandles).toHaveBeenCalledWith({
      symbol: "BTC-USDT",
      timeframe: "1h",
      limit: 100,
    });
  });

  it("accepts a slash-separated symbol and normalizes it", async () => {
    const getCandles = vi.fn().mockResolvedValue(validCandlesPayload);
    const quantEngineMarketDataClient: QuantEngineMarketDataClient = {
      getCandles,
    };
    const app = createApp({ quantEngineMarketDataClient });

    await request(app)
      .get("/api/v1/market-data/candles")
      .query({
        symbol: "BTC/USD",
        timeframe: "1h",
      })
      .expect(200);

    expect(getCandles).toHaveBeenCalledWith({
      symbol: "BTC-USD",
      timeframe: "1h",
      limit: 100,
    });
  });

  it("rejects an invalid request before calling the Quant Engine", async () => {
    const getCandles = vi.fn();
    const quantEngineMarketDataClient: QuantEngineMarketDataClient = {
      getCandles,
    };
    const app = createApp({ quantEngineMarketDataClient });

    const response = await request(app)
      .get("/api/v1/market-data/candles")
      .query({
        symbol: "BTC-USDT",
        timeframe: "1h",
        limit: 1,
      })
      .expect(400);

    expect(response.body).toEqual({
      error: {
        code: "INVALID_MARKET_DATA_REQUEST",
        message: "The market data request is invalid.",
      },
    });
    expect(getCandles).not.toHaveBeenCalled();
  });

  it("returns a gateway error when market data retrieval fails", async () => {
    const quantEngineMarketDataClient: QuantEngineMarketDataClient = {
      getCandles: vi
        .fn()
        .mockRejectedValue(
          new QuantEngineClientError("could not retrieve candles from Binance"),
        ),
    };
    const app = createApp({ quantEngineMarketDataClient });

    const response = await request(app)
      .get("/api/v1/market-data/candles")
      .query({
        symbol: "BTC-USDT",
        timeframe: "1h",
      })
      .expect(502);

    expect(response.body).toEqual({
      error: {
        code: "MARKET_DATA_UNAVAILABLE",
        message: "could not retrieve candles from Binance",
      },
    });
  });
});