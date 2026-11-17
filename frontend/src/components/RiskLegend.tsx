import { RISK_STYLES } from "@/lib/risk";
import type { RiskLevelValue } from "@/types/plan";

const LEVELS: RiskLevelValue[] = [0, 1, 2, 3, 4];

export function RiskLegend() {
  return (
    <div className="risk-legend">
      {LEVELS.map((lvl) => (
        <span key={lvl} className="risk-legend__item">
          <span className="swatch" style={{ background: RISK_STYLES[lvl].color }} />
          {RISK_STYLES[lvl].label}
        </span>
      ))}
    </div>
  );
}
