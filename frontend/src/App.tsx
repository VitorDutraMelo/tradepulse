
import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Check,
  Clipboard,
  Clock3,
  Code2,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
  Timer,
  Wifi,
  WifiOff,
  Pause,
  TrendingUp,
  ChartNoAxesColumnIncreasing,
} from "lucide-react";

import {
  getAnalysis,
  isStale,
  number,
  timeUTC,
  type Result,
} from "./api";

const ASSETS = [
  "EURUSD-OTC",
  "GBPUSD-OTC",
  "USDJPY-OTC",
  "EURJPY-OTC",
  "EURGBP-OTC",
  "AUDUSD-OTC",
  "USDCAD-OTC",
  "AUDCAD-OTC",
] as const;

const REFRESH_SECONDS = 60;
const TIMEOUT_MS = 15000;

const indicators = [
  { key: "ema9", label: "EMA 9", color: "#1595f5", digits: 6 },
  { key: "ema21", label: "EMA 21", color: "#9854ef", digits: 6 },
  { key: "ma50", label: "MA 50", color: "#f78c38", digits: 6 },
  { key: "rsi14", label: "RSI 14", color: "#f4d51b", digits: 2 },
  { key: "adx14", label: "ADX 14", color: "#00d96a", digits: 2 },
  { key: "atr14", label: "ATR 14", color: "#0edddd", digits: 6 },
] as const;

function Info({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="info">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function App() {
  const [symbol, setSymbol] = useState<string>("EURUSD-OTC");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastFetch, setLastFetch] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [duplicate, setDuplicate] = useState(false);
  const [auto, setAuto] = useState(true);
  const [copied, setCopied] = useState(false);

  const controllerRef = useRef<AbortController | null>(null);
  const generationRef = useRef(0);
  const selectedRef = useRef(symbol);
  const candleRef = useRef<string | null>(null);
  const mountedRef = useRef(false);

  const changeSymbol = useCallback((nextSymbol: string) => {
    if (!ASSETS.some((asset) => asset === nextSymbol)) return;
    if (selectedRef.current === nextSymbol) return;

    generationRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;

    selectedRef.current = nextSymbol;
    candleRef.current = null;

    setSymbol(nextSymbol);
    setResult(null);
    setError("");
    setLoading(false);
    setLastFetch(null);
    setDuplicate(false);
    setCopied(false);
  }, []);

  const load = useCallback(async (
    requestedSymbol: string,
    generation: number
  ) => {
    if (controllerRef.current) return;

    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setError("");

    const timeout = window.setTimeout(
      () => controller.abort(),
      TIMEOUT_MS
    );

    try {
      const response = await getAnalysis(
        requestedSymbol,
        controller.signal
      );

      if (
        !mountedRef.current ||
        controller.signal.aborted ||
        generation !== generationRef.current ||
        requestedSymbol !== selectedRef.current
      ) {
        return;
      }

      const candle =
        response.analysis.lastClosedCandle?.closeTime ?? null;

      setDuplicate(
        Boolean(candle && candleRef.current === candle)
      );

      candleRef.current = candle;
      setResult(response);
      setLastFetch(Date.now());
      setNow(Date.now());
    } catch (err) {
      if (
        !mountedRef.current ||
        generation !== generationRef.current ||
        requestedSymbol !== selectedRef.current
      ) {
        return;
      }

      setError(
        controller.signal.aborted
          ? `Tempo limite ao analisar ${requestedSymbol}.`
          : err instanceof Error
            ? err.message
            : `Falha na análise de ${requestedSymbol}.`
      );

      setResult(null);
    } finally {
      window.clearTimeout(timeout);

      if (controllerRef.current === controller) {
        controllerRef.current = null;

        if (
          mountedRef.current &&
          generation === generationRef.current
        ) {
          setLoading(false);
        }
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      generationRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const generation = generationRef.current;

    void load(symbol, generation);

    if (!auto) return;

    const interval = window.setInterval(() => {
      void load(symbol, generation);
    }, REFRESH_SECONDS * 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, [symbol, auto, load]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => window.clearInterval(interval);
  }, []);

  const analysis =
    result?.analysis.symbol === symbol
      ? result.analysis
      : undefined;

  const freshness = analysis
    ? isStale(analysis, now)
    : { stale: true, reason: "Sem análise atual" };

  const current = Boolean(
    analysis && !freshness.stale && !error
  );

  const action = current ? analysis!.action : null;

  const mode =
    action === "CALL"
      ? "call"
      : action === "PUT"
        ? "put"
        : "wait";

  const status = error
    ? "Erro na análise"
    : loading && !analysis
      ? "Consultando..."
      : current
        ? "Dados recebidos"
        : "Sem sinal atual";

  async function copyJSON() {
    if (!result || !analysis) return;

    try {
      await navigator.clipboard.writeText(
        JSON.stringify(result.raw, null, 2)
      );

      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Não foi possível copiar o JSON.");
    }
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="brandIcon">
            <span />
            <span />
            <span />
          </div>

          <div>
            <h1>
              Trade<span>Pulse</span>
            </h1>
            <p>Análise de Mercado</p>
          </div>
        </div>

        <div className="topright">
          <div className="pill">
            <span className="iq">▥</span>
            IQ Option · DEMO
          </div>

          <div className={`pill status ${current ? "online" : "offline"}`}>
            {current ? <Wifi size={17} /> : <WifiOff size={17} />}
            {status}
          </div>
        </div>
      </header>

      <div className="marketSelector">
        <div className="marketField">
          <label htmlFor="asset-select">Ativo</label>

          <select
            id="asset-select"
            value={symbol}
            onChange={(event) => changeSymbol(event.target.value)}
          >
            {ASSETS.map((asset) => (
              <option key={asset} value={asset}>
                {asset}
              </option>
            ))}
          </select>
        </div>

        <div className="marketField">
          <span>Timeframe</span>
          <strong>M1 (1 minuto)</strong>
        </div>

        <div className="marketField">
          <span>Fonte</span>
          <strong>IQ Option DEMO</strong>
        </div>
      </div>

      <div className="toolbar">
        <div className="toolbarText">
          <span className="eyebrow">
            MONITORAMENTO DE MERCADO
          </span>
          <p>Somente leitura · Nenhuma ordem é enviada</p>
        </div>

        <div className="actions">
          <button
            className={`secondary ${auto ? "selected" : ""}`}
            onClick={() => setAuto((value) => !value)}
          >
            {auto ? <Activity size={16} /> : <Pause size={16} />}
            Auto {auto ? "ligado" : "desligado"} (60s)
          </button>

          <button
            className="primary"
            disabled={loading}
            onClick={() =>
              void load(selectedRef.current, generationRef.current)
            }
          >
            {loading ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <RefreshCw size={16} />
            )}
            Atualizar análise
          </button>
        </div>
      </div>

      {error && (
        <div className="error" role="alert">
          <ShieldAlert size={20} />
          <div>
            <strong>Falha na análise de {symbol}</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      <main className="layout">
        <section className="signalCard panel">
          <div
            className={`signalHero ${mode} ${
              !current ? "inactive" : ""
            }`}
          >
            <div className="signalTitle">SINAL</div>

            <div className="signalMain">
              {action === "CALL" ? (
                <ArrowUpRight />
              ) : action === "PUT" ? (
                <ArrowDownRight />
              ) : (
                <Timer />
              )}

              <strong>
                {action ?? (loading ? "..." : "—")}
              </strong>
            </div>

            <div className="signalSubtitle">
              {error
                ? "Análise indisponível"
                : loading && !analysis
                  ? `Analisando ${symbol}...`
                  : !current
                    ? freshness.reason
                    : action === "CALL"
                      ? "Cenário de alta identificado"
                      : action === "PUT"
                        ? "Cenário de baixa identificado"
                        : "Aguardar confirmação"}
            </div>
          </div>

          <div className="details">
            <Info label="Ativo" value={symbol} />
            <Info label="Timeframe" value="M1 (1 minuto)" />
            <Info label="Conta" value={analysis?.accountMode ?? "—"} />
            <Info label="Fonte" value={analysis?.source ?? "—"} />
            <Info
              label="Última análise"
              value={timeUTC(analysis?.analysisAt)}
            />
            <Info
              label="Último candle fechado"
              value={timeUTC(analysis?.lastClosedCandle?.closeTime)}
            />
            <Info
              label="Entrada de referência"
              value={timeUTC(analysis?.reference?.entryTime)}
            />
            <Info
              label="Vencimento"
              value={timeUTC(analysis?.reference?.expirationTime)}
            />
            <Info
              label="Preço de referência"
              value={number(analysis?.reference?.price)}
            />
          </div>
        </section>

        <section className="rightColumn">
          <div className="panel indicators">
            <h2>
              <ChartNoAxesColumnIncreasing />
              Indicadores
            </h2>

            <div className="indicatorGrid">
              {indicators
                .filter(
                  (item) =>
                    item.key !== "ma50" ||
                    analysis?.indicators.ma50 != null
                )
                .map((item) => (
                  <div className="indicator" key={item.key}>
                    <span>{item.label}</span>
                    <strong>
                      {number(
                        analysis?.indicators[item.key],
                        item.digits
                      )}
                    </strong>
                    <div
                      className="indicatorLine"
                      style={{ background: item.color }}
                    />
                  </div>
                ))}
            </div>
          </div>

          <div className="panel reasons">
            <h2>
              <Check />
              Motivos do Sinal
            </h2>

            {analysis?.reasons?.length ? (
              <ul>
                {analysis.reasons.map((reason, index) => (
                  <li key={index}>
                    <Check size={17} />
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">
                Nenhum motivo disponível na análise atual.
              </p>
            )}
          </div>

          <div className="panel jsonPanel">
            <details>
              <summary>
                <span>
                  <Code2 />
                  JSON (Resposta Completa)
                </span>
                <span className="muted">Ver resposta JSON</span>
              </summary>

              <div className="jsonActions">
                <button
                  className="secondary"
                  disabled={!analysis}
                  onClick={() => void copyJSON()}
                >
                  {copied ? (
                    <Check size={16} />
                  ) : (
                    <Clipboard size={16} />
                  )}
                  {copied ? "Copiado!" : "Copiar JSON"}
                </button>
              </div>

              <pre>
                {analysis
                  ? JSON.stringify(result?.raw, null, 2)
                  : "Nenhuma resposta disponível."}
              </pre>
            </details>
          </div>

          <div className="panel metadata">
            <span>
              <Clock3 size={16} />
              Última atualização:{" "}
              {lastFetch
                ? timeUTC(new Date(lastFetch).toISOString())
                : "—"}
            </span>

            <span>
              {duplicate
                ? "Candle repetido"
                : "Atualização por HTTP"}
            </span>

            <span>
              {freshness.stale
                ? freshness.reason
                : "Análise dentro da janela de referência"}
            </span>
          </div>
        </section>
      </main>

      <footer>
        <TrendingUp size={16} />
        TradePulse é uma ferramenta informativa.
        Nenhuma ordem é enviada. Sinais não garantem resultados.
        {analysis?.disclaimer ?? ""}
      </footer>
    </div>
  );
}
