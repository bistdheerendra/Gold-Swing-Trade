import { useEffect, useRef } from "react";
import {
  ColorType,
  CrosshairMode,
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type MouseEventParams,
  type UTCTimestamp,
} from "lightweight-charts";
import type { OHLCVBar, SmcAnalyzeResponse } from "../../lib/api";
import {
  EMA_COLORS,
  barsToCandles,
  barsToEmaSeries,
  formatIstDateTime,
  formatPrice,
  fromChartTime,
} from "../../lib/chartData";
import { DEFAULT_EMA_PERIODS, type EmaPeriod } from "../../lib/ema";
import { barsToSessionHistogram } from "../../lib/sessionBands";
import {
  supportsSessionBands,
  type SessionDefinition,
} from "../../lib/sessions";
import { buildSmcMarkers, buildSmcPriceLevels } from "../../lib/smcOverlays";
import {
  DEFAULT_SMC_OVERLAYS,
  type SmcOverlayVisibility,
} from "../../lib/smcTheme";

export type OhlcReadout = {
  time: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
};

type CandlestickChartProps = {
  bars: readonly OHLCVBar[];
  height?: number;
  showEma?: Partial<Record<EmaPeriod, boolean>>;
  smc?: SmcAnalyzeResponse | null;
  smcVisibility?: SmcOverlayVisibility;
  /** Session definitions from GET /api/market/sessions (single source of truth). */
  sessionDefinitions?: readonly SessionDefinition[];
  /** Show session background bands (intraday TFs only). Toggle — no chart rebuild. */
  showSessionBands?: boolean;
  timeframe?: string;
  onCrosshairOhlc?: (readout: OhlcReadout) => void;
  className?: string;
};

const DEFAULT_EMA_VISIBILITY: Record<EmaPeriod, boolean> = {
  20: true,
  50: true,
  100: false,
  200: false,
};

type SmcLineHost = ISeriesApi<"Candlestick"> & { _smcLines?: IPriceLine[] };

/** Show recent bars with breathing room instead of packing the full series. */
const VISIBLE_BARS = 96;

function focusRecentBars(chart: IChartApi, barCount: number) {
  const from = Math.max(-2, barCount - VISIBLE_BARS);
  const to = barCount + 6;
  chart.timeScale().setVisibleLogicalRange({ from, to });
}

function clearSmcPriceLines(series: ISeriesApi<"Candlestick"> | null) {
  if (!series) return;
  const host = series as SmcLineHost;
  const existing = host._smcLines;
  if (!existing?.length) return;
  for (const line of existing) {
    try {
      series.removePriceLine(line);
    } catch {
      // Series may already be disposed during unmount
    }
  }
  host._smcLines = [];
}

function applySmcOverlays(
  series: ISeriesApi<"Candlestick"> | null,
  bars: readonly OHLCVBar[],
  smc: SmcAnalyzeResponse | null,
  visibility: SmcOverlayVisibility,
) {
  if (!series) return;
  try {
    series.setMarkers(buildSmcMarkers(bars, smc, visibility));
  } catch {
    try {
      series.setMarkers([]);
    } catch {
      /* ignore */
    }
  }

  clearSmcPriceLines(series);
  try {
    const levels = buildSmcPriceLevels(smc, visibility);
    const created = levels.map((level) =>
      series.createPriceLine({
        price: level.price,
        color: level.color,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: level.title,
      }),
    );
    (series as SmcLineHost)._smcLines = created;
  } catch {
    (series as SmcLineHost)._smcLines = [];
  }
}

function applySessionBands(
  series: ISeriesApi<"Histogram"> | null,
  bars: readonly OHLCVBar[],
  definitions: readonly SessionDefinition[],
  visible: boolean,
  timeframe: string | undefined,
) {
  if (!series) return;
  const allow =
    visible && Boolean(timeframe) && supportsSessionBands(timeframe ?? "");
  try {
    series.applyOptions({ visible: allow });
    if (!allow || !definitions.length) {
      series.setData([]);
      return;
    }
    series.setData(barsToSessionHistogram(bars, definitions));
  } catch {
    try {
      series.setData([]);
    } catch {
      /* ignore */
    }
  }
}

/**
 * Reusable gold-themed candlestick chart with EMA overlays.
 * Zoom / pan via Lightweight Charts timeScale; crosshair emits OHLC.
 */
export function CandlestickChartView({
  bars,
  height = 420,
  showEma = DEFAULT_EMA_VISIBILITY,
  smc = null,
  smcVisibility = DEFAULT_SMC_OVERLAYS,
  sessionDefinitions = [],
  showSessionBands = false,
  timeframe,
  onCrosshairOhlc,
  className,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const sessionRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const emaRefs = useRef<Partial<Record<EmaPeriod, ISeriesApi<"Line">>>>({});
  const barsRef = useRef(bars);
  const smcRef = useRef(smc);
  const smcVisibilityRef = useRef(smcVisibility);
  const showEmaRef = useRef(showEma);
  const sessionDefsRef = useRef(sessionDefinitions);
  const showSessionBandsRef = useRef(showSessionBands);
  const timeframeRef = useRef(timeframe);
  const onCrosshairRef = useRef(onCrosshairOhlc);
  const readyRef = useRef(false);

  barsRef.current = bars;
  smcRef.current = smc;
  smcVisibilityRef.current = smcVisibility;
  showEmaRef.current = showEma;
  sessionDefsRef.current = sessionDefinitions;
  showSessionBandsRef.current = showSessionBands;
  timeframeRef.current = timeframe;
  onCrosshairRef.current = onCrosshairOhlc;

  // Create chart once (or when height changes)
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#14120e" },
        textColor: "#a89a7c",
        fontFamily: "Manrope, ui-sans-serif, system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(58, 50, 36, 0.35)" },
        horzLines: { color: "rgba(58, 50, 36, 0.35)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "rgba(212, 175, 55, 0.45)", labelBackgroundColor: "#9a7420" },
        horzLine: { color: "rgba(212, 175, 55, 0.45)", labelBackgroundColor: "#9a7420" },
      },
      rightPriceScale: {
        borderColor: "#3a3224",
        scaleMargins: { top: 0.12, bottom: 0.14 },
      },
      timeScale: {
        borderColor: "#3a3224",
        timeVisible: true,
        secondsVisible: false,
        barSpacing: 12,
        minBarSpacing: 4,
        rightOffset: 10,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    });

    // Session bands behind candles (own scale, full-height translucent columns)
    const sessionSeries = chart.addHistogramSeries({
      priceScaleId: "sessions",
      lastValueVisible: false,
      priceLineVisible: false,
      base: 0,
    });
    chart.priceScale("sessions").applyOptions({
      visible: false,
      scaleMargins: { top: 0, bottom: 0 },
    });

    const candles = chart.addCandlestickSeries({
      upColor: "#3ecf8e",
      downColor: "#ef6b6b",
      borderUpColor: "#3ecf8e",
      borderDownColor: "#ef6b6b",
      wickUpColor: "#3ecf8e",
      wickDownColor: "#ef6b6b",
    });

    const emaSeries: Partial<Record<EmaPeriod, ISeriesApi<"Line">>> = {};
    for (const period of DEFAULT_EMA_PERIODS) {
      emaSeries[period] = chart.addLineSeries({
        color: EMA_COLORS[period],
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: `EMA ${period}`,
      });
    }

    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      const callback = onCrosshairRef.current;
      if (!callback) return;
      if (!param.time || !param.seriesData.size) {
        callback({ time: null, open: null, high: null, low: null, close: null });
        return;
      }
      const candle = param.seriesData.get(candles) as
        | { open: number; high: number; low: number; close: number }
        | undefined;
      if (!candle) {
        callback({ time: null, open: null, high: null, low: null, close: null });
        return;
      }
      const time =
        typeof param.time === "number"
          ? new Date(fromChartTime(param.time as UTCTimestamp) * 1000).toISOString()
          : null;
      callback({
        time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      });
    });

    chartRef.current = chart;
    candleRef.current = candles;
    sessionRef.current = sessionSeries;
    emaRefs.current = emaSeries;
    readyRef.current = true;

    // Seed current props without waiting for other effects
    const candleData = barsToCandles(barsRef.current);
    candles.setData(candleData);
    const emaData = barsToEmaSeries(barsRef.current);
    for (const period of DEFAULT_EMA_PERIODS) {
      const series = emaSeries[period];
      if (!series) continue;
      const visible = showEmaRef.current[period] ?? true;
      series.applyOptions({ visible });
      series.setData(visible ? (emaData[period] ?? []) : []);
    }
    applySmcOverlays(
      candles,
      barsRef.current,
      smcRef.current,
      smcVisibilityRef.current,
    );
    applySessionBands(
      sessionSeries,
      barsRef.current,
      sessionDefsRef.current,
      showSessionBandsRef.current,
      timeframeRef.current,
    );
    if (candleData.length > 0) {
      focusRecentBars(chart, candleData.length);
    }

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const nextWidth = Math.max(0, Math.floor(entry.contentRect.width));
      const nextHeight = Math.max(0, Math.floor(entry.contentRect.height));
      chart.applyOptions({
        width: nextWidth,
        ...(nextHeight > 0 ? { height: nextHeight } : {}),
      });
    });
    observer.observe(el);

    return () => {
      readyRef.current = false;
      observer.disconnect();
      clearSmcPriceLines(candleRef.current);
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      sessionRef.current = null;
      emaRefs.current = {};
    };
  }, [height]);

  // Bars / market data only — refit once when series changes
  useEffect(() => {
    if (!readyRef.current || !candleRef.current || !chartRef.current) return;

    const candleData = barsToCandles(bars);
    candleRef.current.setData(candleData);

    const emaData = barsToEmaSeries(bars);
    for (const period of DEFAULT_EMA_PERIODS) {
      const series = emaRefs.current[period];
      if (!series) continue;
      const visible = showEmaRef.current[period] ?? true;
      series.applyOptions({ visible });
      series.setData(visible ? (emaData[period] ?? []) : []);
    }

    applySmcOverlays(
      candleRef.current,
      bars,
      smcRef.current,
      smcVisibilityRef.current,
    );
    applySessionBands(
      sessionRef.current,
      bars,
      sessionDefsRef.current,
      showSessionBandsRef.current,
      timeframeRef.current,
    );

    if (candleData.length > 0) {
      focusRecentBars(chartRef.current, candleData.length);
    }
  }, [bars]);

  // EMA visibility toggle — no bar recompute, no fitContent flash
  useEffect(() => {
    if (!readyRef.current) return;
    for (const period of DEFAULT_EMA_PERIODS) {
      const series = emaRefs.current[period];
      if (!series) continue;
      const visible = showEma[period] ?? true;
      series.applyOptions({ visible });
    }
  }, [showEma]);

  // SMC overlay toggles — markers/price lines only (cheap, no blank flash)
  useEffect(() => {
    if (!readyRef.current || !candleRef.current) return;
    applySmcOverlays(candleRef.current, barsRef.current, smc, smcVisibility);
  }, [smc, smcVisibility]);

  // Session bands toggle / defs / TF — histogram only, no chart rebuild
  useEffect(() => {
    if (!readyRef.current) return;
    applySessionBands(
      sessionRef.current,
      barsRef.current,
      sessionDefinitions,
      showSessionBands,
      timeframe,
    );
  }, [sessionDefinitions, showSessionBands, timeframe]);

  return (
    <div
      ref={containerRef}
      className={className}
      data-testid="candlestick-chart"
      style={{ height }}
    />
  );
}

export function OhlcBanner({
  readout,
  fallbackClose,
}: {
  readout: OhlcReadout;
  fallbackClose?: number | null;
}) {
  const close = readout.close ?? fallbackClose ?? null;
  const bull =
    readout.open != null && readout.close != null
      ? readout.close >= readout.open
      : null;
  const tone =
    bull == null ? "text-cream" : bull ? "text-bull" : "text-bear";

  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-1 pb-3 text-[11px] font-medium tracking-wide text-muted sm:gap-x-5 sm:text-xs"
      data-testid="ohlc-banner"
    >
      <span>
        O <span className={tone}>{formatPrice(readout.open ?? close)}</span>
      </span>
      <span>
        H <span className="text-cream">{formatPrice(readout.high ?? close)}</span>
      </span>
      <span>
        L <span className="text-cream">{formatPrice(readout.low ?? close)}</span>
      </span>
      <span>
        C <span className={tone}>{formatPrice(close)}</span>
      </span>
      {readout.time ? (
        <span className="w-full truncate text-gold-muted sm:w-auto">
          {formatIstDateTime(readout.time)}
        </span>
      ) : null}
    </div>
  );
}
