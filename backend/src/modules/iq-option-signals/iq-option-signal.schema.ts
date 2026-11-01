import { z } from "zod";

export const iqOptionSignalRequestSchema = z.object({
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
    .min(22, "limit must be at least 22 for EMA 9/21 analysis")
    .max(1000, "limit must not exceed 1000")
    .default(100),
  market: z
    .enum(["CRYPTO", "FOREX", "INDEX", "COMMODITY", "OTC"])
    .default("CRYPTO"),
});

export const iqOptionSignalResponseSchema = z.object({
  platform: z.literal("IQ_OPTION"),
  asset: z.string().min(1),
  market: z.enum(["CRYPTO", "FOREX", "INDEX", "COMMODITY", "OTC"]),
  timeframe: z.string().min(1),
  timestamp: z.string().min(1),
  dataSource: z.string().min(1),
  analysisDirection: z.enum(["LONG", "SHORT", "NEUTRAL"]),
  action: z.enum(["CALL", "PUT", "WAIT"]),
  entryTime: z.string().min(1).nullable(),
  expirationTime: z.string().min(1).nullable(),
  reasons: z.array(z.string().min(1)).min(1),
});

export type IqOptionSignalRequest = z.infer<
  typeof iqOptionSignalRequestSchema
>;

export type IqOptionSignalResponse = z.infer<
  typeof iqOptionSignalResponseSchema
>;