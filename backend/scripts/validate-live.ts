/**
 * Live validation of blocks A.1/A.2 against IQ Option PRACTICE.
 *
 * Run with the backend already started (npm run dev) and PRACTICE
 * credentials configured in the backend environment:
 *
 *   npm run validate:live -- --minutes 30 --pairs EURUSD-OTC:1m,GBPUSD-OTC:1m,GBPUSD-OTC:5m
 *
 * The script only reads the local API. It records every publication
 * (one per closed candle), the observed latencies and the login counters,
 * and writes a JSON + Markdown report to backend/data/validation/.
 * It never sends orders and never reads or prints credentials.
 */
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

type Pair = { symbol: string; timeframe: "1m" | "5m" };

function argument(name: string, fallback: string): string {
  const index = process.argv.indexOf(`--${name}`);
  return index !== -1 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const baseUrl = argument("url", "http://127.0.0.1:3001").replace(/\/$/, "");
const minutes = Number(argument("minutes", "30"));
const pairs: Pair[] = argument("pairs", "EURUSD-OTC:1m,GBPUSD-OTC:1m,GBPUSD-OTC:5m")
  .split(",")
  .map((item) => {
    const [symbol, timeframe] = item.split(":");
    return { symbol: symbol.trim().toUpperCase(), timeframe: timeframe.trim() as Pair["timeframe"] };
  });

async function getJson(url: string): Promise<any> {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  const body = await response.json().catch(() => ({}));
  return { status: response.status, body };
}

function percentile(values: number[], p: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1)];
}

async function main(): Promise<void> {
  const startedAt = new Date();
  const endAt = startedAt.getTime() + minutes * 60_000;
  const statusBefore = (await getJson(`${baseUrl}/api/v1/iq-option/demo/status`)).body?.data;
  const publications = new Map<string, Record<string, unknown>>();
  const errors: Array<Record<string, unknown>> = [];
  const staleShownAsCurrent: string[] = [];

  console.log(`Validating ${pairs.map((p) => `${p.symbol} ${p.timeframe}`).join(", ")} for ${minutes} min...`);

  while (Date.now() < endAt) {
    for (const pair of pairs) {
      const { status, body } = await getJson(
        `${baseUrl}/api/v1/iq-option/demo/live?symbol=${pair.symbol}&timeframe=${pair.timeframe}`,
      );

      if (status !== 200) {
        errors.push({ at: new Date().toISOString(), pair, status, error: body?.error });
        continue;
      }

      const view = body.data;
      const publication = view.publication;

      if (view.lastError) {
        errors.push({ at: view.observedAt, pair, error: view.lastError });
      }

      if (publication && view.dataState === "CURRENT") {
        const closeMs = Date.parse(publication.candleCloseTime);
        const expectedMs = Date.parse(view.expectedLatestCloseTime);
        if (closeMs < expectedMs) staleShownAsCurrent.push(publication.candleId);
      }

      if (publication && !publications.has(publication.candleId)) {
        publications.set(publication.candleId, {
          candleId: publication.candleId,
          symbol: pair.symbol,
          timeframe: pair.timeframe,
          strategy: view.strategy.id,
          candleCloseTime: publication.candleCloseTime,
          publishedAt: publication.publishedAt,
          totalLatencyFromCloseMs: publication.timing.totalLatencyFromCloseMs,
          collectionLatencyMs: publication.timing.collectionLatencyMs,
          processingLatencyMs: publication.timing.processingLatencyMs,
          attempts: publication.timing.attempts,
          action: publication.signal.action,
          status: publication.signal.status,
          timeliness: publication.signal.timeliness,
        });
        console.log(
          `${publication.candleId} published ${publication.timing.totalLatencyFromCloseMs} ms after close ` +
            `(${publication.signal.action}, ${publication.signal.status})`,
        );
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  const statusAfter = (await getJson(`${baseUrl}/api/v1/iq-option/demo/status`)).body?.data;
  const rows = [...publications.values()];
  // The first publication of each pair can be a mid-candle subscription: exclude it.
  const boundaryRows = rows.filter((row, index) => rows.findIndex((r) => r.symbol === row.symbol && r.timeframe === row.timeframe) !== index);
  const latencies = boundaryRows.map((row) => Number(row.totalLatencyFromCloseMs));
  const logins = (data: any) => data?.gateway?.session?.counters?.loginsSucceeded ?? null;

  const report = {
    startedAt: startedAt.toISOString(),
    finishedAt: new Date().toISOString(),
    minutes,
    pairs,
    publications: rows,
    summary: {
      publications: rows.length,
      boundaryPublications: boundaryRows.length,
      latencyMs: {
        median: percentile(latencies, 50),
        p95: percentile(latencies, 95),
        max: latencies.length ? Math.max(...latencies) : null,
      },
      loginsBefore: logins(statusBefore),
      loginsAfter: logins(statusAfter),
      workerStartsAfter: statusAfter?.gateway?.workerStarts ?? null,
      errors: errors.length,
      staleShownAsCurrent: staleShownAsCurrent.length,
    },
    errors: errors.slice(0, 200),
    statusAfter,
  };

  const directory = path.resolve("data/validation");
  await mkdir(directory, { recursive: true });
  const stamp = startedAt.toISOString().replace(/[:.]/g, "-");
  const jsonPath = path.join(directory, `live-validation-${stamp}.json`);
  await writeFile(jsonPath, JSON.stringify(report, null, 2), "utf8");

  const markdown = [
    `# TradePulse live validation — ${report.startedAt}`,
    "",
    `- Duration: ${minutes} min · pairs: ${pairs.map((p) => `${p.symbol} ${p.timeframe}`).join(", ")}`,
    `- Publications: ${rows.length} (${boundaryRows.length} after a candle boundary)`,
    `- Latency close → publication (boundary publications): median ${report.summary.latencyMs.median} ms · p95 ${report.summary.latencyMs.p95} ms · max ${report.summary.latencyMs.max} ms`,
    `- Successful IQ logins: before ${report.summary.loginsBefore} · after ${report.summary.loginsAfter} · worker starts ${report.summary.workerStartsAfter}`,
    `- Errors observed: ${errors.length} · previous candle shown as current: ${staleShownAsCurrent.length}`,
    "",
    "| Candle | Published | Latency (ms) | Attempts | Action | Status |",
    "|---|---|---|---|---|---|",
    ...rows.map(
      (row) =>
        `| ${row.candleId} | ${row.publishedAt} | ${row.totalLatencyFromCloseMs} | ${row.attempts} | ${row.action} | ${row.status} |`,
    ),
    "",
  ].join("\n");
  await writeFile(jsonPath.replace(/\.json$/, ".md"), markdown, "utf8");

  console.log(`\nReport written to ${jsonPath} (and .md)`);
  console.log(JSON.stringify(report.summary, null, 2));
}

void main();
