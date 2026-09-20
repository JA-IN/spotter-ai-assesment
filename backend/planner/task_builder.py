"""
Task builder module: converts route parameters and customer stops into ordered task sequences.

Separation of Concerns:
- task_builder.py defines WHAT must happen (Pickup, Driving segments, Fuel stops, Dropoff).
- scheduler.py defines WHEN it can legally happen under FMCSA Hours-of-Service rules.
"""
from typing import List, Optional, Tuple, Union

from planner.constants import (
    AVERAGE_DRIVE_SPEED_MPH,
    DROPOFF_DURATION_HOURS,
    FUEL_DURATION_HOURS,
    FUEL_INTERVAL_MILES,
    PICKUP_DURATION_HOURS,
)
from planner.routing import RouteResult
from planner.tasks import (
    DriveTask,
    DutyEvent,
    DutyStatus,
    Location,
    ServiceTask,
    ServiceType,
    Stop,
)


def _planning_duration_hours(distance_miles: float) -> float:
    """
    HOS scheduling uses a planning duration derived from the project's operating
    assumption, not OSRM route ETA.

    This is a deliberate architectural split:
      - RouteSegment.duration_hours = OSRM estimated road ETA for display/routing
      - DriveTask.duration_hours    = HOS planning duration used by the scheduler

    The project already defines an operational average driving speed of 55 mph in
    planner.constants, so we use that as the scheduler's planning assumption.
    """
    if distance_miles <= 0:
        return 0.0
    return distance_miles / AVERAGE_DRIVE_SPEED_MPH

__all__ = [
    "DutyStatus",
    "ServiceType",
    "Location",
    "DriveTask",
    "ServiceTask",
    "DutyEvent",
    "Stop",
    "build_tasks",
    "build_tasks_from_route",
]


def build_tasks_from_route(
    route: RouteResult,
    pickup_duration_hours: float = PICKUP_DURATION_HOURS,
    dropoff_duration_hours: float = DROPOFF_DURATION_HOURS,
) -> List[Union[DriveTask, ServiceTask]]:
    """
    Convert a route result into the canonical ordered task stream expected by the scheduler:
    Drive(current -> pickup)
    Pickup
    Drive(pickup -> dropoff)
    Dropoff

    RouteResult is defined as exactly two segments to represent:
      current -> pickup
      pickup -> dropoff

    This function consumes only RouteResult/RouteSegment data and does not know or care
    how the coordinates were obtained from Nominatim or OSRM.

    The HOS scheduler uses DriveTask.duration_hours as a planning duration based on the
    project's operating assumption (55 mph default), while RouteSegment.duration_hours remains
    the OSRM ETA for route/display purposes.
    """
    tasks: List[Union[DriveTask, ServiceTask]] = []

    if len(route.segments) != 2:
        raise ValueError(
            "RouteResult must contain exactly 2 segments: current -> pickup and pickup -> dropoff."
        )

    first_segment = route.segments[0]
    second_segment = route.segments[1]

    segment_1_distance = first_segment.distance_miles
    segment_2_distance = second_segment.distance_miles

    tasks.append(
        DriveTask(
            duration_hours=_planning_duration_hours(segment_1_distance),
            distance_miles=segment_1_distance,
            start_mile=0.0,
            end_mile=segment_1_distance,
            origin=first_segment.origin,
            destination=first_segment.destination,
            origin_coordinates=first_segment.origin_coordinates,
            destination_coordinates=first_segment.destination_coordinates,
            polyline=first_segment.geometry,
        )
    )

    tasks.append(
        ServiceTask(
            duration_hours=pickup_duration_hours,
            route_mile=segment_1_distance,
            location=route.pickup_location.name,
            service_type=ServiceType.PICKUP,
            annotation=f"Pickup at {route.pickup_location.name}",
        )
    )

    tasks.append(
        DriveTask(
            duration_hours=_planning_duration_hours(segment_2_distance),
            distance_miles=segment_2_distance,
            start_mile=segment_1_distance,
            end_mile=route.total_distance_miles,
            origin=second_segment.origin,
            destination=second_segment.destination,
            origin_coordinates=second_segment.origin_coordinates,
            destination_coordinates=second_segment.destination_coordinates,
            polyline=second_segment.geometry,
        )
    )

    tasks.append(
        ServiceTask(
            duration_hours=dropoff_duration_hours,
            route_mile=route.total_distance_miles,
            location=route.dropoff_location.name,
            service_type=ServiceType.DROPOFF,
            annotation=f"Dropoff at {route.dropoff_location.name}",
        )
    )

    return tasks


def build_tasks(
    origin: str,
    destination: str,
    distance_miles: float,
    duration_hours: Optional[float] = None,
    pickup_duration_hours: float = PICKUP_DURATION_HOURS,
    dropoff_duration_hours: float = DROPOFF_DURATION_HOURS,
    fuel_interval_miles: float = FUEL_INTERVAL_MILES,
    fuel_duration_hours: float = FUEL_DURATION_HOURS,
    polyline: Optional[List[Tuple[float, float]]] = None,
) -> List[Union[DriveTask, ServiceTask]]:
    """
    Constructs an ordered list of tasks for a trip:
    1. Origin Pickup service task (1h default)
    2. Driving segments with Fuel service tasks inserted at every fuel_interval_miles (1,000 miles default)
    3. Destination Dropoff service task (1h default)
    """
    tasks: List[Union[DriveTask, ServiceTask]] = []

    # 1. Pickup at Origin
    tasks.append(
        ServiceTask(
            duration_hours=pickup_duration_hours,
            route_mile=0.0,
            location=origin,
            service_type=ServiceType.PICKUP,
            annotation=f"Pickup at {origin}",
        )
    )

    if distance_miles <= 0:
        # Direct dropoff if zero distance
        tasks.append(
            ServiceTask(
                duration_hours=dropoff_duration_hours,
                route_mile=0.0,
                location=destination,
                service_type=ServiceType.DROPOFF,
                annotation=f"Dropoff at {destination}",
            )
        )
        return tasks

    total_driving_duration = (
        duration_hours
        if (duration_hours is not None and duration_hours > 0)
        else (distance_miles / AVERAGE_DRIVE_SPEED_MPH)
    )
    speed_mph = distance_miles / total_driving_duration

    # Calculate mile markers including intermediate fuel stops
    mile_markers = [0.0]
    if fuel_interval_miles > 0:
        current_fuel_mile = fuel_interval_miles
        while current_fuel_mile < distance_miles:
            mile_markers.append(current_fuel_mile)
            current_fuel_mile += fuel_interval_miles
    mile_markers.append(distance_miles)

    # 2. Add Driving Legs and Fuel Stops
    for i in range(len(mile_markers) - 1):
        start_m = mile_markers[i]
        end_m = mile_markers[i + 1]
        leg_dist = end_m - start_m
        leg_dur = leg_dist / speed_mph
        is_final_leg = (i == len(mile_markers) - 2)

        leg_origin = origin if start_m == 0.0 else f"Fuel Stop @ Mile {int(round(start_m))}"
        leg_dest = destination if is_final_leg else f"Fuel Stop @ Mile {int(round(end_m))}"

        tasks.append(
            DriveTask(
                duration_hours=leg_dur,
                distance_miles=leg_dist,
                start_mile=start_m,
                end_mile=end_m,
                origin=leg_origin,
                destination=leg_dest,
            )
        )

        if not is_final_leg:
            tasks.append(
                ServiceTask(
                    duration_hours=fuel_duration_hours,
                    route_mile=end_m,
                    location=f"Fuel Stop @ Mile {int(round(end_m))}",
                    service_type=ServiceType.FUEL,
                    annotation=f"Mandatory Fuel Stop at Mile {int(round(end_m))}",
                )
            )

    # 3. Dropoff at Destination
    tasks.append(
        ServiceTask(
            duration_hours=dropoff_duration_hours,
            route_mile=distance_miles,
            location=destination,
            service_type=ServiceType.DROPOFF,
            annotation=f"Dropoff at {destination}",
        )
    )

    return tasks