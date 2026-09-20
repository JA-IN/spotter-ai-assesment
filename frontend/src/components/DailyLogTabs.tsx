import React from 'react';
import { DailyLog as DailyLogData } from '../types/planner';
import { DailyLog } from './DailyLog';

interface DailyLogTabsProps {
  logs: DailyLogData[];
}

export const DailyLogTabs: React.FC<DailyLogTabsProps> = ({ logs }) => {
  const [activeIndex, setActiveIndex] = React.useState(0);
  const activeLog = logs[activeIndex];

  return (
    <section className="daily-log-tabs-container">
      <div className="log-tabs-heading">
        <div>
          <div className="section-kicker">Daily log record</div>
          <h2 id="daily-logs">Daily ELD logs</h2>
          <p className="panel-subtitle">Generated from the scheduler duty events returned for this trip.</p>
        </div>
        <div className="log-tabs" role="tablist" aria-label="Daily logs">
          {logs.map((log, index) => (
            <button
              key={log.date}
              className={index === activeIndex ? 'active' : ''}
              onClick={() => setActiveIndex(index)}
              role="tab"
              aria-selected={index === activeIndex}
              type="button"
            >
                Day {log.day_number}<span>{log.date}</span>
            </button>
          ))}
        </div>
      </div>
      {activeLog ? <DailyLog log={activeLog} /> : <p className="muted-copy">No daily logs were returned.</p>}
    </section>
  );
};
