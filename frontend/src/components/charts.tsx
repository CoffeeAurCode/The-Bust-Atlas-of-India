import { scaleLinear } from "d3-scale";
import { line as d3line } from "d3-shape";
import { format } from "d3-format";

const f2 = format(".2f");
const f0 = format(".0f");

export function LeadCurve({ points, baseline, lead, onLead, flagAt }: {
  points: { lead: number; prob: number }[]; baseline?: { lead: number; prob: number }[];
  lead: number; onLead?: (l: number) => void; flagAt: number;
}) {
  const W = 352, H = 120, m = { l: 34, r: 8, t: 10, b: 22 };
  const x = scaleLinear().domain([1, 10]).range([m.l, W - m.r]);
  const maxP = Math.max(0.3, ...points.map((p) => p.prob), ...(baseline ?? []).map((p) => p.prob));
  const y = scaleLinear().domain([0, maxP]).range([H - m.b, m.t]);
  const ln = d3line<{ lead: number; prob: number }>().x((d) => x(d.lead)).y((d) => y(d.prob));
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Bust probability by lead day">
      {[0, maxP / 2, maxP].map((v) => (
        <g key={v}><line className="grid" x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} /><text x={m.l - 6} y={y(v) + 3} textAnchor="end">{f0(v * 100)}%</text></g>
      ))}
      <line className="ref" x1={m.l} x2={W - m.r} y1={y(flagAt)} y2={y(flagAt)} />
      {baseline && <path className="line line--base" d={ln(baseline) ?? ""} />}
      <path className="line" d={ln(points) ?? ""} />
      {points.map((p) => (
        <circle key={p.lead} className="dot" cx={x(p.lead)} cy={y(p.prob)} r={p.lead === lead ? 4.5 : 2.5}
                style={{ cursor: onLead ? "pointer" : undefined }} onClick={() => onLead?.(p.lead)} />
      ))}
      {points.map((p) => <text key={p.lead} x={x(p.lead)} y={H - 6} textAnchor="middle">{p.lead}</text>)}
      <text x={W - m.r} y={y(flagAt) - 3} textAnchor="end">flag {f0(flagAt * 100)}%</text>
    </svg>
  );
}

export function Sparkline({ values, label }: { values: (number | null)[]; label: string }) {
  const W = 352, H = 56, m = { l: 34, r: 8, t: 8, b: 6 };
  const vals = values.map((v) => v ?? 0);
  const ext = Math.max(1, ...vals.map((v) => Math.abs(v)));
  const x = scaleLinear().domain([0, values.length - 1]).range([m.l, W - m.r]);
  const y = scaleLinear().domain([-ext, ext]).range([H - m.b, m.t]);
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <line className="axis" x1={m.l} x2={W - m.r} y1={y(0)} y2={y(0)} />
      {values.map((v, i) => v == null ? null : (
        <rect key={i} className="strip" x={x(i) - 5} width={10} y={Math.min(y(0), y(v))} height={Math.abs(y(v) - y(0))} />
      ))}
      <text x={m.l - 6} y={m.t + 4} textAnchor="end">+{f0(ext)}</text>
      <text x={m.l - 6} y={H - m.b} textAnchor="end">-{f0(ext)}</text>
    </svg>
  );
}

export function Distribution({ p50, p90, p95, max, value, unit }: { p50: number; p90: number; p95: number; max: number; value?: number; unit: string }) {
  const W = 352, H = 54, m = { l: 8, r: 8 };
  const x = scaleLinear().domain([0, Math.max(max, p95 * 1.2)]).range([m.l, W - m.r]);
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Error distribution">
      <rect className="area" x={x(0)} width={x(p95) - x(0)} y={14} height={16} />
      <rect className="bar" x={x(p95)} width={Math.max(1, x(max) - x(p95))} y={14} height={16} />
      {[["p50", p50], ["p90", p90], ["p95", p95]].map(([k, v]) => (
        <g key={k as string}><line className="mark" x1={x(v as number)} x2={x(v as number)} y1={10} y2={34} /><text x={x(v as number)} y={46} textAnchor="middle">{k as string} {f0(v as number)}</text></g>
      ))}
      {value != null && <g><line x1={x(value)} x2={x(value)} y1={4} y2={36} stroke="var(--accent)" strokeWidth={2} /><text x={x(value)} y={8} textAnchor="middle" fill="var(--accent)">{f0(value)} {unit}</text></g>}
    </svg>
  );
}

export function Reliability({ bins, baseline }: { bins: { mean_forecast: number | null; observed_freq: number | null; n: number }[]; baseline?: { mean_forecast: number | null; observed_freq: number | null; n: number }[] }) {
  const W = 360, H = 300, m = { l: 40, r: 10, t: 10, b: 34 };
  const x = scaleLinear().domain([0, 1]).range([m.l, W - m.r]);
  const y = scaleLinear().domain([0, 1]).range([H - m.b, m.t]);
  const pts = (b: typeof bins) => b.filter((d) => d.mean_forecast != null && d.observed_freq != null && d.n > 20) as { mean_forecast: number; observed_freq: number; n: number }[];
  const ln = d3line<{ mean_forecast: number; observed_freq: number }>().x((d) => x(d.mean_forecast)).y((d) => y(d.observed_freq));
  const maxN = Math.max(...bins.map((b) => b.n));
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Reliability diagram">
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line className="grid" x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} />
          <text x={m.l - 6} y={y(v) + 3} textAnchor="end">{f2(v)}</text>
          <text x={x(v)} y={H - m.b + 14} textAnchor="middle">{f2(v)}</text>
        </g>
      ))}
      <line className="ref" x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} />
      {bins.map((b, i) => (
        <rect key={i} className="strip" x={x(i / bins.length) + 1} width={(x(1) - x(0)) / bins.length - 2}
              y={y(0) - 22 * (b.n / maxN)} height={22 * (b.n / maxN)} />
      ))}
      {baseline && <path className="line line--base" d={ln(pts(baseline)) ?? ""} />}
      <path className="line" d={ln(pts(bins)) ?? ""} />
      {pts(bins).map((d, i) => <circle key={i} className="dot" cx={x(d.mean_forecast)} cy={y(d.observed_freq)} r={3} />)}
      <text x={(m.l + W - m.r) / 2} y={H - 4} textAnchor="middle">forecast probability</text>
      <text transform={`translate(10 ${(m.t + H - m.b) / 2}) rotate(-90)`} textAnchor="middle">observed frequency</text>
    </svg>
  );
}

export function PRCurve({ model, baseline, baseRate }: { model: { precision: number | null; recall: number | null }[]; baseline: { precision: number | null; recall: number | null }[]; baseRate: number }) {
  const W = 360, H = 300, m = { l: 40, r: 10, t: 10, b: 34 };
  const x = scaleLinear().domain([0, 1]).range([m.l, W - m.r]);
  const y = scaleLinear().domain([0, 1]).range([H - m.b, m.t]);
  const clean = (c: typeof model) => c.filter((d) => d.precision != null && d.recall != null).sort((a, b) => (b.recall! - a.recall!)) as { precision: number; recall: number }[];
  const ln = d3line<{ precision: number; recall: number }>().x((d) => x(d.recall)).y((d) => y(d.precision));
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Precision-recall curve">
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line className="grid" x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} />
          <text x={m.l - 6} y={y(v) + 3} textAnchor="end">{f2(v)}</text>
          <text x={x(v)} y={H - m.b + 14} textAnchor="middle">{f2(v)}</text>
        </g>
      ))}
      <line className="ref" x1={x(0)} x2={x(1)} y1={y(baseRate)} y2={y(baseRate)} />
      <text x={x(1)} y={y(baseRate) - 4} textAnchor="end">no skill {f2(baseRate)}</text>
      <path className="line line--base" d={ln(clean(baseline)) ?? ""} />
      <path className="line" d={ln(clean(model)) ?? ""} />
      <text x={(m.l + W - m.r) / 2} y={H - 4} textAnchor="middle">recall</text>
      <text transform={`translate(10 ${(m.t + H - m.b) / 2}) rotate(-90)`} textAnchor="middle">precision</text>
    </svg>
  );
}

export function Bars({ rows, a, b, labelKey, aLabel, bLabel }: { rows: Record<string, unknown>[]; a: string; b: string; labelKey: string; aLabel: string; bLabel: string }) {
  const W = 520, rowH = 22, m = { l: 150, r: 40, t: 18 };
  const H = m.t + rows.length * rowH + 6;
  const max = Math.max(...rows.flatMap((r) => [Number(r[a]), Number(r[b])]), 0.05);
  const x = scaleLinear().domain([0, max]).range([m.l, W - m.r]);
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${aLabel} versus ${bLabel}`}>
      <text x={m.l} y={10}>{bLabel} (grey) vs {aLabel} (accent)</text>
      {rows.map((r, i) => {
        const yy = m.t + i * rowH;
        return (
          <g key={i}>
            <text x={m.l - 8} y={yy + 13} textAnchor="end" style={{ fontFamily: "var(--font-ui)", fontSize: 11 }}>{String(r[labelKey])}</text>
            <rect className="bar bar--base" x={x(0)} y={yy + 2} width={x(Number(r[b])) - x(0)} height={7} />
            <rect className="bar" x={x(0)} y={yy + 10} width={x(Number(r[a])) - x(0)} height={7} />
            <text x={x(Number(r[a])) + 4} y={yy + 17}>{f2(Number(r[a]))}</text>
          </g>
        );
      })}
    </svg>
  );
}
