"""API views for trip planning."""

from datetime import date, datetime
from enum import Enum

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.logs import DailyLog, generate_daily_logs
from planner.routing import calculate_route
from planner.scheduler import HOSScheduler
from planner.serializers import TripPlanRequestSerializer
from planner.task_builder import build_tasks_from_route


def _serialize_value(value):
    """Convert Python values into JSON-safe serializable values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    return value


def _serialize_route(route):
    """Serialize the route result into a JSON-friendly dictionary."""
    return {
        "current_location": {
            "name": route.current_location.name,
            "latitude": route.current_location.latitude,
            "longitude": route.current_location.longitude,
        },
        "pickup_location": {
            "name": route.pickup_location.name,
            "latitude": route.pickup_location.latitude,
            "longitude": route.pickup_location.longitude,
        },
        "dropoff_location": {
            "name": route.dropoff_location.name,
            "latitude": route.dropoff_location.latitude,
            "longitude": route.dropoff_location.longitude,
        },
        "total_distance_miles": route.total_distance_miles,
        "total_duration_hours": route.total_duration_hours,
        "geometry": [[lat, lng] for lat, lng in route.geometry],
        "segments": [
            {
                "origin": segment.origin,
                "destination": segment.destination,
                "origin_coordinates": list(segment.origin_coordinates),
                "destination_coordinates": list(segment.destination_coordinates),
                "distance_miles": segment.distance_miles,
                "duration_hours": segment.duration_hours,
                "geometry": [[lat, lng] for lat, lng in segment.geometry],
            }
            for segment in route.segments
        ],
    }


def _serialize_task(task):
    """Serialize drive and service tasks into a JSON-friendly dictionary."""
    if isinstance(task, dict):
        return _serialize_value(task)

    payload = {
        "type": task.__class__.__name__,
        "duration_hours": task.duration_hours,
        "annotation": getattr(task, "annotation", ""),
    }

    for field_name in [
        "distance_miles",
        "start_mile",
        "end_mile",
        "route_mile",
        "location",
        "service_type",
        "origin",
        "destination",
        "origin_coordinates",
        "destination_coordinates",
        "polyline",
    ]:
        if hasattr(task, field_name):
            value = getattr(task, field_name)
            if field_name == "service_type" and value is not None:
                payload[field_name] = value.value if hasattr(value, "value") else value
            elif field_name in {"origin_coordinates", "destination_coordinates", "polyline"} and value is not None:
                if isinstance(value, list):
                    payload[field_name] = [[lat, lng] for lat, lng in value]
                else:
                    payload[field_name] = list(value)
            else:
                payload[field_name] = _serialize_value(value)

    return payload


def _serialize_event(event):
    """Serialize a scheduled duty event into a JSON-friendly dictionary."""
    return {
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat(),
        "duration_hours": event.duration_hours,
        "status": event.status.value,
        "annotation": event.annotation,
        "route_mile": event.route_mile,
        "end_route_mile": event.end_route_mile,
        "location_name": event.location_name,
        "event_type": event.event_type,
    }


def _serialize_daily_log(log: DailyLog):
    """Serialize a daily log into a JSON-friendly dictionary."""
    return {
        "date": log.date.isoformat(),
        "day_number": log.day_number,
        "events": [_serialize_event(event) for event in log.events],
        "off_duty_hours": log.off_duty_hours,
        "sleeper_berth_hours": log.sleeper_berth_hours,
        "driving_hours": log.driving_hours,
        "on_duty_not_driving_hours": log.on_duty_not_driving_hours,
        "total_hours": log.total_hours,
        "miles_driven": log.miles_driven,
        "remarks": [
            {
                "time": remark.time.isoformat(),
                "location": remark.location,
                "annotation": remark.annotation,
                "status": remark.status.value,
                "route_mile": remark.route_mile,
            }
            for remark in log.remarks
        ],
    }


def _serialize_stop(stop):
    return {
        "stop_type": stop.stop_type.value,
        "name": stop.name,
        "route_mile": stop.route_mile,
        "arrival_time": stop.arrival_time.isoformat(),
        "departure_time": stop.departure_time.isoformat(),
        "duration_hours": stop.duration_hours,
        "annotation": stop.annotation,
        "lat": stop.lat,
        "lng": stop.lng,
    }


class PlanTripView(APIView):
    """End-to-end orchestration for trip planning."""

    def post(self, request, *args, **kwargs):
        serializer = TripPlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            route = calculate_route(
                data["current_location"],
                data["pickup_location"],
                data["dropoff_location"],
            )
            tasks = build_tasks_from_route(route)

            scheduler = HOSScheduler(initial_cycle_used=data["current_cycle_used"])
            scheduled_state = scheduler.schedule(tasks)
            daily_logs = generate_daily_logs(scheduled_state.events)

            return Response(
                {
                    "route": _serialize_route(route),
                    "tasks": [_serialize_task(task) for task in tasks],
                    "events": [_serialize_event(event) for event in scheduled_state.events],
                    "stops": [_serialize_stop(stop) for stop in scheduled_state.stops],
                    "daily_logs": [_serialize_daily_log(log) for log in daily_logs],
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:  # pragma: no cover - unexpected backend failure guard
            return Response({"detail": "Unexpected backend error while planning the trip."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
