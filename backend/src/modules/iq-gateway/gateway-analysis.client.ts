import {
  iqOptionDemoAnalysisResponseSchema,
  type IqOptionDemoAnalysisRequest,
  type IqOptionDemoAnalysisResponse,
} from "../iq-option-demo-analysis/iq-option-demo-analysis.schema";
import {
  iqOptionDemoCandlesResponseSchema,
  type IqOptionDemoCandlesRequest,
  type IqOptionDemoCandlesResponse,
} from "../iq-option-demo-analysis/iq-option-demo-candles.schema";
import type {
  IqOptionDemoM5SignalRequest,
  IqOptionDemoM5SignalResponse,
} from "../iq-option-demo-analysis/iq-option-demo-m5-signal.schema";
import {
  iqOptionDemoM5SyncResponseSchema,
  type IqOptionDemoM5SyncRequest,
  type IqOptionDemoM5SyncResponse,
} from "../iq-option-demo-analysis/iq-option-demo-m5-sync.schema";
import type {
  QuantEngineIqOptionDemoAnalysisClient,
  QuantEngineIqOptionDemoCandleClient,
  QuantEngineIqOptionDemoM5SignalClient,
  QuantEngineIqOptionDemoM5SyncClient,
} from "../market-analysis/python-quant-engine.client";
import { GatewayError, type GatewayWorker } from "./gateway-worker";
import type { LiveAnalysisService } from "./live-analysis.service";

function parseOrThrow<T>(
  schema: { safeParse: (value: unknown) => { success: true; data: T } | { success: false } },
  value: unknown,
  what: string,
): T {
  const parsed = schema.safeParse(value);

  if (!parsed.success) {
    throw new GatewayError("ENGINE_PAYLOAD_INVALID", `The IQ gateway returned an invalid ${what}.`);
  }

  return parsed.data;
}

/**
 * Serves the existing IQ Option PRACTICE endpoints through the persistent
 * gateway instead of one Python process (and one IQ login) per request.
 */
export class GatewayAnalysisClient
  implements
    QuantEngineIqOptionDemoAnalysisClient,
    QuantEngineIqOptionDemoCandleClient,
    QuantEngineIqOptionDemoM5SyncClient,
    QuantEngineIqOptionDemoM5SignalClient
{
  constructor(
    private readonly gateway: GatewayWorker,
    private readonly live: LiveAnalysisService,
    private readonly m5WaitMs = 20_000,
  ) {}

  async analyzeIqOptionDemo(
    input: IqOptionDemoAnalysisRequest,
  ): Promise<IqOptionDemoAnalysisResponse> {
    const response = await this.gateway.request("analyze_m1", input, {
      key: `analyze_m1:${input.symbol}:${input.timeframe}:${input.limit}`,
    });

    return parseOrThrow(iqOptionDemoAnalysisResponseSchema, response.result, "analysis");
  }

  async getIqOptionDemoCandles(
    input: IqOptionDemoCandlesRequest,
  ): Promise<IqOptionDemoCandlesResponse> {
    const response = await this.gateway.request("candles", input, {
      key: `candles:${input.symbol}:${input.timeframe}:${input.limit}`,
    });

    return parseOrThrow(iqOptionDemoCandlesResponseSchema, response.result, "candle list");
  }

  async getIqOptionDemoM5Sync(
    input: IqOptionDemoM5SyncRequest,
  ): Promise<IqOptionDemoM5SyncResponse> {
    const response = await this.gateway.request("m5_sync", input, {
      key: `m5_sync:${input.symbol}`,
    });

    return parseOrThrow(iqOptionDemoM5SyncResponseSchema, response.result, "M5 sync snapshot");
  }

  /**
   * The M5 endpoint now returns the publication of the scheduler. Its
   * ``state`` is recomputed at read time, so the previous candle is never
   * served as UPDATED after a new M5 boundary.
   */
  async getIqOptionDemoM5Signal(
    input: IqOptionDemoM5SignalRequest,
  ): Promise<IqOptionDemoM5SignalResponse> {
    const view = await this.live.getLive(input.symbol, "5m", { waitMs: this.m5WaitMs });
    const publication = view.publication as Record<string, unknown> | null;

    if (publication === null) {
      const lastError = view.lastError as { code?: string; message?: string } | null;
      throw new GatewayError(
        lastError?.code ?? "M5_ANALYSIS_PENDING",
        lastError?.message ?? "The first M5 analysis is still being prepared.",
      );
    }

    const { analysis, ...publicationMeta } = publication;

    return {
      ...(analysis as IqOptionDemoM5SignalResponse),
      live: {
        dataState: view.dataState,
        strategy: view.strategy,
        expectedLatestCloseTime: view.expectedLatestCloseTime,
        publication: publicationMeta,
      },
    } as IqOptionDemoM5SignalResponse;
  }
}
