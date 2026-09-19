import React from 'react';
import { Header } from '../components/Header';
import { TripForm } from '../components/TripForm';
import { TripSummary } from '../components/TripSummary';
import { RouteMap } from '../components/RouteMap';
import { DailyLog } from '../components/DailyLog';

export const PlannerPage: React.FC = () => {
  return (
    <div className="planner-page">
      <Header />
      <main className="planner-content">
        <TripForm />
        <TripSummary />
        <RouteMap />
        <DailyLog />
      </main>
    </div>
  );
};
