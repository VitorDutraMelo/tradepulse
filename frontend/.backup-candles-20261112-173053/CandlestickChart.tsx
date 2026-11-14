import { useEffect, useMemo, useState } from "react";
import {
  getIqHistoricalCandles,
  type IqCandle,
} from "./iqHistory";

type Props = {
  symbol: string;
  timeframe: string;
};

type ChartState = {
  candles: IqCandle[];
  loading: boolean;
  error: string;
};

export default function CandlestickChart({
  symbol,
  timeframe,
}: Props) {
  const [state, setState] = useState<ChartState>({
    candles: [],
    loading: true,
    error: "",
  });

  useEffect(() => {
    const controller = new AbortController();

    setState({
      candles: [],
      loading: true,
      error: "",
    });

    const load = async () => {
      try {
        const candles = await getIqHistoricalCandles(
          symbol,
          timeframe,
          controller.signal
        );

        if (!controller.signal.aborted) {
          setState({
            candles,
            loading: false,
            error: "",
          });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setState({
            candles: [],
            loading: false,
            error:
              error instanceof Error
                ? error.message
                : "Falha no historico.",
          });
        }
      }
    };

    void load();

    const interval = window.setInterval(
      () => void load(),
      60000
    );

    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [symbol, timeframe]);

  const geometry = useMemo(() => {
    const candles = state.candles;

    if (candles.length === 0) {
      return null;
    }

    const high = Math.max(...candles.map(c => c.high));
    const low = Math.min(...candles.map(c => c.low));

    const spread = Math.max(high - low, Math.abs(high) * 0.000001);
    const min = low - spread * 0.08;
    const max = high + spread * 0.08;

    const width = 900;
    const height = 320;
    const left = 14;
    const right = 74;
    const top = 16;
    const bottom = 30;

    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;

    const y = (price: number) =>
      top + ((max - price) / (max - min)) * plotHeight;

    const step = plotWidth / candles.length;
    const bodyWidth = Math.max(2, step * 0.58);

    return {
      width,
      height,
      left,
      right,
      top,
      bottom,
      plotWidth,
      plotHeight,
      min,
      max,
      y,
      step,
      bodyWidth,
    };
  }, [state.candles]);

  if (state.loading && state.candles.length === 0) {
    return (
      <div className="tp-chart-empty">
        Consultando historico IQ Option...
      </div>
    );
  }

  if (state.error || !geometry) {
    return (
      <div className="tp-chart-empty">
        <strong>Grafico historico indisponivel</strong>
        <p>
          {state.error ||
            "Nao existem candles IQ Option registrados para este ativo e periodo."}
        </p>
      </div>
    );
  }

  const g = geometry;

  const latest = state.candles[state.candles.length - 1];
  const latestTime = new Date(latest.timestamp);

  return (
    <div className="tp-real-chart">
      <div className="tp-chart-caption">
        <span>Historico IQ Option · Candles fechados</span>
        <span>
          Ultimo:{" "}
          {latestTime.toLocaleString("pt-BR", {
            timeZone: "UTC",
          })}{" "}
          UTC
        </span>
      </div>

      <svg
        viewBox={`0 0 ${g.width} ${g.height}`}
        role="img"
        aria-label={`Grafico historico de ${symbol}, periodo ${timeframe}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {[0, 1, 2, 3, 4].map(index => {
          const price =
            g.min + ((g.max - g.min) * (4 - index)) / 4;

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
                {price.toFixed(5)}
              </text>
            </g>
          );
        })}

        {state.candles.map((candle, index) => {
          const x =
            g.left + g.step * index + g.step / 2;

          const up = candle.close >= candle.open;
          const color = up ? "#19f477" : "#f06470";

          const openY = g.y(candle.open);
          const closeY = g.y(candle.close);
          const highY = g.y(candle.high);
          const lowY = g.y(candle.low);

          return (
            <g key={candle.timestamp}>
              <line
                x1={x}
                y1={highY}
                x2={x}
                y2={lowY}
                stroke={color}
                strokeWidth="1.5"
              />

              <rect
                x={x - g.bodyWidth / 2}
                y={Math.min(openY, closeY)}
                width={g.bodyWidth}
                height={Math.max(
                  1.5,
                  Math.abs(openY - closeY)
                )}
                fill={color}
                rx="1"
              />
            </g>
          );
        })}
      </svg>

      <p className="tp-chart-note">
        Visualizacao historica. Nao representa cotacao ao vivo.
      </p>
    </div>
  );
}
