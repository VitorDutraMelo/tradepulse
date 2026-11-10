import "dotenv/config";

import path from "node:path";

import { z } from "zod";

const environmentBoolean = (defaultValue: boolean) =>
  z
    .enum(["true", "false"])
    .default(defaultValue ? "true" : "false")
    .transform((value) => value === "true");

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  PORT: z.coerce.number().int().positive().default(3001),
  FRONTEND_ORIGIN: z.string().url().default("http://localhost:5173"),
  QUANT_ENGINE_PYTHON: z
    .string()
    .min(1)
    .default("../quant-engine/.venv/Scripts/python.exe"),
  QUANT_ENGINE_WORKING_DIRECTORY: z.string().min(1).default("../quant-engine"),
  QUANT_ENGINE_TIMEOUT_MS: z.coerce
    .number()
    .int()
    .min(1000)
    .max(60000)
    .default(15000),

  /*
   * Real trading is intentionally disabled by default.
   *
   * An actual order executor does not exist yet. These values establish
   * the security contract it must obey when it is added.
   */
  IQ_OPTION_REAL_TRADING_ENABLED: environmentBoolean(false),
  IQ_OPTION_REAL_KILL_SWITCH: environmentBoolean(true),
  IQ_OPTION_REAL_MAX_STAKE: z.coerce
    .number()
    .positive()
    .max(10_000)
    .default(2),
  IQ_OPTION_REAL_MAX_DAILY_LOSS: z.coerce
    .number()
    .positive()
    .max(100_000)
    .default(10),
  IQ_OPTION_REAL_MAX_DAILY_ORDERS: z.coerce
    .number()
    .int()
    .positive()
    .max(1_000)
    .default(5),
  IQ_OPTION_REAL_COOLDOWN_SECONDS: z.coerce
    .number()
    .int()
    .min(1)
    .max(86_400)
    .default(300),
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
};