import { z } from "zod";

export const iqOptionDemoSupportedOtcSymbols = [
  "EURUSD-OTC",
  "GBPUSD-OTC",
  "USDJPY-OTC",
  "EURJPY-OTC",
  "EURGBP-OTC",
  "AUDUSD-OTC",
  "USDCAD-OTC",
  "AUDCAD-OTC",
] as const;

const iqOptionDemoCandleSchema = z.object({
  timestamp: z.string().min(1),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
  closed: z.literal(true),
});

export const iqOptionDemoCandlesRequestSchema = z.object({
  symbol: z.enum(iqOptionDemoSupportedOtcSymbols),
  timeframe: z.literal("1m").default("1m"),
  limit: z.coerce.number().int().min(1).max(1_000).default(100),
});

export const iqOptionDemoCandlesResponseSchema = z.object({
  source: z.literal("iq_option_demo"),
  venue: z.literal("iq"),
  accountMode: z.literal("PRACTICE"),
  symbol: z.enum(iqOptionDemoSupportedOtcSymbols),
  timeframe: z.literal("1m"),
  candles: z.array(iqOptionDemoCandleSchema),
});

export type IqOptionDemoCandlesRequest = z.infer<
  typeof iqOptionDemoCandlesRequestSchema
>;

export type IqOptionDemoCandlesResponse = z.infer<
  typeof iqOptionDemoCandlesResponseSchema
>;
