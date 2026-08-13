import { describe, expect, it } from "vitest";
import {
  checkExit,
  contractsForOneBase,
  realizedPnlUsd,
  tryOpenFromSignal,
  unrealizedPnlUsd,
} from "./paperTrade";

describe("paperTrade", () => {
  it("sizes 1 PAXG as 1000 contracts of 0.001", () => {
    expect(contractsForOneBase("PAXGUSD")).toBe(1000);
  });

  it("computes BUY PnL as $1 per $1 move for 1 PAXG", () => {
    const trade = {
      side: "BUY" as const,
      entry: 2300,
      contractSize: 0.001,
      quantity: 1000,
    };
    expect(realizedPnlUsd(trade, 2310)).toBeCloseTo(10, 6);
    expect(unrealizedPnlUsd({ ...trade, id: "x", signalId: null, symbol: "PAXGUSD", baseUnits: 1, stopLoss: 2290, takeProfit: 2320, openedAt: "" }, 2295)).toBeCloseTo(-5, 6);
  });

  it("hits SL/TP for BUY", () => {
    const open = tryOpenFromSignal(
      "PAXGUSD",
      {
        signal: "BUY",
        entry: { low: 2299, high: 2301, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320, label: "TP1" }],
      },
      2300,
      null,
    );
    expect(open).not.toBeNull();
    expect(checkExit(open!, 2289)?.reason).toBe("SL");
    expect(checkExit(open!, 2321)?.reason).toBe("TP");
    expect(checkExit(open!, 2305)).toBeNull();
  });

  it("does not open when a trade is already open", () => {
    const first = tryOpenFromSignal(
      "PAXGUSD",
      {
        signal: "BUY",
        entry: { low: 1, high: 2, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320 }],
      },
      2300,
      null,
    )!;
    const second = tryOpenFromSignal(
      "PAXGUSD",
      {
        signal: "BUY",
        entry: { low: 1, high: 2, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320 }],
      },
      2300,
      first,
    );
    expect(second).toBeNull();
  });
});
