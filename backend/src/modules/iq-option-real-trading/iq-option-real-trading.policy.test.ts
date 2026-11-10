import { describe, expect, it } from "vitest";

import {
  IqOptionRealTradingSafetyPolicy,
} from "./iq-option-real-trading.policy";

const request = {
  symbol: "GBPUSD-OTC",
  timeframe: "1m" as const,
  action: "CALL" as const,
  stake: 2,
};

function createPolicy(
  overrides: Partial<ConstructorParameters<
    typeof IqOptionRealTradingSafetyPolicy
  >[0]> = {},
): IqOptionRealTradingSafetyPolicy {
  return new IqOptionRealTradingSafetyPolicy({
    tradingEnabled: false,
    killSwitchActive: true,
    maxStake: 2,
    maxDailyLoss: 10,
    maxDailyOrders: 5,
    cooldownSeconds: 300,
    ...overrides,
  });
}

describe("IqOptionRealTradingSafetyPolicy", () => {
  it("keeps real trading blocked by default", () => {
    const response = createPolicy().preflight(request);

    expect(response.allowed).toBe(false);
    expect(response.riskChecksPassed).toBe(false);
    expect(response.blockers.map((blocker) => blocker.code)).toEqual([
      "REAL_TRADING_DISABLED",
      "REAL_TRADING_KILL_SWITCH_ACTIVE",
      "REAL_ORDER_EXECUTION_NOT_IMPLEMENTED",
    ]);
  });

  it("blocks a stake above the configured maximum", () => {
    const response = createPolicy({
      tradingEnabled: true,
      killSwitchActive: false,
    }).preflight({
      ...request,
      stake: 2.01,
    });

    expect(response.allowed).toBe(false);
    expect(response.riskChecksPassed).toBe(false);
    expect(response.blockers.map((blocker) => blocker.code)).toEqual([
      "STAKE_EXCEEDS_MAXIMUM",
      "REAL_ORDER_EXECUTION_NOT_IMPLEMENTED",
    ]);
  });

  it("does not claim an order is allowed even when configuration checks pass", () => {
    const response = createPolicy({
      tradingEnabled: true,
      killSwitchActive: false,
    }).preflight(request);

    expect(response.allowed).toBe(false);
    expect(response.riskChecksPassed).toBe(true);
    expect(response.orderExecutionImplemented).toBe(false);
    expect(response.blockers.map((blocker) => blocker.code)).toEqual([
      "REAL_ORDER_EXECUTION_NOT_IMPLEMENTED",
    ]);
  });
});