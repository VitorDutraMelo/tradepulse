import request from "supertest";
import { describe, expect, it } from "vitest";

import { createApp } from "./app";
import { env, LOOPBACK_HOSTS } from "./config/env";
import { GatewayWorker } from "./modules/iq-gateway/gateway-worker";

function appWithoutIq() {
  const gatewayWorker = new GatewayWorker({
    spawnWorker: () => {
      throw new Error("no IQ worker may be spawned in this test");
    },
  });

  return createApp({ gatewayWorker });
}

describe("security defaults", () => {
  it("binds to a loopback address by default", () => {
    expect(env.HOST).toBe("127.0.0.1");
    expect(LOOPBACK_HOSTS).not.toContain("0.0.0.0");
  });

  it("does not expose any REAL account route", async () => {
    const app = appWithoutIq();

    await request(app).get("/api/v1/iq-option/real/status").expect(404);
    await request(app)
      .post("/api/v1/iq-option/real/preflight")
      .send({ symbol: "EURUSD-OTC", timeframe: "1m", action: "CALL", stake: 1 })
      .expect(404);
  });

  it("only allows the configured frontend origins and GET requests", async () => {
    const app = appWithoutIq();

    const allowed = await request(app)
      .get("/api/v1/health")
      .set("Origin", "http://localhost:5173")
      .expect(200);
    expect(allowed.headers["access-control-allow-origin"]).toBe("http://localhost:5173");

    const other = await request(app)
      .get("/api/v1/health")
      .set("Origin", "http://evil.example")
      .expect(200);
    expect(other.headers["access-control-allow-origin"]).toBeUndefined();
  });

  it("reports gateway status without credentials or account data", async () => {
    const response = await request(appWithoutIq()).get("/api/v1/iq-option/demo/status").expect(200);
    const text = JSON.stringify(response.body);

    expect(response.body.data.gateway.workerState).toBe("STOPPED");
    expect(text).not.toMatch(/password|email|ssid|token/i);
  });

  it("validates live requests before touching IQ Option", async () => {
    const app = appWithoutIq();

    await request(app).get("/api/v1/iq-option/demo/live?symbol=BTCUSD&timeframe=1m").expect(400);
    await request(app).get("/api/v1/iq-option/demo/live?symbol=EURUSD-OTC&timeframe=15m").expect(400);
    const unsupported = await request(app)
      .get("/api/v1/iq-option/demo/live?symbol=EURUSD-OTC&timeframe=5m")
      .expect(422);
    expect(unsupported.body.error.code).toBe("STRATEGY_NOT_AVAILABLE_FOR_SYMBOL");
  });
});
