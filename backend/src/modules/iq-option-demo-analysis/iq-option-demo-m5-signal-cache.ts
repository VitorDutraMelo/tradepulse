import type {
  QuantEngineIqOptionDemoM5SignalClient,
} from "../market-analysis/python-quant-engine.client";
import type {
  IqOptionDemoM5SignalRequest,
  IqOptionDemoM5SignalResponse,
} from "./iq-option-demo-m5-signal.schema";

type CacheEntry = {
  expiresAt: number;
  value: IqOptionDemoM5SignalResponse;
};

export type CachedIqOptionDemoM5SignalClientOptions = {
  gracePeriodMs?: number;
  minimumReuseMs?: number;
  now?: () => number;
};

/**
 * Protects the unofficial IQ Option integration.
 *
 * - One M5 analysis runs at a time for all symbols.
 * - Equal concurrent requests share one active IQ Option operation.
 * - A completed analysis is reused until the next M5 close plus grace.
 * - Failed requests are never cached.
 * - Expired data is never returned as a new analysis.
 */
export class CachedIqOptionDemoM5SignalClient
  implements QuantEngineIqOptionDemoM5SignalClient
{
  private readonly cache = new Map<string, CacheEntry>();

  private readonly inFlight = new Map<
    string,
    Promise<IqOptionDemoM5SignalResponse>
  >();

  private queueTail: Promise<void> = Promise.resolve();

  private readonly gracePeriodMs: number;
  private readonly minimumReuseMs: number;
  private readonly now: () => number;

  constructor(
    private readonly client: QuantEngineIqOptionDemoM5SignalClient,
    options: CachedIqOptionDemoM5SignalClientOptions = {},
  ) {
    this.gracePeriodMs = options.gracePeriodMs ?? 90_000;
    this.minimumReuseMs = options.minimumReuseMs ?? 30_000;
    this.now = options.now ?? Date.now;

    if (
      !Number.isFinite(this.gracePeriodMs) ||
      this.gracePeriodMs < 0
    ) {
      throw new RangeError(
        "gracePeriodMs must be a non-negative finite number",
      );
    }

    if (
      !Number.isFinite(this.minimumReuseMs) ||
      this.minimumReuseMs <= 0
    ) {
      throw new RangeError(
        "minimumReuseMs must be a positive finite number",
      );
    }
  }

  getIqOptionDemoM5Signal(
    input: IqOptionDemoM5SignalRequest,
  ): Promise<IqOptionDemoM5SignalResponse> {
    const key = input.symbol;
    const cached = this.getCached(key);

    if (cached) {
      return Promise.resolve(cached);
    }

    const activeRequest = this.inFlight.get(key);

    if (activeRequest) {
      return activeRequest;
    }

    const request = this.enqueue(async () => {
      const cachedAfterQueue = this.getCached(key);

      if (cachedAfterQueue) {
        return cachedAfterQueue;
      }

      const analysis =
        await this.client.getIqOptionDemoM5Signal(input);

      this.cache.set(key, {
        value: analysis,
        expiresAt: this.getExpiryTime(analysis),
      });

      return analysis;
    });

    this.inFlight.set(key, request);

    void request
      .finally(() => {
        if (this.inFlight.get(key) === request) {
          this.inFlight.delete(key);
        }
      })
      .catch(() => undefined);

    return request;
  }

  private getCached(
    key: string,
  ): IqOptionDemoM5SignalResponse | undefined {
    const entry = this.cache.get(key);

    if (!entry) {
      return undefined;
    }

    if (entry.expiresAt <= this.now()) {
      this.cache.delete(key);
      return undefined;
    }

    return entry.value;
  }

  private getExpiryTime(
    analysis: IqOptionDemoM5SignalResponse,
  ): number {
    const now = this.now();
    const latestCloseTime = Date.parse(
      analysis.latestClosedCandle.closeTime,
    );

    if (!Number.isFinite(latestCloseTime)) {
      return now + this.minimumReuseMs;
    }

    const nextM5CollectionAt =
      latestCloseTime + 5 * 60_000 + this.gracePeriodMs;

    return Math.max(
      now + this.minimumReuseMs,
      nextM5CollectionAt,
    );
  }

  private enqueue<T>(
    operation: () => Promise<T>,
  ): Promise<T> {
    const previousOperation = this.queueTail;

    let releaseQueue!: () => void;

    this.queueTail = new Promise<void>((resolve) => {
      releaseQueue = resolve;
    });

    return previousOperation.then(async () => {
      try {
        return await operation();
      } finally {
        releaseQueue();
      }
    });
  }
}
