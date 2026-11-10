import { Router } from "express";

import {
  IqOptionRealTradingSafetyPolicy,
} from "./iq-option-real-trading.policy";
import {
  iqOptionRealTradingPreflightRequestSchema,
} from "./iq-option-real-trading.schema";

export function createIqOptionRealTradingRouter(
  safetyPolicy: IqOptionRealTradingSafetyPolicy,
): Router {
  const router = Router();

  router.get("/status", (_request, response) => {
    response.status(200).json({
      data: safetyPolicy.getSafetyStatus(),
    });
  });

  router.post("/preflight", (request, response) => {
    const parsedRequest = iqOptionRealTradingPreflightRequestSchema.safeParse(
      request.body,
    );

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_REAL_PREFLIGHT_REQUEST",
          message:
            "A valid symbol, timeframe, CALL or PUT action and positive stake are required.",
        },
      });
      return;
    }

    response.status(200).json({
      data: safetyPolicy.preflight(parsedRequest.data),
    });
  });

  return router;
}