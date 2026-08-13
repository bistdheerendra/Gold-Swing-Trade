/** Client-side paper trade engine — research only, no live broker orders. */

import type { TradeSymbol } from "./symbols";

export type PaperSide = "BUY" | "SELL";
export type PaperExitReason = "TP" | "SL" | "MANUAL";

export type OpenPaperTrade = {
  id: string;
  signalId: string | null;
  symbol: TradeSymbol;
  side: PaperSide;
  /** Contracts on exchange (integer). */
  quantity: number;
  /** Base-asset units (e.g. 1 PAXG). */
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
};

const STORAGE_KEY = "gold-swing-paper-trades-v1";

/** Delta contract_value — keep in sync with backend instrument specs. */
export const CONTRACT_SIZE: Record<TradeSymbol, number> = {
  PAXGUSD: 0.001,
  SLVONUSD: 0.1,
};

/** Fixed paper size: 1 base unit (1 PAXG / 1 SLVON). */
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

/** Check SL / TP against last traded price. */
export function checkExit(
  trade: OpenPaperTrade,
  price: number,
): { reason: PaperExitReason; exit: number } | null {
  if (!Number.isFinite(price)) return null;
  if (trade.side === "BUY") {
    if (price <= trade.stopLoss) return { reason: "SL", exit: trade.stopLoss };
    if (price >= trade.takeProfit) return { reason: "TP", exit: trade.takeProfit };
  } else {
    if (price >= trade.stopLoss) return { reason: "SL", exit: trade.stopLoss };
    if (price <= trade.takeProfit) return { reason: "TP", exit: trade.takeProfit };
  }
  return null;
}

export function emptyStore(): PaperTradeStore {
  return { open: null, history: [] };
}

export function loadPaperStore(): PaperTradeStore {
  if (typeof localStorage === "undefined") return emptyStore();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return emptyStore();
    const parsed = JSON.parse(raw) as PaperTradeStore;
    return {
      open: parsed.open ?? null,
      history: Array.isArray(parsed.history) ? parsed.history : [],
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
  entry?: { low: number; high: number; preferred: number } | null;
  stop_loss?: number | null;
  targets?: Array<{ price: number; rr?: number; label?: string }> | null;
  score?: number | null;
};

/** Build an open trade from a live BUY/SELL signal + market price. */
export function tryOpenFromSignal(
  symbol: TradeSymbol,
  signal: SignalLevels,
  marketPrice: number,
  existing: OpenPaperTrade | null,
): OpenPaperTrade | null {
  if (existing) return null;
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

  // Basic sanity: SL/TP on correct side of entry
  if (signal.signal === "BUY" && !(sl < entry && tp > entry)) return null;
  if (signal.signal === "SELL" && !(sl > entry && tp < entry)) return null;

  const contractSize = CONTRACT_SIZE[symbol];
  const quantity = contractsForOneBase(symbol);

  return {
    id: makeTradeId(),
    signalId: signal.signalId ?? null,
    symbol,
    side: signal.signal,
    quantity,
    baseUnits: PAPER_BASE_UNITS,
    contractSize,
    entry,
    stopLoss: sl,
    takeProfit: tp,
    openedAt: new Date().toISOString(),
    score: signal.score ?? null,
  };
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
