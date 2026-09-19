/**
 * API client for the Spotter Trip Planner API.
 * To be implemented in Phase 5.
 */
import { PlanTripRequest, PlanTripResponse } from '../types/planner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function planTrip(_request: PlanTripRequest): Promise<PlanTripResponse> {
  // Stub implementation; full HTTP integration in Phase 5
  throw new Error(`API client not yet implemented. Target URL: ${API_BASE_URL}`);
}
