import { z } from "zod";

export const marketCandlesRequestSchema = z.object({
  symbol: z
    .string()
    .trim()
    .toUpperCase()
    .regex(
      /^[A-Z0-9]+[-/][A-Z0-9]+$/,
      "symbol must follow the BASE-QUOTE format, such as BTC-USDT or BTC/USD",
    )
    .transform((symbol) => symbol.replace("/", "-")),
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
    .min(2, "limit must be at least 2")
    .max(1000, "limit must not exceed 1000")
    .default(100),
});

export const marketCandleSchema = z.object({
  timestamp: z.string().min(1),
  open: z.number().positive(),
  high: z.number().positive(),
  low: z.number().positive(),
  close: z.number().positive(),
  volume: z.number().nonnegative(),
});

export const marketCandlesResponseSchema = z.object({
  symbol: z.string().min(1),
  timeframe: z.string().min(1),
  source: z.string().min(1),
  candles: z.array(marketCandleSchema).min(1),
});

export type MarketCandlesRequest = z.infer<typeof marketCandlesRequestSchema>;
export type MarketCandle = z.infer<typeof marketCandleSchema>;
export type MarketCandlesResponse = z.infer<
  typeof marketCandlesResponseSchema
>;