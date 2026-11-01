import { Router } from "express";

import {
  QuantEngineClientError,
  type QuantEngineMarketDataClient,
} from "../market-analysis/python-quant-engine.client";
import { marketCandlesRequestSchema } from "./market-data.schema";

export function createMarketDataRouter(
  quantEngineMarketDataClient: QuantEngineMarketDataClient,
): Router {
  const router = Router();

  router.get("/candles", async (request, response) => {
    const parsedRequest = marketCandlesRequestSchema.safeParse(request.query);

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_MARKET_DATA_REQUEST",
          message: "The market data request is invalid.",
        },
      });
      return;
    }

    try {
      const candles = await quantEngineMarketDataClient.getCandles(
        parsedRequest.data,
      );

      response.status(200).json({
        data: candles,
      });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "MARKET_DATA_UNAVAILABLE",
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