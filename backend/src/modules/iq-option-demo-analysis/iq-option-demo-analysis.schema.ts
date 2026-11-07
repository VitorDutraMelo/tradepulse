import { z } from "zod";

export const iqOptionDemoAnalysisRequestSchema = z.object({
  symbol: z
    .string()
    .trim()
    .toUpperCase()
    .regex(
      /^[A-Z0-9]+(?:-OTC)?$/,
      "symbol must be an IQ Option asset such as EURUSD or EURUSD-OTC",
    ),
  timeframe: z.enum(["1m", "5m", "15m", "1h"]),
  limit: z.coerce
    .number()
    .int()
    .min(22, "limit must be at least 22 for EMA 9/21 analysis")
    .max(1000, "limit must not exceed 1000")
    .default(100),
});

export const iqOptionDemoAnalysisResponseSchema = z.object({
  recordId: z.string().min(1),
  symbol: z.string().min(1),
  timeframe: z.string().min(1),
  timestamp: z.string().min(1),
  direction: z.enum(["LONG", "SHORT", "NEUTRAL"]),
  score: z.number().int().min(0).max(100),
  reasons: z.array(z.string().min(1)).min(1),
  source: z.literal("iq_option_demo"),
  venue: z.literal("iq"),
  accountMode: z.literal("PRACTICE"),
  strategy: z.literal("ema_crossover"),
  indicators: z.object({
    fastEmaPeriod: z.number().int().positive(),
    slowEmaPeriod: z.number().int().positive(),
  }),
  disclaimer: z.string().min(1),
});

export type IqOptionDemoAnalysisRequest = z.infer<
  typeof iqOptionDemoAnalysisRequestSchema
>;

export type IqOptionDemoAnalysisResponse = z.infer<
  typeof iqOptionDemoAnalysisResponseSchema
>;