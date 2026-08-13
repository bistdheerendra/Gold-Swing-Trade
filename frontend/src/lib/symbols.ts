/** Research symbols — decision-support only (no live broker). */

export type TradeSymbol = "PAXGUSD" | "SLVONUSD";

export type InstrumentTheme = "gold" | "silver";

export type SymbolMeta = {
  symbol: TradeSymbol;
  label: string;
  shortLabel: string;
  description: string;
  theme: InstrumentTheme;
};

export const TRADE_SYMBOLS: SymbolMeta[] = [
  {
    symbol: "PAXGUSD",
    label: "PAX Gold / PAXGUSD",
    shortLabel: "PAXGUSD",
    description: "Delta India live perpetual",
    theme: "gold",
  },
  {
    symbol: "SLVONUSD",
    label: "iShares Silver / SLVONUSD",
    shortLabel: "SLVONUSD",
    description: "Delta India live silver perpetual (independent research track)",
    theme: "silver",
  },
];

export const DEFAULT_SYMBOL: TradeSymbol = "PAXGUSD";

export function symbolLabel(symbol: string): string {
  const found = TRADE_SYMBOLS.find((s) => s.symbol === symbol);
  return found?.label ?? symbol;
}

export function themeForSymbol(symbol: string): InstrumentTheme {
  const found = TRADE_SYMBOLS.find((s) => s.symbol === symbol);
  return found?.theme ?? "gold";
}
