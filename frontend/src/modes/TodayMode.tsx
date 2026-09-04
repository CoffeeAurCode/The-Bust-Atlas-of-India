import { useEffect, useMemo, useState } from "react";
import { api } from "../data/api";
import { IndiaMap, type RegionValue } from "../components/IndiaMap";
import { LeadCurve, Sparkline } from "../components/charts";
import { DatePicker, LeadSlider, Legend } from "../components/controls";
import type { GeoCollection, Meta, Prediction } from "../data/schema";
import { probToT } from "../data/scale";
import { BAND_LABEL, fmtInit, forecasterNote, pct, seasonOf } from "../data/text";
import type { UrlState } from "../state/url";

export function TodayMode({ meta, geo, inits, state, update }: { meta: Meta; geo: GeoCollection; inits: string[]; state: UrlState; update: (p: Partial<UrlState>) => void }) {
  const init = state.init && inits.includes(state.init) ? state.init : inits[inits.length - 1];
  const [pred, setPred] = useState<Prediction | null>(null);
  const [history, setHistory] = useState<(Prediction | null)[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setErr(null);
    api.prediction(init).then((p) => alive && setPred(p)).catch((e) => alive && setErr(String(e)));
    const idx = inits.indexOf(init);
    const prev = inits.slice(Math.max(0, idx - 6), idx);
    Promise.all(prev.map((i) => api.prediction(i).catch(() => null))).then((h) => alive && setHistory(h));
    return () => { alive = false; };
  }, [init, inits]);

  const values = useMemo<Record<string, RegionValue>>(() => {
    if (!pred) return {};
    const out: Record<string, RegionValue> = {};
    for (const [r, v] of Object.entries(pred.regions)) {
      const lp = v.leads.find((l) => l.lead === state.lead);
      if (lp) out[r] = { t: probToT(lp.prob), label: pct(lp.prob), detail: BAND_LABEL[lp.band].toLowerCase(), flag: lp.flag };
    }
    return out;
  }, [pred, state.lead]);

  const season = seasonOf(init);
  const region = state.region;
  const rp = region && pred ? pred.regions[region] : null;
  const lp = rp?.leads.find((l) => l.lead === state.lead) ?? null;
  const selMeta = meta.regions.find((r) => r.id === region);
  const flagged = pred ? Object.entries(pred.regions).map(([r, v]) => ({ r, lp: v.leads.find((l) => l.lead === state.lead)! })).filter((x) => x.lp).sort((a, b) => b.lp.prob - a.lp.prob) : [];
  const jumpHistory = region ? [...history.map((h) => h?.regions[region]?.leads.find((l) => l.lead === state.lead)?.jumpiness ?? null), lp?.jumpiness ?? null] : [];

  return (
    <div className="main">
      <section className="stage">
        <div className="toolbar">
          <DatePicker inits={inits} value={init} onChange={(i) => update({ init: i })} />
          <LeadSlider leads={meta.leads} value={state.lead} onChange={(lead) => update({ lead })} />
          <div className="toolbar__group"><span className="label">Ensemble</span><span className="badge">{meta.source_label} · {meta.members} members</span></div>
        </div>
        {err ? <div className="empty">Could not load this forecast: {err}</div> : pred ? (
          <IndiaMap geo={geo} meta={meta} values={values} selected={region} onSelect={(r) => update({ region: r })} />
        ) : <div className="skeleton" style={{ minHeight: 480 }} />}
        <Legend low="0%" high="40%+" hatch={`flagged unreliable (≥ ${pct(meta.flag_threshold)})`} />
      </section>
      <aside className="side" aria-live="polite">
        {!pred ? <div className="skeleton" style={{ height: 200 }} /> : !region || !lp || !selMeta ? (
          <>
            <h2>Forecast issued {fmtInit(init)}</h2>
            <p className="muted" style={{ marginTop: 8 }}>Probability that the Day {state.lead} Z500 forecast busts in each region, from the ensemble as it stood at issue time. Click a region for the forecaster's note.</p>
            <h3>Ranked by bust risk, Day {state.lead}</h3>
            <ol className="rank">
              {flagged.map(({ r, lp }) => (
                <li key={r}><button onClick={() => update({ region: r })}>{meta.regions.find((m) => m.id === r)?.label}{lp.flag && <span className="badge badge--warn" style={{ marginLeft: 8 }}>flagged</span>}</button><span className="num">{pct(lp.prob)}</span></li>
              ))}
            </ol>
          </>
        ) : (
          <>
            <button className="small muted" onClick={() => update({ region: null })} style={{ marginBottom: 10 }}>‹ All regions</button>
            <h2>{selMeta.label}</h2>
            <p className="muted small">Day {state.lead} forecast, issued {fmtInit(init)}</p>
            <div className="prob"><span className="v">{pct(lp.prob)}</span><span className={`band band--${lp.band}`}>{BAND_LABEL[lp.band]}</span></div>
            <p className="small muted">bust probability · spread alone would say <span className="num">{pct(lp.baseline_prob)}</span></p>
            <h3>Forecaster's note</h3>
            <div className="note">
              {forecasterNote(meta, lp, season).map((s, i) => <p key={i}>{s}</p>)}
            </div>
            <h3>Risk across lead days</h3>
            <LeadCurve points={rp!.leads.map((l) => ({ lead: l.lead, prob: l.prob }))} baseline={rp!.leads.map((l) => ({ lead: l.lead, prob: l.baseline_prob }))} lead={state.lead} onLead={(lead) => update({ lead })} flagAt={meta.flag_threshold} />
            <p className="small muted">Accent: this system. Dashed: ensemble spread alone.</p>
            <h3>Run-to-run change, last {jumpHistory.length} issues</h3>
            <Sparkline values={jumpHistory} label="Jumpiness of successive runs for this valid time" />
            <div className="kpi">
              <div><div className="v">{lp.std.toFixed(0)}</div><div className="k">spread, m² s⁻² · top {Math.max(1, Math.round((1 - lp.std_pct_climo) * 100))}% for here</div></div>
              <div><div className="v">{lp.cluster_gap.toFixed(2)}</div><div className="k">cluster gap (above 1: two camps)</div></div>
            </div>
            {lp.outcome && (
              <>
                <h3>What happened</h3>
                <p className="small">Verifying error <span className="num">{lp.outcome.error.toFixed(0)}</span> against a threshold of <span className="num">{lp.outcome.threshold.toFixed(0)}</span> m² s⁻².
                  <span className={`verdict verdict--${lp.outcome.busted ? "bust" : "held"}`}>{lp.outcome.busted ? "Bust" : "Held"}</span></p>
              </>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
