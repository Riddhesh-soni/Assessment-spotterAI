import { useMutation } from "@tanstack/react-query";

import { planTrip } from "@/api/planApi";
import type { PlanRequest, PlanResponse } from "@/types/plan";

// A mutation (not a query) because planning is an explicit user action with a
// POST body, and we don't want it to auto-refetch.
export function usePlanTrip() {
  return useMutation<PlanResponse, Error, PlanRequest>({
    mutationFn: planTrip,
  });
}
