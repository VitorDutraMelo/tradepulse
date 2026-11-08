import { Router } from "express";

import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoAnalysisClient,
} from "../market-analysis/python-quant-engine.client";
import { iqOptionDemoAnalysisRequestSchema } from "./iq-option-demo-analysis.schema";

export function createIqOptionDemoAnalysisRouter(
  quantEngineClient: QuantEngineIqOptionDemoAnalysisClient,
): Router {
  const router = Router();

  router.get("/", async (request, response) => {
    const parsedRequest = iqOptionDemoAnalysisRequestSchema.safeParse(
      request.query,
    );

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_DEMO_ANALYSIS_REQUEST",
          message: "The IQ Option demo analysis request is invalid.",
        },
      });
      return;
    }

    try {
      const analysis = await quantEngineClient.analyzeIqOptionDemo(
        parsedRequest.data,
      );

      response.status(200).json(analysis);
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_DEMO_ANALYSIS_UNAVAILABLE",
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