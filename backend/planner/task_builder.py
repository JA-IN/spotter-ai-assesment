"""
Task builder module: converts route parameters and stops into ordered task sequences.

Separation of Concerns:
- task_builder.py defines WHAT must happen (Pickup, Driving segments, Fuel stops, Dropoff).
- scheduler.py defines WHEN it can legally happen under FMCSA Hours-of-Service rules.
"""
from typing import List, Optional, Tuple, Union

from planner.scheduler import (
    AVERAGE_DRIVE_SPEED_MPH,
    DROPOFF_DURATION_HOURS,
    FUEL_DURATION_HOURS,
    FUEL_INTERVAL_MILES,
    PICKUP_DURATION_HOURS,
)
from planner.tasks import (
    DriveTask,
    DutyEvent,
    DutyStatus,
    Location,
    ServiceTask,
    ServiceType,
    Stop,
)

__all__ = [
    "DutyStatus",
    "ServiceType",
    "Location",
    "DriveTask",
    "ServiceTask",
    "DutyEvent",
    "Stop",
    "build_tasks",
]


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