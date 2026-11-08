
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Clock3,
  Code2,
  Copy,
  LoaderCircle,
  Pause,
  Power,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";

import {
  getAnalysis,
  isStale,
  timeUTC,
  type Result,
} from "./api";

import "./style.css";

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

type Asset = (typeof ASSETS)[number];

const INITIAL_ASSETS: Asset[] = [
  "EURUSD-OTC",
  "GBPUSD-OTC",
  "USDJPY-OTC",
  "EURJPY-OTC",
];

const REFRESH_MS = 60_000;

function isAsset(value: string): value is Asset {
  return ASSETS.some((asset) => asset === value);
}

function displayAsset(symbol: string): string {
  const pair = symbol.replace("-OTC", "");
  return `${pair.slice(0, 3)}/${pair.slice(3)} OTC`;
}

function assetFlags(symbol: string): string {
  const pair = symbol.replace("-OTC", "");

  const flags: Record<string, string> = {
    EUR: "🇪🇺",
    USD: "🇺🇸",
    GBP: "🇬🇧",
    JPY: "🇯🇵",
    AUD: "🇦🇺",
    CAD: "🇨🇦",
  };

  return (
    (flags[pair.slice(0, 3)] ?? "🌐") +
    (flags[pair.slice(3)] ?? "🌐")
  );
}

function formatNumber(
  value: number | null | undefined,
  digits = 6
): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return value.toLocaleString("pt-BR", {
    maximumFractionDigits: digits,
  });
}

function formatCountdown(milliseconds: number): string {
  const seconds = Math.max(
    0,
    Math.ceil(milliseconds / 1000)
  );

  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;

  return `${String(minutes).padStart(2, "0")}:${String(
    remainder
  ).padStart(2, "0")}`;
}

function formatClock(now: number): string {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(now);
}

interface SignalPanelProps {
  index: number;
  symbol: Asset;
  enabled: boolean;
  onSymbolChange: (symbol: Asset) => void;
  onEnabledChange: (enabled: boolean) => void;
  onConnectionChange: (
    index: number,
    connected: boolean
  ) => void;
}

function SignalPanel({
  index,
  symbol,
  enabled,
  onSymbolChange,
  onEnabledChange,
  onConnectionChange,
}: SignalPanelProps) {
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(Date.now());

  const [updatedAt, setUpdatedAt] =
    useState<number | null>(null);

  const [showDetails, setShowDetails] = useState(false);
  const [copied, setCopied] = useState(false);

  const controllerRef =
    useRef<AbortController | null>(null);

  const generationRef = useRef(0);
  const mountedRef = useRef(false);
  const symbolRef = useRef(symbol);
  const enabledRef = useRef(enabled);

  const load = useCallback(
    async (asset: Asset, generation: number) => {
      // Não consulta painéis desativados.
      if (!enabledRef.current) return;

      // Não permite requisições simultâneas
      // dentro do mesmo painel.
      if (controllerRef.current) return;

      const controller = new AbortController();
      controllerRef.current = controller;

      setLoading(true);
      setError("");

      try {
        const response = await getAnalysis(
          asset,
          controller.signal
        );

        // Ignora resultados obsoletos.
        if (
          !mountedRef.current ||
          !enabledRef.current ||
          controller.signal.aborted ||
          generation !== generationRef.current ||
          symbolRef.current !== asset
        ) {
          return;
        }

        if (response.analysis.symbol !== asset) {
          throw new Error(
            "O backend retornou outro ativo."
          );
        }

        setResult(response);
        setUpdatedAt(Date.now());
        setNow(Date.now());
        onConnectionChange(index, true);
      } catch (cause) {
        if (
          !mountedRef.current ||
          !enabledRef.current ||
          controller.signal.aborted ||
          generation !== generationRef.current ||
          symbolRef.current !== asset
        ) {
          return;
        }

        setResult(null);
        setUpdatedAt(null);
        onConnectionChange(index, false);

        setError(
          cause instanceof Error
            ? cause.message
            : "Não foi possível consultar a análise."
        );
      } finally {
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
    },
    [index, onConnectionChange]
  );

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
    generationRef.current += 1;
    const generation = generationRef.current;

    symbolRef.current = symbol;
    enabledRef.current = enabled;

    controllerRef.current?.abort();
    controllerRef.current = null;

    setResult(null);
    setError("");
    setLoading(false);
    setUpdatedAt(null);
    setCopied(false);
    onConnectionChange(index, false);

    // Painel desligado: nenhuma requisição
    // nem atualização automática.
    if (!enabled) {
      return;
    }

    void load(symbol, generation);

    const interval = window.setInterval(() => {
      void load(symbol, generation);
    }, REFRESH_MS);

    return () => {
      window.clearInterval(interval);
      generationRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [
    symbol,
    enabled,
    index,
    load,
    onConnectionChange,
  ]);

  useEffect(() => {
    if (!enabled) return;

    const interval = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => window.clearInterval(interval);
  }, [enabled]);

  const analysis =
    enabled && result?.analysis.symbol === symbol
      ? result.analysis
      : null;

  const freshness = analysis
    ? isStale(analysis, now)
    : { stale: true, reason: "Sem análise atual" };

  const valid = Boolean(
    enabled && analysis && !freshness.stale && !error
  );

  const action =
    valid && analysis ? analysis.action : null;

  const signalClass = action
    ? action.toLowerCase()
    : "neutral";

  const reference = analysis?.reference;
  const indicators = analysis?.indicators;

  const entryMs = reference?.entryTime
    ? Date.parse(reference.entryTime)
    : NaN;

  const expirationMs = reference?.expirationTime
    ? Date.parse(reference.expirationTime)
    : NaN;

  const beforeEntry =
    Number.isFinite(entryMs) && now < entryMs;

  const beforeExpiration =
    Number.isFinite(expirationMs) &&
    now < expirationMs;

  const countdownTarget = beforeEntry
    ? entryMs
    : beforeExpiration
      ? expirationMs
      : null;

  const countdownLabel = beforeEntry
    ? "Até a entrada"
    : beforeExpiration
      ? "Até o vencimento"
      : "Sem contagem ativa";

  const statusText = !enabled
    ? "Análise pausada"
    : error
      ? "Erro na análise"
      : loading && !analysis
        ? "Consultando análise"
        : !analysis
          ? "Aguardando dados"
          : freshness.stale
            ? freshness.reason
            : action === "CALL"
              ? "Cenário de alta identificado"
              : action === "PUT"
                ? "Cenário de baixa identificado"
                : "Aguardar confirmação";

  function changeAsset(value: string) {
    if (!isAsset(value) || value === symbolRef.current) {
      return;
    }

    generationRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;

    symbolRef.current = value;

    setResult(null);
    setError("");
    setUpdatedAt(null);
    setLoading(enabled);
    onConnectionChange(index, false);

    onSymbolChange(value);
  }

  function toggleEnabled() {
    const nextEnabled = !enabled;

    // Interrompe imediatamente o painel
    // ao desligar, sem esperar pelo React.
    if (!nextEnabled) {
      enabledRef.current = false;
      generationRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;

      setResult(null);
      setError("");
      setLoading(false);
      setUpdatedAt(null);
      setShowDetails(false);
      onConnectionChange(index, false);
    }

    onEnabledChange(nextEnabled);
  }

  function refresh() {
    if (!enabledRef.current) return;
    if (controllerRef.current) return;

    void load(
      symbolRef.current,
      generationRef.current
    );
  }

  async function copyJson() {
    if (!enabled || !result) return;

    try {
      await navigator.clipboard.writeText(
        JSON.stringify(result.raw, null, 2)
      );

      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <article
      className="terminal-panel"
      aria-label={`Painel ${index + 1}: ${symbol}`}
      style={
        enabled
          ? undefined
          : {
              opacity: 0.78,
              borderColor: "#46505c",
            }
      }
    >
      <div className="panel-header">
        <div className="panel-asset">
          <span className="panel-flags">
            {assetFlags(symbol)}
          </span>

          <div className="panel-asset-info">
            <label
              className="sr-only"
              htmlFor={`asset-${index}`}
            >
              Ativo do painel {index + 1}
            </label>

            <select
              id={`asset-${index}`}
              className="asset-select"
              value={symbol}
              onChange={(event) =>
                changeAsset(event.target.value)
              }
            >
              {ASSETS.map((asset) => (
                <option key={asset} value={asset}>
                  {displayAsset(asset)}
                </option>
              ))}
            </select>

            <span className="timeframe">
              Timeframe: M1 · DEMO
            </span>
          </div>
        </div>

        <div className="panel-tools">
          <button
            type="button"
            onClick={toggleEnabled}
            aria-pressed={enabled}
            title={
              enabled
                ? "Desativar este painel"
                : "Ativar este painel"
            }
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "9px 11px",
              borderRadius: 8,
              border: `1px solid ${
                enabled ? "#16885a" : "#667080"
              }`,
              background: enabled
                ? "#0a3528"
                : "#252c37",
              color: enabled
                ? "#27eb91"
                : "#c6ced8",
              fontWeight: 700,
              fontSize: 11,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            <Power size={15} />
            {enabled ? "ON" : "NONE"}
          </button>

          {enabled && (
            <>
              <div className="timer-box">
                <Clock3 size={18} />

                <div>
                  <span>{countdownLabel}</span>
                  <strong>
                    {countdownTarget !== null
                      ? formatCountdown(
                          countdownTarget - now
                        )
                      : "—"}
                  </strong>
                </div>
              </div>

              <button
                type="button"
                className="icon-button"
                title="Atualizar análise"
                aria-label={`Atualizar ${symbol}`}
                disabled={loading}
                onClick={refresh}
              >
                <RefreshCw
                  size={19}
                  className={loading ? "spin" : ""}
                />
              </button>
            </>
          )}
        </div>
      </div>

      <div className="panel-content">
        <p className="signal-caption">
          {statusText}
        </p>

        {!enabled ? (
          <div className="signal-box neutral">
            <Power size={38} />
            <span>NONE</span>
          </div>
        ) : loading && !analysis ? (
          <div className="signal-box neutral">
            <LoaderCircle
              className="spin"
              size={38}
            />
            <span>CARREGANDO</span>
          </div>
        ) : error ? (
          <div className="signal-box neutral">
            <ShieldAlert size={38} />
            <span>ERRO</span>
          </div>
        ) : action ? (
          <div className={`signal-box ${signalClass}`}>
            {action === "CALL" ? (
              <ArrowUpRight size={52} />
            ) : action === "PUT" ? (
              <ArrowDownRight size={52} />
            ) : (
              <Pause size={43} />
            )}
            <span>{action}</span>
          </div>
        ) : (
          <div className="signal-box neutral">
            <Clock3 size={38} />
            <span>
              {analysis ? "EXPIRADO" : "SEM DADOS"}
            </span>
          </div>
        )}

        {enabled && error && (
          <p className="panel-error" role="alert">
            {error}
          </p>
        )}

        {enabled ? (
          <div className="panel-times">
            <span>
              Análise: {timeUTC(analysis?.analysisAt)}
            </span>
            <span>
              Entrada: {timeUTC(reference?.entryTime)}
            </span>
            <span>
              Vencimento:{" "}
              {timeUTC(reference?.expirationTime)}
            </span>
          </div>
        ) : (
          <p
            style={{
              color: "#94a3b8",
              fontSize: 12,
              textAlign: "center",
              margin: 0,
            }}
          >
            Nenhuma requisição será enviada
            enquanto este painel estiver desativado.
          </p>
        )}
      </div>

      <div className="panel-footer">
        <span>
          {!enabled
            ? "Painel desativado"
            : loading
              ? "Atualizando..."
              : updatedAt !== null
                ? `Consultado: ${timeUTC(
                    new Date(updatedAt).toISOString()
                  )}`
                : "Aguardando resposta"}
        </span>

        {enabled && (
          <button
            type="button"
            className="details-button"
            onClick={() =>
              setShowDetails((current) => !current)
            }
          >
            <Code2 size={15} />
            {showDetails
              ? "Ocultar detalhes"
              : "Detalhes"}
          </button>
        )}
      </div>

      {enabled && showDetails && (
        <div className="panel-details">
          <div className="detail-grid">
            <div>
              <span>EMA 9</span>
              <strong>
                {formatNumber(indicators?.ema9)}
              </strong>
            </div>

            <div>
              <span>EMA 21</span>
              <strong>
                {formatNumber(indicators?.ema21)}
              </strong>
            </div>

            <div>
              <span>RSI 14</span>
              <strong>
                {formatNumber(indicators?.rsi14, 2)}
              </strong>
            </div>

            <div>
              <span>ADX 14</span>
              <strong>
                {formatNumber(indicators?.adx14, 2)}
              </strong>
            </div>

            <div>
              <span>ATR 14</span>
              <strong>
                {formatNumber(indicators?.atr14)}
              </strong>
            </div>

            <div>
              <span>Preço</span>
              <strong>
                {formatNumber(reference?.price)}
              </strong>
            </div>
          </div>

          <h3>Motivos da análise</h3>

          {analysis?.reasons?.length ? (
            <ul>
              {analysis.reasons.map((reason, i) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">
              Nenhum motivo disponível.
            </p>
          )}

          <div className="json-heading">
            <h3>Resposta JSON</h3>

            <button
              type="button"
              className="details-button"
              disabled={!result}
              onClick={() => void copyJson()}
            >
              <Copy size={15} />
              {copied ? "Copiado" : "Copiar"}
            </button>
          </div>

          <pre className="json-output">
            {result
              ? JSON.stringify(result.raw, null, 2)
              : "Sem resposta disponível."}
          </pre>
        </div>
      )}
    </article>
  );
}

export default function App() {
  const [assets, setAssets] = useState<Asset[]>(
    [...INITIAL_ASSETS]
  );

  // Somente o primeiro painel inicia ativo.
  const [enabledPanels, setEnabledPanels] = useState<
    boolean[]
  >([true, false, false, false]);

  const [now, setNow] = useState(Date.now());

  const [connections, setConnections] = useState<
    boolean[]
  >([false, false, false, false]);

  const updateConnection = useCallback(
    (index: number, connected: boolean) => {
      setConnections((current) => {
        if (current[index] === connected) {
          return current;
        }

        return current.map((value, position) =>
          position === index ? connected : value
        );
      });
    },
    []
  );

  useEffect(() => {
    const interval = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => window.clearInterval(interval);
  }, []);

  function updateAsset(index: number, symbol: Asset) {
    setAssets((current) =>
      current.map((asset, position) =>
        position === index ? symbol : asset
      )
    );
  }

  function updateEnabled(
    index: number,
    enabled: boolean
  ) {
    setEnabledPanels((current) =>
      current.map((value, position) =>
        position === index ? enabled : value
      )
    );
  }

  const activeCount = enabledPanels.filter(
    Boolean
  ).length;

  const connectedCount = connections.filter(
    (connected, index) =>
      connected && enabledPanels[index]
  ).length;

  return (
    <div className="terminal-app">
      <header className="terminal-topbar">
        <div className="terminal-brand">
          <div className="terminal-logo">
            <Activity size={26} strokeWidth={3} />
          </div>
          <strong>TradePulse</strong>
        </div>

        <nav
          className="top-assets"
          aria-label="Ativos monitorados"
        >
          {assets.map((asset, index) => (
            <div className="top-asset" key={index}>
              <span className="top-flag">
                {assetFlags(asset)}
              </span>

              <div>
                <strong>{displayAsset(asset)}</strong>
                <small>
                  {enabledPanels[index]
                    ? `M1 · Painel ${index + 1} · ON`
                    : `Painel ${index + 1} · NONE`}
                </small>
              </div>
            </div>
          ))}
        </nav>

        <div className="top-status">
          <span className="practice-badge">
            <span className="status-dot" />
            PRACTICE
          </span>

          <span className="top-clock">
            {formatClock(now)}
            <small>UTC</small>
          </span>
        </div>
      </header>

      <div className="terminal-body">
        <aside className="terminal-sidebar">
          <div className="sidebar-item active">
            <Activity size={24} />
            <span>Análise</span>
          </div>

          <div className="sidebar-spacer" />

          <div className="sidebar-bottom">
            <ShieldAlert size={24} />
          </div>
        </aside>

        <main className="terminal-main">
          <div className="signal-grid">
            {assets.map((asset, index) => (
              <SignalPanel
                key={index}
                index={index}
                symbol={asset}
                enabled={enabledPanels[index]}
                onSymbolChange={(next) =>
                  updateAsset(index, next)
                }
                onEnabledChange={(next) =>
                  updateEnabled(index, next)
                }
                onConnectionChange={updateConnection}
              />
            ))}
          </div>

          <footer className="terminal-footer">
            <span className="footer-note">
              <ShieldAlert size={17} />
              Somente leitura. Nenhuma ordem é enviada.
            </span>

            <span className="footer-refresh">
              <RefreshCw size={17} />
              {activeCount === 0
                ? "Todas as análises pausadas"
                : `${activeCount} painel(is) ativo(s) · Atualização: 60s`}
            </span>

            <span className="footer-connection">
              <Activity size={17} />
              {connectedCount}/{activeCount} painéis
              com resposta válida da API
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
