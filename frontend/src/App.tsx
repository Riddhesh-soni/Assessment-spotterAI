import { useEffect, useState } from "react";

import { RiskLegend } from "@/components/RiskLegend";
import { ForecastSlider } from "@/features/heatmap/ForecastSlider";
import { RouteMap } from "@/features/map/RouteMap";
import { RouteList } from "@/features/routes/RouteList";
import { TripForm } from "@/features/trip-form/TripForm";
import { usePlanTrip } from "@/hooks/usePlanTrip";
import type { PlanRequest } from "@/types/plan";

export default function App() {
  const plan = usePlanTrip();
  const [selectedRoute, setSelectedRoute] = useState(0);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [hourIndex, setHourIndex] = useState(0);

  const result = plan.data;

  // When a new plan arrives, select the recommended route and reset the slider.
  useEffect(() => {
    if (result) {
      setSelectedRoute(result.recommended_index ?? 0);
      setHourIndex(0);
    }
  }, [result]);

  function handlePlan(request: PlanRequest) {
    plan.mutate(request);
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="brand">
          <h1>Weather-Aware Routing</h1>
          <p>Pick the safest truck route for the weather, load &amp; timing.</p>
        </header>

        <TripForm onSubmit={handlePlan} isLoading={plan.isPending} />

        {plan.isError && (
          <div className="error-box">{(plan.error as Error).message}</div>
        )}

        {result && (
          <>
            <h2 className="section-title">
              Routes <span className="muted">({result.routes.length})</span>
            </h2>
            <RouteList
              routes={result.routes}
              selectedIndex={selectedRoute}
              onSelect={setSelectedRoute}
            />
          </>
        )}

        <footer className="credits">Routing: ORS · Weather: Open-Meteo · Geocoding: Nominatim</footer>
      </aside>

      <main className="content">
        {result ? (
          <>
            <RouteMap
              plan={result}
              selectedRoute={selectedRoute}
              onSelectRoute={setSelectedRoute}
              showHeatmap={showHeatmap}
              hourIndex={hourIndex}
            />
            <div className="map-overlay">
              <RiskLegend />
              <ForecastSlider
                times={result.heatmap.times}
                hourIndex={hourIndex}
                onChange={setHourIndex}
                enabled={showHeatmap}
                onToggle={setShowHeatmap}
              />
            </div>
          </>
        ) : (
          <div className="empty-state">
            <div className="empty-state__inner">
              {plan.isPending ? (
                <>
                  <div className="big-spinner" />
                  <h2>
                    Planning your route
                    <span className="loading-dots">
                      <span>.</span>
                      <span>.</span>
                      <span>.</span>
                    </span>
                  </h2>
                  <p>Generating routes, sampling weather at each checkpoint, and scoring risk.</p>
                </>
              ) : (
                <>
                  <span className="empty-state__icon">🚚</span>
                  <h2>Enter a trip to begin</h2>
                  <p>
                    We’ll generate route options, sample weather at timed checkpoints, and
                    recommend the safest one.
                  </p>
                </>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
