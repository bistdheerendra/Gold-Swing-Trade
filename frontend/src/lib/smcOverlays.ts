import type { SeriesMarker, UTCTimestamp } from "lightweight-charts";
import type { OHLCVBar, SmcAnalyzeResponse, SmcEventDto } from "./api";
import { toChartTime } from "./chartData";
import { SMC_COLORS, type SmcOverlayVisibility } from "./smcTheme";

function timeAt(bars: readonly OHLCVBar[], index: number): UTCTimestamp | null {
  const bar = bars[index];
  if (!bar) return null;
  return toChartTime(bar.timestamp);
}

function marker(
  time: UTCTimestamp,
  position: "aboveBar" | "belowBar",
  color: string,
  shape: "arrowUp" | "arrowDown" | "circle",
  text: string,
): SeriesMarker<UTCTimestamp> {
  return { time, position, color, shape, text };
}

type StructureWithSwings = SmcAnalyzeResponse["structure"] & {
  swing_highs?: SmcEventDto[];
  swing_lows?: SmcEventDto[];
};

export function buildSmcMarkers(
  bars: readonly OHLCVBar[],
  smc: SmcAnalyzeResponse | null,
  visibility: SmcOverlayVisibility,
): SeriesMarker<UTCTimestamp>[] {
  if (!smc) return [];
  const markers: SeriesMarker<UTCTimestamp>[] = [];
  const structure = smc.structure as StructureWithSwings;

  if (visibility.swing) {
    for (const s of structure.swing_highs?.slice(-8) ?? []) {
      const t = timeAt(bars, s.confirm_index);
      if (t) markers.push(marker(t, "aboveBar", SMC_COLORS.swingHigh, "circle", "SH"));
    }
    for (const s of structure.swing_lows?.slice(-8) ?? []) {
      const t = timeAt(bars, s.confirm_index);
      if (t) markers.push(marker(t, "belowBar", SMC_COLORS.swingLow, "circle", "SL"));
    }
  }

  if (visibility.bos) {
    for (const e of smc.bos.slice(-10)) {
      const t = timeAt(bars, e.confirm_index);
      if (!t) continue;
      const bull = e.direction === "BULLISH";
      markers.push(
        marker(t, bull ? "belowBar" : "aboveBar", SMC_COLORS.bos, bull ? "arrowUp" : "arrowDown", "BOS"),
      );
    }
  }

  if (visibility.choch) {
    for (const e of smc.choch.slice(-10)) {
      const t = timeAt(bars, e.confirm_index);
      if (!t) continue;
      const bull = e.direction === "BULLISH";
      markers.push(
        marker(
          t,
          bull ? "belowBar" : "aboveBar",
          SMC_COLORS.choch,
          bull ? "arrowUp" : "arrowDown",
          "CHoCH",
        ),
      );
    }
  }

  if (visibility.sweep) {
    for (const e of smc.liquidity_sweeps.slice(-8)) {
      const t = timeAt(bars, e.confirm_index);
      if (t) markers.push(marker(t, "aboveBar", SMC_COLORS.sweep, "circle", "SWP"));
    }
  }

  // Lightweight Charts requires ascending time; equal times are allowed.
  markers.sort((a, b) => Number(a.time) - Number(b.time));
  return markers;
}

export type SmcPriceLevel = {
  price: number;
  color: string;
  title: string;
};

export function buildSmcPriceLevels(
  smc: SmcAnalyzeResponse | null,
  visibility: SmcOverlayVisibility,
): SmcPriceLevel[] {
  if (!smc) return [];
  const levels: SmcPriceLevel[] = [];

  if (visibility.fvg) {
    for (const f of smc.fvg.filter((x) => x.valid).slice(-4)) {
      const color = f.direction === "BULLISH" ? SMC_COLORS.fvgBull : SMC_COLORS.fvgBear;
      if (f.high != null) levels.push({ price: f.high, color, title: "FVG H" });
      if (f.low != null) levels.push({ price: f.low, color, title: "FVG L" });
    }
  }
  if (visibility.ob) {
    for (const z of smc.order_blocks.filter((x) => x.valid).slice(-3)) {
      if (z.high != null) levels.push({ price: z.high, color: SMC_COLORS.orderBlock, title: "OB H" });
      if (z.low != null) levels.push({ price: z.low, color: SMC_COLORS.orderBlock, title: "OB L" });
    }
  }
  if (visibility.zones) {
    for (const z of smc.demand_zones.filter((x) => x.valid).slice(-2)) {
      if (z.low != null) levels.push({ price: z.low, color: SMC_COLORS.demand, title: "DEM" });
    }
    for (const z of smc.supply_zones.filter((x) => x.valid).slice(-2)) {
      if (z.high != null) levels.push({ price: z.high, color: SMC_COLORS.supply, title: "SUP" });
    }
  }
  if (visibility.liq) {
    for (const p of smc.liquidity.slice(-6)) {
      if (p.price != null) levels.push({ price: p.price, color: SMC_COLORS.liquidity, title: "LIQ" });
    }
  }
  return levels;
}
