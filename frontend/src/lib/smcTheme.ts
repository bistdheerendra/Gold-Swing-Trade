/** Central SMC overlay visual tokens — do not scatter hex in components. */

export const SMC_COLORS = {
  swingHigh: "#f0d78c",
  swingLow: "#7ec8e3",
  bos: "#3ecf8e",
  choch: "#c084fc",
  fvgBull: "rgba(62, 207, 142, 0.35)",
  fvgBear: "rgba(239, 107, 107, 0.35)",
  orderBlock: "#f59e0b",
  demand: "#34d399",
  supply: "#f87171",
  liquidity: "#60a5fa",
  sweep: "#fb7185",
} as const;

export type SmcOverlayKey =
  | "swing"
  | "bos"
  | "choch"
  | "fvg"
  | "ob"
  | "zones"
  | "liq"
  | "sweep";

export type SmcOverlayVisibility = Record<SmcOverlayKey, boolean>;

export const DEFAULT_SMC_OVERLAYS: SmcOverlayVisibility = {
  swing: false,
  bos: false,
  choch: false,
  fvg: false,
  ob: false,
  zones: false,
  liq: false,
  sweep: false,
};
