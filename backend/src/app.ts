import cors from "cors";
import express from "express";
import helmet from "helmet";

import { env } from "./config/env";
import { createMarketAnalysisRouter } from "./modules/market-analysis/market-analysis.router";
import {
  PythonQuantEngineClient,
  type QuantEngineClient,
} from "./modules/market-analysis/python-quant-engine.client";

type AppDependencies = {
  quantEngineClient?: QuantEngineClient;
};

export function createApp(dependencies: AppDependencies = {}) {
  const app = express();

  const quantEngineClient =
    dependencies.quantEngineClient ??
    new PythonQuantEngineClient({
      pythonExecutable: env.QUANT_ENGINE_PYTHON,
      workingDirectory: env.QUANT_ENGINE_WORKING_DIRECTORY,
      timeoutMs: env.QUANT_ENGINE_TIMEOUT_MS,
    });

  app.use(helmet());
  app.use(
    cors({
      origin: env.FRONTEND_ORIGIN,
    }),
  );
  app.use(express.json());

  app.get("/api/v1/health", (_request, response) => {
    response.status(200).json({
      status: "ok",
      service: "tradepulse-backend",
    });
  });

  app.use(
    "/api/v1/market-analysis",
    createMarketAnalysisRouter(quantEngineClient),
  );

  return app;
}

export const app = createApp();