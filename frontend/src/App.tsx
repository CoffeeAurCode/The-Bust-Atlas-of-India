import { Moon, Sun } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { api } from "./data/api";
import type { Atlas, CaseStudies, Eval, GeoCollection, Meta } from "./data/schema";
import { AtlasMode } from "./modes/AtlasMode";
import { CasesMode } from "./modes/CasesMode";
import { EvidenceMode } from "./modes/EvidenceMode";
import { TodayMode } from "./modes/TodayMode";
import { useUrlState, type Mode } from "./state/url";

type Data = { meta: Meta; atlas: Atlas; geo: GeoCollection; inits: string[]; ev: Eval; cases: CaseStudies | null };

const MODES: { id: Mode; label: string }[] = [
  { id: "atlas", label: "Atlas" },
  { id: "today", label: "Today" },
  { id: "evidence", label: "Evidence" },
  { id: "cases", label: "Cases" },
];

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark" | null>(() => {
    try { return (localStorage.getItem("theme") as "light" | "dark" | null) ?? null; } catch { return null; }
  });
  useEffect(() => {
    if (theme) document.documentElement.setAttribute("data-theme", theme);
    else document.documentElement.removeAttribute("data-theme");
    try { theme ? localStorage.setItem("theme", theme) : localStorage.removeItem("theme"); } catch { /* ignore */ }
  }, [theme]);
  const isDark = theme ? theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  return { isDark, toggle: () => setTheme(isDark ? "light" : "dark") };
}

export default function App() {
  const [state, update] = useUrlState();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { isDark, toggle } = useTheme();

  useEffect(() => {
    Promise.all([api.meta(), api.atlas(), api.geo(), api.inits(), api.eval(), api.cases().catch(() => null)])
      .then(([meta, atlas, geo, inits, ev, cases]) => setData({ meta, atlas, geo, inits: inits.inits, ev, cases }))
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="shell">
      <header className="mast">
        <div style={{ display: "flex", alignItems: "baseline" }}>
          <h1 className="mast__title">The Bust Atlas <em>of India</em></h1>
          <span className="mast__sub">forecast confidence, Day 1 to 10</span>
        </div>
        <nav className="modes" role="tablist" aria-label="Mode">
          {MODES.map((m) => <button key={m.id} role="tab" aria-selected={state.mode === m.id} onClick={() => update({ mode: m.id })}>{m.label}</button>)}
        </nav>
        <div className="mast__right">
          {data?.meta.synthetic && <span className="badge badge--warn">synthetic data</span>}
          <button className="iconbtn" aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"} onClick={toggle}>{isDark ? <Sun size={16} /> : <Moon size={16} />}</button>
        </div>
      </header>
      {error ? (
        <div className="page"><h2>Could not load the atlas</h2><p className="intro">{error}</p></div>
      ) : !data ? (
        <div className="main"><div className="stage"><div className="skeleton" style={{ height: 40, width: 480 }} /><div className="skeleton" style={{ minHeight: 520 }} /></div><aside className="side"><div className="skeleton" style={{ height: 240 }} /></aside></div>
      ) : state.mode === "atlas" ? (
        <AtlasMode meta={data.meta} atlas={data.atlas} geo={data.geo} state={state} update={update} />
      ) : state.mode === "today" ? (
        <TodayMode meta={data.meta} geo={data.geo} inits={data.inits} state={state} update={update} />
      ) : state.mode === "evidence" ? (
        <EvidenceMode meta={data.meta} ev={data.ev} />
      ) : data.cases ? (
        <CasesMode meta={data.meta} cases={data.cases} state={state} update={update} />
      ) : <div className="page"><h2>Case studies</h2><p className="empty">Not exported yet.</p></div>}
      <footer className="foot">
        <span>Vishwas by Team Gryffindor, SIH26079. Decision support for forecasters; not a replacement for IMD's official bulletin.</span>
        <span>{data ? `${data.meta.source_label} · ERA5 truth · WeatherBench 2 · build ${data.meta.git_sha}` : ""}</span>
      </footer>
    </div>
  );
}
