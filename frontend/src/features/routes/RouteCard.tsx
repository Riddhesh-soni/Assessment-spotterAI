import type { Route } from "@/types/plan";
import { RISK_STYLES, formatDuration, riskColor } from "@/lib/risk";
import type { RiskLevelValue } from "@/types/plan";

interface Props {
  route: Route;
  selected: boolean;
  onSelect: () => void;
}

const LEVELS: RiskLevelValue[] = [0, 1, 2, 3, 4];

export function RouteCard({ route, selected, onSelect }: Props) {
  const { summary } = route;
  const total = summary.total_miles || 1;

  return (
    <button
      type="button"
      className={`route-card${selected ? " selected" : ""}`}
      onClick={onSelect}
    >
      <div className="route-card__head">
        <span className="route-card__title">{route.label}</span>
        {route.is_recommended && <span className="badge recommended">Recommended</span>}
        {summary.has_no_travel && <span className="badge danger">No-Travel segment</span>}
      </div>

      <div className="route-card__stats">
        <div>
          <span className="stat-value">{route.distance_miles.toFixed(0)}</span>
          <span className="stat-label">miles</span>
        </div>
        <div>
          <span className="stat-value">{formatDuration(route.duration_seconds)}</span>
          <span className="stat-label">drive</span>
        </div>
        <div>
          <span className="stat-value" style={{ color: riskColor(3) }}>
            {summary.miles_by_level.severe?.toFixed(0) ?? 0}
          </span>
          <span className="stat-label">severe mi</span>
        </div>
        <div>
          <span className="stat-value" style={{ color: riskColor(2) }}>
            {summary.miles_by_level.high?.toFixed(0) ?? 0}
          </span>
          <span className="stat-label">high mi</span>
        </div>
      </div>

      {/* Proportional risk bar: how many miles at each risk level. */}
      <div className="risk-bar" title={`Avg risk ${summary.average_risk.toFixed(2)}`}>
        {LEVELS.map((lvl) => {
          const miles = summary.miles_by_level[RISK_STYLES[lvl].label.toLowerCase().replace(" ", "_")] ?? 0;
          const pct = (miles / total) * 100;
          return pct > 0 ? (
            <span
              key={lvl}
              className="risk-bar__seg"
              style={{ width: `${pct}%`, background: riskColor(lvl) }}
            />
          ) : null;
        })}
      </div>
    </button>
  );
}
