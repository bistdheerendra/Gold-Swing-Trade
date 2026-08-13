import { beforeEach, describe, expect, it } from "vitest";
import {
  checkExit,
  closeOpenTrade,
  contractsForOneBase,
  emptyStore,
  loadPaperStore,
  openPaperTrade,
  realizedPnlUsd,
  savePaperStore,
  tryOpenFromSignal,
  unrealizedPnlUsd,
} from "./paperTrade";

beforeEach(() => {
  savePaperStore(emptyStore());
});

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
    expect(
      unrealizedPnlUsd(
        {
          ...trade,
          id: "x",
          signalId: null,
          signalKey: "k",
          symbol: "PAXGUSD",
          baseUnits: 1,
          stopLoss: 2290,
          takeProfit: 2320,
          openedAt: "",
        },
        2295,
      ),
    ).toBeCloseTo(-5, 6);
  });

  it("hits SL/TP for BUY", () => {
    const open = openPaperTrade(
      "PAXGUSD",
      {
        signal: "BUY",
        signalId: "sig-1",
        entry: { low: 2299, high: 2301, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320, label: "TP1" }],
      },
      2300,
    );
    expect(open).not.toBeNull();
    expect(checkExit(open!, 2289)?.reason).toBe("SL");
    expect(checkExit(open!, 2321)?.reason).toBe("TP");
    expect(checkExit(open!, 2305)).toBeNull();
  });

  it("does not open when a trade is already open", () => {
    const first = openPaperTrade(
      "PAXGUSD",
      {
        signal: "BUY",
        signalId: "sig-a",
        entry: { low: 1, high: 2, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320 }],
      },
      2300,
    );
    expect(first).not.toBeNull();
    const second = openPaperTrade(
      "PAXGUSD",
      {
        signal: "BUY",
        signalId: "sig-b",
        entry: { low: 1, high: 2, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320 }],
      },
      2300,
    );
    expect(second).toBeNull();
  });

  it("does not re-open the same consumed signal after close", () => {
    const opened = openPaperTrade(
      "PAXGUSD",
      {
        signal: "BUY",
        signalId: "sig-same",
        entry: { low: 2299, high: 2301, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320 }],
      },
      2300,
    )!;
    const closed = closeOpenTrade(opened.id, 2320, "TP");
    expect(closed).not.toBeNull();
    expect(loadPaperStore().open).toBeNull();

    const again = openPaperTrade(
      "PAXGUSD",
      {
        signal: "BUY",
        signalId: "sig-same",
        entry: { low: 2299, high: 2301, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320 }],
      },
      2300,
    );
    expect(again).toBeNull();
  });

  it("closes a trade only once even if called twice", () => {
    const opened = openPaperTrade(
      "PAXGUSD",
      {
        signal: "BUY",
        signalId: "sig-once",
        entry: { low: 2299, high: 2301, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320 }],
      },
      2300,
    )!;
    const first = closeOpenTrade(opened.id, 2320, "TP");
    const second = closeOpenTrade(opened.id, 2320, "TP");
    expect(first).not.toBeNull();
    expect(second).toBeNull();
    expect(loadPaperStore().history).toHaveLength(1);
  });

  it("refuses to open when price already past TP", () => {
    const opened = openPaperTrade(
      "PAXGUSD",
      {
        signal: "BUY",
        signalId: "sig-past",
        entry: { low: 2299, high: 2301, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320 }],
      },
      2325,
    );
    expect(opened).toBeNull();
  });

  it("tryOpenFromSignal still works with existing guard", () => {
    const first = tryOpenFromSignal(
      "PAXGUSD",
      {
        signal: "BUY",
        signalId: "sig-try",
        entry: { low: 1, high: 2, preferred: 2300 },
        stop_loss: 2290,
        targets: [{ price: 2320 }],
      },
      2300,
      null,
    )!;
    expect(
      tryOpenFromSignal(
        "PAXGUSD",
        {
          signal: "BUY",
          signalId: "sig-try-2",
          entry: { low: 1, high: 2, preferred: 2300 },
          stop_loss: 2290,
          targets: [{ price: 2320 }],
        },
        2300,
        first,
      ),
    ).toBeNull();
  });
});
