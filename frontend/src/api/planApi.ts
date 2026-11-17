import type { PlanRequest, PlanResponse } from "@/types/plan";
import { postJson } from "./client";

export function planTrip(request: PlanRequest): Promise<PlanResponse> {
  return postJson<PlanResponse, PlanRequest>("/api/plan/", request);
}
