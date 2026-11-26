import { Router } from "express";
import { z } from "zod";

import { GatewayError } from "./gateway-worker";
import { StrategyUnavailableError, type LiveAnalysisService } from "./live-analysis.service";
import { SUPPORTED_OTC_SYMBOLS } from "./strategies";

const liveRequestSchema = z.object({
  symbol: z.string().trim().toUpperCase().pipe(z.enum(SUPPORTED_OTC_SYMBOLS)),
  timeframe: z.enum(["1m", "5m"]),
});

export function createIqGatewayRouter(live: LiveAnalysisService): Router {
  const router = Router();

  router.get("/status", (_request, response) => {
    response.status(200).json({ data: live.status() });
  });

  router.get("/live", async (request, response) => {
    const parsed = liveRequestSchema.safeParse(request.query);

    if (!parsed.success) {
      response.status(400).json({
        error: {
          code: "INVALID_LIVE_REQUEST",
          message: `symbol must be one of ${SUPPORTED_OTC_SYMBOLS.join(", ")} and timeframe 1m or 5m.`,
        },
      });
      return;
    }

    try {
      const view = await live.getLive(parsed.data.symbol, parsed.data.timeframe);
      response.status(200).json({ data: view });
    } catch (error) {
      if (error instanceof StrategyUnavailableError) {
        response
          .status(error.code === "LIVE_SUBSCRIPTION_LIMIT" ? 429 : 422)
          .json({ error: { code: error.code, message: error.message } });
        return;
      }

      if (error instanceof GatewayError) {
        response.status(503).json({ error: { code: error.code, message: error.message } });
        return;
      }

      response.status(500).json({
        error: { code: "INTERNAL_SERVER_ERROR", message: "An unexpected error occurred." },
      });
    }
  });

  return router;
}
