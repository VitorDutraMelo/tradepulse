import cors from "cors";
import express from "express";
import helmet from "helmet";

import { env } from "./config/env";
import { createIqOptionDemoAnalysisRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-analysis.router";
import { createIqOptionSignalRouter } from "./modules/iq-option-signals/iq-option-signal.router";
import { createMarketAnalysisRouter } from "./modules/market-analysis/market-analysis.router";
import {
  PythonQuantEngineClient,
  type QuantEngineClient,
  type QuantEngineIqOptionDemoAnalysisClient,
  type QuantEngineIqOptionSignalClient,
  type QuantEngineMarketDataClient,
} from "./modules/market-analysis/python-quant-engine.client";
import { createMarketDataRouter } from "./modules/market-data/market-data.router";

type AppDependencies = {
  quantEngineClient?: QuantEngineClient;
  quantEngineIqOptionDemoAnalysisClient?: QuantEngineIqOptionDemoAnalysisClient;
  quantEngineIqOptionSignalClient?: QuantEngineIqOptionSignalClient;
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

  const quantEngineIqOptionDemoAnalysisClient =
    dependencies.quantEngineIqOptionDemoAnalysisClient ??
    defaultQuantEngineClient;

  const quantEngineIqOptionSignalClient =
    dependencies.quantEngineIqOptionSignalClient ?? defaultQuantEngineClient;

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

  app.use(
    "/api/v1/iq-option/signals",
    createIqOptionSignalRouter(quantEngineIqOptionSignalClient),
  );

  app.use(
    "/api/v1/iq-option/demo/market-analysis",
    createIqOptionDemoAnalysisRouter(quantEngineIqOptionDemoAnalysisClient),
  );

  return app;
}

export const app = createApp();