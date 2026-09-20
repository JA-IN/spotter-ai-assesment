import React from 'react';
import { PlannerStop } from '../types/planner';

interface StopListProps {
  stops: PlannerStop[];
}

function formatTime(value: string): string {
  return new Date(value).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

export const StopList: React.FC<StopListProps> = ({ stops }) => {
  return (
    <section className="detail-panel stop-list-container">
      <div className="section-kicker">Trip stops</div>
      <h2>Stops along the route</h2>
      <div className="stop-list">
        {stops.map((stop, index) => (
          <article className="stop-item" key={`${stop.stop_type}-${stop.route_mile}-${stop.arrival_time}`}>
            <div className="stop-index">{String(index + 1).padStart(2, '0')}</div>
            <div className="stop-marker" aria-hidden="true" />
            <div className="stop-copy">
              <div className="stop-type">{stop.stop_type}</div>
              <h3>{stop.name}</h3>
              <p>{stop.annotation}</p>
            </div>
            <div className="stop-meta">
              <strong>{stop.route_mile.toFixed(1)} mi</strong>
              <span>{formatTime(stop.arrival_time)}</span>
            </div>
          </article>
        ))}
        {stops.length === 0 && <p className="muted-copy">No scheduled stops were returned.</p>}
      </div>
    </section>
  );
};
