/** Client-side paper trade engine — research only, no live broker orders. */

import type { TradeSymbol } from "./symbols";

export type PaperSide = "BUY" | "SELL";
export type PaperExitReason = "TP" | "SL" | "MANUAL";

export type OpenPaperTrade = {
  id: string;
  signalId: string | null;
  /** Dedup key so the same live signal is not re-opened after close. */
  signalKey: string;
  symbol: TradeSymbol;
  side: PaperSide;
  quantity: number;
  baseUnits: number;
  contractSize: number;
  entry: number;
  stopLoss: number;
  takeProfit: number;
  openedAt: string;
  score?: number | null;
};

export type ClosedPaperTrade = OpenPaperTrade & {
  exit: number;
  closedAt: string;
  exitReason: PaperExitReason;
  pnlUsd: number;
};

export type PaperTradeStore = {
  open: OpenPaperTrade | null;
  history: ClosedPaperTrade[];
  /** Signal keys already traded (open or closed) — block re-entry. */
  consumedKeys: string[];
};

const STORAGE_KEY = "gold-swing-paper-trades-v1";
const MAX_CONSUMED = 100;
const MAX_HISTORY = 200;

export const CONTRACT_SIZE: Record<TradeSymbol, number> = {
  PAXGUSD: 0.001,
  SLVONUSD: 0.1,
};

export const PAPER_BASE_UNITS = 1;

export function contractsForOneBase(symbol: TradeSymbol): number {
  const cs = CONTRACT_SIZE[symbol];
  return Math.max(1, Math.round(PAPER_BASE_UNITS / cs));
}

export function baseLabel(symbol: TradeSymbol): string {
  return symbol === "PAXGUSD" ? "1 PAXG" : "1 SLVON";
}

export function unrealizedPnlUsd(
  trade: OpenPaperTrade,
  currentPrice: number,
): number {
  const diff =
    trade.side === "BUY"
      ? currentPrice - trade.entry
      : trade.entry - currentPrice;
  return diff * trade.contractSize * trade.quantity;
}

export function realizedPnlUsd(
  trade: Pick<OpenPaperTrade, "side" | "entry" | "contractSize" | "quantity">,
  exit: number,
): number {
  const diff = trade.side === "BUY" ? exit - trade.entry : trade.entry - exit;
  return diff * trade.contractSize * trade.quantity;
}

export function checkExit(
  trade: OpenPaperTrade,
  price: number,
): { reason: PaperExitReason; exit: number } | null {
  if (!Number.isFinite(price)) return null;
  if (trade.side === "BUY") {
    if (price <= trade.stopLoss) return { reason: "SL", exit: trade.stopLoss };
    if (price >= trade.takeProfit)
      return { reason: "TP", exit: trade.takeProfit };
  } else {
    if (price >= trade.stopLoss) return { reason: "SL", exit: trade.stopLoss };
    if (price <= trade.takeProfit)
      return { reason: "TP", exit: trade.takeProfit };
  }
  return null;
}

export function emptyStore(): PaperTradeStore {
  return { open: null, history: [], consumedKeys: [] };
}

function historyFingerprint(row: ClosedPaperTrade): string {
  // Minute-level stamp collapses the open→TP→reopen spam loop rows
  const minute = (row.closedAt ?? "").slice(0, 16);
  return [
    row.symbol,
    row.side,
    row.entry,
    row.exit,
    row.stopLoss,
    row.takeProfit,
    row.exitReason,
    minute,
  ].join("|");
}

export function dedupeClosedHistory(
  history: ClosedPaperTrade[],
): ClosedPaperTrade[] {
  const seenIds = new Set<string>();
  const seenPrints = new Set<string>();
  const deduped: ClosedPaperTrade[] = [];
  for (const row of history) {
    if (!row?.id || seenIds.has(row.id)) continue;
    const print = historyFingerprint(row);
    if (seenPrints.has(print)) continue;
    seenIds.add(row.id);
    seenPrints.add(print);
    deduped.push(row);
  }
  return deduped;
}

export function loadPaperStore(): PaperTradeStore {
  if (typeof localStorage === "undefined") return emptyStore();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return emptyStore();
    const parsed = JSON.parse(raw) as Partial<PaperTradeStore>;
    const history = Array.isArray(parsed.history) ? parsed.history : [];
    const deduped = dedupeClosedHistory(history);
    // Persist cleanup so the UI and storage stay in sync
    if (deduped.length !== history.length) {
      const next: PaperTradeStore = {
        open: parsed.open ?? null,
        history: deduped,
        consumedKeys: Array.isArray(parsed.consumedKeys)
          ? parsed.consumedKeys
          : deduped.map((t) => t.signalKey).filter(Boolean),
      };
      savePaperStore(next);
      return next;
    }
    return {
      open: parsed.open ?? null,
      history: deduped,
      consumedKeys: Array.isArray(parsed.consumedKeys)
        ? parsed.consumedKeys
        : deduped.map((t) => t.signalKey).filter(Boolean),
    };
  } catch {
    return emptyStore();
  }
}

export function savePaperStore(store: PaperTradeStore): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function makeTradeId(): string {
  return `pt_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export type SignalLevels = {
  signal: string;
  signalId?: string | null;
  asOf?: string | null;
  entry?: { low: number; high: number; preferred: number } | null;
  stop_loss?: number | null;
  targets?: Array<{ price: number; rr?: number; label?: string }> | null;
  score?: number | null;
};

export function signalKeyFromLevels(
  symbol: TradeSymbol,
  signal: SignalLevels,
): string {
  // Prefer stable signal id; otherwise levels only (no asOf) so the same
  // live BUY/SELL cannot reopen after TP/SL within the same setup.
  if (signal.signalId) return `${symbol}:${signal.signalId}`;
  const entry = signal.entry?.preferred ?? signal.entry?.low ?? "";
  const tp = signal.targets?.[0]?.price ?? "";
  const sl = signal.stop_loss ?? "";
  return `${symbol}:${signal.signal}:${entry}:${sl}:${tp}`;
}

/**
 * Atomically open one paper trade. Returns null if blocked (already open,
 * signal already consumed, levels invalid, or price already past SL/TP).
 */
export function openPaperTrade(
  symbol: TradeSymbol,
  signal: SignalLevels,
  marketPrice: number,
): OpenPaperTrade | null {
  if (signal.signal !== "BUY" && signal.signal !== "SELL") return null;
  const sl = signal.stop_loss;
  const tp = signal.targets?.[0]?.price;
  if (sl == null || !Number.isFinite(sl) || tp == null || !Number.isFinite(tp)) {
    return null;
  }
  if (!Number.isFinite(marketPrice) || marketPrice <= 0) return null;

  const preferred = signal.entry?.preferred;
  const entry =
    preferred != null && Number.isFinite(preferred) ? preferred : marketPrice;

  if (signal.signal === "BUY" && !(sl < entry && tp > entry)) return null;
  if (signal.signal === "SELL" && !(sl > entry && tp < entry)) return null;

  // Do not open if market has already hit SL or TP (would spam close loops)
  const probe: OpenPaperTrade = {
    id: "probe",
    signalId: null,
    signalKey: "",
    symbol,
    side: signal.signal,
    quantity: 1,
    baseUnits: 1,
    contractSize: 1,
    entry,
    stopLoss: sl,
    takeProfit: tp,
    openedAt: "",
  };
  if (checkExit(probe, marketPrice)) return null;

  const store = loadPaperStore();
  if (store.open) return null;

  const signalKey = signalKeyFromLevels(symbol, signal);
  if (store.consumedKeys.includes(signalKey)) return null;

  const trade: OpenPaperTrade = {
    id: makeTradeId(),
    signalId: signal.signalId ?? null,
    signalKey,
    symbol,
    side: signal.signal,
    quantity: contractsForOneBase(symbol),
    baseUnits: PAPER_BASE_UNITS,
    contractSize: CONTRACT_SIZE[symbol],
    entry,
    stopLoss: sl,
    takeProfit: tp,
    openedAt: new Date().toISOString(),
    score: signal.score ?? null,
  };

  const consumedKeys = [signalKey, ...store.consumedKeys].slice(0, MAX_CONSUMED);
  savePaperStore({ open: trade, history: store.history, consumedKeys });
  return trade;
}

/**
 * Atomically close the open trade by id. Safe under concurrent polls —
 * returns null if already closed / id mismatch.
 */
export function closeOpenTrade(
  tradeId: string,
  exit: number,
  reason: PaperExitReason,
): ClosedPaperTrade | null {
  const store = loadPaperStore();
  if (!store.open || store.open.id !== tradeId) return null;

  const closed: ClosedPaperTrade = {
    ...store.open,
    exit,
    closedAt: new Date().toISOString(),
    exitReason: reason,
    pnlUsd: realizedPnlUsd(store.open, exit),
  };

  // Guard: never append the same trade id twice
  if (store.history.some((h) => h.id === closed.id)) {
    savePaperStore({ ...store, open: null });
    return null;
  }

  const history = [closed, ...store.history].slice(0, MAX_HISTORY);
  const consumedKeys = Array.from(
    new Set([closed.signalKey, ...store.consumedKeys]),
  ).slice(0, MAX_CONSUMED);

  savePaperStore({ open: null, history, consumedKeys });
  return closed;
}

/** @deprecated use openPaperTrade */
export function tryOpenFromSignal(
  symbol: TradeSymbol,
  signal: SignalLevels,
  marketPrice: number,
  existing: OpenPaperTrade | null,
): OpenPaperTrade | null {
  if (existing) return null;
  return openPaperTrade(symbol, signal, marketPrice);
}

export function closeTrade(
  open: OpenPaperTrade,
  exit: number,
  reason: PaperExitReason,
): ClosedPaperTrade {
  return {
    ...open,
    exit,
    closedAt: new Date().toISOString(),
    exitReason: reason,
    pnlUsd: realizedPnlUsd(open, exit),
  };
}

export function formatUsd(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}$${n.toFixed(digits)}`;
}
