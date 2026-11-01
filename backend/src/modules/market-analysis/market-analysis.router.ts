import { Router } from "express";

import {
  QuantEngineClientError,
  type QuantEngineClient,
} from "./python-quant-engine.client";
import { marketAnalysisRequestSchema } from "./market-analysis.schema";

export function createMarketAnalysisRouter(
  quantEngineClient: QuantEngineClient,
): Router {
  const router = Router();

  router.get("/", async (request, response) => {
    const parsedRequest = marketAnalysisRequestSchema.safeParse(request.query);

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_ANALYSIS_REQUEST",
          message: "The market analysis request is invalid.",
        },
      });
      return;
    }

    try {
      const analysis = await quantEngineClient.analyze(parsedRequest.data);

      response.status(200).json({
        data: analysis,
      });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "QUANT_ENGINE_UNAVAILABLE",
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