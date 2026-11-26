import { spawn } from "node:child_process";
import { createInterface } from "node:readline";

import { QuantEngineClientError } from "../market-analysis/python-quant-engine.client";
import { redactText, silentLogger, type Logger } from "./logger";

/**
 * Error raised by the gateway. It extends QuantEngineClientError so existing
 * routers keep mapping it to "IQ Option unavailable" responses.
 */
export class GatewayError extends QuantEngineClientError {
  constructor(
    public readonly code: string,
    message: string,
    public readonly retryAt: string | null = null,
  ) {
    super(message);
    this.name = "GatewayError";
  }
}

export type GatewayCommand =
  | "status"
  | "candles"
  | "analyze_m1"
  | "analyze_m5"
  | "m5_sync"
  | "shutdown";

export type WorkerMeta = {
  analysisStartedAt?: string;
  analysisCompletedAt?: string;
  workerDurationMs?: number;
  fetches?: Array<Record<string, unknown>>;
  session?: Record<string, unknown>;
  cache?: { hits: number; misses: number };
};

export type GatewayResponse<T = unknown> = {
  result: T;
  meta: WorkerMeta;
  dispatchedAt: number;
  respondedAt: number;
};

/** Minimal process contract so tests can replace the real Python worker. */
export interface WorkerProcess {
  readonly pid: number | undefined;
  write(line: string): void;
  onLine(listener: (line: string) => void): void;
  onStderrLine(listener: (line: string) => void): void;
  onExit(listener: (code: number | null) => void): void;
  kill(): void;
}

export type WorkerSpawner = () => WorkerProcess;

export function createPythonWorkerSpawner(options: {
  pythonExecutable: string;
  workingDirectory: string;
  env?: NodeJS.ProcessEnv;
}): WorkerSpawner {
  return () => {
    const child = spawn(
      options.pythonExecutable,
      ["-u", "-m", "app.gateway.worker"],
      {
        cwd: options.workingDirectory,
        env: { ...(options.env ?? process.env), PYTHONUNBUFFERED: "1" },
        stdio: ["pipe", "pipe", "pipe"],
        windowsHide: true,
      },
    );

    const stdout = createInterface({ input: child.stdout });
    const stderr = createInterface({ input: child.stderr });

    return {
      pid: child.pid,
      write: (line) => {
        child.stdin.write(line);
      },
      onLine: (listener) => stdout.on("line", listener),
      onStderrLine: (listener) => stderr.on("line", listener),
      onExit: (listener) => {
        child.on("exit", listener);
        child.on("error", () => listener(null));
      },
      kill: () => {
        child.kill();
      },
    };
  };
}

type Job = {
  id: string;
  key: string | null;
  command: GatewayCommand;
  args: Record<string, unknown>;
  timeoutMs: number;
  waiters: Array<{
    resolve: (value: GatewayResponse) => void;
    reject: (error: Error) => void;
    signal?: AbortSignal;
    onAbort?: () => void;
  }>;
  dispatchedAt?: number;
  timer?: NodeJS.Timeout;
};

export type GatewayWorkerOptions = {
  spawnWorker: WorkerSpawner;
  requestTimeoutMs?: number;
  maxQueue?: number;
  restartBackoffMaxMs?: number;
  now?: () => number;
  logger?: Logger;
};

export type GatewayWorkerStatus = {
  workerState: "STOPPED" | "STARTING" | "READY" | "RESTART_BACKOFF";
  workerPid: number | null;
  workerStarts: number;
  workerCrashes: number;
  queue: { pending: number; max: number; inFlight: boolean };
  requests: {
    total: number;
    failed: number;
    deduplicated: number;
    cancelled: number;
    rejectedQueueFull: number;
    timedOut: number;
  };
  lastErrorCode: string | null;
  session: Record<string, unknown> | null;
  nextRestartAt: string | null;
};

/**
 * Owns the single Python gateway worker.
 *
 * - One request is in flight at a time (the worker holds one IQ session).
 * - Requests with the same key share one job (no duplicate IQ reads).
 * - The queue is bounded; overflow fails fast with GATEWAY_QUEUE_FULL.
 * - A caller can abort while queued; the job is dropped when nobody waits.
 * - A request that exceeds its timeout kills the worker (the library may be
 *   stuck); the next request restarts it after a progressive backoff.
 */
export class GatewayWorker {
  private process: WorkerProcess | null = null;
  private ready: Promise<void> | null = null;
  private queue: Job[] = [];
  private inFlight: Job | null = null;
  private nextId = 1;
  private restartFailures = 0;
  private restartNotBefore = 0;
  private stopping = false;

  private readonly spawnWorker: WorkerSpawner;
  private readonly requestTimeoutMs: number;
  private readonly maxQueue: number;
  private readonly restartBackoffMaxMs: number;
  private readonly now: () => number;
  private readonly log: Logger;

  private readonly stats = {
    workerStarts: 0,
    workerCrashes: 0,
    total: 0,
    failed: 0,
    deduplicated: 0,
    cancelled: 0,
    rejectedQueueFull: 0,
    timedOut: 0,
  };

  private lastErrorCode: string | null = null;
  private lastSession: Record<string, unknown> | null = null;

  constructor(options: GatewayWorkerOptions) {
    this.spawnWorker = options.spawnWorker;
    this.requestTimeoutMs = options.requestTimeoutMs ?? 45_000;
    this.maxQueue = options.maxQueue ?? 16;
    this.restartBackoffMaxMs = options.restartBackoffMaxMs ?? 30_000;
    this.now = options.now ?? Date.now;
    this.log = options.logger ?? silentLogger;
  }

  request<T = unknown>(
    command: GatewayCommand,
    args: Record<string, unknown> = {},
    options: { key?: string; signal?: AbortSignal; timeoutMs?: number } = {},
  ): Promise<GatewayResponse<T>> {
    if (this.stopping) {
      return Promise.reject(new GatewayError("GATEWAY_STOPPED", "The IQ gateway is stopping."));
    }

    if (options.signal?.aborted) {
      return Promise.reject(new GatewayError("GATEWAY_REQUEST_CANCELLED", "Request cancelled."));
    }

    this.stats.total += 1;
    const key = options.key ?? null;
    const existing =
      key === null
        ? undefined
        : [this.inFlight, ...this.queue].find((job) => job !== null && job.key === key);

    return new Promise<GatewayResponse<T>>((resolve, reject) => {
      const waiter = {
        resolve: resolve as (value: GatewayResponse) => void,
        reject,
        signal: options.signal,
      } as Job["waiters"][number];

      if (existing) {
        this.stats.deduplicated += 1;
        this.attachWaiter(existing, waiter);
        return;
      }

      if (this.queue.length >= this.maxQueue) {
        this.stats.rejectedQueueFull += 1;
        this.stats.failed += 1;
        reject(
          new GatewayError(
            "GATEWAY_QUEUE_FULL",
            `The IQ gateway queue is full (${this.maxQueue} pending requests).`,
          ),
        );
        return;
      }

      const job: Job = {
        id: `r${this.nextId++}`,
        key,
        command,
        args,
        timeoutMs: options.timeoutMs ?? this.requestTimeoutMs,
        waiters: [],
      };

      this.attachWaiter(job, waiter);
      this.queue.push(job);
      void this.pump();
    });
  }

  status(): GatewayWorkerStatus {
    const workerState: GatewayWorkerStatus["workerState"] =
      this.process === null
        ? this.restartNotBefore > this.now()
          ? "RESTART_BACKOFF"
          : "STOPPED"
        : this.ready === null
          ? "READY"
          : "STARTING";

    return {
      workerState,
      workerPid: this.process?.pid ?? null,
      workerStarts: this.stats.workerStarts,
      workerCrashes: this.stats.workerCrashes,
      queue: {
        pending: this.queue.length,
        max: this.maxQueue,
        inFlight: this.inFlight !== null,
      },
      requests: {
        total: this.stats.total,
        failed: this.stats.failed,
        deduplicated: this.stats.deduplicated,
        cancelled: this.stats.cancelled,
        rejectedQueueFull: this.stats.rejectedQueueFull,
        timedOut: this.stats.timedOut,
      },
      lastErrorCode: this.lastErrorCode,
      session: this.lastSession,
      nextRestartAt:
        this.restartNotBefore > this.now() ? new Date(this.restartNotBefore).toISOString() : null,
    };
  }

  async shutdown(graceMs = 3000): Promise<void> {
    this.stopping = true;

    for (const job of this.queue.splice(0)) {
      this.failJob(job, new GatewayError("GATEWAY_STOPPED", "The IQ gateway is stopping."));
    }

    const process = this.process;

    if (process === null) {
      return;
    }

    await new Promise<void>((resolve) => {
      const timer = setTimeout(() => {
        process.kill();
        resolve();
      }, graceMs);

      process.onExit(() => {
        clearTimeout(timer);
        resolve();
      });

      try {
        process.write(`${JSON.stringify({ id: "shutdown", cmd: "shutdown", args: {} })}\n`);
      } catch {
        process.kill();
      }
    });

    this.process = null;
  }

  // ------------------------------------------------------------------ internals

  private attachWaiter(job: Job, waiter: Job["waiters"][number]): void {
    if (waiter.signal) {
      waiter.onAbort = () => this.cancelWaiter(job, waiter);
      waiter.signal.addEventListener("abort", waiter.onAbort, { once: true });
    }

    job.waiters.push(waiter);
  }

  private cancelWaiter(job: Job, waiter: Job["waiters"][number]): void {
    const index = job.waiters.indexOf(waiter);

    if (index === -1) {
      return;
    }

    job.waiters.splice(index, 1);
    this.stats.cancelled += 1;
    waiter.reject(new GatewayError("GATEWAY_REQUEST_CANCELLED", "Request cancelled."));

    // A queued job nobody waits for is obsolete: drop it before it reaches IQ.
    if (job.waiters.length === 0 && job !== this.inFlight) {
      this.queue = this.queue.filter((queued) => queued !== job);
    }
  }

  private async pump(): Promise<void> {
    if (this.inFlight !== null || this.queue.length === 0 || this.stopping) {
      return;
    }

    const job = this.queue.shift()!;
    this.inFlight = job;

    try {
      await this.ensureProcess();
    } catch (error) {
      this.inFlight = null;
      this.failJob(job, error as Error);
      void this.pump();
      return;
    }

    if (job.waiters.length === 0) {
      // Everyone cancelled while the worker was starting: obsolete request.
      this.inFlight = null;
      void this.pump();
      return;
    }

    const process = this.process!;
    job.dispatchedAt = this.now();
    job.timer = setTimeout(() => this.onTimeout(job), job.timeoutMs);

    try {
      process.write(`${JSON.stringify({ id: job.id, cmd: job.command, args: job.args })}\n`);
    } catch (error) {
      this.onProcessExit(null, error as Error);
    }
  }

  private ensureProcess(): Promise<void> {
    if (this.process !== null) {
      return this.ready ?? Promise.resolve();
    }

    const waitMs = this.restartNotBefore - this.now();

    if (waitMs > 0) {
      return Promise.reject(
        new GatewayError(
          "GATEWAY_RESTART_BACKOFF",
          "The IQ gateway worker is restarting after a failure.",
          new Date(this.restartNotBefore).toISOString(),
        ),
      );
    }

    const process = this.spawnWorker();
    this.process = process;
    this.stats.workerStarts += 1;
    this.log("info", "iq_gateway_worker_started", { pid: process.pid ?? null });

    this.ready = new Promise<void>((resolve, reject) => {
      const readyTimer = setTimeout(() => {
        reject(new GatewayError("GATEWAY_WORKER_NOT_READY", "The IQ gateway worker did not start."));
        process.kill();
      }, 15_000);

      process.onLine((line) => {
        let message: Record<string, unknown>;

        try {
          message = JSON.parse(line) as Record<string, unknown>;
        } catch {
          this.log("warn", "iq_gateway_protocol_noise", { line: redactText(line.slice(0, 200)) });
          return;
        }

        if (message.type === "ready") {
          clearTimeout(readyTimer);
          this.ready = null;
          this.restartFailures = 0;
          resolve();
          return;
        }

        this.onMessage(message);
      });

      process.onStderrLine((line) => this.onStderr(line));
      process.onExit((code) => {
        clearTimeout(readyTimer);
        reject(new GatewayError("GATEWAY_WORKER_EXITED", "The IQ gateway worker exited."));
        this.onProcessExit(code);
      });
    });

    return this.ready;
  }

  private onMessage(message: Record<string, unknown>): void {
    if (message.type === "fatal") {
      this.log("error", "iq_gateway_worker_fatal", { reason: message.reason });
      return;
    }

    if (message.type !== "response") {
      return;
    }

    const job = this.inFlight;

    if (job === null || message.id !== job.id) {
      return;
    }

    clearTimeout(job.timer);
    this.inFlight = null;

    const meta = (message.meta ?? {}) as WorkerMeta;

    if (meta.session && typeof meta.session === "object") {
      this.lastSession = meta.session;
    }

    if (message.ok === true) {
      this.lastErrorCode = null;
      const response: GatewayResponse = {
        result: message.result,
        meta,
        dispatchedAt: job.dispatchedAt ?? this.now(),
        respondedAt: this.now(),
      };

      for (const waiter of job.waiters.splice(0)) {
        this.detach(waiter);
        waiter.resolve(response);
      }
    } else {
      const error = (message.error ?? {}) as Record<string, unknown>;
      const code = typeof error.code === "string" ? error.code : "GATEWAY_INTERNAL_ERROR";
      this.failJob(
        job,
        new GatewayError(
          code,
          typeof error.message === "string" ? error.message : "The IQ gateway failed.",
          typeof error.retryAt === "string" ? error.retryAt : null,
        ),
      );
    }

    void this.pump();
  }

  private onStderr(line: string): void {
    let parsed: Record<string, unknown> | null = null;

    try {
      parsed = JSON.parse(line) as Record<string, unknown>;
    } catch {
      parsed = null;
    }

    if (parsed && parsed.type === "log") {
      const { type: _type, at: _at, event, ...rest } = parsed;
      void _type;
      void _at;
      this.log("info", `worker.${String(event)}`, rest);
    } else if (line.trim()) {
      this.log("warn", "iq_gateway_worker_stderr", { line: redactText(line.slice(0, 300)) });
    }
  }

  private onTimeout(job: Job): void {
    if (this.inFlight !== job) {
      return;
    }

    this.stats.timedOut += 1;
    this.log("error", "iq_gateway_request_timeout", {
      command: job.command,
      timeoutMs: job.timeoutMs,
    });
    this.inFlight = null;
    this.failJob(
      job,
      new GatewayError(
        "IQ_OPTION_TIMEOUT",
        `The IQ gateway did not answer within ${Math.round(job.timeoutMs / 1000)} s.`,
      ),
    );
    // The library may be stuck: replace the worker (and its session).
    this.process?.kill();
  }

  private onProcessExit(code: number | null, cause?: Error): void {
    if (this.process === null) {
      return;
    }

    this.process = null;
    this.ready = null;

    if (this.stopping) {
      return;
    }

    this.stats.workerCrashes += 1;
    this.restartFailures += 1;
    const backoff = Math.min(1000 * 2 ** (this.restartFailures - 1), this.restartBackoffMaxMs);
    this.restartNotBefore = this.now() + backoff;
    this.log("warn", "iq_gateway_worker_exited", {
      exitCode: code,
      restartInMs: backoff,
      cause: cause ? redactText(cause.message) : null,
    });

    const job = this.inFlight;

    if (job !== null) {
      clearTimeout(job.timer);
      this.inFlight = null;
      this.failJob(job, new GatewayError("GATEWAY_WORKER_EXITED", "The IQ gateway worker exited."));
    }

    // Queued jobs wait for the restart; they fail fast only if still in backoff.
    if (this.queue.length > 0) {
      setTimeout(() => void this.pump(), backoff);
    }
  }

  private failJob(job: Job, error: Error): void {
    clearTimeout(job.timer);
    this.stats.failed += 1;

    if (error instanceof GatewayError) {
      this.lastErrorCode = error.code;
    }

    for (const waiter of job.waiters.splice(0)) {
      this.detach(waiter);
      waiter.reject(error);
    }
  }

  private detach(waiter: Job["waiters"][number]): void {
    if (waiter.signal && waiter.onAbort) {
      waiter.signal.removeEventListener("abort", waiter.onAbort);
    }
  }
}
