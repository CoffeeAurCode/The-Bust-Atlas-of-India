import type { Band, LeadPrediction, Meta } from "./schema";

/** Render a driver into a sentence using the templates shipped in meta.json. */
export function driverSentence(meta: Meta, feature: string, contribution: number, lead: number, season: string, stdPct: number): string {
  const rule = meta.rules[feature];
  if (!rule) return feature;
  const tpl = contribution > 0 ? rule[0] : rule[1];
  const pct = Math.max(1, Math.round((1 - stdPct) * 100));
  return tpl
    .replaceAll("{lead}", String(lead))
    .replaceAll("{lead_prev}", String(Math.max(lead - 1, 1)))
    .replaceAll("{season}", meta.season_words[season] ?? "this season")
    .replaceAll("{pct}", String(pct));
}

export function forecasterNote(meta: Meta, lp: LeadPrediction, season: string): string[] {
  return lp.drivers.map((d) => driverSentence(meta, d.feature, d.contribution, lp.lead, season, lp.std_pct_climo));
}

export const BAND_LABEL: Record<Band, string> = {
  low: "Low risk",
  moderate: "Moderate",
  high: "High risk",
  severe: "Severe",
};

export function seasonOf(init: string): string {
  const m = Number(init.slice(5, 7));
  if (m === 12 || m <= 2) return "DJF";
  if (m <= 5) return "MAM";
  if (m <= 9) return "JJAS";
  return "ON";
}

export function fmtInit(init: string): string {
  const d = new Date(init.slice(0, 10) + "T00:00:00Z");
  const day = d.getUTCDate();
  const month = d.toLocaleString("en-GB", { month: "long", timeZone: "UTC" });
  return `${day} ${month} ${d.getUTCFullYear()}, ${init.slice(11, 13)}Z`;
}

export function pct(p: number, digits = 0): string {
  return (p * 100).toFixed(digits) + "%";
}
