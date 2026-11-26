import express from "express";
import request from "supertest";
import { describe, expect, it, vi } from "vitest";

import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoM5ValidationHistoryClient,
} from "../market-analysis/python-quant-engine.client";
import { createIqOptionDemoM5ValidationHistoryRouter } from "./iq-option-demo-m5-validation-history.router";

const recordId =
  "iq-demo-m5-20261121-160002-000000-gbpusd-otc-0123456789";

function createHistoryResponse() {
  return {
    source: "iq_option_demo" as const,
    venue: "iq" as const,
    accountMode: "PRACTICE" as const,
    records: [
      {
        recordId,
        recordedAt: "2026-11-21T16:00:02+00:00",
        symbol: "GBPUSD-OTC",
        timeframe: "5m" as const,
        candidateAction: "CALL" as const,
        m5CandidateAction: "CALL" as const,
        actionability: "NOT_ACTIONABLE_LATE",
        theoreticalEntryTime: "2026-11-21T16:00:00+00:00",
        theoreticalExpirationTime: "2026-11-21T16:05:00+00:00",
        outcome: {
          status: "PENDING" as const,
          settledAt: null,
          settlementPrice: null,
        },
      },
    ],
  };
}

function createRecordResponse() {
  return {
    source: "iq_option_demo" as const,
    venue: "iq" as const,
    accountMode: "PRACTICE" as const,
    record: {
      schemaVersion: 1,
      recordId,
      recordedAt: "2026-11-21T16:00:02+00:00",
      source: "iq_option_demo" as const,
      venue: "iq" as const,
      accountMode: "PRACTICE" as const,
      symbol: "GBPUSD-OTC",
      timeframe: "5m",
      outcome: {
        status: "PENDING",
        settledAt: null,
        settlementPrice: null,
      },
    },
  };
}

function createApp(
  client: QuantEngineIqOptionDemoM5ValidationHistoryClient,
) {
  const app = express();

  app.use(
    "/api/v1/iq-option/demo/m5-validations",
    createIqOptionDemoM5ValidationHistoryRouter(client),
  );

  return app;
}

describe("IQ Option DEMO M5 validation history router", () => {
  it("lists theoretical M5 plus M15 validation records", async () => {
    const client: QuantEngineIqOptionDemoM5ValidationHistoryClient = {
      listIqOptionDemoM5Validations: vi
        .fn()
        .mockResolvedValue(createHistoryResponse()),
      getIqOptionDemoM5ValidationRecord: vi.fn(),
    };

    const response = await request(createApp(client)).get(
      "/api/v1/iq-option/demo/m5-validations?limit=20",
    );

    expect(response.status).toBe(200);
    expect(response.body.data.records[0].recordId).toBe(recordId);
    expect(
      client.listIqOptionDemoM5Validations,
    ).toHaveBeenCalledWith({
      limit: 20,
    });
  });

  it("returns one complete theoretical validation record", async () => {
    const client: QuantEngineIqOptionDemoM5ValidationHistoryClient = {
      listIqOptionDemoM5Validations: vi.fn(),
      getIqOptionDemoM5ValidationRecord: vi
        .fn()
        .mockResolvedValue(createRecordResponse()),
    };

    const response = await request(createApp(client)).get(
      `/api/v1/iq-option/demo/m5-validations/${recordId}`,
    );

    expect(response.status).toBe(200);
    expect(response.body.data.record.recordId).toBe(recordId);
  });

  it("rejects an invalid history limit", async () => {
    const client: QuantEngineIqOptionDemoM5ValidationHistoryClient = {
      listIqOptionDemoM5Validations: vi.fn(),
      getIqOptionDemoM5ValidationRecord: vi.fn(),
    };

    const response = await request(createApp(client)).get(
      "/api/v1/iq-option/demo/m5-validations?limit=0",
    );

    expect(response.status).toBe(400);
    expect(
      response.body.error.code,
    ).toBe("INVALID_IQ_OPTION_DEMO_M5_VALIDATION_HISTORY_REQUEST");
  });

  it("returns 502 when the Quant Engine is unavailable", async () => {
    const client: QuantEngineIqOptionDemoM5ValidationHistoryClient = {
      listIqOptionDemoM5Validations: vi
        .fn()
        .mockRejectedValue(
          new QuantEngineClientError("Validation history unavailable"),
        ),
      getIqOptionDemoM5ValidationRecord: vi.fn(),
    };

    const response = await request(createApp(client)).get(
      "/api/v1/iq-option/demo/m5-validations?limit=20",
    );

    expect(response.status).toBe(502);
    expect(response.body.error.code).toBe(
      "IQ_OPTION_DEMO_M5_VALIDATION_HISTORY_UNAVAILABLE",
    );
  });
});
