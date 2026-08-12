import { describe, expect, it } from "vitest";
import {
  dominantSessionId,
  sessionsForTimestamp,
  supportsSessionBands,
  type SessionDefinition,
} from "./sessions";

/** API-shaped defs: local London/NY + derived overlap (summer UTC display optional). */
const DEFS: SessionDefinition[] = [
  {
    id: "asia",
    name: "Asia",
    ist_window: "5:30 AM – 2:30 PM",
    utc_start_minute: 0,
    utc_end_minute: 540,
    utc_window: "00:00–09:00 UTC",
    behavior: "range",
    color: "#3b82f6",
    emoji: "🟦",
    chart_fill: "rgba(59, 130, 246, 0.12)",
    priority: 1,
    window_mode: "fixed_utc",
  },
  {
    id: "london",
    name: "London",
    ist_window: "12:30 PM – 9:30 PM",
    utc_start_minute: 420,
    utc_end_minute: 960,
    utc_window: "07:00–16:00 UTC",
    behavior: "vol up",
    color: "#eab308",
    emoji: "🟨",
    chart_fill: "rgba(234, 179, 8, 0.12)",
    priority: 2,
    window_mode: "local",
    timezone: "Europe/London",
    local_start_minute: 8 * 60,
    local_end_minute: 17 * 60,
  },
  {
    id: "new_york",
    name: "New York",
    ist_window: "5:30 PM – 2:30 AM",
    utc_start_minute: 720,
    utc_end_minute: 1260,
    utc_window: "12:00–21:00 UTC",
    behavior: "high move",
    color: "#ef4444",
    emoji: "🟥",
    chart_fill: "rgba(239, 68, 68, 0.14)",
    priority: 3,
    window_mode: "local",
    timezone: "America/New_York",
    local_start_minute: 8 * 60,
    local_end_minute: 17 * 60,
  },
  {
    id: "london_ny_overlap",
    name: "London + NY Overlap",
    ist_window: "5:30 PM – 9:30 PM",
    utc_start_minute: 720,
    utc_end_minute: 960,
    utc_window: "12:00–16:00 UTC",
    behavior: "peak",
    color: "#f97316",
    emoji: "🔥",
    chart_fill: "rgba(249, 115, 22, 0.22)",
    priority: 4,
    window_mode: "overlap",
  },
];

describe("sessions tagging (DST-aware)", () => {
  it("tags Asia+London at 07:00 UTC in summer", () => {
    expect(sessionsForTimestamp("2026-06-15T07:00:00Z", DEFS).sort()).toEqual([
      "asia",
      "london",
    ]);
  });

  it("opens New York at 12:00 UTC in summer (EDT)", () => {
    expect(sessionsForTimestamp("2026-06-15T12:00:00Z", DEFS).sort()).toEqual([
      "london",
      "london_ny_overlap",
      "new_york",
    ]);
  });

  it("keeps New York closed at 12:00 UTC in winter (EST)", () => {
    expect(sessionsForTimestamp("2026-01-15T12:00:00Z", DEFS).sort()).toEqual([
      "london",
    ]);
  });

  it("handles US-on / UK-off spring transition week", () => {
    // 2026-03-15: US EDT, UK still GMT → NY open 12:00, London open 08:00
    expect(sessionsForTimestamp("2026-03-15T12:00:00Z", DEFS).sort()).toEqual([
      "london",
      "london_ny_overlap",
      "new_york",
    ]);
    expect(sessionsForTimestamp("2026-03-15T07:00:00Z", DEFS)).toEqual(["asia"]);
  });

  it("prefers overlap as dominant color", () => {
    expect(
      dominantSessionId(["london", "new_york", "london_ny_overlap"], DEFS),
    ).toBe("london_ny_overlap");
  });

  it("only allows intraday band timeframes", () => {
    expect(supportsSessionBands("15m")).toBe(true);
    expect(supportsSessionBands("4h")).toBe(false);
  });
});
