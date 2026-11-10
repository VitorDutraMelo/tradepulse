import type { IqOptionRealTradingPreflightRequest } from "./iq-option-real-trading.schema";

export type IqOptionRealTradingSafetySettings = {
  tradingEnabled: boolean;
  killSwitchActive: boolean;
  maxStake: number;
  maxDailyLoss: number;
  maxDailyOrders: number;
  cooldownSeconds: number;
};

export type IqOptionRealTradingBlockerCode =
  | "REAL_TRADING_DISABLED"
  | "REAL_TRADING_KILL_SWITCH_ACTIVE"
  | "STAKE_EXCEEDS_MAXIMUM"
  | "REAL_ORDER_EXECUTION_NOT_IMPLEMENTED";

export type IqOptionRealTradingBlocker = {
  code: IqOptionRealTradingBlockerCode;
  message: string;
};

export type IqOptionRealTradingSafetyStatus = {
  tradingEnabled: boolean;
  killSwitchActive: boolean;
  maxStake: number;
  maxDailyLoss: number;
  maxDailyOrders: number;
  cooldownSeconds: number;
  orderExecutionImplemented: false;
};

export type IqOptionRealTradingPreflightResponse = {
  allowed: false;
  riskChecksPassed: boolean;
  orderExecutionImplemented: false;
  request: IqOptionRealTradingPreflightRequest;
  blockers: IqOptionRealTradingBlocker[];
  safety: IqOptionRealTradingSafetyStatus;
};

export class IqOptionRealTradingSafetyPolicy {
  constructor(
    private readonly settings: IqOptionRealTradingSafetySettings,
  ) {}

  getSafetyStatus(): IqOptionRealTradingSafetyStatus {
    return {
      tradingEnabled: this.settings.tradingEnabled,
      killSwitchActive: this.settings.killSwitchActive,
      maxStake: this.settings.maxStake,
      maxDailyLoss: this.settings.maxDailyLoss,
      maxDailyOrders: this.settings.maxDailyOrders,
      cooldownSeconds: this.settings.cooldownSeconds,
      orderExecutionImplemented: false,
    };
  }

  preflight(
    request: IqOptionRealTradingPreflightRequest,
  ): IqOptionRealTradingPreflightResponse {
    const blockers: IqOptionRealTradingBlocker[] = [];

    if (!this.settings.tradingEnabled) {
      blockers.push({
        code: "REAL_TRADING_DISABLED",
        message:
          "Real trading is disabled. Set IQ_OPTION_REAL_TRADING_ENABLED=true only after the real order executor and risk ledger are approved.",
      });
    }

    if (this.settings.killSwitchActive) {
      blockers.push({
        code: "REAL_TRADING_KILL_SWITCH_ACTIVE",
        message:
          "The real trading kill switch is active. No real order can be submitted.",
      });
    }

    if (request.stake > this.settings.maxStake) {
      blockers.push({
        code: "STAKE_EXCEEDS_MAXIMUM",
        message: `Requested stake ${request.stake.toFixed(2)} exceeds the configured maximum of ${this.settings.maxStake.toFixed(2)}.`,
      });
    }

    const riskChecksPassed = blockers.length === 0;

    blockers.push({
      code: "REAL_ORDER_EXECUTION_NOT_IMPLEMENTED",
      message:
        "The real order executor is not implemented. This endpoint performs safety preflight only and never sends an IQ Option order.",
    });

    return {
      allowed: false,
      riskChecksPassed,
      orderExecutionImplemented: false,
      request,
      blockers,
      safety: this.getSafetyStatus(),
    };
  }
}