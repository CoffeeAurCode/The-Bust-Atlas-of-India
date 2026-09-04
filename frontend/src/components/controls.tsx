import { useId } from "react";

export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: { id: T; label: string }[]; value: T; onChange: (v: T) => void; label: string;
}) {
  return (
    <div className="toolbar__group">
      <span className="label">{label}</span>
      <div className="seg" role="radiogroup" aria-label={label}>
        {options.map((o) => (
          <button key={o.id} role="radio" aria-checked={o.id === value} onClick={() => onChange(o.id)}>{o.label}</button>
        ))}
      </div>
    </div>
  );
}

export function LeadSlider({ value, onChange, leads }: { value: number; onChange: (v: number) => void; leads: number[] }) {
  const id = useId();
  const min = Math.min(...leads);
  const max = Math.max(...leads);
  return (
    <div className="toolbar__group">
      <label className="label" htmlFor={id}>Lead time</label>
      <div className="lead">
        <span className="lead__val" aria-live="polite">Day {value}</span>
        <div>
          <input id={id} type="range" min={min} max={max} step={1} value={value}
                 onChange={(e) => onChange(Number(e.target.value))} aria-valuetext={`Day ${value}`} />
          <div className="lead__ticks" aria-hidden="true">{leads.map((l) => <span key={l}>{l}</span>)}</div>
        </div>
      </div>
    </div>
  );
}

export function DatePicker({ inits, value, onChange }: { inits: string[]; value: string; onChange: (v: string) => void }) {
  const id = useId();
  const dates = inits.map((i) => i.slice(0, 10));
  const min = dates[0];
  const max = dates[dates.length - 1];
  const idx = inits.indexOf(value);
  const step = (d: number) => { const n = inits[idx + d]; if (n) onChange(n); };
  return (
    <div className="toolbar__group">
      <label className="label" htmlFor={id}>Forecast issued</label>
      <div className="datepick">
        <button className="iconbtn" aria-label="Previous day" onClick={() => step(-1)} disabled={idx <= 0}>‹</button>
        <input id={id} type="date" min={min} max={max} value={value.slice(0, 10)}
               onChange={(e) => { const hit = inits.find((i) => i.startsWith(e.target.value)); if (hit) onChange(hit); }} />
        <button className="iconbtn" aria-label="Next day" onClick={() => step(1)} disabled={idx >= inits.length - 1}>›</button>
      </div>
    </div>
  );
}

export function Legend({ low, high, hatch }: { low: string; high: string; hatch?: string }) {
  return (
    <div className="legend">
      <div className="legend__ramp"><span className="num">{low}</span><div className="legend__bar" /><span className="num">{high}</span></div>
      {hatch && <div className="legend__ramp"><div className="legend__hatch" /><span>{hatch}</span></div>}
      <span>Values are per homogeneous region (10 regions on a 5.6° grid); states are shaded by their parent region.</span>
    </div>
  );
}
