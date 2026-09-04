import { Bars, PRCurve, Reliability } from "../components/charts";
import type { Eval, Meta } from "../data/schema";

const f3 = (v: unknown) => Number(v).toFixed(3);

export function EvidenceMode({ meta, ev }: { meta: Meta; ev: Eval }) {
  const rows = [
    ["Brier score (lower is better)", ev.baseline.brier, ev.model.brier, true],
    ["Brier skill vs climatology", ev.baseline.bss_vs_climatology, ev.model.bss_vs_climatology, false],
    ["PR-AUC", ev.baseline.pr_auc, ev.model.pr_auc, false],
    ["ROC-AUC", ev.baseline.roc_auc, ev.model.roc_auc, false],
  ] as const;
  const cm = ev.cross_model;
  const crossRows: [string, number, number][] = cm ? [
    ["Brier score (lower is better)", ev.model.brier, cm.model.brier],
    ["Brier skill vs climatology", ev.model.bss_vs_climatology, cm.model.bss_vs_climatology],
    ["PR-AUC", ev.model.pr_auc, cm.model.pr_auc],
    ["ROC-AUC", ev.model.roc_auc, cm.model.roc_auc],
  ] : [];
  const byRegion = ev.by_region.map((r) => ({ ...r, label: meta.regions.find((m) => m.id === r.region)?.label ?? String(r.region) }));
  return (
    <div className="page">
      <h2>Does it work?</h2>
      <p className="intro">
        Tested on {ev.test_years.join(", ")}, a year the model never saw: {ev.n.toLocaleString()} region-lead forecasts, {ev.positives.toLocaleString()} of them busts ({(ev.base_rate * 100).toFixed(1)}%). Every number is against the spread-only baseline, which is what a forecaster already has.
        {meta.synthetic && <strong> These numbers come from synthetic data and mean nothing yet.</strong>}
      </p>
      <div className="grid2">
        <div className="figure">
          <h4>Scores on the test year</h4>
          <p className="cap">Brier skill score versus the spread baseline: <span className="num">{f3(ev.model.bss_vs_spread)}</span>. Positive means the layer adds information beyond spread.</p>
          <table className="tbl">
            <thead><tr><th>Metric</th><th>Spread only</th><th>This system</th></tr></thead>
            <tbody>
              {rows.map(([k, b, m, lowerBetter]) => (
                <tr key={k}><td>{k}</td><td>{f3(b)}</td><td className={(lowerBetter ? m < b : m > b) ? "up" : "down"}>{f3(m)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="figure">
          <h4>Reliability</h4>
          <p className="cap">When the system says 15%, does it bust 15% of the time? Points on the diagonal are honest probabilities. Bars show how many forecasts fall in each bin.</p>
          <Reliability bins={ev.model.reliability} baseline={ev.baseline.reliability} />
        </div>
        <div className="figure">
          <h4>Precision and recall</h4>
          <p className="cap">Busts are rare, so this is the curve that matters. The flat line is what guessing at the base rate achieves.</p>
          <PRCurve model={ev.model.pr_curve} baseline={ev.baseline.pr_curve} baseRate={ev.base_rate} />
        </div>
        <div className="figure">
          <h4>By region</h4>
          <p className="cap">PR-AUC per region, this system against spread alone.</p>
          <Bars rows={byRegion} a="model_pr_auc" b="baseline_pr_auc" labelKey="label" aLabel="this system" bLabel="spread" />
        </div>
        <div className="figure">
          <h4>By lead day</h4>
          <p className="cap">PR-AUC per lead day.</p>
          <Bars rows={ev.by_lead.map((r) => ({ ...r, label: `Day ${r.lead}` }))} a="model_pr_auc" b="baseline_pr_auc" labelKey="label" aLabel="this system" bLabel="spread" />
        </div>
        {ev.cross_model && (
          <div className="figure">
            <h4>Same model, different ensemble</h4>
            <p className="cap">
              The confidence layer was trained on {meta.source_label} and then scored, unchanged, on {ev.cross_model.source_label} with {ev.cross_model.members} members, over the same test year: {ev.cross_model.n.toLocaleString()} region-lead forecasts, {ev.cross_model.positives.toLocaleString()} busts ({(ev.cross_model.base_rate * 100).toFixed(1)}%). Nothing was refitted, not the thresholds, not the model, not the calibration. Some drop is expected when the ensemble changes, and it is reported here rather than hidden.
            </p>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>{meta.source_label} (trained on)</th>
                  <th>{ev.cross_model.source_label} (never seen)</th>
                </tr>
              </thead>
              <tbody>
                {crossRows.map(([k, a, b]) => (
                  <tr key={k}><td>{k}</td><td>{f3(a)}</td><td>{f3(b)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="method">
        <h4 style={{ fontSize: 15, marginBottom: 8 }}>Method</h4>
        <blockquote>{meta.bust_definition}</blockquote>
        <p>Training ensemble: {meta.source_label}, {meta.members} members, {meta.grid}. Truth: ERA5 reanalysis with a 1990 to 2019 climatology. Variable: {meta.variable}.</p>
        <p>Split: trained on {meta.years.train?.join(", ")}, calibrated on {meta.years.cal?.join(", ")}, tested on {meta.years.test?.join(", ")}. Strictly temporal; no random shuffling.</p>
        <p>Every feature is computed from information available when the forecast is issued: ensemble spread and its growth across lead days, the shape of the member distribution, whether the members have split into camps, how much the run changed from the previous day's run for the same valid time, and the historical bust rate of that region, lead and season. A test in the repository recomputes all features on a truncated archive and asserts they are identical.</p>
        <p>Model: gradient-boosted trees with class weighting, then isotonic calibration on the held-out year. Explanations come from the per-feature contribution of each prediction, rendered through a fixed table of sentences.</p>
        <p>Decision support for forecasters. Not a replacement for IMD's official bulletin.</p>
      </div>
    </div>
  );
}
