import { app, type AppServices } from "./app";
import { env } from "./config/env";
import { jsonLogger } from "./modules/iq-gateway/logger";

const services = app.locals.services as AppServices;

const server = app.listen(env.PORT, env.HOST, () => {
  jsonLogger("info", "api_started", {
    url: `http://${env.HOST.includes(":") ? `[${env.HOST}]` : env.HOST}:${env.PORT}`,
    bind: "loopback-only",
  });
});

let shuttingDown = false;

async function shutdown(signal: string): Promise<void> {
  if (shuttingDown) {
    return;
  }

  shuttingDown = true;
  jsonLogger("info", "api_stopping", { signal });

  services.liveAnalysis.stop();
  await services.gatewayWorker.shutdown();

  server.close(() => {
    process.exit(0);
  });

  setTimeout(() => process.exit(0), 5000).unref();
}

process.on("SIGINT", () => void shutdown("SIGINT"));
process.on("SIGTERM", () => void shutdown("SIGTERM"));
