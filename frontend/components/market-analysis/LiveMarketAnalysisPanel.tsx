"use client";

import { Activity, CircleAlert, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";

import {
  getMarketAnalysis,
  MarketAnalysisApiError,
  type AnalysisDirection,
  type MarketAnalysis,
} from "@/services/marketAnalysisService";

interface LiveMarketAnalysisPanelProps {
  symbol: string;
  timeframe: string;
}

function DirectionIcon({ direction }: { direction: AnalysisDirection }) {
  if (direction === "LONG") {
    return <TrendingUp size={16} />;
  }

  if (direction === "SHORT") {
    return <TrendingDown size={16} />;
  }

  return <Activity size={16} />;
}

function formatTimestamp(timestamp: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(timestamp));
}

function formatSource(source: string): string {
  if (source === "binance_spot") {
    return "Binance Spot";
  }

  return source;
}

export function LiveMarketAnalysisPanel({
  symbol,
  timeframe,
}: LiveMarketAnalysisPanelProps) {
  const [analysis, setAnalysis] = useState<MarketAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadAnalysis(): Promise<void> {
      setIsLoading(true);
      setError(null);

      try {
        const result = await getMarketAnalysis(
          symbol,
          timeframe,
          100,
          controller.signal,
        );

        if (!controller.signal.aborted) {
          setAnalysis(result);
        }
      } catch (caughtError) {
        if (controller.signal.aborted) {
          return;
        }

        setAnalysis(null);

        if (caughtError instanceof MarketAnalysisApiError) {
          setError(caughtError.message);
          return;
        }

        setError("Ocorreu um erro inesperado ao obter a análise.");
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void loadAnalysis();

    return () => {
      controller.abort();
    };
  }, [symbol, timeframe, requestVersion]);

  return (
    <section className="panel signal-panel" aria-live="polite">
      <div className="panel-head">
        <div>
          <h2>Análise atual</h2>
          <p>Dados reais do motor TradePulse.</p>
        </div>

        <button
          className="tool"
          type="button"
          onClick={() => setRequestVersion((version) => version + 1)}
          disabled={isLoading}
        >
          <RefreshCw size={15} />
          Atualizar
        </button>
      </div>

      {isLoading && (
        <div className="loading">
          <i />
          Consultando dados de mercado...
        </div>
      )}

      {!isLoading && error && (
        <div className="empty">
          <CircleAlert size={20} />
          <p>{error}</p>
          <button
            className="primary"
            type="button"
            onClick={() => setRequestVersion((version) => version + 1)}
          >
            Tentar novamente
          </button>
        </div>
      )}

      {!isLoading && analysis && (
        <>
          <div className="signal-hero neutral">
            <span className="direction neutral">
              <DirectionIcon direction={analysis.direction} />
              {analysis.direction}
            </span>
            <b>ANÁLISE TÉCNICA INTERNA</b>
            <span>Score técnico: {analysis.score}/100</span>
          </div>

          <dl>
            <div>
              <dt>Ativo</dt>
              <dd>{analysis.symbol}</dd>
            </div>

            <div>
              <dt>Timeframe</dt>
              <dd>{analysis.timeframe}</dd>
            </div>

            <div>
              <dt>Última vela fechada</dt>
              <dd>{formatTimestamp(analysis.timestamp)} UTC</dd>
            </div>

            <div>
              <dt>Origem</dt>
              <dd>{formatSource(analysis.source)}</dd>
            </div>

            <div>
              <dt>Estratégia</dt>
              <dd>{analysis.strategy}</dd>
            </div>

            <div>
              <dt>EMAs</dt>
              <dd>
                {analysis.indicators.fastEmaPeriod} /{" "}
                {analysis.indicators.slowEmaPeriod}
              </dd>
            </div>
          </dl>

          <h3>Justificativas</h3>

          <ul className="checks">
            {analysis.reasons.map((reason) => (
              <li key={reason}>
                <Activity size={16} />
                {reason}
              </li>
            ))}
          </ul>

          <p className="disclaimer">
            O score é uma medida técnica da estratégia, não uma probabilidade de
            acerto e não representa recomendação financeira. LONG, SHORT e
            NEUTRAL não equivalem automaticamente a CALL, PUT ou WAIT.
          </p>
        </>
      )}
    </section>
  );
}