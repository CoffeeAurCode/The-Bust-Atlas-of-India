import { useMemo } from "react";
import { IndiaMap, type RegionValue } from "../components/IndiaMap";
import { Distribution } from "../components/charts";
import { LeadSlider, Legend, Segmented } from "../components/controls";
import type { Atlas, GeoCollection, Meta } from "../data/schema";
import { errToT, rateToT } from "../data/scale";
import { pct } from "../data/text";
import type { AtlasMetric, UrlState } from "../state/url";

export function AtlasMode({ meta, atlas, geo, state, update }: { meta: Meta; atlas: Atlas; geo: GeoCollection; state: UrlState; update: (p: Partial<UrlState>) => void }) {
  const cells = useMemo(() => atlas.cells.filter((c) => c.season === state.season && c.lead === state.lead), [atlas, state.season, state.lead]);
  const national = atlas.national.find((n) => n.season === state.season && n.lead === state.lead);
  const values = useMemo<Record<string, RegionValue>>(() => {
    const out: Record<string, RegionValue> = {};
    for (const c of cells) {
      out[c.region] = state.metric === "bust_rate"
        ? { t: rateToT(c.bust_rate), label: pct(c.bust_rate, 1), detail: "bust rate" }
        : { t: errToT(c.err_p95, national?.err_p95 ?? c.err_p95), label: `${c.err_p95.toFixed(0)}`, detail: "p95 error" };
    }
    return out;
  }, [cells, state.metric, national]);

  const sel = cells.find((c) => c.region === state.region);
  const selMeta = meta.regions.find((r) => r.id === state.region);
  const byLead = useMemo(() => state.region ? atlas.cells.filter((c) => c.region === state.region && c.season === state.season).sort((a, b) => a.lead - b.lead) : [], [atlas, state.region, state.season]);
  const ranked = [...cells].sort((a, b) => b.bust_rate - a.bust_rate);

  return (
    <div className="main">
      <section className="stage">
        <div className="toolbar">
          <Segmented label="Season" options={meta.seasons.map((s) => ({ id: s.id, label: s.label.split(" (")[0] }))} value={state.season} onChange={(season) => update({ season })} />
          <LeadSlider leads={meta.leads} value={state.lead} onChange={(lead) => update({ lead })} />
          <Segmented<AtlasMetric> label="Shade by" options={[{ id: "bust_rate", label: "Bust rate" }, { id: "err_p95", label: "Error p95" }]} value={state.metric} onChange={(metric) => update({ metric })} />
        </div>
        <IndiaMap geo={geo} meta={meta} values={values} selected={state.region} onSelect={(region) => update({ region })} />
        <Legend low={state.metric === "bust_rate" ? "0%" : "0"} high={state.metric === "bust_rate" ? "12%+" : "high"} />
      </section>
      <aside className="side" aria-live="polite">
        {!sel || !selMeta ? (
          <>
            <h2>Where forecasts bust, {meta.years.atlas?.[0]}–{meta.years.atlas?.at(-1)}</h2>
            <p className="muted" style={{ marginTop: 8 }}>
              Historical bust rate of the Day {state.lead} Z500 forecast in {meta.seasons.find((s) => s.id === state.season)?.label.toLowerCase()}, from {meta.source_label}. Hover a region for its numbers; click to open its record.
            </p>
            <h3>Regions, most to least bust-prone</h3>
            <ol className="rank">
              {ranked.map((c) => (
                <li key={c.region}><button onClick={() => update({ region: c.region })}>{meta.regions.find((r) => r.id === c.region)?.label}</button><span className="num">{pct(c.bust_rate, 1)}</span></li>
              ))}
            </ol>
            {national && <p className="small muted" style={{ marginTop: 14 }}>National rate at this lead and season: <span className="num">{pct(national.bust_rate, 1)}</span> of {national.n.toLocaleString()} forecasts.</p>}
          </>
        ) : (
          <>
            <button className="small muted" onClick={() => update({ region: null })} style={{ marginBottom: 10 }}>‹ All regions</button>
            <h2>{selMeta.label}</h2>
            <p className="muted small">Day {state.lead}, {meta.seasons.find((s) => s.id === state.season)?.label}. {sel.n.toLocaleString()} forecasts.</p>
            <div className="kpi">
              <div><div className="v">{pct(sel.bust_rate, 1)}</div><div className="k">bust rate (national {national ? pct(national.bust_rate, 1) : "–"})</div></div>
              <div><div className="v">{sel.err_p95.toFixed(0)}<small>m² s⁻²</small></div><div className="k">p95 error, the bust threshold</div></div>
              <div><div className="v">{sel.spread_p50.toFixed(0)}<small>m² s⁻²</small></div><div className="k">typical ensemble spread</div></div>
              <div><div className="v">{sel.spread_skill.toFixed(2)}</div><div className="k">spread ÷ error (1 is well-tuned)</div></div>
            </div>
            <h3>Error distribution</h3>
            <Distribution p50={sel.err_p50} p90={sel.err_p90} p95={sel.err_p95} max={sel.err_max} unit="" />
            <h3>Bust rate by lead day</h3>
            <svg className="chart" viewBox="0 0 352 70" role="img" aria-label="Bust rate by lead">
              {byLead.map((c, i) => {
                const w = 352 / byLead.length; const h = Math.max(2, (c.bust_rate / 0.15) * 50);
                return <g key={c.lead}><rect className="bar" x={i * w + 4} width={w - 8} y={56 - h} height={h} fillOpacity={c.lead === state.lead ? 1 : 0.35} style={{ cursor: "pointer" }} onClick={() => update({ lead: c.lead })} /><text x={i * w + w / 2} y={67} textAnchor="middle">{c.lead}</text></g>;
              })}
            </svg>
            <h3>Worst busts on record</h3>
            <ul className="events">
              {sel.worst_events.map((e) => <li key={e.init}><span>{e.init}</span><span className="num">{e.error.toFixed(0)}</span></li>)}
            </ul>
          </>
        )}
      </aside>
    </div>
  );
}
