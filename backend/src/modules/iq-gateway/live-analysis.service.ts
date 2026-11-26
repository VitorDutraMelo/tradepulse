import { appendFile, mkdir } from "node:fs/promises";
import path from "node:path";

import { GatewayError, type GatewayResponse, type GatewayWorker } from "./gateway-worker";
import { silentLogger, type Logger } from "./logger";
import {
  strategyForTimeframe,
  type ExtractedAnalysis,
  type StrategyDefinition,
} from "./strategies";
import {
  candleId,
  iso,
  latestExpectedCloseMs,
  nextBoundaryMs,
  parseIso,
  timeframeMs,
  type GatewayTimeframe,
} from "./timeframes";

/**
 * Candle-close driven analysis publisher (blocks A.1/A.2).
 *
 * For every active subscription (symbol + timeframe + strategy) the service
 * fires at each candle boundary, asks the gateway for the analysis and keeps
 * retrying with a short, growing interval until the just-closed candle is
 * actually available. There is no fixed waiting delay. The newest result is
 * published once per candle; freshness and signal validity are recomputed
 * at every read, so an old analysis is never presented as current.
 */

export type DataState = "CURRENT" | "AWAITING_NEW_CANDLE" | "STALE" | "NO_DATA";

export type SignalStatus =
  | "WAIT"
  | "EXPERIMENTAL_CANDIDATE"
  | "LATE_NOT_ACTIONABLE"
  | "EXPIRED"
  | "NOT_CURRENT";

export type Publication = {
  strategyId: string;
  strategyVersion: string;
  symbol: string;
  timeframe: GatewayTimeframe;
  candleId: string;
  candleOpenMs: number;
  candleCloseMs: number;
  scheduledForMs: number;
  attempts: number;
  publishedAtMs: number;
  extracted: ExtractedAnalysis;
  payload: Record<string, unknown>;
  timing: Record<string, unknown>;
  observedQuote: Record<string, unknown> | null;
};

type CycleState = {
  expectedCloseMs: number;
  promise: Promise<void>;
  abort: AbortController;
  attempts: number;
  lastAttemptAtMs: number | null;
};

type Subscription = {
  key: string;
  symbol: string;
  timeframe: GatewayTimeframe;
  strategy: StrategyDefinition;
  lastReadAtMs: number;
  timer: NodeJS.Timeout | null;
  latest: Publication | null;
  cycle: CycleState | null;
  /** Close of the newest candle a cycle was started for (one cycle per candle). */
  lastCycleCloseMs: number | null;
  lastError: { code: string; message: string; atMs: number; retryAt: string | null } | null;
};

export type LiveAnalysisOptions = {
  toleranceMs?: Partial<Record<GatewayTimeframe, number>>;
  retryScheduleMs?: readonly number[];
  maxSubscriptions?: number;
  subscriptionTtlMs?: number;
  publicationLogPath?: string | null;
  now?: () => number;
  logger?: Logger;
};

const DEFAULT_RETRY_SCHEDULE_MS = [500, 1000, 1000, 2000, 3000, 5000] as const;
const NON_RETRYABLE_CODES = new Set([
  "IQ_OPTION_CREDENTIALS_MISSING",
  "IQ_OPTION_PRACTICE_NOT_CONFIRMED",
  "INVALID_GATEWAY_REQUEST",
  "IQ_OPTION_DATA_NOT_FOUND",
  "GATEWAY_STOPPED",
]);

export class StrategyUnavailableError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "StrategyUnavailableError";
  }
}

export class LiveAnalysisService {
  private readonly subscriptions = new Map<string, Subscription>();
  private readonly toleranceMs: Record<GatewayTimeframe, number>;
  private readonly retryScheduleMs: readonly number[];
  private readonly maxSubscriptions: number;
  private readonly subscriptionTtlMs: number;
  private readonly publicationLogPath: string | null;
  private readonly now: () => number;
  private readonly log: Logger;
  private stopped = false;
  private clockOffsetMs = 0;
  private publications = 0;

  constructor(
    private readonly gateway: GatewayWorker,
    options: LiveAnalysisOptions = {},
  ) {
    this.toleranceMs = {
      "1m": 10_000,
      "5m": 30_000,
      "15m": 60_000,
      "1h": 120_000,
      ...options.toleranceMs,
    };
    this.retryScheduleMs = options.retryScheduleMs ?? DEFAULT_RETRY_SCHEDULE_MS;
    this.maxSubscriptions = options.maxSubscriptions ?? 8;
    this.subscriptionTtlMs = options.subscriptionTtlMs ?? 600_000;
    this.publicationLogPath = options.publicationLogPath ?? null;
    this.now = options.now ?? Date.now;
    this.log = options.logger ?? silentLogger;
  }

  /** Current time aligned with the IQ server clock when the session knows it. */
  private sourceNow(): number {
    return this.now() + this.clockOffsetMs;
  }

  resolveStrategy(symbol: string, timeframe: GatewayTimeframe): StrategyDefinition {
    const strategy = strategyForTimeframe(timeframe);

    if (!strategy) {
      throw new StrategyUnavailableError(
        "STRATEGY_NOT_AVAILABLE_FOR_TIMEFRAME",
        `No TradePulse strategy is configured for ${timeframe}.`,
      );
    }

    if (!strategy.symbols.includes(symbol)) {
      throw new StrategyUnavailableError(
        "STRATEGY_NOT_AVAILABLE_FOR_SYMBOL",
        `${strategy.label} is only available for ${strategy.symbols.join(", ")}.`,
      );
    }

    return strategy;
  }

  /**
   * Return the live view for a symbol/timeframe. Subscribes on first read.
   * With ``waitMs`` the call waits (bounded) for the analysis of the newest
   * closed candle when a cycle is running.
   */
  async getLive(
    symbol: string,
    timeframe: GatewayTimeframe,
    options: { waitMs?: number } = {},
  ): Promise<Record<string, unknown>> {
    const subscription = this.subscribe(symbol, timeframe);
    const expected = latestExpectedCloseMs(this.sourceNow(), timeframe);

    if (
      (subscription.latest === null || subscription.latest.candleCloseMs < expected) &&
      subscription.cycle === null &&
      subscription.lastCycleCloseMs !== expected &&
      !this.stopped
    ) {
      this.startCycle(subscription, expected);
    }

    if (options.waitMs && subscription.cycle) {
      await Promise.race([
        subscription.cycle.promise,
        new Promise((resolve) => setTimeout(resolve, options.waitMs)),
      ]);
    }

    return this.view(subscription);
  }

  status(): Record<string, unknown> {
    return {
      gateway: this.gateway.status(),
      clockOffsetMs: this.clockOffsetMs,
      publications: this.publications,
      subscriptions: [...this.subscriptions.values()].map((subscription) => ({
        symbol: subscription.symbol,
        timeframe: subscription.timeframe,
        strategyId: subscription.strategy.id,
        latestCandleId: subscription.latest?.candleId ?? null,
        cycleRunning: subscription.cycle !== null,
        lastErrorCode: subscription.lastError?.code ?? null,
      })),
    };
  }

  stop(): void {
    this.stopped = true;

    for (const subscription of this.subscriptions.values()) {
      if (subscription.timer) {
        clearTimeout(subscription.timer);
      }

      subscription.cycle?.abort.abort();
    }

    this.subscriptions.clear();
  }

  // ---------------------------------------------------------------- scheduling

  private subscribe(symbol: string, timeframe: GatewayTimeframe): Subscription {
    const strategy = this.resolveStrategy(symbol, timeframe);
    const key = `${strategy.id}:${symbol}:${timeframe}`;
    let subscription = this.subscriptions.get(key);

    if (!subscription) {
      this.expireIdleSubscriptions();

      if (this.subscriptions.size >= this.maxSubscriptions) {
        throw new StrategyUnavailableError(
          "LIVE_SUBSCRIPTION_LIMIT",
          `At most ${this.maxSubscriptions} live symbol/timeframe pairs can be followed.`,
        );
      }

      subscription = {
        key,
        symbol,
        timeframe,
        strategy,
        lastReadAtMs: this.now(),
        timer: null,
        latest: null,
        cycle: null,
        lastCycleCloseMs: null,
        lastError: null,
      };
      this.subscriptions.set(key, subscription);
      this.log("info", "live_subscription_started", { key });
      this.scheduleNext(subscription);
    }

    subscription.lastReadAtMs = this.now();
    return subscription;
  }

  private expireIdleSubscriptions(): void {
    for (const subscription of [...this.subscriptions.values()]) {
      if (this.now() - subscription.lastReadAtMs > this.subscriptionTtlMs) {
        this.unsubscribe(subscription);
      }
    }
  }

  private unsubscribe(subscription: Subscription): void {
    if (subscription.timer) {
      clearTimeout(subscription.timer);
    }

    subscription.cycle?.abort.abort();
    this.subscriptions.delete(subscription.key);
    this.log("info", "live_subscription_expired", { key: subscription.key });
  }

  private scheduleNext(subscription: Subscription): void {
    if (this.stopped) {
      return;
    }

    const boundary = nextBoundaryMs(this.sourceNow(), subscription.timeframe);
    const delay = Math.max(0, boundary - this.sourceNow());

    subscription.timer = setTimeout(() => {
      subscription.timer = null;

      if (this.now() - subscription.lastReadAtMs > this.subscriptionTtlMs) {
        this.unsubscribe(subscription);
        return;
      }

      if (subscription.cycle) {
        // The previous candle never arrived: it is obsolete now.
        subscription.cycle.abort.abort();
        subscription.cycle = null;
      }

      this.startCycle(subscription, boundary);
      this.scheduleNext(subscription);
    }, delay);
  }

  private startCycle(subscription: Subscription, expectedCloseMs: number): void {
    const abort = new AbortController();
    const cycle: CycleState = {
      expectedCloseMs,
      abort,
      attempts: 0,
      lastAttemptAtMs: null,
      promise: Promise.resolve(),
    };

    cycle.promise = this.runCycle(subscription, cycle).finally(() => {
      if (subscription.cycle === cycle) {
        subscription.cycle = null;
      }
    });
    subscription.cycle = cycle;
    subscription.lastCycleCloseMs = expectedCloseMs;
  }

  private async runCycle(subscription: Subscription, cycle: CycleState): Promise<void> {
    const deadline = cycle.expectedCloseMs + timeframeMs(subscription.timeframe);

    while (!cycle.abort.signal.aborted && !this.stopped) {
      if (subscription.latest && subscription.latest.candleCloseMs >= cycle.expectedCloseMs) {
        return; // already published for this candle: never analyse it twice
      }

      cycle.attempts += 1;
      cycle.lastAttemptAtMs = this.now();
      let waitHintMs: number | null = null;

      try {
        const response = await this.gateway.request<unknown>(
          subscription.strategy.command,
          subscription.strategy.args(subscription.symbol),
          { key: subscription.key, signal: cycle.abort.signal },
        );

        this.updateClockOffset(response);
        const payload = subscription.strategy.parse(response.result);
        const extracted = subscription.strategy.extract(payload);
        subscription.lastError = null;

        if (extracted.candleCloseMs >= cycle.expectedCloseMs) {
          this.publish(subscription, cycle, payload, extracted, response);
          return;
        }

        // Source has not published the closed candle yet: controlled retry.
        if (subscription.latest === null) {
          this.publish(subscription, cycle, payload, extracted, response);
        }
      } catch (error) {
        if (cycle.abort.signal.aborted) {
          return;
        }

        const code =
          error instanceof GatewayError
            ? error.code
            : error instanceof Error && error.name === "ZodError"
              ? "ENGINE_PAYLOAD_INVALID"
              : "LIVE_ANALYSIS_FAILED";
        const retryAt = error instanceof GatewayError ? error.retryAt : null;
        subscription.lastError = {
          code,
          message: error instanceof Error ? error.message : String(error),
          atMs: this.now(),
          retryAt,
        };
        this.log("warn", "live_analysis_attempt_failed", {
          key: subscription.key,
          code,
          attempt: cycle.attempts,
        });

        if (NON_RETRYABLE_CODES.has(code)) {
          return;
        }

        const retryAtMs = parseIso(retryAt);
        if (retryAtMs !== null) {
          waitHintMs = Math.max(0, retryAtMs - this.now());
        }
      }

      const scheduleIndex = Math.min(cycle.attempts - 1, this.retryScheduleMs.length - 1);
      const delay = Math.max(this.retryScheduleMs[scheduleIndex], waitHintMs ?? 0);

      if (this.sourceNow() + delay >= deadline) {
        this.log("warn", "live_candle_not_published", {
          key: subscription.key,
          expectedClose: iso(cycle.expectedCloseMs),
          attempts: cycle.attempts,
        });
        return;
      }

      await new Promise<void>((resolve) => {
        const timer = setTimeout(resolve, delay);
        cycle.abort.signal.addEventListener(
          "abort",
          () => {
            clearTimeout(timer);
            resolve();
          },
          { once: true },
        );
      });
    }
  }

  private updateClockOffset(response: GatewayResponse): void {
    const offset = response.meta.session?.serverClockOffsetMs;

    if (typeof offset === "number" && Number.isFinite(offset) && Math.abs(offset) < 60_000) {
      this.clockOffsetMs = offset;
    }
  }

  // --------------------------------------------------------------- publication

  private publish(
    subscription: Subscription,
    cycle: CycleState,
    payload: Record<string, unknown>,
    extracted: ExtractedAnalysis,
    response: GatewayResponse,
  ): void {
    const publishedAtMs = this.now();
    const fetches = response.meta.fetches ?? [];
    const mainFetch =
      fetches.find((fetch) => fetch.timeframe === subscription.timeframe) ?? fetches[0] ?? null;
    const receivedAtMs = parseIso(mainFetch?.receivedAt);
    const requestedAtMs = parseIso(mainFetch?.requestedAt);
    const analysisStartedMs = parseIso(response.meta.analysisStartedAt);
    const analysisCompletedMs = parseIso(response.meta.analysisCompletedAt);

    const timing = {
      clock: "LOCAL_UTC_CLOCK",
      serverClockOffsetMs: this.clockOffsetMs,
      candleOpenTime: iso(extracted.candleOpenMs),
      candleCloseTime: iso(extracted.candleCloseMs),
      candleCloseTimeKind: "DERIVED_OPEN_PLUS_INTERVAL",
      scheduledFor: iso(cycle.expectedCloseMs),
      dataRequestedAt: iso(requestedAtMs),
      dataReceivedAt: iso(receivedAtMs),
      dataReceivedAtKind: receivedAtMs === null ? "NOT_AVAILABLE" : "OBSERVED_LOCAL_CLOCK",
      analysisStartedAt: iso(analysisStartedMs),
      analysisCompletedAt: iso(analysisCompletedMs),
      publishedAt: iso(publishedAtMs),
      collectionLatencyMs:
        typeof mainFetch?.collectionDurationMs === "number" ? mainFetch.collectionDurationMs : null,
      cacheHit: typeof mainFetch?.cacheHit === "boolean" ? mainFetch.cacheHit : null,
      processingLatencyMs:
        analysisStartedMs !== null && analysisCompletedMs !== null
          ? analysisCompletedMs - analysisStartedMs
          : null,
      gatewayRoundTripMs: response.respondedAt - response.dispatchedAt,
      totalLatencyFromCloseMs: publishedAtMs - extracted.candleCloseMs,
      attempts: cycle.attempts,
      iqCandleAvailabilityAt: null,
      iqCandleAvailabilityKind: "NOT_AVAILABLE_FROM_IQ_OPTION_API",
    };

    const publication: Publication = {
      strategyId: subscription.strategy.id,
      strategyVersion: subscription.strategy.version,
      symbol: subscription.symbol,
      timeframe: subscription.timeframe,
      candleId: candleId(subscription.symbol, subscription.timeframe, extracted.candleOpenMs),
      candleOpenMs: extracted.candleOpenMs,
      candleCloseMs: extracted.candleCloseMs,
      scheduledForMs: cycle.expectedCloseMs,
      attempts: cycle.attempts,
      publishedAtMs,
      extracted,
      payload,
      timing,
      observedQuote:
        mainFetch && typeof mainFetch.observedQuote === "object"
          ? (mainFetch.observedQuote as Record<string, unknown>)
          : null,
    };

    subscription.latest = publication;
    this.publications += 1;
    this.log("info", "live_analysis_published", {
      key: subscription.key,
      candleId: publication.candleId,
      action: extracted.action,
      totalLatencyFromCloseMs: timing.totalLatencyFromCloseMs,
      attempts: cycle.attempts,
    });
    void this.appendPublicationLog(publication);
  }

  private async appendPublicationLog(publication: Publication): Promise<void> {
    if (!this.publicationLogPath) {
      return;
    }

    const record = {
      candleId: publication.candleId,
      strategyId: publication.strategyId,
      strategyVersion: publication.strategyVersion,
      symbol: publication.symbol,
      timeframe: publication.timeframe,
      action: publication.extracted.action,
      engineAction: publication.extracted.engineAction,
      timing: publication.timing,
      observedQuote: publication.observedQuote,
      experimental: true,
    };

    try {
      await mkdir(path.dirname(this.publicationLogPath), { recursive: true });
      await appendFile(this.publicationLogPath, `${JSON.stringify(record)}\n`, "utf8");
    } catch (error) {
      this.log("warn", "publication_log_write_failed", {
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  // ---------------------------------------------------------------------- view

  private view(subscription: Subscription): Record<string, unknown> {
    const nowMs = this.now();
    const sourceNowMs = this.sourceNow();
    const expected = latestExpectedCloseMs(sourceNowMs, subscription.timeframe);
    const interval = timeframeMs(subscription.timeframe);
    const latest = subscription.latest;

    let dataState: DataState;

    if (latest === null) {
      dataState = "NO_DATA";
    } else if (latest.candleCloseMs >= expected) {
      dataState = "CURRENT";
    } else if (latest.candleCloseMs === expected - interval) {
      dataState = "AWAITING_NEW_CANDLE";
    } else {
      dataState = "STALE";
    }

    return {
      strategy: {
        id: subscription.strategy.id,
        version: subscription.strategy.version,
        label: subscription.strategy.label,
        timeframe: subscription.strategy.timeframe,
        experimentalEngine: subscription.strategy.experimentalEngine,
        methodology: "PROVISIONAL_NOT_APPROVED",
        operational: false,
      },
      symbol: subscription.symbol,
      timeframe: subscription.timeframe,
      observedAt: iso(nowMs),
      expectedLatestCloseTime: iso(expected),
      nextCloseTime: iso(expected + interval),
      dataState,
      cycle: {
        running: subscription.cycle !== null,
        forCandleClose: iso(subscription.cycle?.expectedCloseMs),
        attempts: subscription.cycle?.attempts ?? 0,
        lastAttemptAt: iso(subscription.cycle?.lastAttemptAtMs),
      },
      lastError: subscription.lastError
        ? {
            code: subscription.lastError.code,
            message: subscription.lastError.message,
            at: iso(subscription.lastError.atMs),
            retryAt: subscription.lastError.retryAt,
          }
        : null,
      publication: latest ? this.publicationView(latest, dataState, nowMs) : null,
      gateway: this.gatewaySummary(),
    };
  }

  private publicationView(
    publication: Publication,
    dataState: DataState,
    nowMs: number,
  ): Record<string, unknown> {
    const { extracted } = publication;
    const toleranceMs = this.toleranceMs[publication.timeframe];
    const delayMs = publication.publishedAtMs - publication.candleCloseMs;
    const timeliness = delayMs <= toleranceMs ? "ON_TIME" : "LATE";
    let status: SignalStatus;

    if (dataState !== "CURRENT") {
      status = "NOT_CURRENT";
    } else if (extracted.action === "WAIT") {
      status = "WAIT";
    } else if (extracted.expirationMs !== null && nowMs >= extracted.expirationMs) {
      status = "EXPIRED";
    } else if (timeliness === "LATE") {
      status = "LATE_NOT_ACTIONABLE";
    } else {
      status = "EXPERIMENTAL_CANDIDATE";
    }

    const analysis = { ...publication.payload };

    // The engine's own "state" was computed when the analysis ran. Recompute
    // it now so a previous candle can never be served as UPDATED.
    if (typeof analysis.state === "string") {
      analysis.state =
        dataState === "CURRENT"
          ? "UPDATED"
          : dataState === "AWAITING_NEW_CANDLE"
            ? "AWAITING_CONFIRMATION"
            : "STALE";
    }

    return {
      candleId: publication.candleId,
      candleOpenTime: iso(publication.candleOpenMs),
      candleCloseTime: iso(publication.candleCloseMs),
      publishedAt: iso(publication.publishedAtMs),
      timing: publication.timing,
      signal: {
        action: extracted.action,
        engineAction: extracted.engineAction,
        status,
        operational: false,
        timeliness,
        publicationDelayMs: delayMs,
        toleranceMs,
        toleranceKind: "PROVISIONAL_EXPERIMENTAL",
        theoreticalEntryTime: iso(extracted.entryMs),
        theoreticalEntryKind: "REFERENCE_CANDLE_CLOSE",
        theoreticalExpirationTime: iso(extracted.expirationMs),
        theoreticalReferencePrice: extracted.referencePrice,
        theoreticalReferencePriceKind: "REFERENCE_CANDLE_CLOSE",
        observedQuoteAtPublication: publication.observedQuote,
        reasons: extracted.reasons,
      },
      analysis,
    };
  }

  private gatewaySummary(): Record<string, unknown> {
    const status = this.gateway.status();
    const session = status.session ?? {};

    return {
      workerState: status.workerState,
      sessionState: typeof session.state === "string" ? session.state : null,
      accountMode: session.accountMode ?? null,
      lastErrorCode: status.lastErrorCode ?? session.lastErrorCode ?? null,
      nextReconnectAt: session.nextReconnectAt ?? status.nextRestartAt ?? null,
    };
  }
}
