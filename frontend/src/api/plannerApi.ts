import { PlanTripRequest, PlannerResponse } from '../types/planner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function planTrip(request: PlanTripRequest): Promise<PlannerResponse> {
  const response = await fetch(`${API_BASE_URL}/api/plan-trip/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(payload?.detail || `Trip planning failed (${response.status}).`);
  }

  return (await response.json()) as PlannerResponse;
}
