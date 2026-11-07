import request from "supertest";
import { describe, expect, it, vi } from "vitest";

import { createApp } from "../../app";
import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoHistoryClient,
} from "../market-analysis/python-quant-engine.client";
import type {
  IqOptionDemoAnalysisHistoryResponse,
  IqOptionDemoAnalysisRecordResponse,
} from "./iq-option-demo-analysis-history.schema";

const recordId = "iq-demo-20261107-095641-813083-eurusd-otc-3d3187891f";

const validHistoryPayload: IqOptionDemoAnalysisHistoryResponse = {
  source: "iq_option_demo",
  venue: "iq",
  accountMode: "PRACTICE",
  records: [
    {
      recordId,
      recordedAt: "2026-11-07T09:56:41.813083+00:00",
      source: "iq_option_demo",
      venue: "iq",
      accountMode: "PRACTICE",
      symbol: "EURUSD-OTC",
      timeframe: "1m",
      timestamp: "2026-11-07T09:55:00+00:00",
      direction: "NEUTRAL",
      score: 20,
      strategy: "ema_crossover",
    },
  ],
};

const validRecordPayload: IqOptionDemoAnalysisRecordResponse = {
  schemaVersion: 1,
  recordId,
  recordedAt: "2026-11-07T09:56:41.813083+00:00",
  source: "iq_option_demo",
  venue: "iq",
  accountMode: "PRACTICE",
  analysis: {
    symbol: "EURUSD-OTC",
    timeframe: "1m",
    timestamp: "2026-11-07T09:55:00+00:00",
    direction: "NEUTRAL",
    score: 20,
    reasons: ["No EMA 9/21 crossover detected"],
    strategy: "ema_crossover",
    indicators: {
      fastEmaPeriod: 9,
      slowEmaPeriod: 21,
    },
  },
  candles: [
    {
      timestamp: "2026-11-07T09:54:00+00:00",
      open: 1.1301,
      high: 1.1304,
      low: 1.13,
      close: 1.1302,
      volume: 0,
      closed: true,
    },
  ],
};

describe("GET /api/v1/iq-option/demo/analyses", () => {
  it("returns recent IQ Option DEMO analysis summaries", async () => {
    const listIqOptionDemoAnalyses = vi
      .fn()
      .mockResolvedValue(validHistoryPayload);

    const quantEngineIqOptionDemoHistoryClient: QuantEngineIqOptionDemoHistoryClient =
      {
        listIqOptionDemoAnalyses,
        getIqOptionDemoAnalysisRecord: vi.fn(),
      };

    const app = createApp({ quantEngineIqOptionDemoHistoryClient });

    const response = await request(app)
      .get("/api/v1/iq-option/demo/analyses")
      .query({ limit: 10 })
      .expect(200);

    expect(response.body).toEqual({
      data: validHistoryPayload,
    });

    expect(listIqOptionDemoAnalyses).toHaveBeenCalledWith({
      limit: 10,
    });
  });

  it("uses the default history limit", async () => {
    const listIqOptionDemoAnalyses = vi
      .fn()
      .mockResolvedValue(validHistoryPayload);

    const quantEngineIqOptionDemoHistoryClient: QuantEngineIqOptionDemoHistoryClient =
      {
        listIqOptionDemoAnalyses,
        getIqOptionDemoAnalysisRecord: vi.fn(),
      };

    const app = createApp({ quantEngineIqOptionDemoHistoryClient });

    await request(app)
      .get("/api/v1/iq-option/demo/analyses")
      .expect(200);

    expect(listIqOptionDemoAnalyses).toHaveBeenCalledWith({
      limit: 20,
    });
  });

  it("returns one complete IQ Option DEMO analysis record", async () => {
    const getIqOptionDemoAnalysisRecord = vi
      .fn()
      .mockResolvedValue(validRecordPayload);

    const quantEngineIqOptionDemoHistoryClient: QuantEngineIqOptionDemoHistoryClient =
      {
        listIqOptionDemoAnalyses: vi.fn(),
        getIqOptionDemoAnalysisRecord,
      };

    const app = createApp({ quantEngineIqOptionDemoHistoryClient });

    const response = await request(app)
      .get(`/api/v1/iq-option/demo/analyses/${recordId}`)
      .expect(200);

    expect(response.body).toEqual({
      data: validRecordPayload,
    });

    expect(getIqOptionDemoAnalysisRecord).toHaveBeenCalledWith({
      recordId,
    });
  });

  it("rejects invalid record identifiers", async () => {
    const quantEngineIqOptionDemoHistoryClient: QuantEngineIqOptionDemoHistoryClient =
      {
        listIqOptionDemoAnalyses: vi.fn(),
        getIqOptionDemoAnalysisRecord: vi.fn(),
      };

    const app = createApp({ quantEngineIqOptionDemoHistoryClient });

    const response = await request(app)
      .get("/api/v1/iq-option/demo/analyses/not-a-record")
      .expect(400);

    expect(response.body).toEqual({
      error: {
        code: "INVALID_IQ_OPTION_DEMO_RECORD_REQUEST",
        message: "The IQ Option demo analysis record request is invalid.",
      },
    });
  });

  it("returns a gateway error when the Quant Engine fails", async () => {
    const quantEngineIqOptionDemoHistoryClient: QuantEngineIqOptionDemoHistoryClient =
      {
        listIqOptionDemoAnalyses: vi
          .fn()
          .mockRejectedValue(
            new QuantEngineClientError(
              "The Quant Engine could not complete the request.",
            ),
          ),
        getIqOptionDemoAnalysisRecord: vi.fn(),
      };

    const app = createApp({ quantEngineIqOptionDemoHistoryClient });

    const response = await request(app)
      .get("/api/v1/iq-option/demo/analyses")
      .expect(502);

    expect(response.body).toEqual({
      error: {
        code: "IQ_OPTION_DEMO_HISTORY_UNAVAILABLE",
        message: "The Quant Engine could not complete the request.",
      },
    });
  });
});

