import { Router } from "express";

import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoHistoryClient,
} from "../market-analysis/python-quant-engine.client";
import {
  iqOptionDemoAnalysisHistoryRequestSchema,
  iqOptionDemoAnalysisRecordRequestSchema,
} from "./iq-option-demo-analysis-history.schema";

export function createIqOptionDemoAnalysisHistoryRouter(
  quantEngineClient: QuantEngineIqOptionDemoHistoryClient,
): Router {
  const router = Router();

  router.get("/", async (request, response) => {
    const parsedRequest = iqOptionDemoAnalysisHistoryRequestSchema.safeParse(
      request.query,
    );

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_DEMO_HISTORY_REQUEST",
          message: "The IQ Option demo history request is invalid.",
        },
      });
      return;
    }

    try {
      const history = await quantEngineClient.listIqOptionDemoAnalyses(
        parsedRequest.data,
      );

      response.status(200).json({
        data: history,
      });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_DEMO_HISTORY_UNAVAILABLE",
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
      iqOptionDemoAnalysisRecordRequestSchema.safeParse(request.params);

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_DEMO_RECORD_REQUEST",
          message: "The IQ Option demo analysis record request is invalid.",
        },
      });
      return;
    }

    try {
      const record = await quantEngineClient.getIqOptionDemoAnalysisRecord(
        parsedRequest.data,
      );

      response.status(200).json({
        data: record,
      });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_DEMO_HISTORY_UNAVAILABLE",
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