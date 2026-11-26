import "dotenv/config";

import path from "node:path";

import { z } from "zod";

/**
 * Hosts the API may bind to. Remote exposure is intentionally impossible in
 * this block: the backend reads a private IQ Option PRACTICE session and has
 * no authentication yet (see docs/SECURITY.md and ADR-0004).
 */
export const LOOPBACK_HOSTS = ["127.0.0.1", "::1", "localhost"] as const;

const positiveInt = (min: number, max: number, defaultValue: number) =>
  z.coerce.number().int().min(min).max(max).default(defaultValue);

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  HOST: z
    .string()
    .default("127.0.0.1")
    .refine(
      (value) => (LOOPBACK_HOSTS as readonly string[]).includes(value),
      "HOST must be a loopback address (127.0.0.1, ::1 or localhost)",
    ),
  PORT: z.coerce.number().int().positive().default(3001),
  FRONTEND_ORIGIN: z
    .string()
    .default("http://localhost:5173,http://127.0.0.1:5173")
    .transform((value) =>
      value
        .split(",")
        .map((origin) => origin.trim())
        .filter(Boolean),
    )
    .pipe(z.array(z.string().url()).min(1)),
  QUANT_ENGINE_PYTHON: z
    .string()
    .min(1)
    .default("../quant-engine/.venv/Scripts/python.exe"),
  QUANT_ENGINE_WORKING_DIRECTORY: z.string().min(1).default("../quant-engine"),
  QUANT_ENGINE_TIMEOUT_MS: positiveInt(1000, 60000, 15000),

  /* Persistent IQ Option gateway (blocks A.1/A.2). */
  IQ_GATEWAY_REQUEST_TIMEOUT_MS: positiveInt(2000, 120000, 45000),
  IQ_GATEWAY_MAX_QUEUE: positiveInt(1, 200, 16),
  IQ_GATEWAY_RESTART_BACKOFF_MAX_MS: positiveInt(1000, 300000, 30000),
  IQ_LIVE_MAX_SUBSCRIPTIONS: positiveInt(1, 32, 8),
  IQ_LIVE_SUBSCRIPTION_TTL_MS: positiveInt(10000, 3600000, 600000),

  /* Provisional publication tolerances (experimental, not approved rules). */
  SIGNAL_TOLERANCE_M1_MS: positiveInt(0, 60000, 10000),
  SIGNAL_TOLERANCE_M5_MS: positiveInt(0, 300000, 30000),

  PUBLICATION_LOG_PATH: z.string().default("data/runtime/publications.jsonl"),
});

const parsedEnvironment = envSchema.safeParse(process.env);

if (!parsedEnvironment.success) {
  console.error(
    "Invalid environment configuration:",
    parsedEnvironment.error.flatten().fieldErrors,
  );
  process.exit(1);
}

const rawEnvironment = parsedEnvironment.data;

export const env = {
  ...rawEnvironment,
  QUANT_ENGINE_PYTHON: path.resolve(rawEnvironment.QUANT_ENGINE_PYTHON),
  QUANT_ENGINE_WORKING_DIRECTORY: path.resolve(
    rawEnvironment.QUANT_ENGINE_WORKING_DIRECTORY,
  ),
  PUBLICATION_LOG_PATH:
    rawEnvironment.PUBLICATION_LOG_PATH.trim() === ""
      ? null
      : path.resolve(rawEnvironment.PUBLICATION_LOG_PATH),
};
