import { Router } from "express";

import {
  QuantEngineClientError,
  type QuantEngineIqOptionSignalClient,
} from "../market-analysis/python-quant-engine.client";
import { iqOptionSignalRequestSchema } from "./iq-option-signal.schema";

export function createIqOptionSignalRouter(
  quantEngineClient: QuantEngineIqOptionSignalClient,
): Router {
  const router = Router();

  router.get("/prepare", async (request, response) => {
    const parsedRequest = iqOptionSignalRequestSchema.safeParse(request.query);

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_SIGNAL_REQUEST",
          message: "The IQ Option signal request is invalid.",
        },
      });
      return;
    }

    try {
      const signal = await quantEngineClient.prepareIqOptionSignal(
        parsedRequest.data,
      );

      response.status(200).json({
        data: signal,
      });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_SIGNAL_PREPARATION_UNAVAILABLE",
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