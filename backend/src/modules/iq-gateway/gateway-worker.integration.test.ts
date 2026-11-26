import { existsSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { createPythonWorkerSpawner, GatewayWorker } from "./gateway-worker";

const quantEngine = path.resolve(__dirname, "../../../../quant-engine");
const python = path.join(
  quantEngine,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);

/**
 * Real Node <-> Python protocol test. It never logs in: credentials are
 * removed from the child environment, so the worker must refuse to connect.
 */
describe.skipIf(!existsSync(python))("gateway worker process (integration)", () => {
  it("starts the real Python worker and reports missing credentials", async () => {
    const env = { ...process.env };
    delete env.IQ_OPTION_DEMO_EMAIL;
    delete env.IQ_OPTION_DEMO_PASSWORD;

    const worker = new GatewayWorker({
      spawnWorker: createPythonWorkerSpawner({
        pythonExecutable: python,
        workingDirectory: quantEngine,
        env,
      }),
      requestTimeoutMs: 20_000,
    });

    try {
      const status = await worker.request("status", {});
      expect(status.result).toMatchObject({
        session: { state: "DISCONNECTED", credentialsConfigured: false, accountMode: null },
      });

      await expect(
        worker.request("analyze_m1", { symbol: "EURUSD-OTC", timeframe: "1m", limit: 120 }),
      ).rejects.toMatchObject({ code: "IQ_OPTION_CREDENTIALS_MISSING" });

      await expect(worker.request("buy" as never, {})).rejects.toMatchObject({
        code: "INVALID_GATEWAY_REQUEST",
      });
      expect(worker.status().workerStarts).toBe(1);
    } finally {
      await worker.shutdown();
    }
  }, 30_000);
});
