export type IqCandle = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed: true;
};

export type CandleTimeframe = "1m" | "5m";

export type IqCandleResult = {
  candles: IqCandle[];
  source: "iq_option_demo";
  venue: "iq";
  accountMode: "PRACTICE";
  symbol: string;
  timeframe: CandleTimeframe;
  derivedFromM1: boolean;
};

type ApiResponse = {
  data?: {
    source?: string;
    venue?: string;
    accountMode?: string;
    symbol?: string;
    timeframe?: string;
    candles?: unknown;
    status?: string;
    isOpen?: boolean;
  };
};

export class IqCandleRequestError extends Error {
  constructor(
    public readonly kind:
      | "connection"
      | "unavailable"
      | "response",
    message: string
  ) {
    super(message);
    this.name = "IqCandleRequestError";
  }
}

const ASSETS = new Set([
  "EURUSD-OTC",
  "GBPUSD-OTC",
  "USDJPY-OTC",
  "EURJPY-OTC",
  "EURGBP-OTC",
  "AUDUSD-OTC",
  "USDCAD-OTC",
  "AUDCAD-OTC",
]);

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? ""
).trim().replace(/\/+$/, "");

const CANDLES_URL =
  `${BASE_URL}/api/v1/iq-option/demo/candles`;

const MINUTE_MS = 60_000;
const FIVE_MINUTES_MS = 5 * MINUTE_MS;

function isObject(
  value: unknown
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function parseClosedCandle(
  value: unknown
): IqCandle | null {
  if (
    !isObject(value) ||
    value.closed !== true ||
    typeof value.timestamp !== "string"
  ) {
    return null;
  }

  const {
    open,
    high,
    low,
    close,
    volume,
  } = value;

  const time = Date.parse(value.timestamp);

  if (
    !Number.isFinite(time) ||
    time % MINUTE_MS !== 0
  ) {
    return null;
  }

  if (
    typeof open !== "number" ||
    typeof high !== "number" ||
    typeof low !== "number" ||
    typeof close !== "number" ||
    typeof volume !== "number"
  ) {
    return null;
  }

  if (
    ![open, high, low, close, volume].every(
      Number.isFinite
    ) ||
    open <= 0 ||
    high <= 0 ||
    low <= 0 ||
    close <= 0 ||
    volume < 0 ||
    high < Math.max(open, close) ||
    low > Math.min(open, close) ||
    high < low
  ) {
    return null;
  }

  return {
    timestamp: new Date(time).toISOString(),
    open,
    high,
    low,
    close,
    volume,
    closed: true,
  };
}

function normalizeM1(
  raw: unknown
): IqCandle[] {
  if (!Array.isArray(raw)) {
    throw new IqCandleRequestError(
      "response",
      "Resposta sem lista de candles."
    );
  }

  const closed = raw.filter(
    value =>
      isObject(value) &&
      value.closed === true
  );

  const parsed = closed.map(parseClosedCandle);

  if (parsed.some(candle => candle === null)) {
    throw new IqCandleRequestError(
      "response",
      "A API retornou candles fechados invalidos."
    );
  }

  const ordered = (parsed as IqCandle[]).sort(
    (a, b) =>
      Date.parse(a.timestamp) -
      Date.parse(b.timestamp)
  );

  const timestamps = ordered.map(
    candle => candle.timestamp
  );

  if (
    new Set(timestamps).size !==
    timestamps.length
  ) {
    throw new IqCandleRequestError(
      "response",
      "A API retornou timestamps duplicados."
    );
  }

  return ordered;
}

export function aggregateM1ToM5(
  candles: IqCandle[]
): IqCandle[] {
  const buckets = new Map<
    number,
    IqCandle[]
  >();

  for (const candle of candles) {
    const time = Date.parse(candle.timestamp);

    if (
      !Number.isFinite(time) ||
      time % MINUTE_MS !== 0
    ) {
      continue;
    }

    const start =
      Math.floor(time / FIVE_MINUTES_MS) *
      FIVE_MINUTES_MS;

    const group = buckets.get(start) ?? [];

    group.push(candle);
    buckets.set(start, group);
  }

  const result: IqCandle[] = [];

  for (const [start, group] of buckets) {
    if (group.length !== 5) {
      continue;
    }

    const sorted = [...group].sort(
      (a, b) =>
        Date.parse(a.timestamp) -
        Date.parse(b.timestamp)
    );

    const complete = sorted.every(
      (candle, index) =>
        Date.parse(candle.timestamp) ===
          start + index * MINUTE_MS &&
        candle.closed === true
    );

    if (!complete) {
      continue;
    }

    result.push({
      timestamp: sorted[0].timestamp,
      open: sorted[0].open,
      high: Math.max(
        ...sorted.map(candle => candle.high)
      ),
      low: Math.min(
        ...sorted.map(candle => candle.low)
      ),
      close: sorted[4].close,
      volume: sorted.reduce(
        (sum, candle) =>
          sum + candle.volume,
        0
      ),
      closed: true,
    });
  }

  return result.sort(
    (a, b) =>
      Date.parse(a.timestamp) -
      Date.parse(b.timestamp)
  );
}

export async function getIqOptionDemoCandles(
  symbol: string,
  timeframe: CandleTimeframe = "1m",
  limit = 100,
  signal?: AbortSignal
): Promise<IqCandleResult> {
  if (!ASSETS.has(symbol)) {
    throw new IqCandleRequestError(
      "response",
      "Ativo nao permitido no TradePulse."
    );
  }

  if (
    timeframe !== "1m" &&
    timeframe !== "5m"
  ) {
    throw new IqCandleRequestError(
      "response",
      "Periodo nao suportado."
    );
  }

  if (
    !Number.isInteger(limit) ||
    limit < 1 ||
    limit > 1000
  ) {
    throw new IqCandleRequestError(
      "response",
      "Limite de candles invalido."
    );
  }

  const params = new URLSearchParams({
    symbol,
    timeframe: "1m",
    limit: String(limit),
  });

  let response: Response;

  try {
    response = await fetch(
      `${CANDLES_URL}?${params.toString()}`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
        signal,
      }
    );
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }

    throw new IqCandleRequestError(
      "connection",
      "Nao foi possivel conectar ao backend para obter candles."
    );
  }

  if (
    [409, 410, 423].includes(response.status)
  ) {
    throw new IqCandleRequestError(
      "unavailable",
      `Ativo ou mercado indisponivel (HTTP ${response.status}).`
    );
  }

  if (!response.ok) {
    throw new IqCandleRequestError(
      "response",
      `Falha ao consultar candles: HTTP ${response.status}.`
    );
  }

  let payload: ApiResponse;

  try {
    payload =
      (await response.json()) as ApiResponse;
  } catch {
    throw new IqCandleRequestError(
      "response",
      "O backend retornou JSON invalido."
    );
  }

  const data = payload?.data;

  if (
    data?.source !== "iq_option_demo" ||
    data.venue !== "iq" ||
    data.accountMode !== "PRACTICE" ||
    data.symbol !== symbol ||
    data.timeframe !== "1m"
  ) {
    throw new IqCandleRequestError(
      "response",
      "Fonte, ativo ou periodo da resposta nao corresponde a IQ Option PRACTICE M1."
    );
  }

  if (
    data.isOpen === false ||
    ["closed", "unavailable", "inactive"].includes(
      (data.status ?? "").toLowerCase()
    )
  ) {
    throw new IqCandleRequestError(
      "unavailable",
      "Ativo indisponivel ou mercado fechado."
    );
  }

  const m1 = normalizeM1(data.candles);

  const candles =
    timeframe === "5m"
      ? aggregateM1ToM5(m1)
      : m1;

  return {
    candles: candles.slice(-60),
    source: "iq_option_demo",
    venue: "iq",
    accountMode: "PRACTICE",
    symbol,
    timeframe,
    derivedFromM1: timeframe === "5m",
  };
}