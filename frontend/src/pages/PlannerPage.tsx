import React from 'react';
import { Header } from '../components/Header';
import { TripForm } from '../components/TripForm';
import { StopList } from '../components/StopList';
import { EventTimeline } from '../components/EventTimeline';
import { DailyLogTabs } from '../components/DailyLogTabs';
import { planTrip } from '../api/plannerApi';
import { PlanTripRequest, PlannerResponse } from '../types/planner';

export const PlannerPage: React.FC = () => {
  const [result, setResult] = React.useState<PlannerResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);

  const handleSubmit = async (request: PlanTripRequest) => {
    setIsLoading(true);
    setError(null);

    try {
      setResult(await planTrip(request));
    } catch (requestError) {
      setResult(null);
      setError(requestError instanceof Error ? requestError.message : 'Unable to plan this trip.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="planner-page">
      <Header />
      <main className="planner-content">
        <section className="planner-intro">
          <div className="section-kicker">Dispatch desk</div>
          <h1>Know the road before you roll.</h1>
          <p>Build a route, schedule the required stops, and receive the driver&apos;s daily log from one request.</p>
        </section>

        <div className="planner-grid">
          <TripForm onSubmit={handleSubmit} isLoading={isLoading} />

          <section className="result-panel" aria-live="polite">
            {!result && !error && (
              <div className="empty-result">
                <span className="result-mark">01</span>
                <h2>Your plan will appear here.</h2>
                <p>Submit the trip details to connect with the scheduling engine.</p>
              </div>
            )}

            {error && (
              <div className="error-result">
                <div className="section-kicker">Request failed</div>
                <h2>We could not plan this trip.</h2>
                <p>{error}</p>
              </div>
            )}

            {result && (
              <div className="success-result">
                <div className="section-kicker">Route ready</div>
                <h2>Trip planned successfully</h2>
                <div className="result-stats">
                  <div><strong>{result.route.total_distance_miles.toFixed(2)}</strong><span>miles</span></div>
                  <div><strong>{result.route.total_duration_hours.toFixed(2)}</strong><span>route hours</span></div>
                  <div><strong>{result.stops.length}</strong><span>stops</span></div>
                  <div><strong>{result.events.length}</strong><span>events</span></div>
                  <div><strong>{result.daily_logs.length}</strong><span>daily logs</span></div>
                </div>
              </div>
            )}
          </section>
        </div>

        {result && (
          <div className="trip-details">
            <div className="detail-grid">
              <StopList stops={result.stops} />
              <EventTimeline events={result.events} />
            </div>
            <DailyLogTabs logs={result.daily_logs} />
          </div>
        )}
      </main>
    </div>
  );
};
