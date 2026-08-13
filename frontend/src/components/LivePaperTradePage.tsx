import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchMarketTicker,
  fetchStrategyAnalyze,
  type StrategyAnalyzeResponse,
} from "../lib/api";
import { formatIstDateTime, formatPrice } from "../lib/chartData";
import {
  baseLabel,
  checkExit,
  closeOpenTrade,
  formatUsd,
  loadPaperStore,
  openPaperTrade,
  savePaperStore,
  unrealizedPnlUsd,
  type ClosedPaperTrade,
  type OpenPaperTrade,
} from "../lib/paperTrade";
import { type TradeSymbol } from "../lib/symbols";
import { AiLoader } from "./AiLoader";

type Props = {
  symbol: TradeSymbol;
  onSymbolChange?: (symbol: TradeSymbol) => void;
};

const SIGNAL_POLL_MS = 15_000;
const TICKER_POLL_MS = 5_000;

export function LivePaperTradePage({ symbol }: Props) {
  const [autoPick, setAutoPick] = useState(true);
  const [open, setOpen] = useState<OpenPaperTrade | null>(null);
  const [history, setHistory] = useState<ClosedPaperTrade[]>([]);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [signal, setSignal] = useState<StrategyAnalyzeResponse | null>(null);
  const [status, setStatus] = useState("Starting…");
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const closingRef = useRef(false);

  const syncFromStore = useCallback(() => {
    const store = loadPaperStore();
    setHistory(store.history);
    setOpen(
      store.open && store.open.symbol === symbol ? store.open : null,
    );
  }, [symbol]);

  useEffect(() => {
    syncFromStore();
    setHydrated(true);
  }, [syncFromStore]);

  const closeOpen = useCallback(
    (tradeId: string, price: number, reason: "TP" | "SL" | "MANUAL") => {
      if (closingRef.current) return;
      closingRef.current = true;
      try {
        const closed = closeOpenTrade(tradeId, price, reason);
        if (!closed) return;
        syncFromStore();
        setStatus(`Closed via ${reason} @ ${formatPrice(price)}`);
      } finally {
        closingRef.current = false;
      }
    },
    [syncFromStore],
  );

  // Ticker + SL/TP monitor
  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;
    let inFlight = false;

    const tick = async () => {
      if (cancelled || inFlight) return;
      inFlight = true;
      try {
        const t = await fetchMarketTicker(symbol);
        if (cancelled) return;
        const price = t.last ?? t.mark_price ?? t.bid ?? t.ask ?? null;
        if (price == null || !Number.isFinite(price)) {
          setError("No live ticker price");
          return;
        }
        setCurrentPrice(price);
        setError(null);

        const storeOpen = loadPaperStore().open;
        const active =
          storeOpen && storeOpen.symbol === symbol ? storeOpen : null;
        if (active) {
          const hit = checkExit(active, price);
          if (hit) {
            closeOpen(active.id, hit.exit, hit.reason);
          }
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Ticker failed");
        }
      } finally {
        inFlight = false;
      }
    };

    void tick();
    const id = window.setInterval(() => void tick(), TICKER_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [symbol, hydrated, closeOpen]);

  // Strategy poll → auto-pick BUY/SELL
  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;
    let inFlight = false;

    const poll = async () => {
      if (cancelled || inFlight) return;
      inFlight = true;
      try {
        const res = await fetchStrategyAnalyze({ limit: 400, symbol });
        if (cancelled) return;
        setSignal(res);
        setStatus(
          `Signal ${res.signal} · score ${res.score} · ${formatIstDateTime(res.as_of)}`,
        );

        if (!autoPick) return;
        const store = loadPaperStore();
        if (store.open) {
          setStatus(
            store.open.symbol === symbol
              ? "Open trade running — waiting for SL / TP"
              : `Another symbol trade is open (${store.open.symbol})`,
          );
          return;
        }

        let price: number | null = null;
        try {
          const t = await fetchMarketTicker(symbol);
          price = t.last ?? t.mark_price ?? t.bid ?? t.ask ?? null;
        } catch {
          price = null;
        }
        if (price == null) return;

        const opened = openPaperTrade(
          symbol,
          {
            signal: res.signal,
            signalId: res.signal_id,
            asOf: res.as_of,
            entry: res.entry,
            stop_loss: res.stop_loss,
            targets: res.targets,
            score: res.score,
          },
          price,
        );
        if (opened) {
          syncFromStore();
          setStatus(`Picked ${opened.side} @ ${formatPrice(opened.entry)}`);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Signal poll failed");
        }
      } finally {
        inFlight = false;
      }
    };

    void poll();
    const id = window.setInterval(() => void poll(), SIGNAL_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [symbol, hydrated, autoPick, syncFromStore]);

  const activeOpen = open && open.symbol === symbol ? open : null;
  const pnl = useMemo(() => {
    if (!activeOpen || currentPrice == null) return null;
    return unrealizedPnlUsd(activeOpen, currentPrice);
  }, [activeOpen, currentPrice]);

  const symbolHistory = useMemo(
    () => history.filter((t) => t.symbol === symbol),
    [history, symbol],
  );

  const stats = useMemo(() => {
    const wins = symbolHistory.filter((t) => t.pnlUsd > 0).length;
    const losses = symbolHistory.filter((t) => t.pnlUsd < 0).length;
    const total = symbolHistory.reduce((s, t) => s + t.pnlUsd, 0);
    return { wins, losses, total, count: symbolHistory.length };
  }, [symbolHistory]);

  const manualClose = () => {
    if (!activeOpen || currentPrice == null) return;
    closeOpen(activeOpen.id, currentPrice, "MANUAL");
  };

  const clearHistory = () => {
    const prior = loadPaperStore();
    const kept = prior.history.filter((t) => t.symbol !== symbol);
    savePaperStore({
      open: prior.open,
      history: kept,
      consumedKeys: prior.consumedKeys,
    });
    syncFromStore();
  };

  return (
    <div className="overflow-x-hidden">
      <div className="mx-auto max-w-6xl px-3 pt-4 sm:px-6">
        <p className="text-xs uppercase tracking-[0.2em] text-gold-muted">
          Paper · research only
        </p>
        <h1 className="font-display text-2xl font-semibold text-gold-bright">
          Live Paper Trades
        </h1>
        <p className="mt-1 text-sm text-muted">
          Auto-picks live BUY/SELL · size {baseLabel(symbol)} · closes on SL / TP
        </p>
      </div>

      <main className="mx-auto max-w-6xl space-y-5 px-3 py-5 sm:px-6 sm:py-6">
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line/70 bg-panel/80 p-4">
          <div className="space-y-1 text-sm">
            <p className="text-cream">{status}</p>
            {error ? <p className="text-bear">{error}</p> : null}
            <p className="text-[11px] text-muted">
              Signal every {SIGNAL_POLL_MS / 1000}s · ticker every{" "}
              {TICKER_POLL_MS / 1000}s · not live broker execution
            </p>
          </div>
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-cream">
            <input
              type="checkbox"
              checked={autoPick}
              onChange={(e) => setAutoPick(e.target.checked)}
              className="h-4 w-4 accent-[var(--color-gold)]"
            />
            Auto-pick trades
          </label>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-line/70 bg-panel/80 p-4 sm:p-5">
            <h2 className="mb-4 text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
              Open trade
            </h2>
            {!hydrated ? (
              <AiLoader label="Loading paper book" size="sm" />
            ) : activeOpen ? (
              <OpenTradeCard
                trade={activeOpen}
                currentPrice={currentPrice}
                pnl={pnl}
                onManualClose={manualClose}
              />
            ) : (
              <div className="space-y-3 text-sm text-muted">
                <p>No open paper trade for {symbol}.</p>
                <p>
                  Waiting for strategy <span className="text-cream">BUY</span> /{" "}
                  <span className="text-cream">SELL</span> with entry, SL, and
                  TP1.
                </p>
                {signal ? (
                  <p className="rounded-lg border border-line/50 bg-ink/40 px-3 py-2 text-cream">
                    Latest signal:{" "}
                    <span
                      className={
                        signal.signal === "BUY"
                          ? "text-bull"
                          : signal.signal === "SELL"
                            ? "text-bear"
                            : "text-wait"
                      }
                    >
                      {signal.signal}
                    </span>{" "}
                    · score {signal.score}
                  </p>
                ) : null}
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-line/70 bg-panel/80 p-4 sm:p-5">
            <h2 className="mb-4 text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
              Session stats · {symbol}
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Trades" value={String(stats.count)} />
              <Stat label="Wins" value={String(stats.wins)} tone="bull" />
              <Stat label="Losses" value={String(stats.losses)} tone="bear" />
              <Stat
                label="Net P&L"
                value={formatUsd(stats.total)}
                tone={stats.total >= 0 ? "bull" : "bear"}
              />
            </div>
            <p className="mt-4 text-[11px] text-muted">
              Size fixed at {baseLabel(symbol)} (
              {activeOpen?.quantity ?? "—"} contracts × contract value). Stored
              in browser localStorage.
            </p>
          </div>
        </section>

        <section className="rounded-2xl border border-line/70 bg-panel/80 p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
              Closed trades · {symbol}
            </h2>
            {symbolHistory.length > 0 ? (
              <button
                type="button"
                onClick={clearHistory}
                className="rounded-md border border-line/70 px-2.5 py-1 text-[11px] text-muted hover:border-bear/50 hover:text-bear"
              >
                Clear {symbol} history
              </button>
            ) : null}
          </div>
          {symbolHistory.length === 0 ? (
            <p className="text-sm text-muted">
              No closed paper trades yet. When SL or TP hits, rows appear here.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-[10px] uppercase tracking-wider text-gold-muted">
                  <tr className="border-b border-line/50">
                    <th className="px-2 py-2 font-medium">Closed</th>
                    <th className="px-2 py-2 font-medium">Side</th>
                    <th className="px-2 py-2 font-medium">Entry</th>
                    <th className="px-2 py-2 font-medium">Exit</th>
                    <th className="px-2 py-2 font-medium">SL</th>
                    <th className="px-2 py-2 font-medium">TP</th>
                    <th className="px-2 py-2 font-medium">Reason</th>
                    <th className="px-2 py-2 font-medium">P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {symbolHistory.map((t) => (
                    <tr
                      key={t.id}
                      className="border-b border-line/30 text-cream"
                      data-testid="closed-paper-trade-row"
                    >
                      <td className="whitespace-nowrap px-2 py-2 text-muted">
                        {formatIstDateTime(t.closedAt)}
                      </td>
                      <td
                        className={`px-2 py-2 font-medium ${
                          t.side === "BUY" ? "text-bull" : "text-bear"
                        }`}
                      >
                        {t.side}
                      </td>
                      <td className="px-2 py-2">{formatPrice(t.entry)}</td>
                      <td className="px-2 py-2">{formatPrice(t.exit)}</td>
                      <td className="px-2 py-2 text-muted">
                        {formatPrice(t.stopLoss)}
                      </td>
                      <td className="px-2 py-2 text-muted">
                        {formatPrice(t.takeProfit)}
                      </td>
                      <td className="px-2 py-2">{t.exitReason}</td>
                      <td
                        className={`px-2 py-2 font-medium ${
                          t.pnlUsd >= 0 ? "text-bull" : "text-bear"
                        }`}
                      >
                        {formatUsd(t.pnlUsd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function OpenTradeCard({
  trade,
  currentPrice,
  pnl,
  onManualClose,
}: {
  trade: OpenPaperTrade;
  currentPrice: number | null;
  pnl: number | null;
  onManualClose: () => void;
}) {
  const pnlTone =
    pnl == null ? "text-cream" : pnl >= 0 ? "text-bull" : "text-bear";

  return (
    <div className="space-y-4" data-testid="open-paper-trade">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p
          className={`font-display text-3xl ${
            trade.side === "BUY" ? "text-bull" : "text-bear"
          }`}
        >
          {trade.side}
        </p>
        <span className="rounded-md border border-gold/40 bg-gold/10 px-2 py-1 text-[11px] uppercase tracking-wide text-gold-bright">
          {baseLabel(trade.symbol)}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
        <Row label="Entry" value={formatPrice(trade.entry)} />
        <Row
          label="Current"
          value={currentPrice != null ? formatPrice(currentPrice) : "—"}
        />
        <Row
          label="Unrealized P&L"
          value={formatUsd(pnl)}
          valueClass={pnlTone}
        />
        <Row label="Stop loss" value={formatPrice(trade.stopLoss)} />
        <Row label="Take profit" value={formatPrice(trade.takeProfit)} />
        <Row label="Opened" value={formatIstDateTime(trade.openedAt)} />
      </dl>

      <button
        type="button"
        onClick={onManualClose}
        disabled={currentPrice == null}
        className="rounded-lg border border-bear/40 bg-bear/10 px-3 py-2 text-sm text-bear hover:bg-bear/20 disabled:opacity-40"
      >
        Close at market
      </button>
    </div>
  );
}

function Row({
  label,
  value,
  valueClass = "text-cream",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-lg border border-line/40 bg-ink/30 px-3 py-2">
      <dt className="text-[10px] uppercase tracking-wider text-gold-muted">
        {label}
      </dt>
      <dd className={`mt-1 font-medium tabular-nums ${valueClass}`}>{value}</dd>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "bull" | "bear";
}) {
  const toneClass =
    tone === "bull" ? "text-bull" : tone === "bear" ? "text-bear" : "text-cream";
  return (
    <div className="rounded-lg border border-line/40 bg-ink/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-gold-muted">
        {label}
      </p>
      <p className={`mt-1 text-lg font-semibold tabular-nums ${toneClass}`}>
        {value}
      </p>
    </div>
  );
}
