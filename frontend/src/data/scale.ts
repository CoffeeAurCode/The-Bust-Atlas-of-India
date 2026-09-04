import { scaleLinear } from "d3-scale";
import { interpolateRgbBasis } from "d3-interpolate";

function cssVar(name: string): string {
  if (typeof window === "undefined") return "#000";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#000";
}

/** Sequential risk ramp from the design tokens, rebuilt when the theme changes. */
export function riskRamp(): (t: number) => string {
  const stops = [0, 1, 2, 3, 4, 5].map((i) => cssVar(`--risk-${i}`));
  const interp = interpolateRgbBasis(stops);
  return (t: number) => interp(Math.max(0, Math.min(1, t)));
}

/** Map a bust probability to 0..1 for the ramp. Base rate ~5%, so a mild power curve
 *  spreads the interesting low range and saturates around 40%. */
export const probToT = scaleLinear().domain([0, 0.05, 0.15, 0.4]).range([0, 0.28, 0.62, 1]).clamp(true);

/** Atlas bust rate: 0..~12% is the meaningful range. */
export const rateToT = scaleLinear().domain([0, 0.05, 0.12]).range([0, 0.5, 1]).clamp(true);

/** Atlas error percentile: relative to the national p95 for that lead. */
export function errToT(value: number, ref: number): number {
  return Math.max(0, Math.min(1, value / (ref * 1.6)));
}
