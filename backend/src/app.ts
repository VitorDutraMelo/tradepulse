import cors from "cors";
import express from "express";
import helmet from "helmet";

import { env } from "./config/env";
import { createMarketAnalysisRouter } from "./modules/market-analysis/market-analysis.router";
import {
  PythonQuantEngineClient,
  type QuantEngineClient,
  type QuantEngineMarketDataClient,
} from "./modules/market-analysis/python-quant-engine.client";
import { createMarketDataRouter } from "./modules/market-data/market-data.router";

type AppDependencies = {
  quantEngineClient?: QuantEngineClient;
  quantEngineMarketDataClient?: QuantEngineMarketDataClient;
};

export function createApp(dependencies: AppDependencies = {}) {
  const app = express();

  const defaultQuantEngineClient = new PythonQuantEngineClient({
    pythonExecutable: env.QUANT_ENGINE_PYTHON,
    workingDirectory: env.QUANT_ENGINE_WORKING_DIRECTORY,
    timeoutMs: env.QUANT_ENGINE_TIMEOUT_MS,
  });

  const quantEngineClient =
    dependencies.quantEngineClient ?? defaultQuantEngineClient;

  const quantEngineMarketDataClient =
    dependencies.quantEngineMarketDataClient ?? defaultQuantEngineClient;

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

  app.use(
    "/api/v1/market-data",
    createMarketDataRouter(quantEngineMarketDataClient),
  );

  return app;
}

export const app = createApp();