import { iqOptionDemoAnalysisResponseSchema } from "../iq-option-demo-analysis/iq-option-demo-analysis.schema";
import { iqOptionDemoM5SignalResponseSchema } from "../iq-option-demo-analysis/iq-option-demo-m5-signal.schema";
import type { GatewayCommand } from "./gateway-worker";
import { parseIso, type GatewayTimeframe } from "./timeframes";

export const SUPPORTED_OTC_SYMBOLS = [
  "EURUSD-OTC",
  "GBPUSD-OTC",
  "USDJPY-OTC",
  "EURJPY-OTC",
  "EURGBP-OTC",
  "AUDUSD-OTC",
  "USDCAD-OTC",
  "AUDCAD-OTC",
] as const;

/** Normalized view of one analysis, independent of the strategy payload. */
export type ExtractedAnalysis = {
  candleOpenMs: number;
  candleCloseMs: number;
  /** Direction proposed by the strategy (candidate for M5). */
  action: "CALL" | "PUT" | "WAIT";
  /** Final action field emitted by the engine itself. */
  engineAction: "CALL" | "PUT" | "WAIT";
  reasons: string[];
  referencePrice: number | null;
  entryMs: number | null;
  expirationMs: number | null;
};

export type StrategyDefinition = {
  id: string;
  version: string;
  label: string;
  timeframe: GatewayTimeframe;
  symbols: readonly string[];
  command: GatewayCommand;
  /** Engine itself is experimental (not validated for use). */
  experimentalEngine: boolean;
  args: (symbol: string) => Record<string, unknown>;
  /** Validates the engine payload against the existing API contract. */
  parse: (payload: unknown) => Record<string, unknown>;
  extract: (payload: Record<string, unknown>) => ExtractedAnalysis;
};

function requireMs(value: unknown, field: string): number {
  const parsed = parseIso(value);

  if (parsed === null) {
    throw new Error(`${field} is missing or invalid in the engine payload`);
  }

  return parsed;
}

export const M1_TREND_STRATEGY: StrategyDefinition = {
  id: "m1-trend-ema9-21-rsi-adx-atr",
  version: "1.1.0",
  label: "M1 — EMA 9/21 · RSI 14 · ADX 14 · ATR 14",
  timeframe: "1m",
  symbols: SUPPORTED_OTC_SYMBOLS,
  command: "analyze_m1",
  experimentalEngine: false,
  args: (symbol) => ({ symbol, timeframe: "1m", limit: 120 }),
  parse: (payload) =>
    iqOptionDemoAnalysisResponseSchema.parse(payload) as unknown as Record<string, unknown>,
  extract: (payload) => {
    const candle = payload.lastClosedCandle as Record<string, unknown>;
    const reference = payload.reference as Record<string, unknown>;
    const action = payload.action as ExtractedAnalysis["action"];

    return {
      candleOpenMs: requireMs(candle.openTime, "lastClosedCandle.openTime"),
      candleCloseMs: requireMs(candle.closeTime, "lastClosedCandle.closeTime"),
      action,
      engineAction: action,
      reasons: payload.reasons as string[],
      referencePrice: typeof reference.price === "number" ? reference.price : null,
      entryMs: parseIso(reference.entryTime),
      expirationMs: parseIso(reference.expirationTime),
    };
  },
};

export const M5_ENGINE_STRATEGY: StrategyDefinition = {
  id: "m5-ema200-rsi14-macd-m15",
  version: "0.1.0-experimental",
  label: "M5 — EMA 200 · RSI 14 · MACD 12/26/9 · contexto M15 (experimental)",
  timeframe: "5m",
  symbols: ["GBPUSD-OTC"],
  command: "analyze_m5",
  experimentalEngine: true,
  args: (symbol) => ({ symbol }),
  parse: (payload) =>
    iqOptionDemoM5SignalResponseSchema.parse(payload) as unknown as Record<string, unknown>,
  extract: (payload) => {
    const candle = payload.latestClosedCandle as Record<string, unknown>;
    const decision = payload.decision as Record<string, unknown>;

    return {
      candleOpenMs: requireMs(candle.timestamp, "latestClosedCandle.timestamp"),
      candleCloseMs: requireMs(candle.closeTime, "latestClosedCandle.closeTime"),
      action: decision.candidateAction as ExtractedAnalysis["action"],
      engineAction: decision.action as ExtractedAnalysis["engineAction"],
      reasons: decision.reasons as string[],
      referencePrice: typeof candle.close === "number" ? candle.close : null,
      entryMs: parseIso(decision.theoreticalEntryTime),
      expirationMs: parseIso(decision.theoreticalExpirationTime),
    };
  },
};

export const STRATEGIES: readonly StrategyDefinition[] = [M1_TREND_STRATEGY, M5_ENGINE_STRATEGY];

export function strategyForTimeframe(timeframe: GatewayTimeframe): StrategyDefinition | undefined {
  return STRATEGIES.find((strategy) => strategy.timeframe === timeframe);
}
