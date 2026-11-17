// Shared risk presentation: colours + labels keyed by risk level (0-4).
// One place to change the palette so the map, heatmap, cards and legend agree.

import type { RiskLevelValue } from "@/types/plan";

export interface RiskStyle {
  label: string;
  color: string;
}

export const RISK_STYLES: Record<RiskLevelValue, RiskStyle> = {
  0: { label: "Low", color: "#16a34a" }, // green
  1: { label: "Moderate", color: "#eab308" }, // yellow
  2: { label: "High", color: "#f97316" }, // orange
  3: { label: "Severe", color: "#dc2626" }, // red
  4: { label: "No Travel", color: "#7e22ce" }, // purple
};

export function riskColor(level: RiskLevelValue): string {
  return RISK_STYLES[level]?.color ?? "#9ca3af";
}

export function riskLabel(level: RiskLevelValue): string {
  return RISK_STYLES[level]?.label ?? "Unknown";
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}
