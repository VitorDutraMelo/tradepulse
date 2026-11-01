"use client";

import { CircleAlert, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  getMarketCandles,
  MarketDataApiError,
  type MarketCandle,
} from "@/services/marketDataService";

interface LiveCandleChartProps {
  symbol: string;
  timeframe: string;
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: value >= 100 ? 2 : 5,
  }).format(value);
}

function formatTimestamp(timestamp: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(new Date(timestamp));
}

function CandleSvg({ candles }: { candles: MarketCandle[] }) {
  const width = 900;
  const height = 350;
  const horizontalPadding = 34;
  const verticalPadding = 22;

  const bounds = useMemo(() => {
    const highest = Math.max(...candles.map((candle) => candle.high));
    const lowest = Math.min(...candles.map((candle) => candle.low));
    const range = highest - lowest || highest * 0.001 || 1;

    return {
      highest: highest + range * 0.04,
      lowest: lowest - range * 0.04,
    };
  }, [candles]);

  const chartHeight = height - verticalPadding * 2;
  const chartWidth = width - horizontalPadding * 2;
  const priceRange = bounds.highest - bounds.lowest;
  const candleSpace = chartWidth / candles.length;
  const candleWidth = Math.max(3, Math.min(14, candleSpace * 0.58));

  const yForPrice = (price: number): number =>
    verticalPadding + ((bounds.highest - price) / priceRange) * chartHeight;

  return (
    <svg
      aria-label="Gráfico de velas reais"
      role="img"
      viewBox={`0 0 ${width} ${height}`}
      style={{ display: "block", height: "350px", width: "100%" }}
    >
      {[0.2, 0.4, 0.6, 0.8].map((position) => {
        const y = verticalPadding + chartHeight * position;

        return (
          <line
            key={position}
            stroke="#173246"
            strokeWidth="1"
            x1={horizontalPadding}
            x2={width - horizontalPadding}
            y1={y}
            y2={y}
          />
        );
      })}

      {candles.map((candle, index) => {
        const x = horizontalPadding + candleSpace * index + candleSpace / 2;
        const isUp = candle.close >= candle.open;
        const color = isUp ? "#12d67b" : "#ff4d62";
        const openY = yForPrice(candle.open);
        const closeY = yForPrice(candle.close);
        const highY = yForPrice(candle.high);
        const lowY = yForPrice(candle.low);
        const bodyY = Math.min(openY, closeY);
        const bodyHeight = Math.max(2, Math.abs(closeY - openY));

        return (
          <g key={candle.timestamp}>
            <line
              stroke={color}
              strokeWidth="1.5"
              x1={x}
              x2={x}
              y1={highY}
              y2={lowY}
            />
            <rect
              fill={color}
              height={bodyHeight}
              rx="1"
              width={candleWidth}
              x={x - candleWidth / 2}
              y={bodyY}
            />
          </g>
        );
      })}
    </svg>
  );
}

export function LiveCandleChart({
  symbol,
  timeframe,
}: LiveCandleChartProps) {
  const [candles, setCandles] = useState<MarketCandle[]>([]);
  const [source, setSource] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadCandles(): Promise<void> {
      setIsLoading(true);
      setError(null);

      try {
        const result = await getMarketCandles(
          symbol,
          timeframe,
          100,
          controller.signal,
        );

        setCandles(result.candles);
        setSource(result.source);
      } catch (requestError) {
        if (controller.signal.aborted) {
          return;
        }

        if (requestError instanceof MarketDataApiError) {
          setError(requestError.message);
        } else {
          setError("Não foi possível carregar as velas reais do mercado.");
        }

        setCandles([]);
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void loadCandles();

    return () => controller.abort();
  }, [symbol, timeframe, refreshToken]);

  const latestCandle = candles.at(-1);
  const sourceLabel =
    source === "binance_spot" ? "Binance Spot" : source || "fonte desconhecida";

  return (
    <div className="chart-wrap">
      <div className="ohlc">
        {latestCandle ? (
          <>
            <span>O <b>{formatPrice(latestCandle.open)}</b></span>
            <span>H <b>{formatPrice(latestCandle.high)}</b></span>
            <span>L <b>{formatPrice(latestCandle.low)}</b></span>
            <span>C <b>{formatPrice(latestCandle.close)}</b></span>
          </>
        ) : (
          <span>Carregando velas fechadas…</span>
        )}

        <button
          aria-label="Atualizar velas"
          className="tool"
          disabled={isLoading}
          onClick={() => setRefreshToken((value) => value + 1)}
          type="button"
        >
          <RefreshCw size={15} />
          Atualizar
        </button>
      </div>

      {isLoading && candles.length === 0 ? (
        <div className="loading" style={{ minHeight: "350px" }}>
          <i />
          Carregando velas reais…
        </div>
      ) : null}

      {!isLoading && error ? (
        <div className="loading" style={{ minHeight: "350px" }}>
          <CircleAlert size={28} />
          <span>{error}</span>
          <button
            className="primary"
            onClick={() => setRefreshToken((value) => value + 1)}
            type="button"
          >
            Tentar novamente
          </button>
        </div>
      ) : null}

      {!isLoading && !error && candles.length > 0 ? (
        <>
          <CandleSvg candles={candles} />
          <p className="disclaimer">
            Velas fechadas reais · {sourceLabel} · última vela:{" "}
            {latestCandle ? `${formatTimestamp(latestCandle.timestamp)} UTC` : "—"}
          </p>
        </>
      ) : null}
    </div>
  );
}