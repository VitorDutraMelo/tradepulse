import { z } from "zod";

export const iqOptionRealTradingPreflightRequestSchema = z.object({
  symbol: z
    .string()
    .trim()
    .min(1)
    .max(30)
    .regex(/^[A-Z0-9-]+$/, "symbol must contain only uppercase letters, numbers or hyphens"),
  timeframe: z.enum(["1m", "5m", "15m", "1h"]),
  action: z.enum(["CALL", "PUT"]),
  stake: z.coerce.number().positive().max(10_000),
});

export type IqOptionRealTradingPreflightRequest = z.infer<
  typeof iqOptionRealTradingPreflightRequestSchema
>;