import type { Route } from "@/types/plan";
import { RouteCard } from "./RouteCard";

interface Props {
  routes: Route[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

export function RouteList({ routes, selectedIndex, onSelect }: Props) {
  return (
    <div className="route-list">
      {routes.map((route, i) => (
        <RouteCard
          key={route.label}
          route={route}
          selected={i === selectedIndex}
          onSelect={() => onSelect(i)}
        />
      ))}
    </div>
  );
}
