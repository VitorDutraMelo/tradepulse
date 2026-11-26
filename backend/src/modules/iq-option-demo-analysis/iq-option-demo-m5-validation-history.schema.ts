import { z } from "zod";

const recordIdSchema = z
  .string()
  .regex(
    /^iq-demo-m5-\d{8}-\d{6}-\d{6}-[a-z0-9-]+-[a-f0-9]{10}$/,
  );

const nullableNumberSchema = z.number().nullable();

const outcomeSchema = z.object({
  status: z.enum(["PENDING", "WIN", "LOSS", "DRAW"]),
  settledAt: z.string().min(1).nullable(),
  settlementPrice: nullableNumberSchema,
});

const summarySchema = z.object({
  recordId: recordIdSchema,
  recordedAt: z.string().min(1),
  symbol: z.string().min(1),
  timeframe: z.literal("5m"),
  candidateAction: z.enum(["CALL", "PUT", "WAIT"]),
  m5CandidateAction: z.enum(["CALL", "PUT", "WAIT"]),
  actionability: z.string().min(1),
  theoreticalEntryTime: z.string(),
  theoreticalExpirationTime: z.string(),
  outcome: outcomeSchema,
});

const persistedRecordSchema = z
  .object({
    recordId: recordIdSchema,
    recordedAt: z.string().min(1),
    source: z.literal("iq_option_demo"),
    venue: z.literal("iq"),
    accountMode: z.literal("PRACTICE"),
  })
  .passthrough();

export const iqOptionDemoM5ValidationHistoryRequestSchema = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20),
});

export const iqOptionDemoM5ValidationRecordRequestSchema = z.object({
  recordId: recordIdSchema,
});

export const iqOptionDemoM5ValidationHistoryResponseSchema = z.object({
  source: z.literal("iq_option_demo"),
  venue: z.literal("iq"),
  accountMode: z.literal("PRACTICE"),
  records: z.array(summarySchema),
});

export const iqOptionDemoM5ValidationRecordResponseSchema = z.object({
  source: z.literal("iq_option_demo"),
  venue: z.literal("iq"),
  accountMode: z.literal("PRACTICE"),
  record: persistedRecordSchema,
});

export type IqOptionDemoM5ValidationHistoryRequest = z.infer<
  typeof iqOptionDemoM5ValidationHistoryRequestSchema
>;

export type IqOptionDemoM5ValidationRecordRequest = z.infer<
  typeof iqOptionDemoM5ValidationRecordRequestSchema
>;

export type IqOptionDemoM5ValidationHistoryResponse = z.infer<
  typeof iqOptionDemoM5ValidationHistoryResponseSchema
>;

export type IqOptionDemoM5ValidationRecordResponse = z.infer<
  typeof iqOptionDemoM5ValidationRecordResponseSchema
>;
