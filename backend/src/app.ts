import cors from "cors";
import express from "express";
import helmet from "helmet";

import { env } from "./config/env";
import { createIqOptionDemoAnalysisRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-analysis.router";
import { createIqOptionDemoAnalysisHistoryRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-analysis-history.router";
import { createIqOptionDemoBinarySignalHistoryRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-binary-signal-history.router";
import { CachedIqOptionDemoAnalysisClient } from "./modules/iq-option-demo-analysis/iq-option-demo-analysis-cache";
import { createIqOptionDemoCandlesRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-candles.router";
import { createIqOptionRealTradingRouter } from "./modules/iq-option-real-trading/iq-option-real-trading.router";
import { IqOptionRealTradingSafetyPolicy } from "./modules/iq-option-real-trading/iq-option-real-trading.policy";
import { createIqOptionSignalRouter } from "./modules/iq-option-signals/iq-option-signal.router";
import { createMarketAnalysisRouter } from "./modules/market-analysis/market-analysis.router";
import {
  PythonQuantEngineClient,
  type QuantEngineClient,
  type QuantEngineIqOptionDemoAnalysisClient,
  type QuantEngineIqOptionDemoCandleClient,
  type QuantEngineIqOptionDemoBinarySignalHistoryClient,
  type QuantEngineIqOptionDemoHistoryClient,
  type QuantEngineIqOptionSignalClient,
  type QuantEngineMarketDataClient,
} from "./modules/market-analysis/python-quant-engine.client";
import { createMarketDataRouter } from "./modules/market-data/market-data.router";

type AppDependencies = {
  quantEngineClient?: QuantEngineClient;
  quantEngineIqOptionDemoAnalysisClient?: QuantEngineIqOptionDemoAnalysisClient;
  quantEngineIqOptionDemoCandleClient?: QuantEngineIqOptionDemoCandleClient;
  quantEngineIqOptionDemoHistoryClient?: QuantEngineIqOptionDemoHistoryClient;
  quantEngineIqOptionDemoBinarySignalHistoryClient?: QuantEngineIqOptionDemoBinarySignalHistoryClient;
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

  const defaultIqOptionDemoAnalysisClient =
    new CachedIqOptionDemoAnalysisClient(defaultQuantEngineClient);

  const quantEngineIqOptionDemoAnalysisClient =
    dependencies.quantEngineIqOptionDemoAnalysisClient ??
    defaultIqOptionDemoAnalysisClient;

  const quantEngineIqOptionDemoCandleClient =
    dependencies.quantEngineIqOptionDemoCandleClient ??
    defaultQuantEngineClient;

  const quantEngineIqOptionSignalClient =
    dependencies.quantEngineIqOptionSignalClient ??
    defaultQuantEngineClient;

  const quantEngineMarketDataClient =
    dependencies.quantEngineMarketDataClient ??
    defaultQuantEngineClient;

  const quantEngineIqOptionDemoHistoryClient =
    dependencies.quantEngineIqOptionDemoHistoryClient ??
    defaultQuantEngineClient;

  const quantEngineIqOptionDemoBinarySignalHistoryClient =
    dependencies.quantEngineIqOptionDemoBinarySignalHistoryClient ??
    defaultQuantEngineClient;

  const realTradingSafetyPolicy = new IqOptionRealTradingSafetyPolicy({
    tradingEnabled: env.IQ_OPTION_REAL_TRADING_ENABLED,
    killSwitchActive: env.IQ_OPTION_REAL_KILL_SWITCH,
    maxStake: env.IQ_OPTION_REAL_MAX_STAKE,
    maxDailyLoss: env.IQ_OPTION_REAL_MAX_DAILY_LOSS,
    maxDailyOrders: env.IQ_OPTION_REAL_MAX_DAILY_ORDERS,
    cooldownSeconds: env.IQ_OPTION_REAL_COOLDOWN_SECONDS,
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
    createIqOptionDemoAnalysisRouter(
      quantEngineIqOptionDemoAnalysisClient,
    ),
  );

  app.use(
    "/api/v1/iq-option/demo/candles",
    createIqOptionDemoCandlesRouter(
      quantEngineIqOptionDemoCandleClient,
    ),
  );

  app.use(
    "/api/v1/iq-option/demo/analyses",
    createIqOptionDemoAnalysisHistoryRouter(
      quantEngineIqOptionDemoHistoryClient,
    ),
  );

  app.use(
    "/api/v1/iq-option/demo/binary-signals",
    createIqOptionDemoBinarySignalHistoryRouter(
      quantEngineIqOptionDemoBinarySignalHistoryClient,
    ),
  );

  app.use(
    "/api/v1/iq-option/real",
    createIqOptionRealTradingRouter(realTradingSafetyPolicy),
  );

  return app;
}

export const app = createApp();