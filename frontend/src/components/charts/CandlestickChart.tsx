import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getIqOptionDemoCandles,
  IqCandleRequestError,
  type CandleTimeframe,
  type IqCandle,
  type IqCandleResult,
} from "./iqHistory";

type Props = {
  symbol: string;
  timeframe: string;
};

type ChartState = {
  status:
    | "loading"
    | "ready"
    | "empty"
    | "unavailable"
    | "error";
  data: IqCandleResult | null;
  message: string;
};

const INITIAL: ChartState = {
  status: "loading",
  data: null,
  message: "",
};

function utcLabel(
  timestamp: string
): string {
  return (
    new Date(timestamp).toLocaleString(
      "pt-BR",
      {
        timeZone: "UTC",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }
    ) + " UTC"
  );
}

export default function CandlestickChart({
  symbol,
  timeframe,
}: Props) {
  const [state, setState] =
    useState<ChartState>(INITIAL);

  useEffect(() => {
    const controller = new AbortController();
    let inFlight = false;

    setState(INITIAL);

    const load = async () => {
      if (
        inFlight ||
        controller.signal.aborted
      ) {
        return;
      }

      inFlight = true;

      try {
        if (
          timeframe !== "1m" &&
          timeframe !== "5m"
        ) {
          throw new Error(
            "Periodo de grafico nao suportado."
          );
        }

        const result =
          await getIqOptionDemoCandles(
            symbol,
            timeframe as CandleTimeframe,
            100,
            controller.signal
          );

        if (!controller.signal.aborted) {
          setState({
            status:
              result.candles.length > 0
                ? "ready"
                : "empty",
            data: result,
            message: "",
          });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setState({
            status:
              error instanceof
                IqCandleRequestError &&
              error.kind === "unavailable"
                ? "unavailable"
                : "error",
            data: null,
            message:
              error instanceof Error
                ? error.message
                : "Erro ao carregar candles.",
          });
        }
      } finally {
        inFlight = false;
      }
    };

    void load();

    const interval = window.setInterval(
      () => void load(),
      60_000
    );

    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [symbol, timeframe]);

  const candles =
    state.data?.candles ?? [];

  const geometry = useMemo(() => {
    if (candles.length === 0) {
      return null;
    }

    const high = Math.max(
      ...candles.map(candle => candle.high)
    );

    const low = Math.min(
      ...candles.map(candle => candle.low)
    );

    const spread = Math.max(
      high - low,
      Math.abs(high) * 0.000001
    );

    const min =
      low - spread * 0.08;

    const max =
      high + spread * 0.08;

    const width = 900;
    const height = 320;
    const left = 14;
    const right = 74;
    const top = 16;
    const bottom = 30;

    const plotWidth =
      width - left - right;

    const plotHeight =
      height - top - bottom;

    const y = (price: number) =>
      top +
      ((max - price) / (max - min)) *
        plotHeight;

    const step =
      plotWidth / candles.length;

    const bodyWidth = Math.max(
      2,
      step * 0.58
    );

    return {
      width,
      height,
      left,
      right,
      top,
      bottom,
      min,
      max,
      y,
      step,
      bodyWidth,
    };
  }, [candles]);

  if (state.status === "loading") {
    return (
      <div
        className="tp-chart-empty"
        role="status"
      >
        Carregando candles IQ Option PRACTICE...
      </div>
    );
  }

  if (
    state.status !== "ready" ||
    !geometry
  ) {
    const title =
      state.status === "empty"
        ? "Nenhum candle fechado disponivel"
        : state.status === "unavailable"
          ? "Ativo indisponivel ou fechado"
          : "Erro ao carregar grafico";

    return (
      <div
        className="tp-chart-empty"
        role="status"
      >
        <strong>{title}</strong>

        <p>
          {state.message ||
            `Sem candles fechados para ${symbol} (${timeframe.toUpperCase()}).`}
        </p>

        <p>
          IQ Option PRACTICE · {symbol} ·{" "}
          {timeframe.toUpperCase()} · 0 candles
        </p>
      </div>
    );
  }

  const g = geometry;

  const latest =
    candles[candles.length - 1];

  return (
    <div className="tp-real-chart">
      <div className="tp-chart-caption">
        <span>
          IQ Option PRACTICE · {symbol} ·{" "}
          {timeframe.toUpperCase()} ·{" "}
          {candles.length} candles
        </span>

        <span>
          Ultimo fechado:{" "}
          {utcLabel(latest.timestamp)}
        </span>
      </div>

      {state.data?.derivedFromM1 && (
        <p className="tp-chart-note">
          M5 agregado de cinco candles M1
          consecutivos e fechados.
        </p>
      )}

      <svg
        viewBox={`0 0 ${g.width} ${g.height}`}
        role="img"
        aria-label={`Grafico historico IQ Option PRACTICE de ${symbol}, ${timeframe}, ${candles.length} candles`}
        preserveAspectRatio="xMidYMid meet"
      >
        {[0, 1, 2, 3, 4].map(index => {
          const price =
            g.min +
            ((g.max - g.min) *
              (4 - index)) /
              4;

          const y = g.y(price);

          return (
            <g key={index}>
              <line
                x1={g.left}
                y1={y}
                x2={g.width - g.right}
                y2={y}
                stroke="#28373c"
                strokeWidth="1"
                strokeDasharray="3 5"
              />

              <text
                x={g.width - g.right + 8}
                y={y + 4}
                fill="#94a5ad"
                fontSize="11"
              >
                {price.toFixed(
                  symbol.includes("JPY")
                    ? 3
                    : 5
                )}
              </text>
            </g>
          );
        })}

        {candles.map(
          (
            candle: IqCandle,
            index
          ) => {
            const x =
              g.left +
              g.step * index +
              g.step / 2;

            const color =
              candle.close >= candle.open
                ? "#19f477"
                : "#f06470";

            const openY =
              g.y(candle.open);

            const closeY =
              g.y(candle.close);

            return (
              <g key={candle.timestamp}>
                <line
                  x1={x}
                  y1={g.y(candle.high)}
                  x2={x}
                  y2={g.y(candle.low)}
                  stroke={color}
                  strokeWidth="1.5"
                />

                <rect
                  x={
                    x -
                    g.bodyWidth / 2
                  }
                  y={Math.min(
                    openY,
                    closeY
                  )}
                  width={g.bodyWidth}
                  height={Math.max(
                    1.5,
                    Math.abs(
                      openY - closeY
                    )
                  )}
                  fill={color}
                  rx="1"
                />
              </g>
            );
          }
        )}
      </svg>

      <p className="tp-chart-note">
        Visualizacao historica.
        Nao representa cotacao ao vivo
        nem confirma sincronizacao com o sinal.
      </p>
    </div>
  );
}