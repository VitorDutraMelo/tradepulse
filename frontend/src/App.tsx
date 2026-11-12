import CandlestickChart from './components/charts/CandlestickChart';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Clock3,
  LayoutDashboard,
  Pause,
  Play,
  RefreshCw,
  ShieldCheck,
  Wifi,
  WifiOff,
} from 'lucide-react';

import {
  getAnalysis,
  isStale,
  number,
  timeUTC,
  type Analysis,
  type Result,
  type Timeframe,
} from './api';

import './style.css';

const ASSETS = [
  'EURUSD-OTC',
  'GBPUSD-OTC',
  'USDJPY-OTC',
  'EURJPY-OTC',
  'EURGBP-OTC',
  'AUDUSD-OTC',
  'USDCAD-OTC',
  'AUDCAD-OTC',
];

type Slot = {
  symbol: string;
  timeframe: Timeframe;
  result: Result | null;
  error: string;
  loading: boolean;
  updated: number | null;
};

const initial = (symbol: string): Slot => ({
  symbol,
  timeframe: '1m',
  result: null,
  error: '',
  loading: false,
  updated: null,
});

const indicatorInfo: {
  key: keyof Analysis['indicators'];
  label: string;
  digits: number;
}[] = [
  { key: 'ema9', label: 'EMA 9', digits: 6 },
  { key: 'ema21', label: 'EMA 21', digits: 6 },
  { key: 'rsi14', label: 'RSI 14', digits: 2 },
  { key: 'adx14', label: 'ADX 14', digits: 2 },
  { key: 'atr14', label: 'ATR 14', digits: 6 },
];

export default function App() {
  const [count, setCount] = useState<1 | 2 | 4>(1);

  const [slots, setSlots] = useState<Slot[]>([
    initial(ASSETS[0]),
    initial(ASSETS[1]),
    initial(ASSETS[2]),
    initial(ASSETS[3]),
  ]);

  const [auto, setAuto] = useState(true);
  const [tick, setTick] = useState(0);
  const [now, setNow] = useState(Date.now());

  const slotsRef = useRef(slots);
  const countRef = useRef(count);
  const generation = useRef(0);
  const running = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const mounted = useRef(false);

  slotsRef.current = slots;
  countRef.current = count;

  const update = useCallback(
    (index: number, change: Partial<Slot>) => {
      setSlots(previous =>
        previous.map((slot, i) =>
          i === index ? { ...slot, ...change } : slot
        )
      );
    },
    []
  );

  const configure = (
    index: number,
    change: Partial<Pick<Slot, 'symbol' | 'timeframe'>>
  ) => {
    generation.current++;
    controller.current?.abort();

    setSlots(previous =>
      previous.map((slot, i) =>
        i === index
          ? {
              ...slot,
              ...change,
              result: null,
              error: '',
              loading: false,
              updated: null,
            }
          : slot
      )
    );

    setTick(t => t + 1);
  };

  const changeCount = (next: 1 | 2 | 4) => {
    generation.current++;
    controller.current?.abort();
    setCount(next);
    setTick(t => t + 1);
  };

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
      generation.current++;
      controller.current?.abort();
    };
  }, []);

  useEffect(() => {
    const interval = window.setInterval(
      () => setNow(Date.now()),
      1000
    );

    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!auto) return;

    const interval = window.setInterval(
      () => setTick(t => t + 1),
      60000
    );

    return () => window.clearInterval(interval);
  }, [auto]);

  useEffect(() => {
    if (running.current) return;

    const currentGeneration = generation.current;

    const run = async () => {
      running.current = true;

      try {
        for (let i = 0; i < countRef.current; i++) {
          if (
            !mounted.current ||
            generation.current !== currentGeneration
          ) {
            break;
          }

          const { symbol, timeframe } = slotsRef.current[i];

          const abort = new AbortController();
          controller.current = abort;

          update(i, {
            loading: true,
            error: '',
          });

          const timeout = window.setTimeout(
            () => abort.abort(),
            15000
          );

          try {
            const result = await getAnalysis(
              symbol,
              timeframe,
              abort.signal
            );

            if (
              mounted.current &&
              generation.current === currentGeneration
            ) {
              update(i, {
                result,
                error: '',
                updated: Date.now(),
              });
            }
          } catch (error) {
            if (
              mounted.current &&
              generation.current === currentGeneration
            ) {
              update(i, {
                result: null,
                error: abort.signal.aborted
                  ? 'Tempo limite ou consulta cancelada.'
                  : error instanceof Error
                    ? error.message
                    : 'Falha na consulta.',
              });
            }
          } finally {
            window.clearTimeout(timeout);

            if (
              mounted.current &&
              generation.current === currentGeneration
            ) {
              update(i, { loading: false });
            }
          }
        }
      } finally {
        running.current = false;
        controller.current = null;

        if (
          mounted.current &&
          generation.current !== currentGeneration
        ) {
          setTick(t => t + 1);
        }
      }
    };

    void run();
  }, [tick, update]);

  const visible = slots.slice(0, count);

  return (
    <div className="tp-shell">
      <aside className="tp-sidebar">
        <div className="tp-brand">
          <span className="tp-logo">
            <Activity size={23} />
          </span>

          <span>
            Trade<span className="tp-accent">Pulse</span>
            <small>MARKET INTELLIGENCE</small>
          </span>
        </div>

        <div className="tp-side-label">WORKSPACE</div>

        <div className="tp-side-active">
          <LayoutDashboard size={18} />
          Dashboard
        </div>

        <div className="tp-side-label tp-side-bottom">
          AMBIENTE
        </div>

        <div className="tp-side-note">
          <ShieldCheck size={17} />
          IQ Option · PRACTICE
        </div>

        <p className="tp-side-disclaimer">
          Análise informativa. Nenhuma ordem é executada.
        </p>
      </aside>

      <div className="tp-content">
        <header className="tp-header">
          <div className="tp-mobile-brand">
            <Activity size={20} />
            Trade<span className="tp-accent">Pulse</span>
          </div>

          <div className="tp-header-title">
            <span className="tp-eyebrow">
              TRADEPULSE / WORKSPACE
            </span>

            <h1>Market Overview</h1>

            <p>Análise técnica · IQ Option DEMO</p>
          </div>

          <div className="tp-header-right">
            <span
              className={`tp-api-connection ${
                slots.slice(0, count).some(slot => slot.error)
                  ? 'offline'
                  : slots.slice(0, count).some(slot => slot.updated !== null)
                    ? 'online'
                    : 'unknown'
              }`}
              title={
                slots.slice(0, count).some(slot => slot.error)
                  ? 'Falha na última consulta à API'
                  : slots.slice(0, count).some(slot => slot.updated !== null)
                    ? 'Última consulta à API realizada com sucesso'
                    : 'Aguardando resposta da API'
              }
              aria-label="Estado da API de análise"
            >
              {slots.slice(0, count).some(slot => slot.error)
                ? <WifiOff size={19} />
                : <Wifi size={19} />}
            </span>

            <span className="tp-clock">
              <Clock3 size={15} />
              {new Date(now).toLocaleTimeString('pt-BR', {
                timeZone: 'UTC',
                hour12: false,
              })} UTC
            </span>
          </div>
        </header>

        <main className="tp-main">
          <div className="tp-toolbar">
            <div>
              <span className="tp-eyebrow">
                PAINEL DE ANÁLISES
              </span>

              <h2>Visão de mercado</h2>
            </div>

            <div className="tp-tools">
              <div
                className="tp-segment"
                aria-label="Quantidade de painéis"
              >
                {([1, 2, 4] as const).map(n => (
                  <button
                    key={n}
                    className={count === n ? 'selected' : ''}
                    onClick={() => changeCount(n)}
                  >
                    {n} {n === 1 ? 'painel' : 'painéis'}
                  </button>
                ))}
              </div>

              <button
                className="tp-icon-button"
                title={
                  auto
                    ? 'Pausar atualizações'
                    : 'Retomar atualizações'
                }
                onClick={() => setAuto(v => !v)}
              >
                {auto
                  ? <Pause size={17} />
                  : <Play size={17} />}

                <span>{auto ? 'Auto' : 'Pausado'}</span>
              </button>

              <button
                className="tp-icon-button"
                title="Atualizar agora"
                onClick={() => {
                  generation.current++;
                  controller.current?.abort();
                  setTick(t => t + 1);
                }}
              >
                <RefreshCw size={17} />
                <span>Atualizar</span>
              </button>
            </div>
          </div>

          <div className={`tp-grid tp-grid-${count}`}>
            {visible.map((slot, i) => {
              const analysis = slot.result?.analysis;

              const freshness = analysis
                ? isStale(analysis, now)
                : {
                    stale: true,
                    reason: 'Aguardando análise',
                  };

              const valid = Boolean(
                analysis &&
                !freshness.stale &&
                !slot.error
              );

              const action = valid
                ? analysis!.action
                : 'WAIT';

              return (
                <article className="tp-market" key={i}>
                  <div className="tp-market-top">
                    <div>
                      <span className="tp-eyebrow">
                        MERCADO / {i + 1}
                      </span>

                      <h3>
                        {slot.symbol.replace('-OTC', '')}
                        {' '}
                        <span>OTC</span>
                      </h3>
                    </div>

                    <span
                      className={`tp-status ${valid ? 'ok' : ''}`}
                    >
                      {slot.loading
                        ? 'Consultando'
                        : slot.error
                          ? 'Indisponível'
                          : valid
                            ? 'Atualizado'
                            : 'Sem sinal atual'}
                    </span>
                  </div>

                  <div className="tp-selectors">
                    <label>
                      Ativo

                      <select
                        value={slot.symbol}
                        onChange={event =>
                          configure(i, {
                            symbol: event.target.value,
                          })
                        }
                      >
                        {ASSETS.map(asset => (
                          <option key={asset} value={asset}>
                            {asset}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label>
                      Período

                      <select
                        value={slot.timeframe}
                        onChange={event =>
                          configure(i, {
                            timeframe: event.target.value as Timeframe,
                          })
                        }
                      >
                        <option value="1m">M1</option>
                        <option value="5m">M5</option>
                      </select>
                    </label>
                  </div>

                  <div className="tp-primary">
                    <section className="tp-chart">
                      <div className="tp-section-head">
                        <span>
                          <BarChart3 size={16} />
                          Gráfico de candles
                        </span>

                        <span className="tp-muted">
                          IQ OPTION · {slot.timeframe.toUpperCase()}
                        </span>
                      </div>

                      <CandlestickChart symbol={slot.symbol} timeframe={slot.timeframe} />
                    </section>

                    <section
                      className={`tp-signal ${
                        valid ? action.toLowerCase() : 'wait'
                      }`}
                    >
                      <span className="tp-eyebrow">
                        SINAL DA ANÁLISE
                      </span>

                      <div className="tp-action">
                        {slot.loading && !analysis
                          ? '...'
                          : valid
                            ? action
                            : '—'}
                      </div>

                      <div className="tp-signal-desc">
                        {slot.error
                          ? slot.error
                          : !valid
                            ? freshness.reason
                            : action === 'CALL'
                              ? 'Cenário de alta'
                              : action === 'PUT'
                                ? 'Cenário de baixa'
                                : 'Aguardar confirmação'}
                      </div>

                      <div className="tp-signal-details">
                        <div>
                          <span>Preço de referência</span>

                          <strong>
                            {valid
                              ? number(analysis?.reference.price)
                              : '—'}
                          </strong>
                        </div>

                        <div>
                          <span>Entrada</span>

                          <strong>
                            {valid
                              ? timeUTC(
                                  analysis?.reference.entryTime
                                )
                              : '—'}
                          </strong>
                        </div>

                        <div>
                          <span>Expiração</span>

                          <strong>
                            {valid
                              ? timeUTC(
                                  analysis?.reference.expirationTime
                                )
                              : '—'}
                          </strong>
                        </div>
                      </div>

                      <div className="tp-signal-footer">
                        <ShieldCheck size={15} />
                        Somente análise · Sem execução
                      </div>
                    </section>
                  </div>

                  <section className="tp-indicators">
                    <div className="tp-section-head">
                      <span>
                        <Activity size={16} />
                        Indicadores técnicos
                      </span>

                      <span className="tp-muted">
                        Último candle fechado
                      </span>
                    </div>

                    <div className="tp-indicator-grid">
                      {indicatorInfo.map(item => (
                        <div
                          className="tp-indicator"
                          key={item.key}
                        >
                          <span>{item.label}</span>

                          <strong>
                            {valid
                              ? number(
                                  analysis?.indicators[item.key],
                                  item.digits
                                )
                              : '—'}
                          </strong>
                        </div>
                      ))}
                    </div>
                  </section>

                  <div className="tp-lower">
                    <section className="tp-reasons">
                      <div className="tp-section-head">
                        <span>
                          <CheckCircle2 size={16} />
                          Motivos da análise
                        </span>
                      </div>

                      {valid && analysis?.reasons.length
                        ? (
                          <ul>
                            {analysis.reasons.map(
                              (reason, index) => (
                                <li key={index}>
                                  {reason}
                                </li>
                              )
                            )}
                          </ul>
                        )
                        : (
                          <p className="tp-muted">
                            {slot.error ||
                              'Motivos disponíveis após uma análise válida.'}
                          </p>
                        )}
                    </section>

                    <section className="tp-meta">
                      <div className="tp-section-head">
                        <span>
                          <Clock3 size={16} />
                          Dados e referência
                        </span>
                      </div>

                      <dl>
                        <div>
                          <dt>Fonte</dt>
                          <dd>{analysis?.source ?? '—'}</dd>
                        </div>

                        <div>
                          <dt>Conta</dt>
                          <dd>{analysis?.accountMode ?? '—'}</dd>
                        </div>

                        <div>
                          <dt>Última análise</dt>
                          <dd>
                            {timeUTC(analysis?.analysisAt)}
                          </dd>
                        </div>

                        <div>
                          <dt>Candle fechado</dt>
                          <dd>
                            {timeUTC(
                              analysis?.lastClosedCandle.closeTime
                            )}
                          </dd>
                        </div>

                        <div>
                          <dt>Consulta HTTP</dt>
                          <dd>
                            {slot.updated
                              ? timeUTC(
                                  new Date(
                                    slot.updated
                                  ).toISOString()
                                )
                              : '—'}
                          </dd>
                        </div>
                      </dl>
                    </section>
                  </div>

                  <details className="tp-json">
                    <summary>
                      Ver resposta técnica JSON
                    </summary>

                    <pre>
                      {slot.result
                        ? JSON.stringify(
                            slot.result.raw,
                            null,
                            2
                          )
                        : 'Sem resposta disponível.'}
                    </pre>
                  </details>
                </article>
              );
            })}
          </div>


        </main>
      </div>
    </div>
  );
}
