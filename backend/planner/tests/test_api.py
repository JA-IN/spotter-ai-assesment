"""API integration tests for POST /api/plan-trip/."""

from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from planner.logs import DailyLog
from planner.tasks import DutyEvent, DutyStatus


class TestPlanTripAPI(TestCase):
    def test_invalid_payload_returns_400(self):
        response = self.client.post(
            "/api/plan-trip/",
            {
                "current_location": "",
                "pickup_location": "Delhi, India",
                "dropoff_location": "Jaipur, India",
                "current_cycle_used": 12.5,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("current_location", response.json())

    @patch("planner.views.calculate_route", side_effect=ValueError("Location not found: 'Invalid Place'") )
    def test_invalid_route_location_returns_clear_error(self, mock_calculate_route):
        response = self.client.post(
            "/api/plan-trip/",
            {
                "current_location": "Invalid Place",
                "pickup_location": "Pickup City",
                "dropoff_location": "Dropoff City",
                "current_cycle_used": 0.0,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Location not found: 'Invalid Place'")

    @patch("planner.views.calculate_route", side_effect=RuntimeError("routing service unavailable"))
    def test_routing_failure_returns_gateway_error(self, mock_calculate_route):
        response = self.client.post(
            "/api/plan-trip/",
            {
                "current_location": "Current City",
                "pickup_location": "Pickup City",
                "dropoff_location": "Dropoff City",
                "current_cycle_used": 0.0,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertIn("routing service unavailable", response.json()["detail"])

    @patch("planner.views.generate_daily_logs")
    @patch("planner.views.HOSScheduler")
    @patch("planner.views.build_tasks_from_route")
    @patch("planner.views.calculate_route")
    def test_plan_trip_pipeline_success(
        self,
        mock_calculate_route,
        mock_build_tasks_from_route,
        mock_scheduler_cls,
        mock_generate_daily_logs,
    ):
        route = type("RouteStub", (), {
            "current_location": type("Loc", (), {"name": "Chandigarh, India", "latitude": 30.73, "longitude": 76.78})(),
            "pickup_location": type("Loc", (), {"name": "Delhi, India", "latitude": 28.61, "longitude": 77.21})(),
            "dropoff_location": type("Loc", (), {"name": "Jaipur, India", "latitude": 26.92, "longitude": 75.82})(),
            "total_distance_miles": 240.0,
            "total_duration_hours": 4.5,
            "geometry": [(30.73, 76.78), (28.61, 77.21), (26.92, 75.82)],
            "segments": [],
        })()
        mock_calculate_route.return_value = route

        tasks = [{"kind": "drive", "duration_hours": 2.0}]
        mock_build_tasks_from_route.return_value = tasks

        scheduler_instance = mock_scheduler_cls.return_value
        scheduler_state = type("SchedulerStateStub", (), {
            "events": [
                DutyEvent(
                    start_time=datetime(2024, 1, 1, 8, 0),
                    end_time=datetime(2024, 1, 1, 10, 0),
                    duration_hours=2.0,
                    status=DutyStatus.DRIVING,
                    annotation="Driving",
                    route_mile=0.0,
                    end_route_mile=120.0,
                    location_name="Chandigarh, India",
                    event_type="DRIVE",
                )
            ],
            "stops": [],
        })()
        scheduler_instance.schedule.return_value = scheduler_state

        daily_log = DailyLog(
            date=datetime(2024, 1, 1).date(),
            day_number=1,
            events=scheduler_state.events,
            driving_hours=2.0,
            total_hours=2.0,
            miles_driven=120.0,
        )
        mock_generate_daily_logs.return_value = [daily_log]

        response = self.client.post(
            "/api/plan-trip/",
            {
                "current_location": "Chandigarh, India",
                "pickup_location": "Delhi, India",
                "dropoff_location": "Jaipur, India",
                "current_cycle_used": 12.5,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("route", payload)
        self.assertIn("tasks", payload)
        self.assertIn("events", payload)
        self.assertIn("daily_logs", payload)
        self.assertEqual(payload["route"]["total_distance_miles"], 240.0)
        self.assertEqual(payload["route"]["total_duration_hours"], 4.5)
