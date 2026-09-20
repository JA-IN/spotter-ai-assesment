import { PlanTripRequest, PlannerResponse } from '../types/planner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function planTrip(request: PlanTripRequest): Promise<PlannerResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/plan-trip/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
  } catch {
    throw new Error('Unable to reach the trip planning service. Please try again.');
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    if (response.status === 502) {
      throw new Error('Unable to calculate the route. Please verify the locations and try again.');
    }
    throw new Error(payload?.detail || 'Unable to generate the trip plan. Please try again.');
  }

  return (await response.json()) as PlannerResponse;
}
