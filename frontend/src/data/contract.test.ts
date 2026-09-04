import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { Atlas, CaseStudies, Eval, Inits, Live, Meta, Prediction } from "./schema";
import { normaliseName } from "./api";
import { driverSentence } from "./text";
import { parse, serialise } from "../state/url";

const DATA = join(__dirname, "../../public/data");
const has = existsSync(join(DATA, "meta.json"));
const read = (f: string) => JSON.parse(readFileSync(join(DATA, f), "utf-8"));

describe.skipIf(!has)("committed data validates against the contract", () => {
  const meta = Meta.parse(read("meta.json"));
  it("meta, atlas, inits, eval parse", () => {
    Atlas.parse(read("atlas.json"));
    Inits.parse(read("inits.json"));
    Eval.parse(read("eval.json"));
    if (existsSync(join(DATA, "case_studies.json"))) CaseStudies.parse(read("case_studies.json"));
  });
  it("the cross-model block, if present, parses", () => {
    const ev = Eval.parse(read("eval.json"));
    if (!ev.cross_model) return;
    expect(ev.cross_model.n).toBeGreaterThan(0);
    expect(ev.cross_model.source.length).toBeGreaterThan(0);
    expect(ev.cross_model.by_lead.length).toBe(ev.by_lead.length);
  });
  it("every state in the basemap maps to a region in meta", () => {
    const geo = read("india.geojson");
    const regions = new Set(meta.regions.map((r) => r.id));
    for (const f of geo.features) {
      const r = meta.state_to_region[normaliseName(f.properties.name)];
      expect(r, f.properties.name).toBeDefined();
      expect(regions.has(r)).toBe(true);
    }
  });
  it("sampled prediction files parse and cover every region and lead", () => {
    const files = readdirSync(join(DATA, "predictions")).filter((f: string) => f.endsWith(".json"));
    expect(files.length).toBeGreaterThan(0);
    for (const f of files.filter((_: string, i: number) => i % 40 === 0)) {
      const p = Prediction.parse(read(`predictions/${f}`));
      expect(Object.keys(p.regions).sort()).toEqual(meta.regions.map((r) => r.id).sort());
      for (const r of Object.values(p.regions)) expect(r.leads.map((l) => l.lead)).toEqual(meta.leads);
    }
  });
  it("live.json, when present, parses and covers every region", () => {
    if (!existsSync(join(DATA, "live.json"))) return;
    const live = Live.parse(read("live.json"));
    expect(Object.keys(live.regions).sort()).toEqual(meta.regions.map((r) => r.id).sort());
    for (const r of Object.values(live.regions)) {
      expect(r.leads.map((l) => l.lead)).toEqual(meta.leads);
      for (const l of r.leads) expect(l.outcome).toBeNull();
    }
  });

  it("every driver feature has a sentence template", () => {
    const s = driverSentence(meta, "std_growth", 1, 5, "JJAS", 0.9);
    expect(s).toContain("Day 5");
    expect(s).not.toContain("{");
  });
});

describe("url state", () => {
  it("round-trips", () => {
    const s = parse("?mode=today&lead=7&region=central&init=2022-07-12T00");
    expect(s.mode).toBe("today");
    expect(s.lead).toBe(7);
    expect(parse(serialise(s))).toEqual(s);
  });
  it("rejects bad values", () => {
    const s = parse("?mode=nope&lead=99");
    expect(s.mode).toBe("atlas");
    expect(s.lead).toBe(5);
  });
});
