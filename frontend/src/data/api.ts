import { z } from "zod";
import { Atlas, CaseStudies, Eval, Inits, Live, Meta, Prediction, type GeoCollection } from "./schema";

const cache = new Map<string, Promise<unknown>>();

async function load<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  if (!cache.has(path)) {
    cache.set(path, (async () => {
      const res = await fetch(path);
      if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
      const json = await res.json();
      const parsed = schema.safeParse(json);
      if (!parsed.success) throw new Error(`${path}: ${parsed.error.issues[0]?.path.join(".")} ${parsed.error.issues[0]?.message}`);
      return parsed.data;
    })().catch((e) => { cache.delete(path); throw e; }));
  }
  return cache.get(path) as Promise<T>;
}

export const api = {
  meta: () => load("/data/meta.json", Meta),
  atlas: () => load("/data/atlas.json", Atlas),
  inits: () => load("/data/inits.json", Inits),
  eval: () => load("/data/eval.json", Eval),
  cases: () => load("/data/case_studies.json", CaseStudies),
  live: () => load("/data/live.json", Live),
  prediction: (init: string) => load(`/data/predictions/${init}.json`, Prediction),
  geo: () => load("/data/india.geojson", z.custom<GeoCollection>((v) => typeof v === "object" && v !== null && (v as GeoCollection).type === "FeatureCollection")),
};

export function normaliseName(name: string): string {
  return name.trim().toLowerCase().replace(/[&\-\s]+/g, "_").replace(/_+/g, "_").replace(/^_|_$/g, "");
}
