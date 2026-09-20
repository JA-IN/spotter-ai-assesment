import React from 'react';
import { CheckCircle2, Clock3, Gauge } from 'lucide-react';
import { DailyLog as DailyLogData, DutyStatus } from '../types/planner';

interface DailyLogProps {
  log: DailyLogData;
}

const rows: { status: DutyStatus; label: string }[] = [
  { status: 'OFF_DUTY', label: 'OFF DUTY' },
  { status: 'SLEEPER_BERTH', label: 'SLEEPER BERTH' },
  { status: 'DRIVING', label: 'DRIVING' },
  { status: 'ON_DUTY_NOT_DRIVING', label: 'ON DUTY (NOT DRIVING)' },
];

function hoursFromLogStart(value: string, logDate: string): number {
  const logStart = new Date(`${logDate}T00:00:00`);
  return (new Date(value).getTime() - logStart.getTime()) / 3_600_000;
}

function statusY(status: DutyStatus): number {
  return { OFF_DUTY: 32, SLEEPER_BERTH: 96, DRIVING: 160, ON_DUTY_NOT_DRIVING: 224 }[status];
}

function buildPath(log: DailyLogData): string {
  const points: string[] = [];
  let previousStatus: DutyStatus | null = null;
  log.events.forEach((event, index) => {
    const start = Math.max(0, Math.min(24, hoursFromLogStart(event.start_time, log.date)));
    const end = Math.max(start, Math.min(24, hoursFromLogStart(event.end_time, log.date)));
    const startX = (start / 24) * 1440;
    const endX = (end / 24) * 1440;
    const y = statusY(event.status);
    if (index === 0) points.push(`M ${startX} ${y}`);
    else if (previousStatus !== event.status) points.push(`L ${startX} ${statusY(previousStatus!)}`, `L ${startX} ${y}`);
    points.push(`L ${endX} ${y}`);
    previousStatus = event.status;
  });
  return points.join(' ');
}

export const DailyLog: React.FC<DailyLogProps> = ({ log }) => {
  return (
    <section className="daily-log-container">
      <div className="log-grid-heading"><span>STATUS / DUTY</span><span>24-HOUR DUTY STATUS GRID</span><span>TOTAL HRS</span></div>
      <div className="eld-chart" role="img" aria-label={`Daily duty log for ${log.date}`}>
        <div className="eld-labels">{rows.map((row) => <div key={row.status}><strong>{row.label}</strong><code>{row.status === 'ON_DUTY_NOT_DRIVING' ? 'ON' : row.status === 'SLEEPER_BERTH' ? 'SB' : row.status === 'OFF_DUTY' ? 'OFF' : 'D'}</code></div>)}</div>
        <div className="eld-plot">
          <div className="eld-axis">{Array.from({ length: 24 }, (_, hour) => <span key={hour}>{hour === 0 ? 'Mid' : hour === 12 ? '12N' : String(hour).padStart(2, '0')}</span>)}</div>
          <div className="eld-canvas">
            <div className="eld-row-bands">{rows.map((row) => <div key={row.status} />)}</div>
            <svg viewBox="0 0 1440 256" preserveAspectRatio="none" aria-hidden="true">
              <defs><pattern id={`ticks-${log.day_number}`} width="60" height="64" patternUnits="userSpaceOnUse"><path d="M15 28V36 M30 22V42 M45 28V36 M60 0V64" stroke="#cbd5e1" strokeWidth="1" /></pattern></defs>
              <rect width="1440" height="256" fill={`url(#ticks-${log.day_number})`} />
              <path className="eld-step-shadow" d={buildPath(log)} />
              <path className="eld-step-line" d={buildPath(log)} />
            </svg>
            {log.events.map((event, index) => <span className={`event-marker marker-${event.status.toLowerCase()}`} key={`${event.start_time}-${index}`} style={{ left: `${Math.max(0, Math.min(100, (hoursFromLogStart(event.start_time, log.date) / 24) * 100))}%`, top: `${((statusY(event.status) - 8) / 256) * 100}%` }} title={event.annotation} />)}
          </div>
          <div className="eld-axis eld-axis-bottom">{Array.from({ length: 24 }, (_, hour) => <span key={hour}>{String(hour).padStart(2, '0')}</span>)}</div>
        </div>
        <div className="eld-hours">{rows.map((row) => <div key={row.status}><span>{row.status === 'DRIVING' ? log.driving_hours : row.status === 'ON_DUTY_NOT_DRIVING' ? log.on_duty_not_driving_hours : row.status === 'OFF_DUTY' ? log.off_duty_hours : log.sleeper_berth_hours}</span> h</div>)}</div>
      </div>
      <div className="log-audit"><span><CheckCircle2 size={14} /> Recorded total: {log.total_hours.toFixed(1)} hours</span><span><Gauge size={14} /> {log.miles_driven.toFixed(1)} route miles</span><span><Clock3 size={14} /> {log.remarks.length} remarks</span></div>
    </section>
  );
};
