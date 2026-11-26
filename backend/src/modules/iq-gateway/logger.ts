/**
 * Structured JSON-lines logger. Strings are redacted so that e-mail
 * addresses, tokens and passwords never reach the logs.
 */

const EMAIL_PATTERN = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const TOKEN_PATTERN =
  /(ssid|token|password|passwd|secret|authorization|cookie)(["']?\s*[:=]\s*["']?)([^\s"',}]+)/gi;

export function redactText(value: string): string {
  return value
    .replace(EMAIL_PATTERN, "[REDACTED_EMAIL]")
    .replace(TOKEN_PATTERN, "$1$2[REDACTED]");
}

function redactValue(value: unknown): unknown {
  if (typeof value === "string") {
    return redactText(value);
  }

  if (Array.isArray(value)) {
    return value.map(redactValue);
  }

  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, redactValue(item)]),
    );
  }

  return value;
}

export type LogLevel = "debug" | "info" | "warn" | "error";

export type Logger = (
  level: LogLevel,
  event: string,
  data?: Record<string, unknown>,
) => void;

export const jsonLogger: Logger = (level, event, data = {}) => {
  const record = {
    at: new Date().toISOString(),
    level,
    event,
    ...(redactValue(data) as Record<string, unknown>),
  };
  const line = JSON.stringify(record);

  if (level === "error" || level === "warn") {
    console.error(line);
  } else {
    console.log(line);
  }
};

export const silentLogger: Logger = () => undefined;
