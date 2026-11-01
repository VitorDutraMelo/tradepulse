export type AnalysisDirection = "LONG" | "SHORT" | "NEUTRAL";

export interface MarketAnalysis {
  symbol: string;
  timeframe: string;
  timestamp: string;
  direction: AnalysisDirection;
  score: number;
  reasons: string[];
  source: string;
  strategy: string;
  indicators: {
    fastEmaPeriod: number;
    slowEmaPeriod: number;
  };
}

interface MarketAnalysisResponse {
  data: MarketAnalysis;
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

export class MarketAnalysisApiError extends Error {
  public constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "MarketAnalysisApiError";
  }
}

export async function getMarketAnalysis(
  symbol: string,
  timeframe: string,
  limit = 100,
  signal?: AbortSignal,
): Promise<MarketAnalysis> {
  const query = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
  });

  let response: Response;

  try {
    response = await fetch(
      `${apiBaseUrl}/api/v1/market-analysis?${query.toString()}`,
      { signal },
    );
  } catch {
    throw new MarketAnalysisApiError(
      "Não foi possível conectar ao backend do TradePulse.",
      0,
      "BACKEND_UNAVAILABLE",
    );
  }

  const body = (await response.json().catch(() => null)) as
    | MarketAnalysisResponse
    | ApiErrorResponse
    | null;

  if (!response.ok || !body || !("data" in body)) {
    const error = body as ApiErrorResponse | null;

    throw new MarketAnalysisApiError(
      error?.error?.message ?? "A análise de mercado não pôde ser obtida.",
      response.status,
      error?.error?.code,
    );
  }

  return body.data;
}