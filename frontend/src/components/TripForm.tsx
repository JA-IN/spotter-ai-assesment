import React from 'react';
import { ArrowRight, MapPin } from 'lucide-react';
import { HOS_CYCLE_LIMIT_HOURS, PlanTripRequest } from '../types/planner';

interface TripFormProps {
  onSubmit: (request: PlanTripRequest) => void;
  isLoading: boolean;
}

export const TripForm: React.FC<TripFormProps> = ({ onSubmit, isLoading }) => {
  const [form, setForm] = React.useState<PlanTripRequest>({
    current_location: '',
    pickup_location: '',
    dropoff_location: '',
    current_cycle_used: 0,
  });

  const updateField = (field: keyof PlanTripRequest, value: string) => {
    setForm((current) => ({
      ...current,
      [field]: field === 'current_cycle_used' ? Number(value) : value,
    }));
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit(form);
  };

  return (
    <form className="trip-form-container panel" onSubmit={handleSubmit} id="trip-plan">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">Trip plan</div>
          <h2>Build a route</h2>
        </div>
        <span className="heading-icon"><MapPin size={18} /></span>
      </div>
      <p className="form-intro">Enter the dispatch request details. The scheduling engine will calculate stops, duty events, and daily logs.</p>

      <label>
        Current Location
        <input
          required
          value={form.current_location}
          onChange={(event) => updateField('current_location', event.target.value)}
          placeholder="Starting location"
        />
      </label>

      <label>
        Pickup Location
        <input
          required
          value={form.pickup_location}
          onChange={(event) => updateField('pickup_location', event.target.value)}
          placeholder="Pickup location"
        />
      </label>

      <label>
        Dropoff Location
        <input
          required
          value={form.dropoff_location}
          onChange={(event) => updateField('dropoff_location', event.target.value)}
          placeholder="Dropoff location"
        />
      </label>

      <label>
        Current Cycle Used
        <input
          required
          min="0"
          max={HOS_CYCLE_LIMIT_HOURS}
          step="0.1"
          type="number"
          value={form.current_cycle_used}
          onChange={(event) => updateField('current_cycle_used', event.target.value)}
          placeholder="0"
        />
      </label>

      <button className="primary-button" type="submit" disabled={isLoading}>
        {isLoading ? 'Planning route...' : 'Plan trip'} <ArrowRight size={16} />
      </button>
    </form>
  );
};
