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
    .min(29, "limit must be at least 29 for EMA, RSI, ADX and ATR analysis")
    .max(1000, "limit must not exceed 1000")
    .default(100),
});

export const iqOptionDemoAnalysisResponseSchema = z.object({
  symbol: z.string().min(1),
  timeframe: z.string().min(1),
  source: z.literal("iq_option_demo"),
  accountMode: z.literal("PRACTICE"),
  analysisAt: z.string().min(1),
  lastClosedCandle: z.object({
    openTime: z.string().min(1).nullable(),
    closeTime: z.string().min(1).nullable(),
    ageSeconds: z.number().finite().nullable(),
  }),
  indicators: z.object({
    ema9: z.number().finite().nullable(),
    ema21: z.number().finite().nullable(),
    rsi14: z.number().finite().nullable(),
    adx14: z.number().finite().nullable(),
    atr14: z.number().finite().nullable(),
  }),
  action: z.enum(["CALL", "PUT", "WAIT"]),
  reference: z.object({
    price: z.number().finite().nullable(),
    entryTime: z.string().min(1).nullable(),
    expirationTime: z.string().min(1).nullable(),
  }),
  reasons: z.array(z.string().min(1)).min(1),
  disclaimer: z.string().min(1),
});

export type IqOptionDemoAnalysisRequest = z.infer<
  typeof iqOptionDemoAnalysisRequestSchema
>;

export type IqOptionDemoAnalysisResponse = z.infer<
  typeof iqOptionDemoAnalysisResponseSchema
>;