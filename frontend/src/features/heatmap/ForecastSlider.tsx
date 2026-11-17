import { formatTime } from "@/lib/risk";

interface Props {
  times: string[];
  hourIndex: number;
  onChange: (index: number) => void;
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
}

// 0–48h forecast slider that scrubs the heatmap through time.
export function ForecastSlider({ times, hourIndex, onChange, enabled, onToggle }: Props) {
  const current = times[hourIndex];

  return (
    <div className="forecast-slider">
      <div className="forecast-slider__head">
        <label className="toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => onToggle(e.target.checked)}
          />
          Weather heatmap
        </label>
        <span className="forecast-slider__time">
          +{hourIndex}h · {current ? formatTime(current) : "—"}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={Math.max(times.length - 1, 0)}
        value={hourIndex}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={!enabled}
      />
    </div>
  );
}
