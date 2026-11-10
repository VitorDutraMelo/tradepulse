import { z } from "zod";

const recordIdSchema = z
  .string()
  .regex(
    /^iq-demo-binary-\d{8}-\d{6}-\d{6}-[a-z0-9-]+-[a-f0-9]{10}$/,
  );

const outcomeSchema = z.object({
  status: z.enum(["PENDING", "WIN", "LOSS", "DRAW"]),
  settledAt: z.string().min(1).nullable(),
  settlementPrice: z.number().finite().nullable(),
});

const referenceSchema = z.object({
  price: z.number().finite(),
  entryTime: z.string().min(1),
  expirationTime: z.string().min(1),
});

const recordSummarySchema = z.object({
  recordId: recordIdSchema,
  recordedAt: z.string().min(1),
  source: z.literal("iq_option_demo"),
  accountMode: z.literal("PRACTICE"),
  symbol: z.string().min(1),
  timeframe: z.enum(["1m", "5m", "15m", "1h"]),
  action: z.enum(["CALL", "PUT"]),
  analysisAt: z.string().min(1),
  reference: referenceSchema,
  outcome: outcomeSchema,
  disclaimer: z.string().min(1),
});

export const iqOptionDemoBinarySignalHistoryRequestSchema = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20),
});

export const iqOptionDemoBinarySignalRecordRequestSchema = z.object({
  recordId: recordIdSchema,
});

export const iqOptionDemoBinarySignalHistoryResponseSchema = z.object({
  source: z.literal("iq_option_demo"),
  accountMode: z.literal("PRACTICE"),
  records: z.array(recordSummarySchema),
});

export const iqOptionDemoBinarySignalRecordResponseSchema = z.object({
  schemaVersion: z.literal(1),
  recordId: recordIdSchema,
  recordedAt: z.string().min(1),
  source: z.literal("iq_option_demo"),
  accountMode: z.literal("PRACTICE"),
  analysis: z.object({
    symbol: z.string().min(1),
    timeframe: z.enum(["1m", "5m", "15m", "1h"]),
    analysisAt: z.string().min(1),
    action: z.enum(["CALL", "PUT"]),
    reasons: z.array(z.string().min(1)).min(1),
    reference: referenceSchema,
  }),
  outcome: outcomeSchema,
  disclaimer: z.string().min(1),
});

export type IqOptionDemoBinarySignalHistoryRequest = z.infer<
  typeof iqOptionDemoBinarySignalHistoryRequestSchema
>;

export type IqOptionDemoBinarySignalRecordRequest = z.infer<
  typeof iqOptionDemoBinarySignalRecordRequestSchema
>;

export type IqOptionDemoBinarySignalHistoryResponse = z.infer<
  typeof iqOptionDemoBinarySignalHistoryResponseSchema
>;

export type IqOptionDemoBinarySignalRecordResponse = z.infer<
  typeof iqOptionDemoBinarySignalRecordResponseSchema
>;
