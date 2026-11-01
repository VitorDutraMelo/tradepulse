import { execFile } from "node:child_process";

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

export class PythonQuantEngineClient implements QuantEngineClient {
  constructor(
    private readonly config: PythonQuantEngineClientConfig,
    private readonly runner: QuantEngineRunner = nodeQuantEngineRunner,
  ) {}

  async analyze(
    input: MarketAnalysisRequest,
  ): Promise<MarketAnalysisResponse> {
    const arguments_ = [
      "-m",
      "app.cli.analyze_market",
      "--symbol",
      input.symbol,
      "--timeframe",
      input.timeframe,
      "--limit",
      String(input.limit),
    ];

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
          "The Quant Engine could not complete the analysis.",
      );
    }

    if (result.stderr.trim()) {
      throw new QuantEngineClientError(
        this.extractProcessErrorMessage(result.stderr) ??
          "The Quant Engine returned an unexpected error.",
      );
    }

    let rawPayload: unknown;

    try {
      rawPayload = JSON.parse(result.stdout);
    } catch {
      throw new QuantEngineClientError(
        "The Quant Engine returned invalid JSON.",
      );
    }

    const parsedPayload = marketAnalysisResponseSchema.safeParse(rawPayload);

    if (!parsedPayload.success) {
      throw new QuantEngineClientError(
        "The Quant Engine returned an invalid analysis payload.",
      );
    }

    return parsedPayload.data;
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