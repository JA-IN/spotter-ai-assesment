import React from 'react';
import { DailyLog as DailyLogData, DutyStatus } from '../types/planner';

interface DailyLogProps {
  log: DailyLogData;
}

const rows: { status: DutyStatus; label: string }[] = [
  { status: 'OFF_DUTY', label: 'Off duty' },
  { status: 'SLEEPER_BERTH', label: 'Sleeper' },
  { status: 'DRIVING', label: 'Driving' },
  { status: 'ON_DUTY_NOT_DRIVING', label: 'On duty' },
];

function hoursFromLogStart(value: string, logDate: string): number {
  const logStart = new Date(`${logDate}T00:00:00`);
  return (new Date(value).getTime() - logStart.getTime()) / 3_600_000;
}

export const DailyLog: React.FC<DailyLogProps> = ({ log }) => {
  return (
    <section className="detail-panel daily-log-container">
      <div className="section-kicker">Electronic log</div>
      <h2>Day {log.day_number} <span>{log.date}</span></h2>
      <div className="eld-chart" role="img" aria-label={`Daily duty log for ${log.date}`}>
        <div className="eld-axis-label" />
        <div className="eld-axis">{[0, 4, 8, 12, 16, 20, 24].map((hour) => <span key={hour}>{String(hour).padStart(2, '0')}</span>)}</div>
        {rows.map((row) => (
          <React.Fragment key={row.status}>
            <div className="eld-row-label">{row.label}</div>
            <div className="eld-track">
              {log.events.filter((event) => event.status === row.status).map((event, index) => {
                const start = hoursFromLogStart(event.start_time, log.date);
                const end = Math.max(start, hoursFromLogStart(event.end_time, log.date));
                return (
                  <span
                    className={`eld-block eld-${row.status.toLowerCase()}`}
                    key={`${event.start_time}-${event.event_type}-${index}`}
                    style={{ left: `${(start / 24) * 100}%`, width: `${((end - start) / 24) * 100}%` }}
                    title={event.annotation}
                  />
                );
              })}
            </div>
          </React.Fragment>
        ))}
      </div>
      <div className="log-totals">
        <span>Driving <strong>{log.driving_hours.toFixed(1)}h</strong></span>
        <span>On duty <strong>{log.on_duty_not_driving_hours.toFixed(1)}h</strong></span>
        <span>Off duty <strong>{log.off_duty_hours.toFixed(1)}h</strong></span>
        <span>Miles <strong>{log.miles_driven.toFixed(1)}</strong></span>
      </div>
    </section>
  );
};
