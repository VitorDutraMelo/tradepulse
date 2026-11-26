import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GatewayError, GatewayWorker, type WorkerProcess } from "./gateway-worker";
import type { LogLevel } from "./logger";

type Handler = (message: { id: string; cmd: string; args: Record<string, unknown> }) =>
  | { ok: true; result: unknown; meta?: Record<string, unknown> }
  | { ok: false; error: Record<string, unknown> }
  | "hang";

class FakeWorkerProcess implements WorkerProcess {
  static nextPid = 100;
  readonly pid = FakeWorkerProcess.nextPid++;
  readonly written: Array<{ id: string; cmd: string; args: Record<string, unknown> }> = [];
  killed = false;
  private lineListeners: Array<(line: string) => void> = [];
  private stderrListeners: Array<(line: string) => void> = [];
  private exitListeners: Array<(code: number | null) => void> = [];

  constructor(private readonly handler: Handler) {
    queueMicrotask(() => this.emit({ type: "ready", protocolVersion: 1, pid: this.pid }));
  }

  write(line: string): void {
    const message = JSON.parse(line);
    this.written.push(message);

    if (message.cmd === "shutdown") {
      queueMicrotask(() => this.exit(0));
      return;
    }

    const outcome = this.handler(message);

    if (outcome === "hang") {
      return;
    }

    setTimeout(() => this.emit({ type: "response", id: message.id, ...outcome }), 5);
  }

  onLine(listener: (line: string) => void): void {
    this.lineListeners.push(listener);
  }

  onStderrLine(listener: (line: string) => void): void {
    this.stderrListeners.push(listener);
  }

  onExit(listener: (code: number | null) => void): void {
    this.exitListeners.push(listener);
  }

  kill(): void {
    this.killed = true;
    queueMicrotask(() => this.exit(null));
  }

  emit(message: Record<string, unknown>): void {
    for (const listener of this.lineListeners) listener(JSON.stringify(message));
  }

  emitRaw(line: string): void {
    for (const listener of this.lineListeners) listener(line);
  }

  emitStderr(line: string): void {
    for (const listener of this.stderrListeners) listener(line);
  }

  exit(code: number | null): void {
    const listeners = this.exitListeners.splice(0);
    for (const listener of listeners) listener(code);
  }
}

const ok = (result: unknown = { fine: true }) => ({
  ok: true as const,
  result,
  meta: { session: { state: "CONNECTED", accountMode: "PRACTICE" } },
});

function setup(handler: Handler = () => ok(), options: { maxQueue?: number; timeoutMs?: number } = {}) {
  const processes: FakeWorkerProcess[] = [];
  const logs: Array<{ level: LogLevel; event: string; data?: Record<string, unknown> }> = [];
  const worker = new GatewayWorker({
    spawnWorker: () => {
      const process = new FakeWorkerProcess(handler);
      processes.push(process);
      return process;
    },
    maxQueue: options.maxQueue ?? 4,
    requestTimeoutMs: options.timeoutMs ?? 1000,
    restartBackoffMaxMs: 4000,
    logger: (level, event, data) => logs.push({ level, event, data }),
  });

  return { worker, processes, logs };
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
  vi.setSystemTime(new Date("2026-11-26T12:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("GatewayWorker", () => {
  it("reuses one worker process (one IQ session) for many requests", async () => {
    const { worker, processes } = setup();

    for (let index = 0; index < 5; index += 1) {
      const pending = worker.request("candles", { symbol: "EURUSD-OTC", index });
      await vi.advanceTimersByTimeAsync(10);
      await expect(pending).resolves.toMatchObject({ result: { fine: true } });
    }

    expect(processes).toHaveLength(1);
    expect(worker.status().workerStarts).toBe(1);
    expect(worker.status().session).toMatchObject({ accountMode: "PRACTICE" });
  });

  it("shares one job between concurrent requests with the same key", async () => {
    const { worker, processes } = setup();

    const first = worker.request("analyze_m1", { symbol: "EURUSD-OTC" }, { key: "m1:EURUSD" });
    const second = worker.request("analyze_m1", { symbol: "EURUSD-OTC" }, { key: "m1:EURUSD" });
    await vi.advanceTimersByTimeAsync(20);

    await expect(first).resolves.toBeDefined();
    await expect(second).resolves.toBeDefined();
    expect(processes[0].written.filter((message) => message.cmd === "analyze_m1")).toHaveLength(1);
    expect(worker.status().requests.deduplicated).toBe(1);
  });

  it("never sends two requests to the session at the same time", async () => {
    let concurrent = 0;
    let maxConcurrent = 0;
    const processes: FakeWorkerProcess[] = [];
    const worker = new GatewayWorker({
      spawnWorker: () => {
        const process = new FakeWorkerProcess(() => {
          concurrent += 1;
          maxConcurrent = Math.max(maxConcurrent, concurrent);
          setTimeout(() => (concurrent -= 1), 5);
          return ok();
        });
        processes.push(process);
        return process;
      },
    });

    const requests = [1, 2, 3].map((index) => worker.request("candles", { index }));
    await vi.advanceTimersByTimeAsync(100);
    await Promise.all(requests);

    expect(maxConcurrent).toBe(1);
  });

  it("rejects requests beyond the queue limit", async () => {
    const { worker } = setup(() => "hang", { maxQueue: 2 });

    const inFlight = worker.request("candles", { n: 0 });
    inFlight.catch(() => undefined);
    await vi.advanceTimersByTimeAsync(1);
    const queued = [worker.request("candles", { n: 1 }), worker.request("candles", { n: 2 })];
    queued.forEach((request) => request.catch(() => undefined));

    await expect(worker.request("candles", { n: 3 })).rejects.toMatchObject({
      code: "GATEWAY_QUEUE_FULL",
    });
    expect(worker.status().requests.rejectedQueueFull).toBe(1);
  });

  it("drops a cancelled request before it reaches IQ Option", async () => {
    const { worker, processes } = setup((message) => (message.args.n === 0 ? "hang" : ok()));

    const blocking = worker.request("candles", { n: 0 });
    blocking.catch(() => undefined);
    await vi.advanceTimersByTimeAsync(1);

    const controller = new AbortController();
    const obsolete = worker.request("candles", { n: 1 }, { signal: controller.signal });
    controller.abort();

    await expect(obsolete).rejects.toMatchObject({ code: "GATEWAY_REQUEST_CANCELLED" });
    expect(worker.status().queue.pending).toBe(0);
    expect(processes[0].written.some((message) => message.args.n === 1)).toBe(false);
  });

  it("times out, replaces a stuck worker and restarts with backoff", async () => {
    let hang = true;
    const { worker, processes } = setup(() => (hang ? "hang" : ok()), { timeoutMs: 500 });

    const stuck = worker.request("analyze_m5", {});
    stuck.catch(() => undefined);
    await vi.advanceTimersByTimeAsync(600);

    await expect(stuck).rejects.toMatchObject({ code: "IQ_OPTION_TIMEOUT" });
    expect(processes[0].killed).toBe(true);
    expect(worker.status().requests.timedOut).toBe(1);

    hang = false;
    await expect(worker.request("candles", {})).rejects.toMatchObject({
      code: "GATEWAY_RESTART_BACKOFF",
    });

    await vi.advanceTimersByTimeAsync(1100);
    const recovered = worker.request("candles", {});
    await vi.advanceTimersByTimeAsync(20);
    await expect(recovered).resolves.toBeDefined();
    expect(processes).toHaveLength(2);
    expect(worker.status().workerCrashes).toBe(1);
  });

  it("maps worker errors to GatewayError with code and retryAt", async () => {
    const { worker } = setup(() => ({
      ok: false,
      error: {
        code: "IQ_OPTION_RECONNECT_BACKOFF",
        message: "waiting",
        retryAt: "2026-11-26T12:00:04+00:00",
      },
    }));

    const failure = worker.request("candles", {}).catch((reason) => reason);
    await vi.advanceTimersByTimeAsync(10);

    const error = await failure;
    expect(error).toBeInstanceOf(GatewayError);
    expect(error).toMatchObject({
      code: "IQ_OPTION_RECONNECT_BACKOFF",
      retryAt: "2026-11-26T12:00:04+00:00",
    });
    expect(worker.status().lastErrorCode).toBe("IQ_OPTION_RECONNECT_BACKOFF");
  });

  it("fails the in-flight request when the worker crashes", async () => {
    const { worker, processes } = setup(() => "hang");

    const request = worker.request("candles", {});
    request.catch(() => undefined);
    await vi.advanceTimersByTimeAsync(1);
    processes[0].exit(1);

    await expect(request).rejects.toMatchObject({ code: "GATEWAY_WORKER_EXITED" });
  });

  it("ignores protocol noise and redacts stderr before logging", async () => {
    const { worker, processes, logs } = setup();
    const request = worker.request("candles", {});
    await vi.advanceTimersByTimeAsync(1);

    processes[0].emitRaw("Asset XYZ not found on consts");
    processes[0].emitStderr("login failed for someone@example.com password=hunter2");
    await vi.advanceTimersByTimeAsync(10);

    await expect(request).resolves.toBeDefined();
    const serialized = JSON.stringify(logs);
    expect(serialized).not.toContain("someone@example.com");
    expect(serialized).not.toContain("hunter2");
  });

  it("shuts down the worker and refuses new requests", async () => {
    const { worker, processes } = setup();
    const request = worker.request("candles", {});
    await vi.advanceTimersByTimeAsync(10);
    await request;

    const stopping = worker.shutdown();
    await vi.advanceTimersByTimeAsync(10);
    await stopping;

    expect(processes[0].written.at(-1)?.cmd).toBe("shutdown");
    await expect(worker.request("candles", {})).rejects.toMatchObject({ code: "GATEWAY_STOPPED" });
  });
});
