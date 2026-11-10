import { Router } from "express";

import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoBinarySignalHistoryClient,
} from "../market-analysis/python-quant-engine.client";
import {
  iqOptionDemoBinarySignalHistoryRequestSchema,
  iqOptionDemoBinarySignalRecordRequestSchema,
} from "./iq-option-demo-binary-signal-history.schema";

export function createIqOptionDemoBinarySignalHistoryRouter(
  quantEngineClient: QuantEngineIqOptionDemoBinarySignalHistoryClient,
): Router {
  const router = Router();

  router.get("/", async (request, response) => {
    const parsedRequest =
      iqOptionDemoBinarySignalHistoryRequestSchema.safeParse(request.query);

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_DEMO_BINARY_SIGNAL_HISTORY_REQUEST",
          message: "The IQ Option DEMO binary signal history request is invalid.",
        },
      });
      return;
    }

    try {
      const history =
        await quantEngineClient.listIqOptionDemoBinarySignals(
          parsedRequest.data,
        );

      response.status(200).json({ data: history });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_DEMO_BINARY_SIGNAL_HISTORY_UNAVAILABLE",
            message: error.message,
          },
        });
        return;
      }

      response.status(500).json({
        error: {
          code: "INTERNAL_SERVER_ERROR",
          message: "An unexpected error occurred.",
        },
      });
    }
  });

  router.get("/:recordId", async (request, response) => {
    const parsedRequest =
      iqOptionDemoBinarySignalRecordRequestSchema.safeParse(request.params);

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_DEMO_BINARY_SIGNAL_RECORD_REQUEST",
          message: "The IQ Option DEMO binary signal record request is invalid.",
        },
      });
      return;
    }

    try {
      const record =
        await quantEngineClient.getIqOptionDemoBinarySignalRecord(
          parsedRequest.data,
        );

      response.status(200).json({ data: record });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_DEMO_BINARY_SIGNAL_HISTORY_UNAVAILABLE",
            message: error.message,
          },
        });
        return;
      }

      response.status(500).json({
        error: {
          code: "INTERNAL_SERVER_ERROR",
          message: "An unexpected error occurred.",
        },
      });
    }
  });

  return router;
}
