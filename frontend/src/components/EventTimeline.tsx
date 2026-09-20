import React from 'react';
import { PlannerEvent } from '../types/planner';

interface EventTimelineProps {
  events: PlannerEvent[];
}

function formatTime(value: string): string {
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDuration(hours: number): string {
  const totalMinutes = Math.round(hours * 60);
  const wholeHours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return wholeHours > 0 ? `${wholeHours}h${minutes ? ` ${minutes}m` : ''}` : `${minutes}m`;
}

export const EventTimeline: React.FC<EventTimelineProps> = ({ events }) => {
  return (
    <section className="detail-panel panel event-timeline-container">
      <div className="panel-heading"><div><div className="section-kicker">Duty events</div><h2>Event timeline</h2></div><span className="count-badge">{events.length}</span></div>
      <div className="event-list">
        {events.map((event, index) => (
          <article className={`event-item event-${event.event_type.toLowerCase()}`} key={`${event.event_type}-${event.start_time}-${index}`}>
            <div className="event-time">
              <strong>{formatTime(event.start_time)}</strong>
              <span>{formatTime(event.end_time)}</span>
            </div>
            <div className="event-line" aria-hidden="true"><span /></div>
            <div className="event-copy">
              <div className="event-label-row">
                <strong className={`status-badge status-${event.status.toLowerCase()}`}>{event.status.replace(/_/g, ' ')}</strong>
                <span>{formatDuration(event.duration_hours)}</span>
              </div>
              <p>{event.annotation}</p>
            </div>
          </article>
        ))}
        {events.length === 0 && <p className="muted-copy">No scheduled events were returned.</p>}
      </div>
    </section>
  );
};
