import type { ReactNode } from "react";

type AiLoaderSize = "sm" | "md" | "lg";

type AiLoaderProps = {
  label?: string;
  size?: AiLoaderSize;
  className?: string;
  /** Fill parent and center the loader (chart panels, page sections). */
  fill?: boolean;
  /** Compact inline row for buttons / tight spaces. */
  inline?: boolean;
};

const SIZE: Record<
  AiLoaderSize,
  { brick: string; ring: string; label: string; gap: string }
> = {
  sm: {
    brick: "h-5 w-8",
    ring: "h-12 w-12",
    label: "text-[10px]",
    gap: "gap-2",
  },
  md: {
    brick: "h-8 w-14",
    ring: "h-20 w-20",
    label: "text-xs",
    gap: "gap-3",
  },
  lg: {
    brick: "h-11 w-20",
    ring: "h-28 w-28",
    label: "text-sm",
    gap: "gap-4",
  },
};

/**
 * Gold-brick AI loader with a scanning beam — matches Gold Swing AI terminal theme.
 */
export function AiLoader({
  label = "Analyzing…",
  size = "md",
  className = "",
  fill = false,
  inline = false,
}: AiLoaderProps) {
  const s = SIZE[size];

  const core = (
    <div
      className={`ai-loader ${inline ? "ai-loader--inline" : ""} ${s.gap} ${className}`}
      role="status"
      aria-live="polite"
      aria-label={label || "Loading"}
      data-testid="ai-loader"
    >
      <div className={`ai-loader__stage ${s.ring}`}>
        <div className="ai-loader__orbit" aria-hidden />
        <div className="ai-loader__pulse" aria-hidden />
        <div className={`ai-loader__brick ${s.brick}`} aria-hidden>
          <span className="ai-loader__bevel ai-loader__bevel--top" />
          <span className="ai-loader__bevel ai-loader__bevel--side" />
          <span className="ai-loader__face">
            <span className="ai-loader__ingot" />
            <span className="ai-loader__scan" />
            <span className="ai-loader__glint" />
          </span>
        </div>
      </div>
      {label ? (
        <p
          className={`ai-loader__label font-display tracking-[0.18em] uppercase text-gold-muted ${s.label}`}
        >
          {label}
        </p>
      ) : null}
    </div>
  );

  if (fill) {
    return (
      <div className="grid h-full min-h-[120px] w-full place-items-center">
        {core}
      </div>
    );
  }

  return core;
}

/** Full-area overlay for long-running actions (backtest / train / build). */
export function AiLoaderOverlay({
  label = "Processing…",
  visible,
}: {
  label?: string;
  visible: boolean;
}): ReactNode {
  if (!visible) return null;
  return (
    <div
      className="absolute inset-0 z-20 grid place-items-center rounded-2xl bg-ink/70 backdrop-blur-[2px]"
      data-testid="ai-loader-overlay"
    >
      <AiLoader label={label} size="lg" />
    </div>
  );
}
