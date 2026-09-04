import { geoMercator, geoPath } from "d3-geo";
import { useEffect, useMemo, useRef, useState } from "react";
import { normaliseName } from "../data/api";
import type { GeoCollection, Meta } from "../data/schema";
import { riskRamp } from "../data/scale";

export type RegionValue = { t: number; label: string; detail?: string; flag?: boolean };

type Props = {
  geo: GeoCollection;
  meta: Meta;
  values: Record<string, RegionValue>;
  selected: string | null;
  onSelect: (region: string | null) => void;
  showLabels?: boolean;
};

const W = 900;
const H = 820;

export function IndiaMap({ geo, meta, values, selected, onSelect, showLabels = true }: Props) {
  const ref = useRef<SVGSVGElement>(null);
  const [tip, setTip] = useState<{ x: number; y: number; region: string } | null>(null);
  const [themeTick, setThemeTick] = useState(0);

  // Re-read the ramp when the theme flips.
  useEffect(() => {
    const obs = new MutationObserver(() => setThemeTick((t) => t + 1));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onMq = () => setThemeTick((t) => t + 1);
    mq.addEventListener("change", onMq);
    return () => { obs.disconnect(); mq.removeEventListener("change", onMq); };
  }, []);
  const ramp = useMemo(() => riskRamp(), [themeTick]);

  const { path, projection } = useMemo(() => {
    const projection = geoMercator().fitExtent([[24, 24], [W - 24, H - 24]], {
      type: "FeatureCollection",
      features: [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[[66, 5], [98, 5], [98, 38], [66, 38], [66, 5]]] } }],
    } as never);
    return { path: geoPath(projection), projection };
  }, []);

  const regionOf = (stateName: string) => meta.state_to_region[normaliseName(stateName)] ?? null;
  const regionMeta = Object.fromEntries(meta.regions.map((r) => [r.id, r]));

  const boxPath = (box: number[]) => {
    const [lat0, lat1, lon0, lon1] = box;
    const pts = [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1]].map(([lo, la]) => projection([lo, la]) as [number, number]);
    return `M${pts.map((p) => p.join(",")).join("L")}Z`;
  };

  const seaRegions = meta.regions.filter((r) => r.id === "bay_of_bengal");

  const onMove = (e: React.MouseEvent, region: string) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    setTip({ x: e.clientX - rect.left, y: e.clientY - rect.top, region });
  };

  return (
    <div className="mapwrap">
      <svg ref={ref} className="map" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Map of India by forecast region"
           onMouseLeave={() => setTip(null)}>
        <defs>
          <pattern id="hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" strokeWidth="1.2" opacity="0.55" />
          </pattern>
        </defs>
        <rect width={W} height={H} fill="var(--sea)" onClick={() => onSelect(null)} />
        {seaRegions.map((r) => {
          const v = values[r.id];
          return (
            <path key={r.id} className={`sea-region${selected === r.id ? " is-selected" : ""}`}
                  d={boxPath(r.box)} fill={v ? ramp(v.t) : "var(--land)"} fillOpacity={0.55}
                  onMouseMove={(e) => onMove(e, r.id)} onClick={() => onSelect(selected === r.id ? null : r.id)} />
          );
        })}
        <g style={{ color: "var(--ink)" }}>
          {geo.features.map((f) => {
            const region = regionOf(f.properties.name);
            const v = region ? values[region] : undefined;
            const d = path(f as never) ?? "";
            return (
              <g key={f.properties.name}>
                <path className={`state${region && selected === region ? " is-selected" : ""}`}
                      d={d} fill={v ? ramp(v.t) : "var(--land)"}
                      onMouseMove={(e) => region && onMove(e, region)}
                      onClick={() => region && onSelect(selected === region ? null : region)}
                      data-region={region ?? undefined} />
                {v?.flag && <path className="flag" d={d} />}
              </g>
            );
          })}
        </g>
        {meta.regions.filter((r) => r.id !== "bay_of_bengal").map((r) => (
          <path key={r.id} className={`rbox${selected === r.id ? " is-selected" : ""}`} d={boxPath(r.box)} />
        ))}
        {showLabels && meta.regions.map((r) => {
          const [lat, lon] = r.centroid;
          const p = projection([lon, lat]);
          const v = values[r.id];
          if (!p) return null;
          return (
            <text key={r.id} className="rlabel" x={p[0]} y={p[1]} textAnchor="middle">
              <tspan x={p[0]} dy="-0.2em">{r.label}</tspan>
              {v && <tspan className="val" x={p[0]} dy="1.2em">{v.label}</tspan>}
            </text>
          );
        })}
      </svg>
      {tip && (
        <div className="tip" style={{ left: tip.x, top: tip.y }} role="tooltip">
          <b>{regionMeta[tip.region]?.label ?? tip.region}</b>
          {values[tip.region] && <div className="num">{values[tip.region].label}{values[tip.region].detail ? ` ${values[tip.region].detail}` : ""}</div>}
          {values[tip.region]?.flag && <div>Flagged unreliable</div>}
        </div>
      )}
    </div>
  );
}
