/** TypeScript definitions for the Django trip-planning response. */

export type DutyStatus =
  | 'OFF_DUTY'
  | 'SLEEPER_BERTH'
  | 'DRIVING'
  | 'ON_DUTY_NOT_DRIVING';

export const HOS_CYCLE_LIMIT_HOURS = 70;

export type ServiceType = 'PICKUP' | 'DROPOFF' | 'FUEL' | 'REST' | 'BREAK';

export interface PlanTripRequest {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_cycle_used: number;
}

export interface RouteLocation {
  name: string;
  latitude: number;
  longitude: number;
}

export interface RouteSegment {
  origin: string;
  destination: string;
  origin_coordinates: [number, number];
  destination_coordinates: [number, number];
  distance_miles: number;
  duration_hours: number;
  geometry: [number, number][];
}

export interface PlannerRoute {
  current_location: RouteLocation;
  pickup_location: RouteLocation;
  dropoff_location: RouteLocation;
  total_distance_miles: number;
  total_duration_hours: number;
  geometry: [number, number][];
  segments: RouteSegment[];
}

export interface PlannerTask {
  type: string;
  duration_hours: number;
  annotation: string;
  distance_miles?: number;
  start_mile?: number;
  end_mile?: number;
  route_mile?: number;
  location?: string;
  service_type?: ServiceType;
  origin?: string;
  destination?: string;
  origin_coordinates?: [number, number];
  destination_coordinates?: [number, number];
  polyline?: [number, number][];
}

export interface PlannerEvent {
  start_time: string;
  end_time: string;
  duration_hours: number;
  status: DutyStatus;
  annotation: string;
  route_mile: number;
  end_route_mile: number | null;
  location_name: string;
  event_type: string;
}

export interface PlannerStop {
  stop_type: ServiceType;
  name: string;
  route_mile: number;
  arrival_time: string;
  departure_time: string;
  duration_hours: number;
  annotation: string;
  lat: number | null;
  lng: number | null;
}

export interface DailyLogRemark {
  time: string;
  location: string;
  annotation: string;
  status: DutyStatus;
  route_mile: number;
}

export interface DailyLog {
  date: string;
  day_number: number;
  events: PlannerEvent[];
  off_duty_hours: number;
  sleeper_berth_hours: number;
  driving_hours: number;
  on_duty_not_driving_hours: number;
  total_hours: number;
  miles_driven: number;
  remarks: DailyLogRemark[];
}

export interface PlannerResponse {
  route: PlannerRoute;
  tasks: PlannerTask[];
  events: PlannerEvent[];
  stops: PlannerStop[];
  daily_logs: DailyLog[];
}

export type PlanTripResponse = PlannerResponse;
