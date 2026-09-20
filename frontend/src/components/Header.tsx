import React from 'react';
import { Bell, ClipboardList, Map, Route, Truck, UserRound } from 'lucide-react';

interface HeaderProps {
  onProtectedNavigation: (section: 'route-map' | 'stops-schedule' | 'daily-logs') => void;
}

export const Header: React.FC<HeaderProps> = ({ onProtectedNavigation }) => {
  return (
    <header className="app-header">
      <div className="brand-lockup">
        <div className="brand-mark"><Route size={18} /></div>
        <div>
          <div className="brand-name">Spotter <span>AI</span></div>
          <div className="brand-subtitle">Trip &amp; HOS Suite</div>
        </div>
      </div>
      <nav className="main-nav" aria-label="Primary navigation">
        <a className="nav-link active" href="#trip-plan"><ClipboardList size={14} /> Trip Plan</a>
        <a className="nav-link" href="#route-map" onClick={(event) => { event.preventDefault(); onProtectedNavigation('route-map'); }}><Map size={14} /> Route Map</a>
        <a className="nav-link" href="#stops-schedule" onClick={(event) => { event.preventDefault(); onProtectedNavigation('stops-schedule'); }}><Truck size={14} /> Stops &amp; Schedule</a>
        <a className="nav-link" href="#daily-logs" onClick={(event) => { event.preventDefault(); onProtectedNavigation('daily-logs'); }}><Route size={14} /> Daily ELD Logs</a>
      </nav>
      <div className="header-actions">
        <div className="live-indicator"><span /> Planning workspace</div>
        <button className="icon-button" type="button" aria-label="Notifications"><Bell size={16} /></button>
        <div className="user-chip"><UserRound size={15} /></div>
      </div>
    </header>
  );
};
