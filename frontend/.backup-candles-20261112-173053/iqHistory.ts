export type IqCandle = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed: true;
};

type HistorySummary = {
  recordId: string;
  symbol: string;
  timeframe: string;
  source: string;
  venue: string;
  accountMode: string;
  recordedAt: string;
};

type HistoryList = {
  data: {
    source: string;
    venue: string;
    accountMode: string;
    records: HistorySummary[];
  };
};

type HistoryDetail = {
  data: {
    source: string;
    venue: string;
    accountMode: string;
    analysis: {
      symbol: string;
      timeframe: string;
    };
    candles: IqCandle[];
  };
};

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:3001"
).replace(/\/+$/, "");

const HISTORY_URL =
  `${BASE_URL}/api/v1/iq-option/demo/analyses`;

const RECORD_ID_PATTERN =
  /^iq-demo-\d{8}-\d{6}-\d{6}-[a-z0-9-]+-[a-f0-9]{10}$/;

const MINUTE_MS = 60_000;
const FIVE_MINUTES_MS = 5 * MINUTE_MS;

let queue: Promise<unknown> = Promise.resolve();

function serial<T>(operation: () => Promise<T>): Promise<T> {
  const next = queue.then(operation, operation);

  queue = next.then(
    () => undefined,
    () => undefined
  );

  return next;
}

async function requestJson<T>(
  url: string,
  signal?: AbortSignal
): Promise<T> {
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal,
  });

  if (!response.ok) {
    throw new Error(
      `Historico IQ Option: HTTP ${response.status}`
    );
  }

  return response.json() as Promise<T>;
}

function validCandle(value: IqCandle): boolean {
  if (
    !value ||
    value.closed !== true ||
    !Number.isFinite(Date.parse(value.timestamp))
  ) {
    return false;
  }

  const prices = [
    value.open,
    value.high,
    value.low,
    value.close,
  ];

  if (
    !prices.every(
      price => Number.isFinite(price) && price > 0
    )
  ) {
    return false;
  }

  if (
    !Number.isFinite(value.volume) ||
    value.volume < 0
  ) {
    return false;
  }

  return (
    value.high >= Math.max(value.open, value.close) &&
    value.high >= value.low &&
    value.low <= Math.min(value.open, value.close)
  );
}

function sortAndValidate(
  candles: IqCandle[]
): IqCandle[] {
  if (!candles.every(validCandle)) {
    throw new Error(
      "Candles historicos IQ Option invalidos."
    );
  }

  const ordered = [...candles].sort(
    (a, b) =>
      Date.parse(a.timestamp) -
      Date.parse(b.timestamp)
  );

  const timestamps = ordered.map(
    candle => Date.parse(candle.timestamp)
  );

  if (
    new Set(timestamps).size !== timestamps.length
  ) {
    throw new Error(
      "Candles duplicados no historico IQ Option."
    );
  }

  return ordered;
}

function aggregateM1ToM5(
  candles: IqCandle[]
): IqCandle[] {
  const ordered = sortAndValidate(candles);

  const groups = new Map<number, IqCandle[]>();

  for (const candle of ordered) {
    const timestamp = Date.parse(candle.timestamp);

    // Apenas candles alinhados ao minuto UTC.
    if (timestamp % MINUTE_MS !== 0) {
      continue;
    }

    const bucket =
      Math.floor(timestamp / FIVE_MINUTES_MS) *
      FIVE_MINUTES_MS;

    const group = groups.get(bucket) ?? [];

    group.push(candle);
    groups.set(bucket, group);
  }

  const aggregated: IqCandle[] = [];

  for (const [bucket, group] of groups) {
    // Um candle M5 precisa de cinco M1 fechados.
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
        bucket + index * MINUTE_MS
    );

    if (!complete) {
      continue;
    }

    const first = sorted[0];
    const last = sorted[sorted.length - 1];

    aggregated.push({
      timestamp: new Date(bucket).toISOString(),
      open: first.open,
      high: Math.max(...sorted.map(c => c.high)),
      low: Math.min(...sorted.map(c => c.low)),
      close: last.close,
      volume: sorted.reduce(
        (total, candle) => total + candle.volume,
        0
      ),
      closed: true,
    });
  }

  return sortAndValidate(aggregated);
}

function validRecord(
  record: HistorySummary,
  symbol: string,
  timeframe: string
): boolean {
  return (
    record.source === "iq_option_demo" &&
    record.venue === "iq" &&
    record.accountMode === "PRACTICE" &&
    record.symbol === symbol &&
    record.timeframe === timeframe &&
    Number.isFinite(Date.parse(record.recordedAt)) &&
    RECORD_ID_PATTERN.test(record.recordId)
  );
}

async function fetchRecordCandles(
  record: HistorySummary,
  symbol: string,
  timeframe: string,
  signal?: AbortSignal
): Promise<IqCandle[]> {
  const detail = await requestJson<HistoryDetail>(
    `${HISTORY_URL}/${encodeURIComponent(record.recordId)}`,
    signal
  );

  const data = detail.data;

  if (
    data?.source !== "iq_option_demo" ||
    data?.venue !== "iq" ||
    data?.accountMode !== "PRACTICE" ||
    data.analysis?.symbol !== symbol ||
    data.analysis?.timeframe !== timeframe ||
    !Array.isArray(data.candles)
  ) {
    throw new Error(
      "Registro historico IQ Option incompatível."
    );
  }

  return sortAndValidate(data.candles);
}

export async function getIqHistoricalCandles(
  symbol: string,
  timeframe: string,
  signal?: AbortSignal
): Promise<IqCandle[]> {
  return serial(async () => {
    if (signal?.aborted) {
      throw new DOMException(
        "Cancelado",
        "AbortError"
      );
    }

    const list = await requestJson<HistoryList>(
      `${HISTORY_URL}?limit=100`,
      signal
    );

    const data = list.data;

    if (
      data?.source !== "iq_option_demo" ||
      data?.venue !== "iq" ||
      data?.accountMode !== "PRACTICE" ||
      !Array.isArray(data.records)
    ) {
      throw new Error(
        "Fonte historica IQ Option nao validada."
      );
    }

    const findLatest = (
      period: string
    ): HistorySummary | undefined =>
      data.records
        .filter(record =>
          validRecord(record, symbol, period)
        )
        .sort(
          (a, b) =>
            Date.parse(b.recordedAt) -
            Date.parse(a.recordedAt)
        )[0];

    // Prioridade: candles originais do periodo solicitado.
    const direct = findLatest(timeframe);

    if (direct) {
      const candles = await fetchRecordCandles(
        direct,
        symbol,
        timeframe,
        signal
      );

      if (candles.length > 0) {
        return candles.slice(-60);
      }
    }

    // Fallback exclusivo de M5 usando M1 da mesma IQ Option.
    if (timeframe === "5m") {
      const m1 = findLatest("1m");

      if (!m1) {
        return [];
      }

      const candlesM1 = await fetchRecordCandles(
        m1,
        symbol,
        "1m",
        signal
      );

      return aggregateM1ToM5(candlesM1).slice(-60);
    }

    return [];
  });
}