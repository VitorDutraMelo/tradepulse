import CandlestickChart from './components/charts/CandlestickChart';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Clock3,
  FlaskConical,
  LayoutDashboard,
  Pause,
  Play,
  RefreshCw,
  ShieldCheck,
  Wifi,
  WifiOff,
} from 'lucide-react';

import { number, timeUTC } from './api';
import {
  DATA_STATE_LABEL,
  GATEWAY_ERROR_LABEL,
  SIGNAL_STATUS_LABEL,
  formatMs,
  getLive,
  LiveRequestError,
  type LiveResult,
  type LiveTimeframe,
  type LiveView,
} from './live';

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

/** The experimental M5 engine is limited to GBPUSD-OTC (decision N.10). */
const M5_ENGINE_ASSETS = ['GBPUSD-OTC'];

/**
 * Reads only the local backend, which publishes once per closed candle.
 * A short interval lets the panel show a new candle seconds after it closes
 * without causing any extra IQ Option request.
 */
const LIVE_POLL_MS = 2000;
const REQUEST_TIMEOUT_MS = 15000;

type Slot = {
  symbol: string;
  timeframe: LiveTimeframe;
  result: LiveResult | null;
  error: string;
  errorCode: string | null;
  loading: boolean;
  updated: number | null;
};

const initial = (symbol: string): Slot => ({
  symbol,
  timeframe: '1m',
  result: null,
  error: '',
  errorCode: null,
  loading: false,
  updated: null,
});

const INDICATORS: Record<LiveTimeframe, { key: string; label: string; digits: number }[]> = {
  '1m': [
    { key: 'ema9', label: 'EMA 9', digits: 6 },
    { key: 'ema21', label: 'EMA 21', digits: 6 },
    { key: 'rsi14', label: 'RSI 14', digits: 2 },
    { key: 'adx14', label: 'ADX 14', digits: 2 },
    { key: 'atr14', label: 'ATR 14', digits: 6 },
  ],
  '5m': [
    { key: 'ema200', label: 'EMA 200', digits: 6 },
    { key: 'rsi14', label: 'RSI 14', digits: 2 },
    { key: 'macd', label: 'MACD', digits: 6 },
    { key: 'macdSignal', label: 'Sinal MACD', digits: 6 },
    { key: 'macdHistogram', label: 'Histograma', digits: 6 },
    { key: 'adx14', label: 'ADX 14', digits: 2 },
    { key: 'atr14', label: 'ATR 14', digits: 6 },
  ],
};

function errorText(slot: Slot): string {
  return (slot.errorCode && GATEWAY_ERROR_LABEL[slot.errorCode]) || slot.error;
}

function connectionState(views: LiveView[], slots: Slot[]): 'online' | 'offline' | 'unknown' {
  if (slots.some((slot) => slot.errorCode === 'BACKEND_UNREACHABLE')) return 'offline';
  const session = views.find((view) => view.gateway.sessionState)?.gateway.sessionState;
  if (session === 'CONNECTED') return 'online';
  if (session || views.some((view) => view.lastError)) return 'offline';
  return 'unknown';
}

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

  const update = useCallback((index: number, change: Partial<Slot>) => {
    setSlots((previous) =>
      previous.map((slot, i) => (i === index ? { ...slot, ...change } : slot)),
    );
  }, []);

  const configure = (index: number, change: Partial<Pick<Slot, 'symbol' | 'timeframe'>>) => {
    generation.current++;
    controller.current?.abort();

    setSlots((previous) =>
      previous.map((slot, i) =>
        i === index
          ? { ...slot, ...change, result: null, error: '', errorCode: null, loading: false, updated: null }
          : slot,
      ),
    );

    setTick((t) => t + 1);
  };

  const changeCount = (next: 1 | 2 | 4) => {
    generation.current++;
    controller.current?.abort();
    setCount(next);
    setTick((t) => t + 1);
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
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!auto) return;
    const interval = window.setInterval(() => setTick((t) => t + 1), LIVE_POLL_MS);
    return () => window.clearInterval(interval);
  }, [auto]);

  useEffect(() => {
    if (running.current) return;

    const currentGeneration = generation.current;

    const run = async () => {
      running.current = true;

      try {
        for (let i = 0; i < countRef.current; i++) {
          if (!mounted.current || generation.current !== currentGeneration) break;

          const { symbol, timeframe } = slotsRef.current[i];
          const abort = new AbortController();
          controller.current = abort;
          update(i, { loading: true });

          const timeout = window.setTimeout(() => abort.abort(), REQUEST_TIMEOUT_MS);

          try {
            const result = await getLive(symbol, timeframe, abort.signal);

            if (mounted.current && generation.current === currentGeneration) {
              update(i, { result, error: '', errorCode: null, updated: Date.now() });
            }
          } catch (error) {
            if (mounted.current && generation.current === currentGeneration) {
              update(i, {
                result: null,
                errorCode: error instanceof LiveRequestError ? error.code : null,
                error: abort.signal.aborted
                  ? 'Tempo limite ou consulta cancelada.'
                  : error instanceof Error
                    ? error.message
                    : 'Falha na consulta.',
              });
            }
          } finally {
            window.clearTimeout(timeout);
            if (mounted.current && generation.current === currentGeneration) {
              update(i, { loading: false });
            }
          }
        }
      } finally {
        running.current = false;
        controller.current = null;

        if (mounted.current && generation.current !== currentGeneration) {
          setTick((t) => t + 1);
        }
      }
    };

    void run();
  }, [tick, update]);

  const visible = slots.slice(0, count);
  const views = visible.map((slot) => slot.result?.view).filter((view): view is LiveView => !!view);
  const connection = connectionState(views, visible);
  const gateway = views[0]?.gateway;

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

        <div className="tp-side-label tp-side-bottom">AMBIENTE</div>

        <div className="tp-side-note">
          <ShieldCheck size={17} />
          IQ Option · PRACTICE
        </div>

        <p className="tp-side-disclaimer">
          Análise informativa e experimental. Nenhuma ordem é executada.
        </p>
      </aside>

      <div className="tp-content">
        <header className="tp-header">
          <div className="tp-mobile-brand">
            <Activity size={20} />
            Trade<span className="tp-accent">Pulse</span>
          </div>

          <div className="tp-header-title">
            <span className="tp-eyebrow">TRADEPULSE / WORKSPACE</span>
            <h1>Market Overview</h1>
            <p>Análise técnica · IQ Option DEMO</p>
          </div>

          <div className="tp-header-right">
            <span
              className={`tp-api-connection ${connection}`}
              title={
                connection === 'online'
                  ? 'Sessão IQ Option PRACTICE conectada'
                  : connection === 'offline'
                    ? `Sem conexão: ${gateway?.lastErrorCode ?? visible.find((s) => s.errorCode)?.errorCode ?? 'erro'}`
                    : 'Aguardando estado da conexão'
              }
              aria-label="Estado da conexão IQ Option"
            >
              {connection === 'offline' ? <WifiOff size={19} /> : <Wifi size={19} />}
            </span>

            <span className="tp-clock">
              <Clock3 size={15} />
              {new Date(now).toLocaleTimeString('pt-BR', { timeZone: 'UTC', hour12: false })} UTC
            </span>
          </div>
        </header>

        <main className="tp-main">
          <div className="tp-toolbar">
            <div>
              <span className="tp-eyebrow">PAINEL DE ANÁLISES</span>
              <h2>Visão de mercado</h2>
              <p className="tp-connection-line">
                Sessão IQ: <strong>{gateway?.sessionState ?? '—'}</strong>
                {' · '}Conta: <strong>{gateway?.accountMode ?? '—'}</strong>
                {' · '}Worker: <strong>{gateway?.workerState ?? '—'}</strong>
                {gateway?.nextReconnectAt ? ` · nova tentativa ${timeUTC(gateway.nextReconnectAt)}` : ''}
              </p>
            </div>

            <div className="tp-tools">
              <div className="tp-segment" aria-label="Quantidade de painéis">
                {([1, 2, 4] as const).map((n) => (
                  <button key={n} className={count === n ? 'selected' : ''} onClick={() => changeCount(n)}>
                    {n} {n === 1 ? 'painel' : 'painéis'}
                  </button>
                ))}
              </div>

              <button
                className="tp-icon-button"
                title={auto ? 'Pausar atualizações' : 'Retomar atualizações'}
                onClick={() => setAuto((v) => !v)}
              >
                {auto ? <Pause size={17} /> : <Play size={17} />}
                <span>{auto ? 'Auto' : 'Pausado'}</span>
              </button>

              <button
                className="tp-icon-button"
                title="Atualizar agora"
                onClick={() => {
                  generation.current++;
                  controller.current?.abort();
                  setTick((t) => t + 1);
                }}
              >
                <RefreshCw size={17} />
                <span>Atualizar</span>
              </button>
            </div>
          </div>

          <div className={`tp-grid tp-grid-${count}`}>
            {visible.map((slot, i) => {
              const view = slot.result?.view;
              const publication = view?.publication ?? null;
              const signal = publication?.signal;
              const timing = publication?.timing;
              const current = view?.dataState === 'CURRENT' && !slot.error;
              const status = signal?.status;
              const showAction = current && (status === 'EXPERIMENTAL_CANDIDATE' || status === 'WAIT');
              const action = showAction ? signal!.action : 'WAIT';
              const indicators = (publication?.analysis.indicators ?? {}) as Record<string, number | null>;
              const m5Unavailable = slot.timeframe === '5m' && !M5_ENGINE_ASSETS.includes(slot.symbol);
              const context = publication?.analysis.contextM15 as
                | { trend?: string; structure?: string; state?: string }
                | undefined;

              const description = m5Unavailable
                ? 'O motor M5 experimental está disponível apenas para GBPUSD-OTC.'
                : slot.error
                  ? errorText(slot)
                  : view?.lastError && !current
                    ? GATEWAY_ERROR_LABEL[view.lastError.code] ?? view.lastError.message
                    : !publication
                      ? 'Aguardando a primeira análise publicada.'
                      : view?.dataState !== 'CURRENT'
                        ? `${DATA_STATE_LABEL[view!.dataState]}: vela de ${timeUTC(view!.expectedLatestCloseTime)} ainda não publicada.`
                        : status === 'LATE_NOT_ACTIONABLE' || status === 'EXPIRED'
                          ? `${SIGNAL_STATUS_LABEL[status]} (candidato ${signal!.action}).`
                          : SIGNAL_STATUS_LABEL[status!];

              return (
                <article className="tp-market" key={i}>
                  <div className="tp-market-top">
                    <div>
                      <span className="tp-eyebrow">MERCADO / {i + 1}</span>
                      <h3>
                        {slot.symbol.replace('-OTC', '')} <span>OTC</span>
                      </h3>
                    </div>

                    <span className={`tp-status ${current ? 'ok' : ''}`}>
                      {slot.loading && !view
                        ? 'Consultando'
                        : slot.error
                          ? 'Indisponível'
                          : view
                            ? DATA_STATE_LABEL[view.dataState]
                            : 'Sem dados'}
                    </span>
                  </div>

                  <div className="tp-selectors">
                    <label>
                      Ativo
                      <select value={slot.symbol} onChange={(event) => configure(i, { symbol: event.target.value })}>
                        {ASSETS.map((asset) => (
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
                        onChange={(event) => configure(i, { timeframe: event.target.value as LiveTimeframe })}
                      >
                        <option value="1m">M1</option>
                        <option value="5m">M5 (experimental)</option>
                      </select>
                    </label>
                  </div>

                  <div className="tp-strategy-line">
                    <span className="tp-badge">{view?.strategy.label ?? (slot.timeframe === '5m' ? 'Motor M5 experimental' : 'Estratégia M1')}</span>
                    {view && <span className="tp-badge muted">v{view.strategy.version}</span>}
                    {(view?.strategy.experimentalEngine || slot.timeframe === '5m') && (
                      <span className="tp-badge warn">
                        <FlaskConical size={12} /> Motor experimental
                      </span>
                    )}
                    <span className="tp-badge muted">Metodologia provisória · não operacional</span>
                  </div>

                  <div className="tp-primary">
                    <section className="tp-chart">
                      <div className="tp-section-head">
                        <span>
                          <BarChart3 size={16} />
                          Gráfico de candles
                        </span>
                        <span className="tp-muted">IQ OPTION · {slot.timeframe.toUpperCase()}</span>
                      </div>

                      <CandlestickChart symbol={slot.symbol} timeframe={slot.timeframe} />
                    </section>

                    <section className={`tp-signal ${showAction ? action.toLowerCase() : 'wait'}`}>
                      <span className="tp-eyebrow">
                        {slot.timeframe === '5m' ? 'CANDIDATO DO MOTOR M5' : 'SINAL DA ANÁLISE'}
                      </span>

                      <div className="tp-action">
                        {slot.loading && !view ? '...' : showAction ? action : '—'}
                      </div>

                      <div className="tp-signal-desc">{description}</div>

                      <div className="tp-signal-details">
                        <div>
                          <span>Preço teórico (fech. vela ref.)</span>
                          <strong>{publication ? number(signal?.theoreticalReferencePrice) : '—'}</strong>
                        </div>

                        <div>
                          <span>Preço observado na publicação</span>
                          <strong>{publication ? number(signal?.observedQuoteAtPublication?.price) : '—'}</strong>
                        </div>

                        <div>
                          <span>Abertura teórica (entrada)</span>
                          <strong>{publication ? timeUTC(signal?.theoreticalEntryTime) : '—'}</strong>
                        </div>

                        <div>
                          <span>Expiração</span>
                          <strong>{publication ? timeUTC(signal?.theoreticalExpirationTime) : '—'}</strong>
                        </div>

                        <div>
                          <span>Publicado · atraso</span>
                          <strong>
                            {publication
                              ? `${timeUTC(publication.publishedAt)} · ${formatMs(signal?.publicationDelayMs)} (tolerância ${formatMs(signal?.toleranceMs)})`
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
                        {publication ? `Vela ${timeUTC(publication.candleOpenTime)} → ${timeUTC(publication.candleCloseTime)}` : 'Último candle fechado'}
                      </span>
                    </div>

                    <div className="tp-indicator-grid">
                      {INDICATORS[slot.timeframe].map((item) => (
                        <div className={`tp-indicator ${current ? '' : 'tp-dim'}`} key={item.key}>
                          <span>{item.label}</span>
                          <strong>{publication ? number(indicators[item.key], item.digits) : '—'}</strong>
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

                      {publication && signal?.reasons.length ? (
                        <ul className={current ? '' : 'tp-dim'}>
                          {signal.reasons.map((reason, index) => (
                            <li key={index}>{reason}</li>
                          ))}
                          {context && (
                            <li>
                              Contexto M15: {context.trend ?? '—'} · estrutura {context.structure ?? '—'} · dados {context.state ?? '—'}
                            </li>
                          )}
                        </ul>
                      ) : (
                        <p className="tp-muted">{errorText(slot) || 'Motivos disponíveis após uma análise publicada.'}</p>
                      )}
                    </section>

                    <section className="tp-meta">
                      <div className="tp-section-head">
                        <span>
                          <Clock3 size={16} />
                          Dados, horários e latência
                        </span>
                      </div>

                      <dl>
                        <div>
                          <dt>Atualidade</dt>
                          <dd>{view ? DATA_STATE_LABEL[view.dataState] : '—'}</dd>
                        </div>
                        <div>
                          <dt>Candle</dt>
                          <dd>{publication?.candleId ?? '—'}</dd>
                        </div>
                        <div>
                          <dt>Próximo fechamento</dt>
                          <dd>{timeUTC(view?.nextCloseTime)}</dd>
                        </div>
                        <div>
                          <dt>Dados recebidos</dt>
                          <dd>{timeUTC(timing?.dataReceivedAt)}</dd>
                        </div>
                        <div>
                          <dt>Análise concluída</dt>
                          <dd>{timeUTC(timing?.analysisCompletedAt)}</dd>
                        </div>
                        <div>
                          <dt>Latência coleta / proc. / total</dt>
                          <dd>
                            {timing
                              ? `${formatMs(timing.collectionLatencyMs)} / ${formatMs(timing.processingLatencyMs)} / ${formatMs(timing.totalLatencyFromCloseMs)}`
                              : '—'}
                          </dd>
                        </div>
                        <div>
                          <dt>Tentativas · cache</dt>
                          <dd>{timing ? `${timing.attempts} · ${timing.cacheHit ? 'sim' : 'não'}` : '—'}</dd>
                        </div>
                        <div>
                          <dt>Conta · sessão</dt>
                          <dd>
                            {view ? `${view.gateway.accountMode ?? '—'} · ${view.gateway.sessionState ?? '—'}` : '—'}
                          </dd>
                        </div>
                        <div>
                          <dt>Consulta ao backend</dt>
                          <dd>{slot.updated ? timeUTC(new Date(slot.updated).toISOString()) : '—'}</dd>
                        </div>
                      </dl>
                    </section>
                  </div>

                  <details className="tp-json">
                    <summary>Ver resposta técnica JSON</summary>
                    <pre>{slot.result ? JSON.stringify(slot.result.raw, null, 2) : 'Sem resposta disponível.'}</pre>
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
