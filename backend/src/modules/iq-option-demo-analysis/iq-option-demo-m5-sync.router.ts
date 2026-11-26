import { Router } from "express";

import {
  QuantEngineClientError,
  type QuantEngineIqOptionDemoM5SyncClient,
} from "../market-analysis/python-quant-engine.client";
import { iqOptionDemoM5SyncRequestSchema } from "./iq-option-demo-m5-sync.schema";

export function createIqOptionDemoM5SyncRouter(
  quantEngineClient: QuantEngineIqOptionDemoM5SyncClient,
): Router {
  const router = Router();

  router.get("/", async (request, response) => {
    const requestStartedAt = new Date();
    const requestStartedAtMs = performance.now();

    const parsedRequest = iqOptionDemoM5SyncRequestSchema.safeParse(
      request.query,
    );

    if (!parsedRequest.success) {
      response.status(400).json({
        error: {
          code: "INVALID_IQ_OPTION_DEMO_M5_SYNC_REQUEST",
          message: "Only GBPUSD-OTC is available for the M5 synchronization demonstration.",
        },
      });
      return;
    }

    try {
      const sync = await quantEngineClient.getIqOptionDemoM5Sync(
        parsedRequest.data,
      );
      const responsePreparedAt = new Date();

      response.status(200).json({
        data: {
          ...sync,
          timing: {
            ...sync.timing,
            nodeApi: {
              requestStartedAt: requestStartedAt.toISOString(),
              responsePreparedAt: responsePreparedAt.toISOString(),
              durationMs: Number(
                (performance.now() - requestStartedAtMs).toFixed(3),
              ),
            },
          },
        },
      });
    } catch (error) {
      if (error instanceof QuantEngineClientError) {
        response.status(502).json({
          error: {
            code: "IQ_OPTION_DEMO_M5_SYNC_UNAVAILABLE",
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