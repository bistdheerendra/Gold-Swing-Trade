/** Research symbols — decision-support only (no live broker). */

export type TradeSymbol = "XAUUSD" | "PAXGUSD";

export type SymbolMeta = {
  symbol: TradeSymbol;
  label: string;
  shortLabel: string;
  description: string;
};

export const TRADE_SYMBOLS: SymbolMeta[] = [
  {
    symbol: "PAXGUSD",
    label: "PAX Gold / PAXGUSD",
    shortLabel: "PAXGUSD",
    description: "Delta India live perpetual",
  },
  {
    symbol: "XAUUSD",
    label: "Gold / XAUUSD",
    shortLabel: "XAUUSD",
    description: "Maps to live PAXGUSD candles",
  },
];

export const DEFAULT_SYMBOL: TradeSymbol = "PAXGUSD";

export function symbolLabel(symbol: string): string {
  const found = TRADE_SYMBOLS.find((s) => s.symbol === symbol);
  return found?.label ?? symbol;
}
