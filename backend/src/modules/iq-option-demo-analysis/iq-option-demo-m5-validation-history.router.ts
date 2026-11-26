import { Router } from "express";

import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoM5ValidationHistoryClient,
} from "../market-analysis/python-quant-engine.client";
import {
  iqOptionDemoM5ValidationHistoryRequestSchema,
  iqOptionDemoM5ValidationRecordRequestSchema,
} from "./iq-option-demo-m5-validation-history.schema";

export function createIqOptionDemoM5ValidationHistoryRouter(
  quantEngineClient: QuantEngineIqOptionDemoM5ValidationHistoryClient,
): Router {
  const router = Router();

  router.get("/", async (request, response) => {
    const parsedRequest =
      iqOptionDemoM5ValidationHistoryRequestSchema.safeParse(
        request.query,
      );

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_DEMO_M5_VALIDATION_HISTORY_REQUEST",
          message: "The IQ Option demo M5 validation history request is invalid.",
        },
      });
      return;
    }

    try {
      const history =
        await quantEngineClient.listIqOptionDemoM5Validations(
          parsedRequest.data,
        );

      response.status(200).json({
        data: history,
      });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_DEMO_M5_VALIDATION_HISTORY_UNAVAILABLE",
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
      iqOptionDemoM5ValidationRecordRequestSchema.safeParse(
        request.params,
      );

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_DEMO_M5_VALIDATION_RECORD_REQUEST",
          message: "The IQ Option demo M5 validation record request is invalid.",
        },
      });
      return;
    }

    try {
      const record =
        await quantEngineClient.getIqOptionDemoM5ValidationRecord(
          parsedRequest.data,
        );

      response.status(200).json({
        data: record,
      });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_DEMO_M5_VALIDATION_RECORD_UNAVAILABLE",
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
