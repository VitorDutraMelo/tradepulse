import "./style.css";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity, ArrowDownRight, ArrowUpRight, Check, Clipboard, Clock3,
  Code2, LoaderCircle, Pause, RefreshCw, ShieldAlert, Timer,
  TrendingUp, Wifi, WifiOff, ChartNoAxesColumnIncreasing,
} from "lucide-react";
import {
  getAnalysis, getReferenceMessage, getReferencePhase, isStale,
  number, timeUTC, type Result,
} from "./api";

const ASSETS = [
  "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "EURJPY-OTC",
  "EURGBP-OTC", "AUDUSD-OTC", "USDCAD-OTC", "AUDCAD-OTC",
] as const;

type Timeframe = "1m" | "5m";
type Layout = 1 | 2 | 4;
type QueueStatus =
  | "Na fila"
  | "Analisando"
  | "Dados recebidos"
  | "Erro na análise";

type PanelConfig = {
  id: number;
  symbol: string;
  timeframe: Timeframe;
};

type PanelData = {
  result: Result | null;
  error: string;
  status: QueueStatus;
  fetchedAt: number | null;
};

const DEFAULTS: PanelConfig[] = [
  { id: 1, symbol: "EURUSD-OTC", timeframe: "1m" },
  { id: 2, symbol: "GBPUSD-OTC", timeframe: "1m" },
  { id: 3, symbol: "USDJPY-OTC", timeframe: "5m" },
  { id: 4, symbol: "EURJPY-OTC", timeframe: "5m" },
];

const REFRESH_MS = 60_000;
const TIMEOUT_MS = 15_000;

const INDICATORS = [
  { key: "ema9", label: "EMA 9", color: "#1595f5", digits: 6 },
  { key: "ema21", label: "EMA 21", color: "#9854ef", digits: 6 },
  { key: "rsi14", label: "RSI 14", color: "#f4d51b", digits: 2 },
  { key: "adx14", label: "ADX 14", color: "#00d96a", digits: 2 },
  { key: "atr14", label: "ATR 14", color: "#0edddd", digits: 6 },
] as const;

function emptyData(): PanelData {
  return {
    result: null,
    error: "",
    status: "Na fila",
    fetchedAt: null,
  };
}

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

function SignalPanel({
  config,
  data,
  now,
  onChange,
  onCopy,
}: {
  config: PanelConfig;
  data: PanelData;
  now: number;
  onChange: (
    id: number,
    patch: Partial<Pick<PanelConfig, "symbol" | "timeframe">>
  ) => void;
  onCopy: (id: number) => void;
}) {
  const analysis =
    data.result?.analysis.symbol === config.symbol &&
    data.result.analysis.timeframe === config.timeframe
      ? data.result.analysis
      : undefined;

  const freshness = analysis
    ? isStale(analysis, now)
    : { stale: true, reason: "Sem análise atual" };

  const available = Boolean(
    analysis && !freshness.stale && !data.error
  );

  const action = available ? analysis!.action : null;

  const phase = analysis
    ? getReferencePhase(analysis, now)
    : "invalid";

  const phaseText =
    analysis && !freshness.stale
      ? getReferenceMessage(phase)
      : freshness.reason;

  const mode =
    action === "CALL"
      ? "call"
      : action === "PUT"
        ? "put"
        : "wait";

  const isExpired = phase === "expired";
  const isWaiting = action === "WAIT";

  const signalSubtitle = data.error
    ? "Análise indisponível"
    : data.status === "Na fila"
      ? "Na fila de análise"
      : data.status === "Analisando"
        ? `Analisando ${config.symbol}...`
        : !available
          ? freshness.reason
          : isExpired
            ? "Sinal expirado — não utilizar como entrada"
            : isWaiting
              ? "Aguardar confirmação"
              : action === "CALL"
                ? "Cenário de alta identificado"
                : "Cenário de baixa identificado";

  return (
    <article className="tradePanel">
      <div className="panelControls">
        <div className="panelHeading">
          <strong>Painel {config.id}</strong>
          <span
            className={`queueBadge ${
              data.status === "Erro na análise"
                ? "queueError"
                : data.status === "Dados recebidos"
                  ? "queueDone"
                  : ""
            }`}
            aria-live="polite"
          >
            {data.status === "Analisando" && (
              <LoaderCircle className="spin" size={14} />
            )}
            {data.status}
          </span>
        </div>

        <div className="panelSelects">
          <div className="marketField">
            <label htmlFor={`asset-${config.id}`}>Ativo</label>
            <select
              id={`asset-${config.id}`}
              value={config.symbol}
              onChange={(event) =>
                onChange(config.id, {
                  symbol: event.target.value,
                })
              }
            >
              {ASSETS.map((asset) => (
                <option key={asset} value={asset}>
                  {asset}
                </option>
              ))}
            </select>
          </div>

          <div className="marketField">
            <label htmlFor={`timeframe-${config.id}`}>
              Velas / Timeframe
            </label>
            <select
              id={`timeframe-${config.id}`}
              value={config.timeframe}
              onChange={(event) =>
                onChange(config.id, {
                  timeframe: event.target.value as Timeframe,
                })
              }
            >
              <option value="1m">M1 - 1 minuto</option>
              <option value="5m">M5 - 5 minutos</option>
            </select>
          </div>
        </div>
      </div>

      {data.error && (
        <div className="error" role="alert">
          <ShieldAlert size={19} />
          <div>
            <strong>
              Falha na análise de {config.symbol}
            </strong>
            <p>{data.error}</p>
          </div>
        </div>
      )}

      <div className="panelContent">
        <section className="signalCard panel">
          <div
            className={`signalHero ${mode} ${
              !available || isExpired ? "inactive" : ""
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
                {action ??
                  (data.status === "Analisando" ? "..." : "—")}
              </strong>
            </div>

            <div className="signalSubtitle">
              {signalSubtitle}
            </div>
          </div>

          <div className="details">
            <Info label="Ativo" value={config.symbol} />
            <Info
              label="Timeframe"
              value={
                config.timeframe === "1m"
                  ? "M1 (1 minuto)"
                  : "M5 (5 minutos)"
              }
            />
            <Info
              label="Conta"
              value={analysis?.accountMode ?? "—"}
            />
            <Info
              label="Fonte"
              value={analysis?.source ?? "—"}
            />
            <Info
              label="Última análise"
              value={timeUTC(analysis?.analysisAt)}
            />
            <Info
              label="Último candle fechado"
              value={
                analysis?.lastClosedCandle
                  ? `${timeUTC(
                      analysis.lastClosedCandle.openTime
                    )} → ${timeUTC(
                      analysis.lastClosedCandle.closeTime
                    )}`
                  : "—"
              }
            />
            <Info
              label="Entrada de referência"
              value={timeUTC(
                analysis?.reference?.entryTime
              )}
            />
            <Info
              label="Vencimento"
              value={timeUTC(
                analysis?.reference?.expirationTime
              )}
            />
            <Info
              label="Preço de referência"
              value={number(
                analysis?.reference?.price
              )}
            />
          </div>

          <div
            className={`referenceStatus ${
              !analysis || freshness.stale
                ? "unavailable"
                : phase === "before"
                  ? "pending"
                  : phase === "during"
                    ? "running"
                    : phase === "expired"
                      ? "expired"
                      : "waiting"
            }`}
            role="status"
          >
            <Clock3 size={19} />
            <div>
              <strong>{phaseText}</strong>
              <p>
                Horários exibidos em UTC. Referência
                informativa, não é uma ordem.
              </p>
            </div>
          </div>
        </section>

        <section className="rightColumn">
          <div className="panel indicators">
            <h2>
              <ChartNoAxesColumnIncreasing />
              Indicadores
            </h2>

            <div className="indicatorGrid">
              {INDICATORS.map((item) => (
                <div
                  className="indicator"
                  key={item.key}
                >
                  <span>{item.label}</span>
                  <strong>
                    {number(
                      analysis?.indicators[item.key],
                      item.digits
                    )}
                  </strong>
                  <div
                    className="indicatorLine"
                    style={{
                      background: item.color,
                    }}
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

            {analysis?.reasons.length ? (
              <ul>
                {analysis.reasons.map(
                  (reason, index) => (
                    <li key={index}>
                      <Check size={17} />
                      <span>{reason}</span>
                    </li>
                  )
                )}
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
                <span className="muted">
                  Ver resposta JSON
                </span>
              </summary>

              <div className="jsonActions">
                <button
                  className="secondary"
                  disabled={!analysis}
                  onClick={() => onCopy(config.id)}
                >
                  <Clipboard size={16} />
                  Copiar JSON
                </button>
              </div>

              <pre>
                {analysis
                  ? JSON.stringify(
                      data.result?.raw,
                      null,
                      2
                    )
                  : "Nenhuma resposta disponível."}
              </pre>
            </details>
          </div>

          <div className="panel metadata">
            <span>
              <Clock3 size={16} />
              Última atualização:{" "}
              {data.fetchedAt
                ? timeUTC(
                    new Date(
                      data.fetchedAt
                    ).toISOString()
                  )
                : "—"}
            </span>

            <span>
              {freshness.stale
                ? freshness.reason
                : "Análise recebida"}
            </span>
          </div>
        </section>
      </div>

      <p className="panelDisclaimer">
        TradePulse é uma ferramenta informativa.
        Nenhuma ordem é enviada.
        Sinais não garantem resultados.{" "}
        {analysis?.disclaimer ?? ""}
      </p>
    </article>
  );
}

export default function App() {
  const [layout, setLayout] = useState<Layout>(1);

  const [configs, setConfigs] =
    useState<PanelConfig[]>(DEFAULTS);

  const [data, setData] = useState<
    Record<number, PanelData>
  >({
    1: emptyData(),
    2: emptyData(),
    3: emptyData(),
    4: emptyData(),
  });

  const [auto, setAuto] = useState(true);
  const [refreshId, setRefreshId] = useState(0);
  const [now, setNow] = useState(Date.now());

  const generationRef = useRef(0);

  const queueTailRef = useRef<Promise<void>>(
    Promise.resolve()
  );

  const controllerRef =
    useRef<AbortController | null>(null);

  const timerRef = useRef<number | null>(null);

  const autoRef = useRef(auto);
  autoRef.current = auto;

  const updatePanel = useCallback(
    (
      id: number,
      patch: Partial<
        Pick<PanelConfig, "symbol" | "timeframe">
      >
    ) => {
      setConfigs((previous) =>
        previous.map((config) =>
          config.id === id
            ? { ...config, ...patch }
            : config
        )
      );
    },
    []
  );

  const updateData = useCallback(
    (
      id: number,
      patch: Partial<PanelData>
    ) => {
      setData((previous) => ({
        ...previous,
        [id]: {
          ...previous[id],
          ...patch,
        },
      }));
    },
    []
  );

  useEffect(() => {
    const interval = window.setInterval(
      () => setNow(Date.now()),
      1000
    );

    return () =>
      window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!auto && timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    if (auto && timerRef.current === null) {
      timerRef.current = window.setTimeout(
        () => {
          timerRef.current = null;
          setRefreshId(
            (previous) => previous + 1
          );
        },
        REFRESH_MS
      );
    }
  }, [auto]);

  useEffect(() => {
    const generation =
      ++generationRef.current;

    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
    }

    timerRef.current = null;
    controllerRef.current?.abort();

    const selected = configs
      .slice(0, layout)
      .map((config) => ({ ...config }));

    setData((previous) => {
      const next = { ...previous };

      selected.forEach((config) => {
        next[config.id] = emptyData();
      });

      return next;
    });

    const run = async () => {
      if (
        generation !== generationRef.current
      ) {
        return;
      }

      const seen = new Map<
        string,
        PanelData
      >();

      for (const config of selected) {
        if (
          generation !==
          generationRef.current
        ) {
          break;
        }

        const key =
          `${config.symbol}:${config.timeframe}`;

        const cached = seen.get(key);

        if (cached) {
          updateData(config.id, cached);
          continue;
        }

        updateData(config.id, {
          status: "Analisando",
          error: "",
        });

        const controller =
          new AbortController();

        controllerRef.current = controller;

        let timedOut = false;

        const timeout = window.setTimeout(
          () => {
            timedOut = true;
            controller.abort();
          },
          TIMEOUT_MS
        );

        let next: PanelData;

        try {
          const result = await getAnalysis(
            config.symbol,
            config.timeframe,
            controller.signal
          );

          next = {
            result,
            error: "",
            status: "Dados recebidos",
            fetchedAt: Date.now(),
          };
        } catch (error) {
          next = {
            result: null,
            error: timedOut
              ? `Tempo limite de ${
                  TIMEOUT_MS / 1000
                }s ao analisar ${config.symbol}.`
              : error instanceof Error
                ? error.message
                : `Falha na análise de ${config.symbol}.`,
            status: "Erro na análise",
            fetchedAt: null,
          };
        } finally {
          window.clearTimeout(timeout);

          if (
            controllerRef.current ===
            controller
          ) {
            controllerRef.current = null;
          }
        }

        if (
          generation !==
          generationRef.current
        ) {
          break;
        }

        seen.set(key, next);
        updateData(config.id, next);
      }

      if (
        generation ===
          generationRef.current &&
        autoRef.current
      ) {
        if (timerRef.current !== null) {
          window.clearTimeout(
            timerRef.current
          );
        }

        timerRef.current =
          window.setTimeout(() => {
            timerRef.current = null;

            setRefreshId(
              (previous) => previous + 1
            );
          }, REFRESH_MS);
      }
    };

    // Uma unica fila compartilhada.
    // Nenhum ciclo inicia outra requisicao
    // antes de o ciclo anterior terminar.
    queueTailRef.current =
      queueTailRef.current
        .then(run, run)
        .then(
          () => {},
          () => {}
        );

    return () => {
      ++generationRef.current;
      controllerRef.current?.abort();

      if (timerRef.current !== null) {
        window.clearTimeout(
          timerRef.current
        );
      }

      timerRef.current = null;
    };
  }, [
    layout,
    configs,
    refreshId,
    updateData,
  ]);

  const copyJSON = useCallback(
    async (id: number) => {
      const raw = data[id]?.result?.raw;

      if (
        raw === undefined ||
        raw === null
      ) {
        return;
      }

      try {
        await navigator.clipboard.writeText(
          JSON.stringify(raw, null, 2)
        );
      } catch {
        // Clipboard pode estar indisponivel.
      }
    },
    [data]
  );

  const visible = configs.slice(0, layout);

  const statuses = visible.map(
    (config) =>
      data[config.id]?.status ?? "Na fila"
  );

  const analyzing =
    statuses.includes("Analisando");

  const hasErrors =
    statuses.includes("Erro na análise");

  const completed = statuses.every(
    (status) =>
      status === "Dados recebidos"
  );

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

          <div
            className={`pill status ${
              completed
                ? "online"
                : "offline"
            }`}
          >
            {completed ? (
              <Wifi size={17} />
            ) : (
              <WifiOff size={17} />
            )}

            {analyzing
              ? "Analisando em sequência"
              : hasErrors
                ? "Erro na análise"
                : completed
                  ? "Dados recebidos"
                  : "Na fila"}
          </div>
        </div>
      </header>

      <div className="marketSelector dashboardControls">
        <div className="marketField">
          <label htmlFor="layout-select">
            Visualização
          </label>

          <select
            id="layout-select"
            value={layout}
            onChange={(event) =>
              setLayout(
                Number(
                  event.target.value
                ) as Layout
              )
            }
          >
            <option value={1}>1 painel</option>
            <option value={2}>2 painéis</option>
            <option value={4}>4 painéis</option>
          </select>
        </div>

        <div className="marketField">
          <span>Fonte</span>
          <strong>
            IQ Option DEMO · PRACTICE
          </strong>
        </div>
      </div>

      <div className="toolbar">
        <div className="toolbarText">
          <span className="eyebrow">
            MONITORAMENTO DE MERCADO
          </span>
          <p>
            Somente leitura · Fila sequencial ·
            Nenhuma ordem é enviada
          </p>
        </div>

        <div className="actions">
          <button
            className={`secondary ${
              auto ? "selected" : ""
            }`}
            onClick={() =>
              setAuto((value) => !value)
            }
          >
            {auto ? (
              <Activity size={16} />
            ) : (
              <Pause size={16} />
            )}

            Auto{" "}
            {auto ? "ligado" : "desligado"}{" "}
            (60s)
          </button>

          <button
            className="primary"
            onClick={() =>
              setRefreshId(
                (previous) => previous + 1
              )
            }
            disabled={analyzing}
          >
            <RefreshCw size={16} />
            Atualizar todos
          </button>
        </div>
      </div>

      <main
        className={`multiLayout layout-${layout}`}
      >
        {visible.map((config) => (
          <SignalPanel
            key={config.id}
            config={config}
            data={
              data[config.id] ??
              emptyData()
            }
            now={now}
            onChange={updatePanel}
            onCopy={copyJSON}
          />
        ))}
      </main>

      <footer>
        <TrendingUp size={16} />
        TradePulse é uma ferramenta
        informativa. Nenhuma ordem é
        enviada. Sinais não garantem
        resultados.
      </footer>
    </div>
  );
}
