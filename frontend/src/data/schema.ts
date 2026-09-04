import { z } from "zod";

export const Band = z.enum(["low", "moderate", "high", "severe"]);
export type Band = z.infer<typeof Band>;

export const Meta = z.object({
  product: z.string(),
  source: z.string(),
  source_label: z.string(),
  members: z.number(),
  grid: z.string(),
  variable: z.string(),
  leads: z.array(z.number().int()),
  years: z.record(z.string(), z.array(z.number().int())),
  regions: z.array(z.object({
    id: z.string(),
    label: z.string(),
    box: z.array(z.number()).length(4),
    centroid: z.array(z.number()).length(2),
  })),
  state_to_region: z.record(z.string(), z.string()),
  seasons: z.array(z.object({ id: z.string(), label: z.string() })),
  bust_definition: z.string(),
  bands: z.record(z.string(), z.number()),
  flag_threshold: z.number(),
  generated_at: z.string(),
  git_sha: z.string(),
  model: z.record(z.string(), z.unknown()),
  rules: z.record(z.string(), z.array(z.string()).length(2)),
  season_words: z.record(z.string(), z.string()),
  synthetic: z.boolean().default(false),
});
export type Meta = z.infer<typeof Meta>;

export const AtlasCell = z.object({
  region: z.string(),
  lead: z.number().int(),
  season: z.string(),
  n: z.number().int(),
  bust_rate: z.number(),
  err_p50: z.number(),
  err_p90: z.number(),
  err_p95: z.number(),
  err_max: z.number(),
  spread_p50: z.number(),
  spread_p95: z.number(),
  spread_skill: z.number(),
  worst_events: z.array(z.object({ init: z.string(), error: z.number() })),
});
export type AtlasCell = z.infer<typeof AtlasCell>;

export const Atlas = z.object({
  cells: z.array(AtlasCell),
  national: z.array(z.object({
    lead: z.number().int(), season: z.string(), n: z.number().int(),
    bust_rate: z.number(), err_p50: z.number(), err_p95: z.number(),
  })),
});
export type Atlas = z.infer<typeof Atlas>;

export const Inits = z.object({ inits: z.array(z.string()) });

export const LeadPrediction = z.object({
  lead: z.number().int(),
  prob: z.number(),
  baseline_prob: z.number(),
  band: Band,
  flag: z.boolean(),
  std: z.number(),
  std_pct_climo: z.number(),
  cluster_gap: z.number(),
  jumpiness: z.number().nullable(),
  drivers: z.array(z.object({ feature: z.string(), contribution: z.number() })),
  outcome: z.object({ error: z.number(), threshold: z.number(), busted: z.boolean() }).nullable(),
});
export type LeadPrediction = z.infer<typeof LeadPrediction>;

export const Prediction = z.object({
  init: z.string(),
  source: z.string(),
  regions: z.record(z.string(), z.object({ leads: z.array(LeadPrediction) })),
});
export type Prediction = z.infer<typeof Prediction>;

const Bin = z.object({
  bin: z.number().int(), lo: z.number(), hi: z.number(), n: z.number().int(),
  mean_forecast: z.number().nullable(), observed_freq: z.number().nullable(),
});
const PRPoint = z.object({ threshold: z.number(), precision: z.number().nullable(), recall: z.number().nullable() });
const Scores = z.object({
  brier: z.number(), bss_vs_climatology: z.number(), bss_vs_spread: z.number().nullable().optional(),
  pr_auc: z.number(), roc_auc: z.number(), reliability: z.array(Bin), pr_curve: z.array(PRPoint),
});
export const Eval = z.object({
  n: z.number().int(), positives: z.number().int(), base_rate: z.number(),
  model: Scores, baseline: Scores,
  by_lead: z.array(z.record(z.string(), z.unknown())),
  by_region: z.array(z.record(z.string(), z.unknown())),
  test_years: z.array(z.number().int()),
});
export type Eval = z.infer<typeof Eval>;

export const CaseStudies = z.object({
  cases: z.array(z.object({
    id: z.string(), title: z.string(), kind: z.enum(["bust", "verified"]),
    init: z.string(), region: z.string(), lead: z.number().int(), prob: z.number(),
    narrative: z.object({ setup: z.string(), flag: z.string(), why: z.string(), outcome: z.string() }),
  })),
});
export type CaseStudies = z.infer<typeof CaseStudies>;
export type CaseStudy = CaseStudies["cases"][number];

export type GeoFeature = {
  type: "Feature";
  properties: { name: string };
  geometry: GeoJSON.Geometry;
};
export type GeoCollection = { type: "FeatureCollection"; features: GeoFeature[] };
