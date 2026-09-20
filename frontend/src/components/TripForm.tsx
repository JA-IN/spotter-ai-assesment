import React from 'react';
import { PlanTripRequest } from '../types/planner';

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
    <form className="trip-form-container" onSubmit={handleSubmit}>
      <div className="section-kicker">New route plan</div>
      <h2>Plan a compliant trip</h2>
      <p className="form-intro">Enter the trip details exactly as they appear in the dispatch request.</p>

      <label>
        Current Location
        <input
          required
          value={form.current_location}
          onChange={(event) => updateField('current_location', event.target.value)}
          placeholder="Chandigarh, India"
        />
      </label>

      <label>
        Pickup Location
        <input
          required
          value={form.pickup_location}
          onChange={(event) => updateField('pickup_location', event.target.value)}
          placeholder="Delhi, India"
        />
      </label>

      <label>
        Dropoff Location
        <input
          required
          value={form.dropoff_location}
          onChange={(event) => updateField('dropoff_location', event.target.value)}
          placeholder="Mumbai, India"
        />
      </label>

      <label>
        Current Cycle Used
        <input
          required
          min="0"
          max="70"
          step="0.1"
          type="number"
          value={form.current_cycle_used}
          onChange={(event) => updateField('current_cycle_used', event.target.value)}
          placeholder="60"
        />
      </label>

      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Planning trip...' : 'Plan Trip'}
      </button>
    </form>
  );
};
