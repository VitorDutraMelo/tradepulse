import { z } from "zod";

export const marketAnalysisRequestSchema = z.object({
  symbol: z
    .string()
    .trim()
    .toUpperCase()
    .regex(
      /^[A-Z0-9]+-[A-Z0-9]+$/,
      "symbol must follow the BASE-QUOTE format, such as BTC-USDT",
    ),
  timeframe: z.enum([
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "8h",
    "12h",
    "1d",
    "3d",
    "1w",
    "1M",
  ]),
  limit: z.coerce
    .number()
    .int()
    .min(22, "limit must be at least 22 for EMA 9/21 analysis")
    .max(1000, "limit must not exceed 1000")
    .default(100),
});

export const marketAnalysisResponseSchema = z.object({
  symbol: z.string().min(1),
  timeframe: z.string().min(1),
  timestamp: z.string().min(1),
  direction: z.enum(["LONG", "SHORT", "NEUTRAL"]),
  score: z.number().int().min(0).max(100),
  reasons: z.array(z.string().min(1)).min(1),
  source: z.string().min(1),
  strategy: z.string().min(1),
  indicators: z.object({
    fastEmaPeriod: z.number().int().positive(),
    slowEmaPeriod: z.number().int().positive(),
  }),
});

export type MarketAnalysisRequest = z.infer<typeof marketAnalysisRequestSchema>;
export type MarketAnalysisResponse = z.infer<
  typeof marketAnalysisResponseSchema
>;