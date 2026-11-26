/**
 * Client for GET /api/v1/iq-option/demo/live (blocks A.1/A.2).
 *
 * The backend publishes one analysis per closed candle and recomputes data
 * freshness and signal status at every read. This client only reads that
 * view; it never decides by itself that an old analysis is current.
 */

export type LiveTimeframe = "1m" | "5m";

export type DataState = "CURRENT" | "AWAITING_NEW_CANDLE" | "STALE" | "NO_DATA";

export type SignalStatus =
  | "WAIT"
  | "EXPERIMENTAL_CANDIDATE"
  | "LATE_NOT_ACTIONABLE"
  | "EXPIRED"
  | "NOT_CURRENT";

export type LiveView = {
  strategy: {
    id: string;
    version: string;
    label: string;
    timeframe: LiveTimeframe;
    experimentalEngine: boolean;
    methodology: string;
    operational: false;
  };
  symbol: string;
  timeframe: LiveTimeframe;
  observedAt: string;
  expectedLatestCloseTime: string;
  nextCloseTime: string;
  dataState: DataState;
  cycle: { running: boolean; forCandleClose: string | null; attempts: number };
  lastError: { code: string; message: string; at: string; retryAt: string | null } | null;
  gateway: {
    workerState: string;
    sessionState: string | null;
    accountMode: string | null;
    lastErrorCode: string | null;
    nextReconnectAt: string | null;
  };
  publication: null | {
    candleId: string;
    candleOpenTime: string;
    candleCloseTime: string;
    publishedAt: string;
    timing: {
      dataReceivedAt: string | null;
      analysisStartedAt: string | null;
      analysisCompletedAt: string | null;
      publishedAt: string;
      collectionLatencyMs: number | null;
      processingLatencyMs: number | null;
      totalLatencyFromCloseMs: number;
      attempts: number;
      cacheHit: boolean | null;
      serverClockOffsetMs: number;
    };
    signal: {
      action: "CALL" | "PUT" | "WAIT";
      engineAction: "CALL" | "PUT" | "WAIT";
      status: SignalStatus;
      operational: false;
      timeliness: "ON_TIME" | "LATE";
      publicationDelayMs: number;
      toleranceMs: number;
      theoreticalEntryTime: string | null;
      theoreticalExpirationTime: string | null;
      theoreticalReferencePrice: number | null;
      observedQuoteAtPublication: { price: number; sourceTimestamp: string | null } | null;
      reasons: string[];
    };
    analysis: Record<string, unknown>;
  };
};

export type LiveResult = { view: LiveView; raw: unknown };

export class LiveRequestError extends Error {
  constructor(
    message: string,
    public readonly code: string | null = null,
  ) {
    super(message);
    this.name = "LiveRequestError";
  }
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:3001").replace(/\/$/, "");

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseView(raw: unknown, symbol: string, timeframe: LiveTimeframe): LiveView {
  const data = isRecord(raw) ? raw.data : undefined;

  if (
    !isRecord(data) ||
    data.symbol !== symbol ||
    data.timeframe !== timeframe ||
    !isRecord(data.strategy) ||
    typeof data.dataState !== "string" ||
    !isRecord(data.gateway)
  ) {
    throw new LiveRequestError("Resposta de análise ao vivo inválida ou de outro ativo.");
  }

  if (data.publication !== null) {
    const publication = data.publication;

    if (
      !isRecord(publication) ||
      !isRecord(publication.signal) ||
      !isRecord(publication.timing) ||
      typeof publication.candleCloseTime !== "string"
    ) {
      throw new LiveRequestError("Publicação de análise inválida.");
    }
  }

  return data as unknown as LiveView;
}

export async function getLive(
  symbol: string,
  timeframe: LiveTimeframe,
  signal: AbortSignal,
): Promise<LiveResult> {
  const params = new URLSearchParams({ symbol, timeframe });
  let response: Response;

  try {
    response = await fetch(`${BASE_URL}/api/v1/iq-option/demo/live?${params.toString()}`, {
      method: "GET",
      signal,
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    if (signal.aborted) {
      throw error;
    }

    throw new LiveRequestError(
      "Backend TradePulse inacessível. Verifique se a API está rodando em 127.0.0.1:3001.",
      "BACKEND_UNREACHABLE",
    );
  }

  let raw: unknown;

  try {
    raw = await response.json();
  } catch {
    throw new LiveRequestError("O backend retornou JSON inválido.");
  }

  if (!response.ok) {
    const error = isRecord(raw) && isRecord(raw.error) ? raw.error : {};
    throw new LiveRequestError(
      typeof error.message === "string" ? error.message : `HTTP ${response.status}`,
      typeof error.code === "string" ? error.code : null,
    );
  }

  return { view: parseView(raw, symbol, timeframe), raw };
}

export const DATA_STATE_LABEL: Record<DataState, string> = {
  CURRENT: "Atualizado",
  AWAITING_NEW_CANDLE: "Aguardando nova vela",
  STALE: "Desatualizado",
  NO_DATA: "Sem dados",
};

export const SIGNAL_STATUS_LABEL: Record<SignalStatus, string> = {
  WAIT: "Aguardar — condições insuficientes",
  EXPERIMENTAL_CANDIDATE: "Candidato experimental dentro da tolerância (não operacional)",
  LATE_NOT_ACTIONABLE: "Publicado após a tolerância — não utilizar",
  EXPIRED: "Expirado — não utilizar",
  NOT_CURRENT: "Análise da vela anterior — não é atual",
};

export const GATEWAY_ERROR_LABEL: Record<string, string> = {
  IQ_OPTION_CREDENTIALS_MISSING: "Credenciais PRACTICE não configuradas no backend.",
  IQ_OPTION_AUTH_FAILED: "IQ Option recusou a autenticação PRACTICE.",
  IQ_OPTION_PRACTICE_NOT_CONFIRMED: "Conta PRACTICE não confirmada — leitura bloqueada.",
  IQ_OPTION_RECONNECT_BACKOFF: "IQ Option indisponível — reconectando com intervalo progressivo.",
  IQ_OPTION_UNAVAILABLE: "IQ Option indisponível.",
  IQ_OPTION_TIMEOUT: "IQ Option não respondeu a tempo.",
  GATEWAY_QUEUE_FULL: "Fila de consultas cheia — tente novamente.",
  GATEWAY_RESTART_BACKOFF: "Gateway IQ reiniciando após falha.",
  STRATEGY_NOT_AVAILABLE_FOR_SYMBOL: "Estratégia indisponível para este ativo.",
  BACKEND_UNREACHABLE: "Backend TradePulse inacessível.",
};

export function formatMs(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
}
