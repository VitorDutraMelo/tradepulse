import { Router } from "express";

import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoCandleClient,
} from "../market-analysis/python-quant-engine.client";
import { iqOptionDemoCandlesRequestSchema } from "./iq-option-demo-candles.schema";

export function createIqOptionDemoCandlesRouter(
  quantEngineClient: QuantEngineIqOptionDemoCandleClient,
): Router {
  const router = Router();

  router.get("/", async (request, response) => {
    const parsedRequest = iqOptionDemoCandlesRequestSchema.safeParse(
      request.query,
    );

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_DEMO_CANDLES_REQUEST",
          message:
            "A supported OTC symbol, timeframe 1m and limit between 1 and 1000 are required.",
        },
      });
      return;
    }

    try {
      const candles = await quantEngineClient.getIqOptionDemoCandles(
        parsedRequest.data,
      );

      response.status(200).json({
        data: candles,
      });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_DEMO_CANDLES_UNAVAILABLE",
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
