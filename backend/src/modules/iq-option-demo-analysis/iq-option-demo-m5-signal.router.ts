import { Router } from "express";

import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoM5SignalClient,
} from "../market-analysis/python-quant-engine.client";
import { iqOptionDemoM5SignalRequestSchema } from "./iq-option-demo-m5-signal.schema";

export function createIqOptionDemoM5SignalRouter(
  quantEngineClient: QuantEngineIqOptionDemoM5SignalClient,
): Router {
  const router = Router();

  router.get("/", async (request, response) => {
    const parsedRequest = iqOptionDemoM5SignalRequestSchema.safeParse(
      request.query,
    );

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_DEMO_M5_SIGNAL_REQUEST",
          message: "Only GBPUSD-OTC is available for the first M5 signal validation.",
        },
      });
      return;
    }

    try {
      const signal = await quantEngineClient.getIqOptionDemoM5Signal(
        parsedRequest.data,
      );

      response.status(200).json({
        data: signal,
      });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_DEMO_M5_SIGNAL_UNAVAILABLE",
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