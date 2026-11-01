import "dotenv/config";

import path from "node:path";

import { z } from "zod";

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