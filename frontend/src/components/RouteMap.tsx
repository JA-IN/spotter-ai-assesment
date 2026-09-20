import React from 'react';
import { MapContainer, Polyline, TileLayer, CircleMarker, Tooltip } from 'react-leaflet';
import { PlannerRoute } from '../types/planner';
import 'leaflet/dist/leaflet.css';

interface RouteMapProps {
  route: PlannerRoute;
}

export const RouteMap: React.FC<RouteMapProps> = ({ route }) => {
  const isValidCoordinate = (latitude: number, longitude: number): boolean => (
    Number.isFinite(latitude) && Number.isFinite(longitude) && latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180
  );
  const positions = route.geometry
    .filter(([latitude, longitude]) => isValidCoordinate(latitude, longitude))
    .map(([latitude, longitude]) => [latitude, longitude] as [number, number]);
  const currentPosition = isValidCoordinate(route.current_location.latitude, route.current_location.longitude)
    ? [route.current_location.latitude, route.current_location.longitude] as [number, number]
    : null;
  const mapCenter = positions[0] || currentPosition;
  const hasMapData = Boolean(mapCenter);

  return (
    <div className="route-map-container" id="route-map">
      {hasMapData && mapCenter ? (
        <MapContainer center={mapCenter} zoom={5} scrollWheelZoom={false} className="route-map">
          <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {positions.length > 1 && <Polyline positions={positions} pathOptions={{ color: '#2563eb', weight: 4 }} />}
          {isValidCoordinate(route.current_location.latitude, route.current_location.longitude) && <CircleMarker center={[route.current_location.latitude, route.current_location.longitude]} pathOptions={{ color: '#64748b', fillColor: '#64748b', fillOpacity: 1 }} radius={6}>
            <Tooltip>{route.current_location.name}</Tooltip>
          </CircleMarker>}
          {isValidCoordinate(route.pickup_location.latitude, route.pickup_location.longitude) && <CircleMarker center={[route.pickup_location.latitude, route.pickup_location.longitude]} pathOptions={{ color: '#d97706', fillColor: '#f59e0b', fillOpacity: 1 }} radius={6}>
            <Tooltip>{route.pickup_location.name}</Tooltip>
          </CircleMarker>}
          {isValidCoordinate(route.dropoff_location.latitude, route.dropoff_location.longitude) && <CircleMarker center={[route.dropoff_location.latitude, route.dropoff_location.longitude]} pathOptions={{ color: '#059669', fillColor: '#10b981', fillOpacity: 1 }} radius={6}>
            <Tooltip>{route.dropoff_location.name}</Tooltip>
          </CircleMarker>}
        </MapContainer>
      ) : (
        <div className="route-map-empty">Route coordinates are not available yet.</div>
      )}
    </div>
  );
};
