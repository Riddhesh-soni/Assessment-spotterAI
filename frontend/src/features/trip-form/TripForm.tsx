import { FormEvent, useState } from "react";

import type { PlanRequest } from "@/types/plan";

interface Props {
  onSubmit: (request: PlanRequest) => void;
  isLoading: boolean;
}

// Default departure = next top-of-hour, formatted for <input type="datetime-local">.
function defaultDeparture(): string {
  const d = new Date();
  d.setMinutes(0, 0, 0);
  d.setHours(d.getHours() + 1);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function TripForm({ onSubmit, isLoading }: Props) {
  const [origin, setOrigin] = useState("Denver, CO");
  const [destination, setDestination] = useState("Salt Lake City, UT");
  const [departure, setDeparture] = useState(defaultDeparture);
  const [loadLb, setLoadLb] = useState(42000);
  const [interval, setInterval] = useState<10 | 25 | 50>(25);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit({
      origin,
      destination,
      // datetime-local has no timezone; interpret as local and convert to ISO.
      departure: new Date(departure).toISOString(),
      load_lb: loadLb,
      interval_miles: interval,
    });
  }

  return (
    <form className="trip-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="origin">Origin</label>
        <input id="origin" value={origin} onChange={(e) => setOrigin(e.target.value)} required />
      </div>

      <div className="field">
        <label htmlFor="destination">Destination</label>
        <input
          id="destination"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="departure">Departure</label>
        <input
          id="departure"
          type="datetime-local"
          value={departure}
          onChange={(e) => setDeparture(e.target.value)}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="load">Load weight (lb)</label>
        <input
          id="load"
          type="number"
          min={0}
          step={500}
          value={loadLb}
          onChange={(e) => setLoadLb(Number(e.target.value))}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="interval">Checkpoint spacing</label>
        <select
          id="interval"
          value={interval}
          onChange={(e) => setInterval(Number(e.target.value) as 10 | 25 | 50)}
        >
          <option value={10}>Every 10 miles</option>
          <option value={25}>Every 25 miles</option>
          <option value={50}>Every 50 miles</option>
        </select>
      </div>

      <button type="submit" className="primary" disabled={isLoading}>
        {isLoading && <span className="spinner" aria-hidden="true" />}
        {isLoading ? "Planning…" : "Plan route"}
      </button>
    </form>
  );
}
