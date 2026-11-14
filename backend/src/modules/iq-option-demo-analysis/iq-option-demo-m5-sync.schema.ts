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

export const iqOptionDemoM5SyncRequestSchema = z.object({
  symbol: z.literal("GBPUSD-OTC").default("GBPUSD-OTC"),
});

export const iqOptionDemoM5SyncResponseSchema = z.object({
  source: z.literal("iq_option_demo"),
  venue: z.literal("iq"),
  accountMode: z.literal("PRACTICE"),
  symbol: z.literal("GBPUSD-OTC"),
  timeframe: z.literal("5m"),
  state: z.enum(["UPDATED", "AWAITING_CONFIRMATION", "STALE"]),
  latestClosedCandle: closedCandleSchema,
  expectedLatestCloseTime: utcTimestampSchema,
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

export type IqOptionDemoM5SyncRequest = z.infer<
  typeof iqOptionDemoM5SyncRequestSchema
>;

export type IqOptionDemoM5SyncResponse = z.infer<
  typeof iqOptionDemoM5SyncResponseSchema
>;