import { z } from "zod";

const recordIdSchema = z
  .string()
  .regex(
    /^iq-demo-\d{8}-\d{6}-\d{6}-[a-z0-9-]+-[a-f0-9]{10}$/,
  );

const analysisSummarySchema = z.object({
  recordId: recordIdSchema,
  recordedAt: z.string().min(1),
  source: z.literal("iq_option_demo"),
  venue: z.literal("iq"),
  accountMode: z.literal("PRACTICE"),
  symbol: z.string().min(1),
  timeframe: z.string().min(1),
  timestamp: z.string().min(1),
  direction: z.enum(["LONG", "SHORT", "NEUTRAL"]),
  score: z.number().int().min(0).max(100),
  strategy: z.literal("ema_crossover"),
});

const candleSchema = z.object({
  timestamp: z.string().min(1),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
  closed: z.literal(true),
});

const analysisRecordSchema = z.object({
  symbol: z.string().min(1),
  timeframe: z.string().min(1),
  timestamp: z.string().min(1),
  direction: z.enum(["LONG", "SHORT", "NEUTRAL"]),
  score: z.number().int().min(0).max(100),
  reasons: z.array(z.string().min(1)).min(1),
  strategy: z.literal("ema_crossover"),
  indicators: z.object({
    fastEmaPeriod: z.literal(9),
    slowEmaPeriod: z.literal(21),
  }),
});

export const iqOptionDemoAnalysisHistoryRequestSchema = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20),
});

export const iqOptionDemoAnalysisRecordRequestSchema = z.object({
  recordId: recordIdSchema,
});

export const iqOptionDemoAnalysisHistoryResponseSchema = z.object({
  source: z.literal("iq_option_demo"),
  venue: z.literal("iq"),
  accountMode: z.literal("PRACTICE"),
  records: z.array(analysisSummarySchema),
});

export const iqOptionDemoAnalysisRecordResponseSchema = z.object({
  schemaVersion: z.literal(1),
  recordId: recordIdSchema,
  recordedAt: z.string().min(1),
  source: z.literal("iq_option_demo"),
  venue: z.literal("iq"),
  accountMode: z.literal("PRACTICE"),
  analysis: analysisRecordSchema,
  candles: z.array(candleSchema),
});

export type IqOptionDemoAnalysisHistoryRequest = z.infer<
  typeof iqOptionDemoAnalysisHistoryRequestSchema
>;

export type IqOptionDemoAnalysisRecordRequest = z.infer<
  typeof iqOptionDemoAnalysisRecordRequestSchema
>;

export type IqOptionDemoAnalysisHistoryResponse = z.infer<
  typeof iqOptionDemoAnalysisHistoryResponseSchema
>;

export type IqOptionDemoAnalysisRecordResponse = z.infer<
  typeof iqOptionDemoAnalysisRecordResponseSchema
>;
