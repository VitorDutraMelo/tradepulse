import cors from "cors";
import express from "express";
import helmet from "helmet";

import { env } from "./config/env";
import { createIqOptionDemoAnalysisRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-analysis.router";
import { createIqOptionDemoAnalysisHistoryRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-analysis-history.router";
import { createIqOptionDemoBinarySignalHistoryRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-binary-signal-history.router";
import { createIqOptionDemoCandlesRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-candles.router";
import { createIqOptionDemoM5SignalRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-m5-signal.router";
import { createIqOptionDemoM5SyncRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-m5-sync.router";
import { createIqOptionDemoM5ValidationHistoryRouter } from "./modules/iq-option-demo-analysis/iq-option-demo-m5-validation-history.router";
import { GatewayAnalysisClient } from "./modules/iq-gateway/gateway-analysis.client";
import { createPythonWorkerSpawner, GatewayWorker } from "./modules/iq-gateway/gateway-worker";
import { createIqGatewayRouter } from "./modules/iq-gateway/iq-gateway.router";
import { LiveAnalysisService } from "./modules/iq-gateway/live-analysis.service";
import { jsonLogger, silentLogger } from "./modules/iq-gateway/logger";
import { createIqOptionSignalRouter } from "./modules/iq-option-signals/iq-option-signal.router";
import { createMarketAnalysisRouter } from "./modules/market-analysis/market-analysis.router";
import {
  PythonQuantEngineClient,
  type QuantEngineClient,
  type QuantEngineIqOptionDemoAnalysisClient,
  type QuantEngineIqOptionDemoBinarySignalHistoryClient,
  type QuantEngineIqOptionDemoCandleClient,
  type QuantEngineIqOptionDemoHistoryClient,
  type QuantEngineIqOptionDemoM5SignalClient,
  type QuantEngineIqOptionDemoM5SyncClient,
  type QuantEngineIqOptionDemoM5ValidationHistoryClient,
  type QuantEngineIqOptionSignalClient,
  type QuantEngineMarketDataClient,
} from "./modules/market-analysis/python-quant-engine.client";
import { createMarketDataRouter } from "./modules/market-data/market-data.router";

type AppDependencies = {
  quantEngineClient?: QuantEngineClient;
  quantEngineIqOptionDemoAnalysisClient?: QuantEngineIqOptionDemoAnalysisClient;
  quantEngineIqOptionDemoBinarySignalHistoryClient?: QuantEngineIqOptionDemoBinarySignalHistoryClient;
  quantEngineIqOptionDemoCandleClient?: QuantEngineIqOptionDemoCandleClient;
  quantEngineIqOptionDemoHistoryClient?: QuantEngineIqOptionDemoHistoryClient;
  quantEngineIqOptionDemoM5SignalClient?: QuantEngineIqOptionDemoM5SignalClient;
  quantEngineIqOptionDemoM5SyncClient?: QuantEngineIqOptionDemoM5SyncClient;
  quantEngineIqOptionDemoM5ValidationHistoryClient?: QuantEngineIqOptionDemoM5ValidationHistoryClient;
  quantEngineIqOptionSignalClient?: QuantEngineIqOptionSignalClient;
  quantEngineMarketDataClient?: QuantEngineMarketDataClient;
  gatewayWorker?: GatewayWorker;
  liveAnalysis?: LiveAnalysisService;
};

export type AppServices = {
  gatewayWorker: GatewayWorker;
  liveAnalysis: LiveAnalysisService;
};

export function createApp(dependencies: AppDependencies = {}) {
  const app = express();
  const logger = env.NODE_ENV === "test" ? silentLogger : jsonLogger;

  /*
   * One persistent PRACTICE-only IQ Option session for the whole backend.
   * The worker process starts lazily on the first IQ request.
   */
  const gatewayWorker =
    dependencies.gatewayWorker ??
    new GatewayWorker({
      spawnWorker: createPythonWorkerSpawner({
        pythonExecutable: env.QUANT_ENGINE_PYTHON,
        workingDirectory: env.QUANT_ENGINE_WORKING_DIRECTORY,
      }),
      requestTimeoutMs: env.IQ_GATEWAY_REQUEST_TIMEOUT_MS,
      maxQueue: env.IQ_GATEWAY_MAX_QUEUE,
      restartBackoffMaxMs: env.IQ_GATEWAY_RESTART_BACKOFF_MAX_MS,
      logger,
    });

  const liveAnalysis =
    dependencies.liveAnalysis ??
    new LiveAnalysisService(gatewayWorker, {
      toleranceMs: {
        "1m": env.SIGNAL_TOLERANCE_M1_MS,
        "5m": env.SIGNAL_TOLERANCE_M5_MS,
      },
      maxSubscriptions: env.IQ_LIVE_MAX_SUBSCRIPTIONS,
      subscriptionTtlMs: env.IQ_LIVE_SUBSCRIPTION_TTL_MS,
      publicationLogPath: env.NODE_ENV === "test" ? null : env.PUBLICATION_LOG_PATH,
      logger,
    });

  const gatewayClient = new GatewayAnalysisClient(gatewayWorker, liveAnalysis);

  // Legacy Binance endpoints and local history readers keep the CLI runner:
  // they never log in to IQ Option.
  const defaultQuantEngineClient = new PythonQuantEngineClient({
    pythonExecutable: env.QUANT_ENGINE_PYTHON,
    workingDirectory: env.QUANT_ENGINE_WORKING_DIRECTORY,
    timeoutMs: env.QUANT_ENGINE_TIMEOUT_MS,
  });

  const quantEngineClient = dependencies.quantEngineClient ?? defaultQuantEngineClient;
  const quantEngineIqOptionDemoAnalysisClient =
    dependencies.quantEngineIqOptionDemoAnalysisClient ?? gatewayClient;
  const quantEngineIqOptionDemoBinarySignalHistoryClient =
    dependencies.quantEngineIqOptionDemoBinarySignalHistoryClient ?? defaultQuantEngineClient;
  const quantEngineIqOptionDemoCandleClient =
    dependencies.quantEngineIqOptionDemoCandleClient ?? gatewayClient;
  const quantEngineIqOptionDemoHistoryClient =
    dependencies.quantEngineIqOptionDemoHistoryClient ?? defaultQuantEngineClient;
  const quantEngineIqOptionDemoM5SignalClient =
    dependencies.quantEngineIqOptionDemoM5SignalClient ?? gatewayClient;
  const quantEngineIqOptionDemoM5SyncClient =
    dependencies.quantEngineIqOptionDemoM5SyncClient ?? gatewayClient;
  const quantEngineIqOptionDemoM5ValidationHistoryClient =
    dependencies.quantEngineIqOptionDemoM5ValidationHistoryClient ?? defaultQuantEngineClient;
  const quantEngineIqOptionSignalClient =
    dependencies.quantEngineIqOptionSignalClient ?? defaultQuantEngineClient;
  const quantEngineMarketDataClient =
    dependencies.quantEngineMarketDataClient ?? defaultQuantEngineClient;

  app.locals.services = { gatewayWorker, liveAnalysis } satisfies AppServices;

  app.disable("x-powered-by");
  app.use(helmet());

  app.use(
    cors({
      origin: env.FRONTEND_ORIGIN,
      methods: ["GET"],
    }),
  );

  app.use(express.json({ limit: "16kb" }));

  app.get("/api/v1/health", (_request, response) => {
    const gateway = gatewayWorker.status();

    response.status(200).json({
      status: "ok",
      service: "tradepulse-backend",
      iqGateway: {
        workerState: gateway.workerState,
        sessionState:
          typeof gateway.session?.state === "string" ? gateway.session.state : null,
      },
    });
  });

  app.use("/api/v1/market-analysis", createMarketAnalysisRouter(quantEngineClient));
  app.use("/api/v1/market-data", createMarketDataRouter(quantEngineMarketDataClient));
  app.use("/api/v1/iq-option/signals", createIqOptionSignalRouter(quantEngineIqOptionSignalClient));

  app.use("/api/v1/iq-option/demo", createIqGatewayRouter(liveAnalysis));

  app.use(
    "/api/v1/iq-option/demo/market-analysis",
    createIqOptionDemoAnalysisRouter(quantEngineIqOptionDemoAnalysisClient),
  );
  app.use(
    "/api/v1/iq-option/demo/candles",
    createIqOptionDemoCandlesRouter(quantEngineIqOptionDemoCandleClient),
  );
  app.use(
    "/api/v1/iq-option/demo/m5-sync",
    createIqOptionDemoM5SyncRouter(quantEngineIqOptionDemoM5SyncClient),
  );
  app.use(
    "/api/v1/iq-option/demo/m5-signal",
    createIqOptionDemoM5SignalRouter(quantEngineIqOptionDemoM5SignalClient),
  );
  app.use(
    "/api/v1/iq-option/demo/m5-validations",
    createIqOptionDemoM5ValidationHistoryRouter(quantEngineIqOptionDemoM5ValidationHistoryClient),
  );
  app.use(
    "/api/v1/iq-option/demo/analyses",
    createIqOptionDemoAnalysisHistoryRouter(quantEngineIqOptionDemoHistoryClient),
  );
  app.use(
    "/api/v1/iq-option/demo/binary-signals",
    createIqOptionDemoBinarySignalHistoryRouter(quantEngineIqOptionDemoBinarySignalHistoryClient),
  );

  /*
   * REAL account isolation (A.1 security): the former
   * /api/v1/iq-option/real/* preflight routes are intentionally NOT mounted.
   * TradePulse has no order executor and must never trade automatically.
   * The unmounted module is kept only until the owner decides (decision N.2).
   */

  return app;
}

export const app = createApp();
