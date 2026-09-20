"""
Data structures for tasks, duty status, duty events, and stops used by the HOS Scheduler.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple


class DutyStatus(str, Enum):
    """FMCSA standard 4-line Duty Status categories."""
    OFF_DUTY = "OFF_DUTY"
    SLEEPER_BERTH = "SLEEPER_BERTH"
    DRIVING = "DRIVING"
    ON_DUTY_NOT_DRIVING = "ON_DUTY_NOT_DRIVING"


class ServiceType(str, Enum):
    """Types of service tasks and stops."""
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"
    FUEL = "FUEL"
    REST = "REST"
    BREAK = "BREAK"


@dataclass
class Location:
    """Geographic or named location on the route."""
    name: str
    lat: Optional[float] = None
    lng: Optional[float] = None


@dataclass
class DriveTask:
    """
    Represents driving a segment of the route.
    
    Attributes:
        duration_hours: Expected driving duration in hours.
        distance_miles: Distance of the leg in miles.
        start_mile: Mile marker along the overall trip where this leg starts.
        end_mile: Mile marker along the overall trip where this leg ends.
        destination: Destination location or name.
        origin: Origin location or name.
        origin_coordinates: Optional coordinates for the leg start.
        destination_coordinates: Optional coordinates for the leg end.
        polyline: Optional list of (lat, lng) coordinate pairs for map rendering.
    """
    duration_hours: float
    distance_miles: float
    start_mile: float
    end_mile: float
    destination: str
    origin: str = ""
    origin_coordinates: Optional[Tuple[float, float]] = None
    destination_coordinates: Optional[Tuple[float, float]] = None
    polyline: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class ServiceTask:
    """
    Represents on-duty or non-driving activity along the route (pickup, dropoff, fuel).
    
    Attributes:
        duration_hours: Required duration in hours for the service task.
        route_mile: Mile marker along the route where this service takes place.
        location: Name or address of the service stop.
        service_type: Type of service (PICKUP, DROPOFF, FUEL, etc.).
        annotation: Human-readable note or label (e.g., 'Pickup at Shipper').
    """
    duration_hours: float
    route_mile: float
    location: str
    service_type: ServiceType
    annotation: str = ""


@dataclass
class DutyEvent:
    """
    A discrete, scheduled HOS event along the single deterministic timeline.
    
    Attributes:
        start_time: ISO timestamp / datetime when the event begins.
        end_time: ISO timestamp / datetime when the event concludes.
        duration_hours: Duration of the event in hours.
        status: FMCSA Duty Status category.
        annotation: Human-readable description (e.g., 'Driving to Dallas', '30-min break').
        route_mile: Mile marker at which the event started.
        end_route_mile: Mile marker at which the event ended. Set for DRIVING events;
                        None for non-driving events (PICKUP, DROPOFF, FUEL, REST, BREAK).
        location_name: Name of location or corridor.
        event_type: Specific event classification (e.g., 'DRIVE', 'PICKUP', 'DROPOFF', 'FUEL', 'REST', 'BREAK').
    """
    start_time: datetime
    end_time: datetime
    duration_hours: float
    status: DutyStatus
    annotation: str
    route_mile: float
    end_route_mile: Optional[float] = None
    location_name: str = ""
    event_type: str = ""


@dataclass
class Stop:
    """
    A concrete scheduled physical stop along the route.
    
    Attributes:
        stop_type: Category of stop (PICKUP, DROPOFF, FUEL, REST, BREAK).
        name: Name or description of the stop location.
        route_mile: Route mile marker where the stop occurs.
        arrival_time: When the vehicle arrives at the stop.
        departure_time: When the vehicle departs from the stop.
        duration_hours: Duration of the stop in hours.
        annotation: Additional remarks.
        lat: Optional latitude.
        lng: Optional longitude.
    """
    stop_type: ServiceType
    name: str
    route_mile: float
    arrival_time: datetime
    departure_time: datetime
    duration_hours: float
    annotation: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
