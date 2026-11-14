import { execFile } from "node:child_process";

import {
  iqOptionDemoAnalysisHistoryResponseSchema,
  iqOptionDemoAnalysisRecordResponseSchema,
  type IqOptionDemoAnalysisHistoryRequest,
  type IqOptionDemoAnalysisHistoryResponse,
  type IqOptionDemoAnalysisRecordRequest,
  type IqOptionDemoAnalysisRecordResponse,
} from "../iq-option-demo-analysis/iq-option-demo-analysis-history.schema";
import {
  iqOptionDemoAnalysisResponseSchema,
  type IqOptionDemoAnalysisRequest,
  type IqOptionDemoAnalysisResponse,
} from "../iq-option-demo-analysis/iq-option-demo-analysis.schema";
import {
  iqOptionDemoBinarySignalHistoryResponseSchema,
  iqOptionDemoBinarySignalRecordResponseSchema,
  type IqOptionDemoBinarySignalHistoryRequest,
  type IqOptionDemoBinarySignalHistoryResponse,
  type IqOptionDemoBinarySignalRecordRequest,
  type IqOptionDemoBinarySignalRecordResponse,
} from "../iq-option-demo-analysis/iq-option-demo-binary-signal-history.schema";
import {
  iqOptionSignalResponseSchema,
  type IqOptionSignalRequest,
  type IqOptionSignalResponse,
} from "../iq-option-signals/iq-option-signal.schema";
import {
  marketCandlesResponseSchema,
  type MarketCandlesRequest,
  type MarketCandlesResponse,
} from "../market-data/market-data.schema";
import {
  iqOptionDemoCandlesResponseSchema,
  type IqOptionDemoCandlesRequest,
  type IqOptionDemoCandlesResponse,
} from "../iq-option-demo-analysis/iq-option-demo-candles.schema";
import {
  iqOptionDemoM5SyncResponseSchema,
  type IqOptionDemoM5SyncRequest,
  type IqOptionDemoM5SyncResponse,
} from "../iq-option-demo-analysis/iq-option-demo-m5-sync.schema";
import {
  iqOptionDemoM5SignalResponseSchema,
  type IqOptionDemoM5SignalRequest,
  type IqOptionDemoM5SignalResponse,
} from "../iq-option-demo-analysis/iq-option-demo-m5-signal.schema";
import {
  marketAnalysisResponseSchema,
  type MarketAnalysisRequest,
  type MarketAnalysisResponse,
} from "./market-analysis.schema";

export type QuantEngineCommandOptions = {
  cwd: string;
  timeoutMs: number;
};

export type QuantEngineCommandResult = {
  stdout: string;
  stderr: string;
};

export interface QuantEngineRunner {
  run(
    command: string,
    arguments_: string[],
    options: QuantEngineCommandOptions,
  ): Promise<QuantEngineCommandResult>;
}

export interface QuantEngineClient {
  analyze(input: MarketAnalysisRequest): Promise<MarketAnalysisResponse>;
}

export interface QuantEngineMarketDataClient {
  getCandles(input: MarketCandlesRequest): Promise<MarketCandlesResponse>;
}

export interface QuantEngineIqOptionDemoCandleClient {
  getIqOptionDemoCandles(
    input: IqOptionDemoCandlesRequest,
  ): Promise<IqOptionDemoCandlesResponse>;
}

export interface QuantEngineIqOptionDemoM5SyncClient {
  getIqOptionDemoM5Sync(
    input: IqOptionDemoM5SyncRequest,
  ): Promise<IqOptionDemoM5SyncResponse>;
}

export interface QuantEngineIqOptionDemoM5SignalClient {
  getIqOptionDemoM5Signal(
    input: IqOptionDemoM5SignalRequest,
  ): Promise<IqOptionDemoM5SignalResponse>;
}

export interface QuantEngineIqOptionDemoM5SignalClient {
  getIqOptionDemoM5Signal(
    input: IqOptionDemoM5SignalRequest,
  ): Promise<IqOptionDemoM5SignalResponse>;
}
export interface QuantEngineIqOptionSignalClient {
  prepareIqOptionSignal(
    input: IqOptionSignalRequest,
  ): Promise<IqOptionSignalResponse>;
}

export interface QuantEngineIqOptionDemoAnalysisClient {
  analyzeIqOptionDemo(
    input: IqOptionDemoAnalysisRequest,
  ): Promise<IqOptionDemoAnalysisResponse>;
}

export interface QuantEngineIqOptionDemoHistoryClient {
  listIqOptionDemoAnalyses(
    input: IqOptionDemoAnalysisHistoryRequest,
  ): Promise<IqOptionDemoAnalysisHistoryResponse>;

  getIqOptionDemoAnalysisRecord(
    input: IqOptionDemoAnalysisRecordRequest,
  ): Promise<IqOptionDemoAnalysisRecordResponse>;
}

export interface QuantEngineIqOptionDemoBinarySignalHistoryClient {
  listIqOptionDemoBinarySignals(
    input: IqOptionDemoBinarySignalHistoryRequest,
  ): Promise<IqOptionDemoBinarySignalHistoryResponse>;

  getIqOptionDemoBinarySignalRecord(
    input: IqOptionDemoBinarySignalRecordRequest,
  ): Promise<IqOptionDemoBinarySignalRecordResponse>;
}

export type PythonQuantEngineClientConfig = {
  pythonExecutable: string;
  workingDirectory: string;
  timeoutMs: number;
};

export class QuantEngineClientError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "QuantEngineClientError";
  }
}

const nodeQuantEngineRunner: QuantEngineRunner = {
  run(command, arguments_, options) {
    return new Promise((resolve, reject) => {
      execFile(
        command,
        arguments_,
        {
          cwd: options.cwd,
          encoding: "utf8",
          maxBuffer: 1024 * 1024,
          timeout: options.timeoutMs,
          windowsHide: true,
        },
        (error, stdout, stderr) => {
          if (error) {
            reject(Object.assign(error, { stderr }));
            return;
          }

          resolve({ stdout, stderr });
        },
      );
    });
  },
};

export class PythonQuantEngineClient
  implements
    QuantEngineClient,
    QuantEngineMarketDataClient,
    QuantEngineIqOptionDemoCandleClient,
    QuantEngineIqOptionDemoM5SyncClient,
    QuantEngineIqOptionDemoM5SignalClient,
    QuantEngineIqOptionSignalClient,
    QuantEngineIqOptionDemoAnalysisClient,
    QuantEngineIqOptionDemoHistoryClient,
    QuantEngineIqOptionDemoBinarySignalHistoryClient
{
  constructor(
    private readonly config: PythonQuantEngineClientConfig,
    private readonly runner: QuantEngineRunner = nodeQuantEngineRunner,
  ) {}

  async analyze(
    input: MarketAnalysisRequest,
  ): Promise<MarketAnalysisResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.analyze_market",
      "--symbol",
      input.symbol,
      "--timeframe",
      input.timeframe,
      "--limit",
      String(input.limit),
    ]);

    const parsedPayload = marketAnalysisResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid analysis payload.",
      );
    }

    return parsedPayload.data;
  }

  async getCandles(
    input: MarketCandlesRequest,
  ): Promise<MarketCandlesResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.get_candles",
      "--symbol",
      input.symbol,
      "--timeframe",
      input.timeframe,
      "--limit",
      String(input.limit),
    ]);

    const parsedPayload = marketCandlesResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid market candles payload.",
      );
    }

    return parsedPayload.data;
  }

  async getIqOptionDemoCandles(
    input: IqOptionDemoCandlesRequest,
  ): Promise<IqOptionDemoCandlesResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.get_iq_option_demo_candles",
      "--symbol",
      input.symbol,
      "--timeframe",
      input.timeframe,
      "--limit",
      String(input.limit),
    ]);

    const parsedPayload =
      iqOptionDemoCandlesResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid IQ Option demo candles payload.",
      );
    }

    return parsedPayload.data;
  }

  async getIqOptionDemoM5Sync(
    input: IqOptionDemoM5SyncRequest,
  ): Promise<IqOptionDemoM5SyncResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.get_iq_option_demo_m5_sync",
      "--symbol",
      input.symbol,
    ]);

    const parsedPayload =
      iqOptionDemoM5SyncResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid IQ Option DEMO M5 synchronization payload.",
      );
    }

    return parsedPayload.data;
  }
  async getIqOptionDemoM5Signal(
    input: IqOptionDemoM5SignalRequest,
  ): Promise<IqOptionDemoM5SignalResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.get_iq_option_demo_m5_signal",
      "--symbol",
      input.symbol,
    ]);

    const parsedPayload =
      iqOptionDemoM5SignalResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid IQ Option DEMO M5 signal payload.",
      );
    }

    return parsedPayload.data;
  }
  async prepareIqOptionSignal(
    input: IqOptionSignalRequest,
  ): Promise<IqOptionSignalResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.prepare_iq_option_signal",
      "--symbol",
      input.symbol,
      "--timeframe",
      input.timeframe,
      "--limit",
      String(input.limit),
      "--market",
      input.market,
    ]);

    const parsedPayload = iqOptionSignalResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid IQ Option signal payload.",
      );
    }

    return parsedPayload.data;
  }

  async analyzeIqOptionDemo(
    input: IqOptionDemoAnalysisRequest,
  ): Promise<IqOptionDemoAnalysisResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.analyze_iq_option_binary_signal",
      "--symbol",
      input.symbol,
      "--timeframe",
      input.timeframe,
      "--limit",
      String(input.limit),
    ]);

    const parsedPayload =
      iqOptionDemoAnalysisResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid IQ Option demo analysis payload.",
      );
    }

    return parsedPayload.data;
  }

  async listIqOptionDemoAnalyses(
    input: IqOptionDemoAnalysisHistoryRequest,
  ): Promise<IqOptionDemoAnalysisHistoryResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.get_iq_option_demo_analysis_history",
      "--limit",
      String(input.limit),
    ]);

    const parsedPayload =
      iqOptionDemoAnalysisHistoryResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid IQ Option demo history payload.",
      );
    }

    return parsedPayload.data;
  }

  async getIqOptionDemoAnalysisRecord(
    input: IqOptionDemoAnalysisRecordRequest,
  ): Promise<IqOptionDemoAnalysisRecordResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.get_iq_option_demo_analysis_history",
      "--record-id",
      input.recordId,
    ]);

    const parsedPayload =
      iqOptionDemoAnalysisRecordResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid IQ Option demo record payload.",
      );
    }

    return parsedPayload.data;
  }

  async listIqOptionDemoBinarySignals(
    input: IqOptionDemoBinarySignalHistoryRequest,
  ): Promise<IqOptionDemoBinarySignalHistoryResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.get_iq_option_demo_binary_signal_history",
      "--limit",
      String(input.limit),
    ]);

    const parsedPayload =
      iqOptionDemoBinarySignalHistoryResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid IQ Option DEMO binary signal history payload.",
      );
    }

    return parsedPayload.data;
  }

  async getIqOptionDemoBinarySignalRecord(
    input: IqOptionDemoBinarySignalRecordRequest,
  ): Promise<IqOptionDemoBinarySignalRecordResponse> {
    const rawPayload = await this.runCli([
      "-m",
      "app.cli.get_iq_option_demo_binary_signal_history",
      "--record-id",
      input.recordId,
    ]);

    const parsedPayload =
      iqOptionDemoBinarySignalRecordResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid IQ Option DEMO binary signal record payload.",
      );
    }

    return parsedPayload.data;
  }

  private async runCli(arguments_: string[]): Promise<unknown> {
    let result: QuantEngineCommandResult;

    try {
      result = await this.runner.run(
        this.config.pythonExecutable,
        arguments_,
        {
          cwd: this.config.workingDirectory,
          timeoutMs: this.config.timeoutMs,
        },
      );
    } catch (error) {
      throw new QuantEngineClientError(
        this.extractProcessErrorMessage(error) ??
          "The Quant Engine could not complete the request.",
      );
    }

    if (result.stderr.trim()) {
      throw new QuantEngineClientError(
        this.extractProcessErrorMessage(result.stderr) ??
          "The Quant Engine returned an unexpected error.",
      );
    }

    try {
      return JSON.parse(result.stdout);
    } catch {
      throw new QuantEngineClientError(
        "The Quant Engine returned invalid JSON.",
      );
    }
  }

  private extractProcessErrorMessage(error: unknown): string | undefined {
    const stderr =
      typeof error === "string"
        ? error
        : typeof error === "object" &&
            error !== null &&
            "stderr" in error &&
            typeof error.stderr === "string"
          ? error.stderr
          : undefined;

    if (!stderr?.trim()) {
      return undefined;
    }

    try {
      const payload = JSON.parse(stderr) as {
        error?: { message?: unknown };
      };

      return typeof payload.error?.message === "string"
        ? payload.error.message
        : undefined;
    } catch {
      return undefined;
    }
  }
}
