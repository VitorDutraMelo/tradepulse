import type {
  QuantEngineIqOptionDemoAnalysisClient,
} from "../market-analysis/python-quant-engine.client";
import type {
  IqOptionDemoAnalysisRequest,
  IqOptionDemoAnalysisResponse,
} from "./iq-option-demo-analysis.schema";

type CacheEntry = {
  expiresAt: number;
  value: IqOptionDemoAnalysisResponse;
};

export type CachedIqOptionDemoAnalysisClientOptions = {
  cacheTtlMs?: number;
  now?: () => number;
};

/**
 * Protects the non-official IQ Option integration from duplicate and
 * concurrent requests while preserving the existing API contract.
 *
 * - One IQ Option analysis runs at a time.
 * - Equal active requests share the same in-flight operation.
 * - Successful responses are cached briefly per symbol/timeframe/limit.
 * - Errors are never cached.
 */
export class CachedIqOptionDemoAnalysisClient
  implements QuantEngineIqOptionDemoAnalysisClient
{
  private readonly cache = new Map<string, CacheEntry>();

  private readonly inFlight = new Map<
    string,
    Promise<IqOptionDemoAnalysisResponse>
  >();

  private queueTail: Promise<void> = Promise.resolve();

  private readonly cacheTtlMs: number;

  private readonly now: () => number;

  constructor(
    private readonly client: QuantEngineIqOptionDemoAnalysisClient,
    options: CachedIqOptionDemoAnalysisClientOptions = {},
  ) {
    this.cacheTtlMs = options.cacheTtlMs ?? 55_000;
    this.now = options.now ?? Date.now;

    if (
      !Number.isFinite(this.cacheTtlMs) ||
      this.cacheTtlMs <= 0
    ) {
      throw new RangeError("cacheTtlMs must be a positive finite number");
    }
  }

  analyzeIqOptionDemo(
    input: IqOptionDemoAnalysisRequest,
  ): Promise<IqOptionDemoAnalysisResponse> {
    const key = this.toCacheKey(input);
    const cached = this.getCached(key);

    if (cached) {
      return Promise.resolve(cached);
    }

    const existingRequest = this.inFlight.get(key);

    if (existingRequest) {
      return existingRequest;
    }

    const request = this.enqueue(async () => {
      const cachedAfterQueue = this.getCached(key);

      if (cachedAfterQueue) {
        return cachedAfterQueue;
      }

      const analysis = await this.client.analyzeIqOptionDemo(input);

      this.cache.set(key, {
        value: analysis,
        expiresAt: this.now() + this.cacheTtlMs,
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
  ): IqOptionDemoAnalysisResponse | undefined {
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

  private enqueue<T>(operation: () => Promise<T>): Promise<T> {
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

  private toCacheKey(
    input: IqOptionDemoAnalysisRequest,
  ): string {
    return `${input.symbol}:${input.timeframe}:${input.limit}`;
  }
}