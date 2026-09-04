import { useEffect, useState } from "react";
import { api } from "../data/api";
import { LeadCurve } from "../components/charts";
import type { CaseStudies, Meta, Prediction } from "../data/schema";
import { fmtInit, forecasterNote, pct, seasonOf } from "../data/text";
import type { UrlState } from "../state/url";

export function CasesMode({ meta, cases, state, update }: { meta: Meta; cases: CaseStudies; state: UrlState; update: (p: Partial<UrlState>) => void }) {
  const current = cases.cases.find((c) => c.id === state.case) ?? cases.cases[0];
  const [step, setStep] = useState(0);
  const [pred, setPred] = useState<Prediction | null>(null);
  useEffect(() => { setStep(0); setPred(null); if (current) api.prediction(current.init).then(setPred).catch(() => setPred(null)); }, [current?.id]);
  if (!current) return <div className="page"><h2>Case studies</h2><p className="empty">No case studies exported yet.</p></div>;
  const lp = pred?.regions[current.region]?.leads.find((l) => l.lead === current.lead);
  const regionLabel = meta.regions.find((r) => r.id === current.region)?.label ?? current.region;
  const steps = [
    { n: "The forecast", body: current.narrative.setup, sub: `Day ${current.lead} outlook for ${regionLabel}, issued ${fmtInit(current.init)}.` },
    { n: "The flag", body: current.narrative.flag, sub: lp ? `Spread alone put it at ${pct(lp.baseline_prob)}.` : undefined },
    { n: "Why", body: lp ? forecasterNote(meta, lp, seasonOf(current.init)).join(" ") : current.narrative.why, sub: "From the ensemble at issue time. Nothing after the issue time is used." },
    { n: "What happened", body: current.narrative.outcome, sub: lp?.outcome ? `Error ${lp.outcome.error.toFixed(0)} against threshold ${lp.outcome.threshold.toFixed(0)} m² s⁻².` : undefined },
  ];
  return (
    <div className="page">
      <h2>Case studies</h2>
      <p className="intro">Two forecasts the system flagged that went on to bust, and one it trusted that held. Step through each the way a forecaster would have seen it.</p>
      <div className="cases">
        <ol className="caselist">
          {cases.cases.map((c) => (
            <li key={c.id}><button aria-current={c.id === current.id} onClick={() => update({ case: c.id })}>
              <div className="t">{c.title}</div>
              <div className="k">{c.kind === "bust" ? "Flagged, busted" : "Trusted, held"} · {pct(c.prob)}</div>
            </button></li>
          ))}
        </ol>
        <div>
          <div className="stepnav">
            <button className="btn" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>Back</button>
            <button className="btn btn--primary" onClick={() => setStep((s) => Math.min(3, s + 1))} disabled={step === 3}>{step === 3 ? "Done" : "Next"}</button>
            <button className="btn" onClick={() => update({ mode: "today", init: current.init, lead: current.lead, region: current.region })}>Open on the map</button>
          </div>
          <div className="steps">
            {steps.map((s, i) => (
              <div key={s.n} className={`step${i <= step ? " is-on" : ""}`}>
                <div className="n">{s.n}</div>
                <div className="body">
                  {s.body}
                  {i === 3 && lp?.outcome && <span className={`verdict verdict--${lp.outcome.busted ? "bust" : "held"}`}>{lp.outcome.busted ? "Bust" : "Held"}</span>}
                  {s.sub && <div className="sub">{s.sub}</div>}
                  {i === 1 && step >= 1 && pred && (
                    <div style={{ maxWidth: 360, marginTop: 10 }}>
                      <LeadCurve points={pred.regions[current.region].leads.map((l) => ({ lead: l.lead, prob: l.prob }))} baseline={pred.regions[current.region].leads.map((l) => ({ lead: l.lead, prob: l.baseline_prob }))} lead={current.lead} flagAt={meta.flag_threshold} />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
