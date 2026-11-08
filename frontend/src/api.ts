
export type Action = "CALL" | "PUT" | "WAIT";

export interface Analysis {
  symbol: string;
  timeframe: string;
  source?: string;
  accountMode?: string;
  analysisAt: string;
  lastClosedCandle?: {
    openTime?: string;
    closeTime?: string;
    ageSeconds?: number;
  };
  indicators: {
    ema9?: number | null;
    ema21?: number | null;
    ma50?: number | null;
    rsi14?: number | null;
    adx14?: number | null;
    atr14?: number | null;
  };
  action: Action;
  reference?: {
    price?: number | null;
    entryTime?: string | null;
    expirationTime?: string | null;
  };
  reasons?: string[];
  disclaimer?: string;
}

export interface Result {
  analysis: Analysis;
  raw: unknown;
}

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:3001"
).replace(/\/$/, "");

const isRecord = (
  value: unknown
): value is Record<string, unknown> =>
  typeof value === "object" &&
  value !== null &&
  !Array.isArray(value);

const validDate = (value: unknown): value is string =>
  typeof value === "string" &&
  Number.isFinite(Date.parse(value));

const validNumber = (value: unknown): boolean =>
  value === null ||
  value === undefined ||
  (typeof value === "number" && Number.isFinite(value));

export function parseAnalysis(raw: unknown): Analysis {
  if (!isRecord(raw)) {
    throw new Error("Resposta JSON inválida.");
  }

  if (
    typeof raw.symbol !== "string" ||
    !raw.symbol ||
    raw.timeframe !== "1m" ||
    !validDate(raw.analysisAt)
  ) {
    throw new Error("Dados principais da análise inválidos.");
  }

  if (
    raw.action !== "CALL" &&
    raw.action !== "PUT" &&
    raw.action !== "WAIT"
  ) {
    throw new Error("Ação inválida na resposta.");
  }

  if (!isRecord(raw.indicators)) {
    throw new Error("Indicadores ausentes.");
  }

  for (const key of [
    "ema9",
    "ema21",
    "ma50",
    "rsi14",
    "adx14",
    "atr14",
  ]) {
    if (!validNumber(raw.indicators[key])) {
      throw new Error(`Indicador inválido: ${key}`);
    }
  }

  if (
    raw.reference !== undefined &&
    !isRecord(raw.reference)
  ) {
    throw new Error("Referência inválida.");
  }

  if (isRecord(raw.reference)) {
    if (!validNumber(raw.reference.price)) {
      throw new Error("Preço de referência inválido.");
    }

    for (const key of ["entryTime", "expirationTime"]) {
      if (
        raw.reference[key] != null &&
        !validDate(raw.reference[key])
      ) {
        throw new Error(`Horário inválido: ${key}`);
      }
    }
  }

  if (
    raw.lastClosedCandle !== undefined &&
    !isRecord(raw.lastClosedCandle)
  ) {
    throw new Error("Último candle inválido.");
  }

  if (isRecord(raw.lastClosedCandle)) {
    for (const key of ["openTime", "closeTime"]) {
      if (
        raw.lastClosedCandle[key] != null &&
        !validDate(raw.lastClosedCandle[key])
      ) {
        throw new Error(`Horário do candle inválido: ${key}`);
      }
    }
  }

  if (
    raw.reasons !== undefined &&
    (!Array.isArray(raw.reasons) ||
      !raw.reasons.every(
        (value: unknown) => typeof value === "string"
      ))
  ) {
    throw new Error("Motivos da análise inválidos.");
  }

  return raw as unknown as Analysis;
}

export async function getAnalysis(
  symbol: string,
  signal: AbortSignal
): Promise<Result> {
  if (!/^[A-Z0-9]+-OTC$/.test(symbol)) {
    throw new Error("Símbolo inválido.");
  }

  const params = new URLSearchParams({
    symbol,
    timeframe: "1m",
    limit: "120",
  });

  const url =
    `${BASE_URL}/api/v1/iq-option/demo/market-analysis?${params}`;

  let response: Response;

  try {
    response = await fetch(url, {
      method: "GET",
      signal,
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });
  } catch (error) {
    if (signal.aborted) throw error;

    throw new Error(
      `Não foi possível consultar ${symbol}. Verifique o backend e o CORS.`
    );
  }

  if (!response.ok) {
    throw new Error(
      `Falha na análise de ${symbol}: HTTP ${response.status}.`
    );
  }

  let raw: unknown;

  try {
    raw = await response.json();
  } catch {
    throw new Error("O backend retornou JSON inválido.");
  }

  const analysis = parseAnalysis(raw);

  if (analysis.symbol !== symbol) {
    throw new Error(
      `Resposta incompatível: esperado ${symbol}, recebido ${analysis.symbol}.`
    );
  }

  return { analysis, raw };
}

export function timeUTC(value?: string | null): string {
  if (!value || !validDate(value)) return "—";

  return (
    new Intl.DateTimeFormat("pt-BR", {
      timeZone: "UTC",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(new Date(value)) + " UTC"
  );
}

export function number(
  value?: number | null,
  digits = 6
): string {
  return typeof value === "number" &&
    Number.isFinite(value)
    ? value.toLocaleString("pt-BR", {
        maximumFractionDigits: digits,
      })
    : "Indisponível";
}

export function isStale(
  analysis: Analysis,
  now: number
): { stale: boolean; reason: string } {
  const analysisTime = Date.parse(analysis.analysisAt);

  const closeTime = analysis.lastClosedCandle?.closeTime
    ? Date.parse(analysis.lastClosedCandle.closeTime)
    : NaN;

  const expiration = analysis.reference?.expirationTime
    ? Date.parse(analysis.reference.expirationTime)
    : NaN;

  const entry = analysis.reference?.entryTime
    ? Date.parse(analysis.reference.entryTime)
    : NaN;

  if (
    Number.isFinite(expiration) &&
    now >= expiration
  ) {
    return { stale: true, reason: "Sinal expirado" };
  }

  if (
    analysis.action !== "WAIT" &&
    Number.isFinite(entry) &&
    now >= entry
  ) {
    return {
      stale: true,
      reason: "Horário de entrada já passou",
    };
  }

  if (now - analysisTime > 120000) {
    return {
      stale: true,
      reason: "Análise desatualizada",
    };
  }

  if (
    Number.isFinite(closeTime) &&
    now - closeTime > 120000
  ) {
    return {
      stale: true,
      reason: "Candle desatualizado",
    };
  }

  if (analysisTime > now + 60000) {
    return {
      stale: true,
      reason: "Horário da análise inconsistente",
    };
  }

  return { stale: false, reason: "" };
}
