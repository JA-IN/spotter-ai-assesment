/**
 * TypeScript definitions for Spotter AI Trip Planner.
 * Mirrors the API contracts defined in the technical specification.
 */

export type DutyStatus = 'off_duty' | 'sleeper_berth' | 'driving' | 'on_duty';

export type TaskType = 'drive' | 'pickup' | 'dropoff' | 'fuel' | 'break' | 'rest' | 'restart';

export interface LatLngCoordinate {
  lat: number;
  lng: number;
}

export interface PlanTripRequest {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_cycle_used: number;
}

export interface RouteGeometry {
  distance_miles: number;
  estimated_driving_minutes: number;
  geometry: [number, number][]; // [lat, lng] ordered coordinates
}

export interface TripSummary {
  total_distance_miles: number;
  driving_minutes: number;
  on_duty_minutes: number;
  off_duty_minutes: number;
  fuel_stops: number;
  breaks_30_min: number;
  rest_stops_10h: number;
  restarts_34h: number;
  daily_logs: number;
}

export interface PlannedStop {
  type: string;
  route_mile: number;
  start: string;
  end: string;
  location: string;
  coordinate: LatLngCoordinate;
  duration_minutes?: number;
  reason?: string;
}

export interface DutyEvent {
  status: DutyStatus;
  start: string;
  end: string;
  duration_minutes: number;
  miles: number;
  location: string;
  coordinate: LatLngCoordinate;
  reason?: string;
  task_type: TaskType;
}

export interface DailyTotals {
  off_duty_minutes: number;
  sleeper_minutes: number;
  driving_minutes: number;
  on_duty_minutes: number;
}

export interface DailyLogSheet {
  date: string;
  total_miles: number;
  events: DutyEvent[];
  totals: DailyTotals;
  remarks: string[];
}

export interface PlanTripResponse {
  route: RouteGeometry;
  summary: TripSummary;
  stops: PlannedStop[];
  events: DutyEvent[];
  daily_logs: DailyLogSheet[];
  warnings: string[];
}
