import { execFile } from "node:child_process";

import {
  marketAnalysisResponseSchema,
  type MarketAnalysisRequest,
  type MarketAnalysisResponse,
} from "./market-analysis.schema";
import {
  marketCandlesResponseSchema,
  type MarketCandlesRequest,
  type MarketCandlesResponse,
} from "../market-data/market-data.schema";

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
  implements QuantEngineClient, QuantEngineMarketDataClient
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
