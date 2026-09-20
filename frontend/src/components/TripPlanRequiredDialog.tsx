import React from 'react';

export type ProtectedSection = 'route-map' | 'stops-schedule' | 'daily-logs';

interface TripPlanRequiredDialogProps {
  section: ProtectedSection | null;
  onGoToTripPlan: () => void;
  onCancel: () => void;
}

const messages: Record<ProtectedSection, string> = {
  'route-map': 'Please enter the required trip details and generate a trip plan first to view the route map.',
  'stops-schedule': 'Please generate a trip plan first to view stops and the HOS schedule.',
  'daily-logs': 'Please generate a trip plan first to view the daily ELD logs.',
};

export const TripPlanRequiredDialog: React.FC<TripPlanRequiredDialogProps> = ({ section, onGoToTripPlan, onCancel }) => {
  if (!section) return null;

  return (
    <div className="dialog-backdrop" role="presentation" onClick={onCancel}>
      <div className="trip-plan-dialog" role="dialog" aria-modal="true" aria-labelledby="trip-plan-dialog-title" onClick={(event) => event.stopPropagation()}>
        <div className="section-kicker">Navigation</div>
        <h2 id="trip-plan-dialog-title">Trip plan required</h2>
        <p>{messages[section]}</p>
        <div className="dialog-actions">
          <button className="primary-button" type="button" onClick={onGoToTripPlan}>Go to Trip Plan</button>
          <button className="dialog-cancel" type="button" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
};
