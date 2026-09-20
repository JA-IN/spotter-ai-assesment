"""
Routing contracts for geocoding and route planning.

This module is intentionally responsible for only two things:
1. turning free-form location strings into coordinates (geocoding)
2. turning coordinates into a road route (route calculation)

The HOS scheduler remains completely unaware of Nominatim/OSRM details.
It consumes structured route results, not raw external APIs.
"""

import requests
from dataclasses import dataclass, field
from typing import List, Tuple, Union


LocationInput = Union[str, "GeocodedLocation"]
Coordinate = Tuple[float, float]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving/"
REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class GeocodedLocation:
    """
    Normalized geocoded result for a human-entered location.

    The scheduler and task-builder should consume this object, not raw
    API dictionaries.
    """

    name: str
    latitude: float
    longitude: float

    @property
    def coordinates(self) -> Coordinate:
        """Return the location as (latitude, longitude)."""
        return (self.latitude, self.longitude)


@dataclass(frozen=True)
class RouteSegment:
    """
    A single route leg within the total trip.

    This represents one road segment such as current -> pickup or
    pickup -> dropoff. The geometry is a list of (lat, lng) coordinate pairs
    suitable for rendering with Leaflet/React.
    """

    origin: str
    destination: str
    origin_coordinates: Coordinate
    destination_coordinates: Coordinate
    distance_miles: float
    duration_hours: float
    geometry: List[Coordinate] = field(default_factory=list)


@dataclass
class RouteResult:
    """
    Full route plan for a trip that includes exactly two path segments:
    current -> pickup and pickup -> dropoff.

    This is a strict contract: route planning must not silently collapse to a
    single segment or invent missing legs. The task builder relies on exactly
    two segments to construct the canonical scheduler task sequence.
    """

    current_location: GeocodedLocation
    pickup_location: GeocodedLocation
    dropoff_location: GeocodedLocation
    total_distance_miles: float
    total_duration_hours: float
    geometry: List[Coordinate] = field(default_factory=list)
    segments: List[RouteSegment] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.segments) != 2:
            raise ValueError(
                "RouteResult must contain exactly 2 segments: current -> pickup and pickup -> dropoff."
            )


def _ensure_geocoded_location(value: LocationInput) -> GeocodedLocation:
    """Normalize route input values to a GeocodedLocation instance."""
    if isinstance(value, GeocodedLocation):
        return value
    if isinstance(value, str):
        return geocode_location(value)
    raise TypeError("Location inputs must be strings or GeocodedLocation objects.")


def _format_osrm_coordinates(start: GeocodedLocation, end: GeocodedLocation) -> str:
    """Return an OSRM route string in longitude,latitude order as required by the API."""
    return f"{start.longitude},{start.latitude};{end.longitude},{end.latitude}"


def _convert_osrm_geometry(raw_geometry: List[List[float]]) -> List[Coordinate]:
    """Convert OSRM GeoJSON coordinates [lon, lat] into internal (lat, lng) tuples."""
    return [(float(lon_lat[1]), float(lon_lat[0])) for lon_lat in raw_geometry]


def _combine_geometry(first: List[Coordinate], second: List[Coordinate]) -> List[Coordinate]:
    """Merge two route geometries while removing the duplicated midpoint coordinate."""
    if not first and not second:
        return []
    if not first:
        return list(second)
    if not second:
        return list(first)

    combined = list(first)
    if second and combined and second[0] == combined[-1]:
        combined.extend(second[1:])
    else:
        combined.extend(second)
    return combined


def _route_between_locations(
    origin: GeocodedLocation,
    destination: GeocodedLocation,
    origin_label: str,
    destination_label: str,
) -> RouteSegment:
    """Fetch and normalize a single road segment from OSRM."""
    route_query = _format_osrm_coordinates(origin, destination)
    request_url = f"{OSRM_BASE_URL}{route_query}"
    params = {
        "geometries": "geojson",
        "overview": "full",
        "steps": "false",
    }
    headers = {
        "User-Agent": "SpotterAI/1.0",
        "Accept": "application/json",
    }

    try:
        response = requests.get(request_url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise RuntimeError(f"OSRM route request failed for {origin_label} -> {destination_label}: {exc}") from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"OSRM route request failed for {origin_label} -> {destination_label}: "
            f"HTTP {response.status_code}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError(
            f"Malformed OSRM response for {origin_label} -> {destination_label}."
        ) from exc

    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError(f"OSRM returned no route for {origin_label} -> {destination_label}.")

    route = routes[0]
    geometry = route.get("geometry")
    if not isinstance(geometry, dict) or "coordinates" not in geometry:
        raise ValueError(f"Malformed OSRM geometry for {origin_label} -> {destination_label}.")

    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError(f"OSRM geometry was empty for {origin_label} -> {destination_label}.")

    distance_meters = route.get("distance")
    duration_seconds = route.get("duration")
    if not isinstance(distance_meters, (int, float)) or not isinstance(duration_seconds, (int, float)):
        raise ValueError(f"Malformed OSRM route metrics for {origin_label} -> {destination_label}.")

    return RouteSegment(
        origin=origin_label,
        destination=destination_label,
        origin_coordinates=origin.coordinates,
        destination_coordinates=destination.coordinates,
        distance_miles=float(distance_meters) / 1609.344,
        duration_hours=float(duration_seconds) / 3600.0,
        geometry=_convert_osrm_geometry(coordinates),
    )


def geocode_location(location: str) -> GeocodedLocation:
    """
    Convert a free-form location string into a normalized coordinate-bearing object.

    Example:
        geocode_location("Chandigarh, India")
        -> GeocodedLocation(name="Chandigarh, India", latitude=30.7333, longitude=76.7794)
    """
    if not isinstance(location, str):
        raise TypeError("Location must be a string.")

    cleaned = location.strip()
    if not cleaned:
        raise ValueError("Location string cannot be empty.")

    params = {
        "q": cleaned,
        "format": "jsonv2",
        "limit": 1,
    }
    headers = {
        "User-Agent": "SpotterAI/1.0",
        "Accept-Language": "en",
    }

    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise RuntimeError(f"Nominatim geocoding request failed for '{cleaned}': {exc}") from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Nominatim geocoding request failed for '{cleaned}': HTTP {response.status_code}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError(f"Malformed Nominatim response for '{cleaned}'.") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError(f"Location not found: '{cleaned}'")

    first_result = payload[0]
    if not isinstance(first_result, dict):
        raise ValueError(f"Malformed Nominatim response for '{cleaned}'.")

    latitude = first_result.get("lat")
    longitude = first_result.get("lon")
    if latitude is None or longitude is None:
        raise ValueError(f"Malformed Nominatim response for '{cleaned}'.")

    try:
        lat_value = float(latitude)
        lon_value = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Malformed Nominatim response for '{cleaned}'.") from exc

    return GeocodedLocation(
        name=first_result.get("display_name") or cleaned,
        latitude=lat_value,
        longitude=lon_value,
    )


def calculate_route(
    current_location: LocationInput,
    pickup_location: LocationInput,
    dropoff_location: LocationInput,
) -> RouteResult:
    """
    Build a route result that combines:
        current -> pickup
        pickup -> dropoff

    Returns a normalized RouteResult containing total distance, total duration,
    concatenated route geometry, and individual segments.
    """
    current = _ensure_geocoded_location(current_location)
    pickup = _ensure_geocoded_location(pickup_location)
    dropoff = _ensure_geocoded_location(dropoff_location)

    current_to_pickup = _route_between_locations(
        current,
        pickup,
        origin_label=current.name,
        destination_label=pickup.name,
    )
    pickup_to_dropoff = _route_between_locations(
        pickup,
        dropoff,
        origin_label=pickup.name,
        destination_label=dropoff.name,
    )

    combined_geometry = _combine_geometry(current_to_pickup.geometry, pickup_to_dropoff.geometry)
    total_distance = current_to_pickup.distance_miles + pickup_to_dropoff.distance_miles
    total_duration = current_to_pickup.duration_hours + pickup_to_dropoff.duration_hours

    return RouteResult(
        current_location=current,
        pickup_location=pickup,
        dropoff_location=dropoff,
        total_distance_miles=total_distance,
        total_duration_hours=total_duration,
        geometry=combined_geometry,
        segments=[current_to_pickup, pickup_to_dropoff],
    )


__all__ = [
    "Coordinate",
    "GeocodedLocation",
    "LocationInput",
    "RouteResult",
    "RouteSegment",
    "calculate_route",
    "geocode_location",
]
