import { z } from "zod";

const utcTimestampSchema = z.string().min(1);

const closedCandleSchema = z.object({
  timestamp: utcTimestampSchema,
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
  closed: z.literal(true),
  closeTime: utcTimestampSchema,
});

const trackingSchema = z.object({
  recordId: z.string().min(1).nullable(),
  status: z.enum([
    "NOT_APPLICABLE",
    "UNAVAILABLE",
    "PENDING",
    "WIN",
    "LOSS",
    "DRAW",
  ]),
  settledAt: utcTimestampSchema.nullable(),
  settlementPrice: z.number().nullable(),
});

const contextM15Schema = z.object({
  state: z.enum(["UPDATED", "AWAITING_CONFIRMATION", "STALE"]),
  trend: z.enum(["BULLISH", "BEARISH", "NEUTRAL"]),
  timeframe: z.literal("15m"),
  latestClosedCandle: closedCandleSchema,
  expectedLatestCloseTime: utcTimestampSchema,
  ema200: z.number().nullable(),
  ema200ThreeCandlesAgo: z.number().nullable(),
  structure: z.enum([
    "HIGHER_HIGH_HIGHER_LOW",
    "LOWER_HIGH_LOWER_LOW",
    "MIXED",
    "UNCONFIRMED",
  ]),
  dataQuality: z.object({
    requiredClosedCandles: z.literal(250),
    receivedClosedCandles: z.number().int().min(0),
    candlesContiguous: z.boolean(),
  }),
  reasons: z.array(z.string().min(1)).min(1),
  timing: z.object({
    sourceCandleCloseTime: utcTimestampSchema,
    observedClosedCandleAgeSeconds: z.number().min(0),
    providerCallStartedAt: utcTimestampSchema,
    providerCallCompletedAt: utcTimestampSchema,
    providerCallDurationMs: z.number().min(0),
    providerCallScope: z.literal(
      "IQ Option connection, M15 candle retrieval and provider parsing",
    ),
  }),
});

export const iqOptionDemoM5SignalRequestSchema = z.object({
  symbol: z.literal("GBPUSD-OTC").default("GBPUSD-OTC"),
});

export const iqOptionDemoM5SignalResponseSchema = z.object({
  source: z.literal("iq_option_demo"),
  venue: z.literal("iq"),
  accountMode: z.literal("PRACTICE"),
  symbol: z.literal("GBPUSD-OTC"),
  timeframe: z.literal("5m"),
  state: z.enum(["UPDATED", "AWAITING_CONFIRMATION", "STALE"]),
  latestClosedCandle: closedCandleSchema,
  expectedLatestCloseTime: utcTimestampSchema,
  indicators: z.object({
    ema200: z.number().nullable(),
    rsi14: z.number().nullable(),
    macd: z.number().nullable(),
    macdSignal: z.number().nullable(),
    macdHistogram: z.number().nullable(),
    previousMacdHistogram: z.number().nullable(),
    adx14: z.number().nullable(),
    atr14: z.number().nullable(),
  }),
  dataQuality: z.object({
    requiredClosedCandles: z.literal(250),
    receivedClosedCandles: z.number().int().min(0),
    candlesContiguous: z.boolean(),
  }),
  decision: z.object({
    action: z.literal("WAIT"),
    candidateAction: z.enum(["CALL", "PUT", "WAIT"]),
    m5CandidateAction: z.enum(["CALL", "PUT", "WAIT"]).optional(),
    actionability: z.enum([
      "NOT_ACTIONABLE_LATE",
      "NO_CANDIDATE",
      "DATA_NOT_CURRENT",
      "DATA_INSUFFICIENT",
      "M15_CONTEXT_NOT_CURRENT",
      "M15_CONTEXT_NOT_ALIGNED",
    ]),
    theoreticalEntryTime: utcTimestampSchema,
    theoreticalExpirationTime: utcTimestampSchema,
    reasons: z.array(z.string().min(1)).min(1),
  }),
  contextM15: contextM15Schema.optional(),
  tracking: trackingSchema.optional(),
  timing: z.object({
    clockSource: z.literal("application_utc_clock"),
    iqCandleAvailabilityAt: z.null(),
    iqCandleAvailabilityMeasurement: z.literal(
      "NOT_AVAILABLE_FROM_IQ_OPTION_API",
    ),
    sourceCandleCloseTime: utcTimestampSchema,
    observedClosedCandleAgeSeconds: z.number().min(0),
    python: z.object({
      analysisStartedAt: utcTimestampSchema,
      providerCallStartedAt: utcTimestampSchema,
      providerCallCompletedAt: utcTimestampSchema,
      payloadBuiltAt: utcTimestampSchema,
      providerCallDurationMs: z.number().min(0),
      payloadProcessingDurationMs: z.number().min(0),
      totalDurationMs: z.number().min(0),
      providerCallScope: z.literal(
        "IQ Option connection, candle retrieval and provider parsing",
      ),
    }),
  }),
});

export type IqOptionDemoM5SignalRequest = z.infer<
  typeof iqOptionDemoM5SignalRequestSchema
>;

export type IqOptionDemoM5SignalResponse = z.infer<
  typeof iqOptionDemoM5SignalResponseSchema
>;
