import { useCallback, useEffect, useState } from "react";

export type Mode = "atlas" | "today" | "evidence" | "cases";
export type AtlasMetric = "bust_rate" | "err_p95";
export type Source = "archive" | "live";

export type UrlState = {
  mode: Mode;
  season: string;
  lead: number;
  region: string | null;
  init: string | null;
  metric: AtlasMetric;
  case: string | null;
  source: Source;
};

const DEFAULTS: UrlState = { mode: "atlas", season: "JJAS", lead: 5, region: null, init: null, metric: "bust_rate", case: null, source: "archive" };

export function parse(search: string): UrlState {
  const p = new URLSearchParams(search);
  const mode = p.get("mode") as Mode | null;
  const lead = Number(p.get("lead"));
  return {
    mode: mode && ["atlas", "today", "evidence", "cases"].includes(mode) ? mode : DEFAULTS.mode,
    season: p.get("season") ?? DEFAULTS.season,
    lead: Number.isInteger(lead) && lead >= 1 && lead <= 10 ? lead : DEFAULTS.lead,
    region: p.get("region"),
    init: p.get("init"),
    metric: (p.get("metric") as AtlasMetric) === "err_p95" ? "err_p95" : "bust_rate",
    case: p.get("case"),
    source: p.get("source") === "live" ? "live" : DEFAULTS.source,
  };
}

export function serialise(s: UrlState): string {
  const p = new URLSearchParams();
  if (s.mode !== DEFAULTS.mode) p.set("mode", s.mode);
  if (s.season !== DEFAULTS.season) p.set("season", s.season);
  if (s.lead !== DEFAULTS.lead) p.set("lead", String(s.lead));
  if (s.region) p.set("region", s.region);
  if (s.init) p.set("init", s.init);
  if (s.metric !== DEFAULTS.metric) p.set("metric", s.metric);
  if (s.case) p.set("case", s.case);
  if (s.source !== DEFAULTS.source) p.set("source", s.source);
  const q = p.toString();
  return q ? `?${q}` : "";
}

export function useUrlState(): [UrlState, (patch: Partial<UrlState>) => void] {
  const [state, setState] = useState<UrlState>(() => parse(window.location.search));
  useEffect(() => {
    const onPop = () => setState(parse(window.location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const update = useCallback((patch: Partial<UrlState>) => {
    setState((prev) => {
      const next = { ...prev, ...patch };
      const url = serialise(next) || window.location.pathname;
      window.history.replaceState(null, "", url);
      return next;
    });
  }, []);
  return [state, update];
}
