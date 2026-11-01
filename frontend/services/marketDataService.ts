export interface MarketCandle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MarketCandles {
  symbol: string;
  timeframe: string;
  source: string;
  candles: MarketCandle[];
}

interface MarketCandlesResponse {
  data: MarketCandles;
}

interface ApiErrorResponse {
  error?: {
    code?: string;
    message?: string;
  };
}

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:3001";

export class MarketDataApiError extends Error {
  public constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "MarketDataApiError";
  }
}

export async function getMarketCandles(
  symbol: string,
  timeframe: string,
  limit = 100,
  signal?: AbortSignal,
): Promise<MarketCandles> {
  const query = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
  });

  let response: Response;

  try {
    response = await fetch(
      `${apiBaseUrl}/api/v1/market-data/candles?${query.toString()}`,
      { signal },
    );
  } catch {
    throw new MarketDataApiError(
      "Não foi possível conectar ao backend do TradePulse.",
      0,
      "BACKEND_UNAVAILABLE",
    );
  }

  const body = (await response.json().catch(() => null)) as
    | MarketCandlesResponse
    | ApiErrorResponse
    | null;

  if (!response.ok || !body || !("data" in body)) {
    const error = body as ApiErrorResponse | null;

    throw new MarketDataApiError(
      error?.error?.message ?? "As velas de mercado não puderam ser obtidas.",
      response.status,
      error?.error?.code,
    );
  }

  return body.data;
}