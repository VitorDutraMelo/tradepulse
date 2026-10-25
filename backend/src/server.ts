import { app } from "./app";
import { env } from "./config/env";

const server = app.listen(env.PORT, () => {
  console.log(`TradePulse API running at http://localhost:${env.PORT}`);
});

function shutdown(signal: string): void {
  console.log(`${signal} received. Shutting down TradePulse API.`);

  server.close(() => {
    process.exit(0);
  });
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));