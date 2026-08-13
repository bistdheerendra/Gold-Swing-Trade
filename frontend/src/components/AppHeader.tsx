import { useEffect, useState, type ReactNode } from "react";
import { Menu, Sparkles, X } from "lucide-react";
import { fetchHealth, type HealthResponse } from "../lib/api";
import { SymbolSelector } from "./SymbolSelector";
import type { TradeSymbol } from "../lib/symbols";

export type AppPage =
  | "dashboard"
  | "backtest"
  | "ml"
  | "ml-lab"
  | "risk"
  | "paper";

const NAV: { id: AppPage; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "backtest", label: "Backtest" },
  { id: "ml", label: "ML Dataset" },
  { id: "ml-lab", label: "ML Model Lab" },
  { id: "risk", label: "Risk" },
  { id: "paper", label: "Live Paper" },
];

type Props = {
  page: AppPage;
  onNavigate: (page: AppPage) => void;
  symbol: TradeSymbol;
  onSymbolChange: (symbol: TradeSymbol) => void;
};

/**
 * Global app header — brand, status, symbol, nav.
 * Sticky + responsive: desktop nav row, mobile drawer.
 */
export function AppHeader({
  page,
  onNavigate,
  symbol,
  onSymbolChange,
}: Props) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((data) => {
        if (!cancelled) {
          setHealth(data);
          setHealthError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setHealthError(err instanceof Error ? err.message : "API offline");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setMenuOpen(false);
  }, [page]);

  const apiOnline = Boolean(health) && !healthError;
  const phase =
    health?.phase != null ? String(health.phase) : healthError ? "—" : "…";

  const go = (id: AppPage) => {
    setMenuOpen(false);
    onNavigate(id);
  };

  return (
    <header
      className="sticky top-0 z-40 border-b border-line/70 bg-ink-soft/90 backdrop-blur-md"
      data-testid="app-header"
    >
      <div className="mx-auto max-w-[1440px] px-3 sm:px-4 md:px-6">
        {/* Top bar */}
        <div className="flex items-center gap-2 py-2.5 sm:gap-3 sm:py-3">
          <button
            type="button"
            onClick={() => go("dashboard")}
            className="flex min-w-0 items-center gap-2.5 text-left sm:gap-3"
            aria-label="Gold Swing AI home"
          >
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-gold/40 bg-gradient-to-br from-gold/30 to-gold-deep/20 shadow-[0_0_20px_rgba(212,175,55,0.15)] sm:h-10 sm:w-10">
              <Sparkles className="h-4 w-4 text-gold-bright sm:h-5 sm:w-5" />
            </span>
            <span className="min-w-0">
              <span className="block truncate font-display text-lg font-semibold tracking-wide text-gold-bright sm:text-xl md:text-2xl">
                Gold Swing AI
              </span>
              <span className="hidden truncate text-[10px] uppercase tracking-[0.16em] text-gold-muted sm:block">
                Decision support · no auto execution
              </span>
            </span>
          </button>

          <div className="ml-auto flex min-w-0 items-center gap-1.5 sm:gap-2">
            <StatusDot
              online={apiOnline}
              label={apiOnline ? "API" : "API off"}
              className="hidden sm:inline-flex"
            />
            <MetaPill className="hidden md:inline-flex" label="Phase" value={phase} />
            <div className="min-w-0 shrink">
              <SymbolSelector value={symbol} onChange={onSymbolChange} />
            </div>

            {/* Desktop / large tablet nav */}
            <nav
              className="ml-1 hidden items-center gap-1 lg:flex"
              aria-label="Primary"
            >
              {NAV.map((item) => (
                <NavLink
                  key={item.id}
                  active={page === item.id}
                  onClick={() => go(item.id)}
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>

            <button
              type="button"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line/80 text-gold-bright hover:border-gold/50 lg:hidden"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((o) => !o)}
            >
              {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile / tablet drawer */}
      {menuOpen ? (
        <div className="border-t border-line/50 bg-ink/95 lg:hidden">
          <div className="mx-auto flex max-w-[1440px] flex-col gap-3 px-3 py-3 sm:px-4 md:px-6">
            <div className="flex flex-wrap items-center gap-2">
              <StatusDot online={apiOnline} label={apiOnline ? "Online" : "Offline"} />
              <MetaPill label="Phase" value={phase} />
              <MetaPill label="Symbol" value={symbol} />
            </div>
            <nav className="flex flex-col gap-1.5" aria-label="Mobile">
              {NAV.map((item) => (
                <NavLink
                  key={item.id}
                  active={page === item.id}
                  onClick={() => go(item.id)}
                  className="w-full justify-start px-3 py-2.5 text-sm"
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      ) : null}
    </header>
  );
}

function NavLink({
  children,
  onClick,
  active,
  className = "",
}: {
  children: ReactNode;
  onClick: () => void;
  active?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={
        active
          ? `inline-flex items-center rounded-full bg-gold px-3 py-1.5 text-xs font-semibold text-ink hover:bg-gold-bright ${className}`
          : `inline-flex items-center rounded-full border border-line/70 px-3 py-1.5 text-xs font-medium text-muted hover:border-gold/40 hover:text-gold-bright ${className}`
      }
    >
      {children}
    </button>
  );
}

function MetaPill({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border border-line/70 px-2 py-1 text-[10px] uppercase tracking-wide text-muted sm:px-2.5 ${className}`}
    >
      <span className="mr-1 opacity-60">{label}</span>
      <span className="font-semibold normal-case tracking-normal text-gold-bright">
        {value}
      </span>
    </span>
  );
}

function StatusDot({
  online,
  label,
  className = "",
}: {
  online: boolean;
  label: string;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[10px] uppercase tracking-wide ${
        online
          ? "border-bull/40 text-bull"
          : "border-bear/40 text-bear"
      } ${className}`}
      title={label}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          online ? "animate-pulse bg-bull" : "bg-bear"
        }`}
        aria-hidden
      />
      <span className="hidden sm:inline">{label}</span>
    </span>
  );
}
