import React from 'react';
import { Header } from '../components/Header';
import { TripForm } from '../components/TripForm';
import { StopList } from '../components/StopList';
import { EventTimeline } from '../components/EventTimeline';
import { DailyLogTabs } from '../components/DailyLogTabs';
import { RouteMap } from '../components/RouteMap';
import { ProtectedSection, TripPlanRequiredDialog } from '../components/TripPlanRequiredDialog';
import { ArrowDown, CalendarDays, CheckCircle2, Clock3, Gauge, Route, Truck } from 'lucide-react';
import { planTrip } from '../api/plannerApi';
import { HOS_CYCLE_LIMIT_HOURS, PlanTripRequest, PlannerResponse } from '../types/planner';

export const PlannerPage: React.FC = () => {
  const [result, setResult] = React.useState<PlannerResponse | null>(null);
  const [submittedCycle, setSubmittedCycle] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [protectedSection, setProtectedSection] = React.useState<ProtectedSection | null>(null);

  const navigateToSection = (section: ProtectedSection) => {
    if (!result) {
      setProtectedSection(section);
      return;
    }

    document.getElementById(section)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const goToTripPlan = () => {
    setProtectedSection(null);
    document.getElementById('trip-plan')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const handleSubmit = async (request: PlanTripRequest) => {
    setIsLoading(true);
    setError(null);
    setSubmittedCycle(request.current_cycle_used);

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
      <Header onProtectedNavigation={navigateToSection} />
      <main className="planner-content">
        <section className="page-titlebar">
          <div>
            <div className="section-kicker">Operations workspace</div>
            <h1>Trip planning desk</h1>
            <p>Plan the route, Schedule stops, and review the resulting duty record.</p>
          </div>
          <div className="date-badge"><CalendarDays size={15} /> Planning workspace</div>
        </section>

        <div className="planner-grid">
          <TripForm onSubmit={handleSubmit} isLoading={isLoading} />

          <section className="result-panel" aria-live="polite">
            {!result && !error && (
              <div className="empty-result">
                <span className="result-mark"><Route size={32} /></span>
                <h2>Your route summary will appear here.</h2>
                <p>Submit trip details to generate the route, stops, events, and daily ELD records.</p>
              </div>
            )}

            {error && (
              <div className="error-result">
                <div className="section-kicker error-kicker">Request failed</div>
                <h2>We could not plan this trip.</h2>
                <p>{error}</p>
              </div>
            )}

            {result && (
              <div className="success-result">
                <div className="section-kicker">Route ready</div>
                <h2>{result.route.current_location.name} <ArrowDown size={18} /> {result.route.dropoff_location.name}</h2>
                <div className="result-stats">
                  <div><Gauge size={16} /><strong>{result.route.total_distance_miles.toFixed(1)}</strong><span>route miles</span></div>
                  <div><Clock3 size={16} /><strong>{result.route.total_duration_hours.toFixed(1)}</strong><span>route hours</span></div>
                  <div><Truck size={16} /><strong>{result.stops.length}</strong><span>scheduled stops</span></div>
                  <div><CheckCircle2 size={16} /><strong>{result.events.length}</strong><span>duty events</span></div>
                </div>
              </div>
            )}
          </section>
        </div>

        {result && (
          <div className="trip-details">
            <div className="overview-grid">
              <RouteMap route={result.route} />
              <section className="panel manifest-panel" id="stops-schedule">
                <div className="panel-heading"><div><div className="section-kicker">Active manifest</div><h2>Route summary</h2></div><Route size={18} /></div>
                <div className="manifest-grid">
                  <div><span>Current location</span><strong>{result.route.current_location.name}</strong></div>
                  <div><span>Pickup</span><strong>{result.route.pickup_location.name}</strong></div>
                  <div><span>Dropoff</span><strong>{result.route.dropoff_location.name}</strong></div>
                  <div><span>Distance</span><strong>{result.route.total_distance_miles.toFixed(1)} mi</strong></div>
                  <div><span>Duration</span><strong>{result.route.total_duration_hours.toFixed(1)} hr</strong></div>
                  <div><span>Cycle used</span><strong>{submittedCycle === null ? 'Not provided' : `${submittedCycle.toFixed(1)} / ${HOS_CYCLE_LIMIT_HOURS} hr`}</strong></div>
                </div>
              </section>
            </div>
            <div className="detail-grid">
              <StopList stops={result.stops} />
              <EventTimeline events={result.events} />
            </div>
            <DailyLogTabs logs={result.daily_logs} />
          </div>
        )}
      </main>
      <TripPlanRequiredDialog section={protectedSection} onGoToTripPlan={goToTripPlan} onCancel={() => setProtectedSection(null)} />
    </div>
  );
};
