/**
 * Instrument theme application — token-level gold/silver swap.
 * Sets data-instrument-theme on <html> so CSS variables cascade site-wide.
 */

import { themeForSymbol, type InstrumentTheme, type TradeSymbol } from "./symbols";

export function applyInstrumentTheme(symbol: TradeSymbol | string): InstrumentTheme {
  const theme = themeForSymbol(symbol);
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-instrument-theme", theme);
  }
  return theme;
}
