export const TIMEFRAME_MS = {
  "1m": 60_000,
  "5m": 300_000,
  "15m": 900_000,
  "1h": 3_600_000,
} as const;

export type GatewayTimeframe = keyof typeof TIMEFRAME_MS;

export function timeframeMs(timeframe: GatewayTimeframe): number {
  return TIMEFRAME_MS[timeframe];
}

/** Newest candle boundary at or before ``nowMs`` (the newest possible close). */
export function latestExpectedCloseMs(nowMs: number, timeframe: GatewayTimeframe): number {
  const interval = timeframeMs(timeframe);
  return Math.floor(nowMs / interval) * interval;
}

/** Next boundary strictly after ``nowMs``. */
export function nextBoundaryMs(nowMs: number, timeframe: GatewayTimeframe): number {
  return latestExpectedCloseMs(nowMs, timeframe) + timeframeMs(timeframe);
}

export function candleId(symbol: string, timeframe: GatewayTimeframe, openMs: number): string {
  return `${symbol.toUpperCase()}:${timeframe}:${Math.floor(openMs / 1000)}`;
}

export function iso(ms: number | null | undefined): string | null {
  return typeof ms === "number" && Number.isFinite(ms) ? new Date(ms).toISOString() : null;
}

export function parseIso(value: unknown): number | null {
  if (typeof value !== "string") {
    return null;
  }

  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}
