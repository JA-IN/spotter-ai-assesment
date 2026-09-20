"""
Comprehensive unit tests for the HOS Scheduler Engine and Task Builder.

Canonical Test Scenarios:
- Test 1: Short trip (under all limits)
- Test 2: 8h driving -> 30m mandatory rest break
- Test 3: 11h driving limit -> 10h consecutive off-duty rest
- Test 4: 14h consecutive shift window (driving + on-duty service interactions)
- Test 5: 70h / 8-day cycle limit -> 34h off-duty restart
- Test 6: Pickup & dropoff service events
- Test 7: Fuel stops at 1,000-mile intervals
- Test 8: Long multi-day cross-country trip
"""
from datetime import datetime, timedelta
import unittest

from planner.constants import (
    AVERAGE_DRIVE_SPEED_MPH,
    BREAK_AFTER_DRIVING_HOURS,
    BREAK_DURATION_HOURS,
    CYCLE_LIMIT_HOURS,
    CYCLE_RESTART_DURATION_HOURS,
    DROPOFF_DURATION_HOURS,
    FUEL_DURATION_HOURS,
    FUEL_INTERVAL_MILES,
    MAX_DRIVING_HOURS,
    MAX_SHIFT_WINDOW_HOURS,
    PICKUP_DURATION_HOURS,
    RESTART_DURATION_HOURS,
    REST_DURATION_HOURS,
)
from planner.scheduler import HOSScheduler, SchedulerState, schedule_trip
from planner.logs import generate_daily_logs
from planner.task_builder import build_tasks, build_tasks_from_route
from planner.routing import GeocodedLocation, RouteResult, RouteSegment
from planner.tasks import (
    DriveTask,
    DutyEvent,
    DutyStatus,
    Location,
    ServiceTask,
    ServiceType,
    Stop,
)


class TestHOSScheduler(unittest.TestCase):
    """Exhaustive test suite verifying pure Python deterministic HOS rules."""

    def test_1_short_trip(self):
        """Test 1: Short trip well within all single-shift limits."""
        start = datetime(2026, 9, 20, 8, 0, 0)
        tasks = [
            DriveTask(
                duration_hours=5.0,
                distance_miles=275.0,
                start_mile=0.0,
                end_mile=275.0,
                origin="City A",
                destination="City B",
            )
        ]
        state = schedule_trip(tasks, start_time=start, initial_cycle_used=0.0)

        self.assertEqual(len(state.events), 1)
        event = state.events[0]
        self.assertEqual(event.status, DutyStatus.DRIVING)
        self.assertEqual(event.duration_hours, 5.0)
        self.assertEqual(event.start_time, start)
        self.assertEqual(event.end_time, start + timedelta(hours=5))
        self.assertEqual(state.shift_driving, 5.0)
        self.assertEqual(state.driving_since_break, 5.0)
        self.assertEqual(state.cycle_used, 5.0)
        self.assertEqual(state.current_mile, 275.0)

    def test_2_8h_driving_to_30m_break(self):
        """Test 2: Mandatory 30-minute break after 8 cumulative hours of driving."""
        start = datetime(2026, 9, 20, 7, 0, 0)
        tasks = [
            DriveTask(
                duration_hours=10.0,
                distance_miles=550.0,
                start_mile=0.0,
                end_mile=550.0,
                origin="City A",
                destination="City B",
            )
        ]
        state = schedule_trip(tasks, start_time=start, initial_cycle_used=0.0)

        # Expected: 8h Drive -> 0.5h Break -> 2h Drive
        self.assertEqual(len(state.events), 3)

        # Leg 1: 8.0h driving
        self.assertEqual(state.events[0].status, DutyStatus.DRIVING)
        self.assertEqual(state.events[0].duration_hours, 8.0)

        # 30-min break
        self.assertEqual(state.events[1].status, DutyStatus.OFF_DUTY)
        self.assertEqual(state.events[1].duration_hours, 0.5)
        self.assertEqual(state.events[1].event_type, "BREAK")

        # Leg 2: 2.0h driving
        self.assertEqual(state.events[2].status, DutyStatus.DRIVING)
        self.assertEqual(state.events[2].duration_hours, 2.0)

        # Driving since break should reset to 2.0h; shift driving total is 10.0h
        self.assertEqual(state.shift_driving, 10.0)
        self.assertEqual(state.driving_since_break, 2.0)

    def test_3_11h_driving_to_10h_rest(self):
        """Test 3: 11-hour driving limit per shift forces a 10-hour consecutive rest."""
        start = datetime(2026, 9, 20, 6, 0, 0)
        tasks = [
            DriveTask(
                duration_hours=15.0,
                distance_miles=825.0,
                start_mile=0.0,
                end_mile=825.0,
                origin="City A",
                destination="City B",
            )
        ]
        state = schedule_trip(tasks, start_time=start, initial_cycle_used=0.0)

        # Total driving hours must be 15.0
        driving_events = [e for e in state.events if e.status == DutyStatus.DRIVING]
        self.assertEqual(sum(e.duration_hours for e in driving_events), 15.0)

        # Must have a 10-hour rest event
        rest_events = [e for e in state.events if e.status == DutyStatus.OFF_DUTY and e.duration_hours == 10.0]
        self.assertEqual(len(rest_events), 1)
        self.assertEqual(rest_events[0].event_type, "REST")

        # In the second shift, driving should be 4.0h
        self.assertEqual(state.shift_driving, 4.0)

    def test_4_14h_shift_window(self):
        """Test 4: 14-hour consecutive shift window enforces 10h rest when window is exhausted."""
        start = datetime(2026, 9, 20, 6, 0, 0)
        tasks = [
            DriveTask(
                duration_hours=5.0,
                distance_miles=275.0,
                start_mile=0.0,
                end_mile=275.0,
                origin="Origin",
                destination="Stop 1",
            ),
            ServiceTask(
                duration_hours=4.0,
                route_mile=275.0,
                location="Stop 1",
                service_type=ServiceType.PICKUP,
                annotation="Extended loading delay",
            ),
            DriveTask(
                duration_hours=6.0,
                distance_miles=330.0,
                start_mile=275.0,
                end_mile=605.0,
                origin="Stop 1",
                destination="Destination",
            ),
        ]
        state = schedule_trip(tasks, start_time=start, initial_cycle_used=0.0)

        # 10h rest must be triggered when the 14h window expires
        rest_events = [e for e in state.events if e.status == DutyStatus.OFF_DUTY and e.duration_hours == 10.0]
        self.assertEqual(len(rest_events), 1)

        # In 1st shift: 5h drive + 4h service + 3h drive (hits 8h driving limit) + 0.5h break + 1.5h drive (hits 14h window limit)
        # In 2nd shift after 10h rest: remaining 1.5h drive is completed
        self.assertEqual(state.shift_driving, 1.5)

    def test_4b_service_exceeding_14h_window_triggers_rest(self):
        """Test 4b: Service task that would push driver beyond 14h window triggers 10h rest."""
        start = datetime(2026, 9, 20, 6, 0, 0)
        tasks = [
            DriveTask(
                duration_hours=10.0,
                distance_miles=550.0,
                start_mile=0.0,
                end_mile=550.0,
                origin="Origin",
                destination="Waypoint",
            ),
            # At this point: 10h drive + 0.5h break = 10.5h elapsed
            # A 4-hour service task (10.5 + 4 = 14.5h) exceeds the 14h window!
            ServiceTask(
                duration_hours=4.0,
                route_mile=550.0,
                location="Waypoint",
                service_type=ServiceType.PICKUP,
                annotation="Delayed pickup",
            ),
        ]
        state = schedule_trip(tasks, start_time=start, initial_cycle_used=0.0)

        # Must trigger 10h rest before the 4-hour service
        rest_events = [e for e in state.events if e.status == DutyStatus.OFF_DUTY and e.duration_hours == 10.0]
        self.assertEqual(len(rest_events), 1)

        # After the rest, service task runs in fresh shift
        service_events = [e for e in state.events if e.status == DutyStatus.ON_DUTY_NOT_DRIVING]
        self.assertEqual(len(service_events), 1)
        self.assertEqual(service_events[0].duration_hours, 4.0)

    def test_14_hour_shift_window_after_break_and_remaining_drive(self):
        """The 8-hour driving threshold takes precedence, then the remaining drive reaches the 14-hour window and triggers a 10-hour rest."""
        scheduler = HOSScheduler()

        tasks = [
            ServiceTask(
                duration_hours=1.0,
                route_mile=0.0,
                location="Pickup",
                service_type=ServiceType.PICKUP,
            ),
            DriveTask(
                duration_hours=13.0,
                distance_miles=715.0,
                start_mile=0.0,
                end_mile=715.0,
                destination="Destination",
            ),
        ]

        state = scheduler.schedule(tasks)

        break_events = [
            event
            for event in state.events
            if event.status == DutyStatus.OFF_DUTY and event.duration_hours == 0.5
        ]
        self.assertEqual(len(break_events), 1)

        rest_events = [
            event
            for event in state.events
            if event.status == DutyStatus.OFF_DUTY
            and "10-hour" in event.annotation.lower()
        ]

        self.assertEqual(len(rest_events), 1)

        break_event = break_events[0]
        rest_event = rest_events[0]
        first_shift_start = state.events[0].start_time

        elapsed_before_break = (
            break_event.start_time - first_shift_start
        ).total_seconds() / 3600.0
        elapsed_before_rest = (
            rest_event.start_time - first_shift_start
        ).total_seconds() / 3600.0

        self.assertEqual(elapsed_before_break, 9.0)
        self.assertEqual(elapsed_before_rest, 12.5)
        self.assertEqual(rest_event.duration_hours, 10.0)

        event_types = [event.event_type for event in state.events]
        self.assertEqual(event_types, ["PICKUP", "DRIVE", "BREAK", "DRIVE", "REST", "DRIVE"])

    def test_5_70h_cycle_to_34h_restart(self):
        """Test 5: 70-hour / 8-day cycle limit triggers 34-hour off-duty restart."""
        start = datetime(2026, 9, 20, 6, 0, 0)
        tasks = [
            DriveTask(
                duration_hours=5.0,
                distance_miles=275.0,
                start_mile=0.0,
                end_mile=275.0,
                origin="City A",
                destination="City B",
            )
        ]
        # Driver has 69 hours already logged in current 70h cycle
        state = schedule_trip(tasks, start_time=start, initial_cycle_used=69.0)

        # Should drive 1.0h, take 34.0h restart, then drive remaining 4.0h
        restart_events = [e for e in state.events if e.duration_hours == 34.0]
        self.assertEqual(len(restart_events), 1)
        self.assertEqual(restart_events[0].event_type, "RESTART")

        # Cycle used resets and logs only the post-restart 4.0h
        self.assertEqual(state.cycle_used, 4.0)
        self.assertEqual(state.shift_driving, 4.0)

    def test_5b_60h_cycle_uses_remaining_hours_then_restarts(self):
        """A 60-hour cycle leaves 10 hours before the 34-hour restart is required."""
        tasks = [
            DriveTask(
                duration_hours=15.0,
                distance_miles=825.0,
                start_mile=0.0,
                end_mile=825.0,
                origin="City A",
                destination="City B",
            )
        ]

        state = schedule_trip(tasks, start_time=datetime(2026, 9, 20, 6, 0, 0), initial_cycle_used=60.0)
        driving_events = [event for event in state.events if event.status == DutyStatus.DRIVING]
        restart_events = [event for event in state.events if event.event_type == "RESTART"]

        self.assertEqual([event.duration_hours for event in driving_events], [8.0, 2.0, 5.0])
        self.assertEqual(len(restart_events), 1)
        self.assertEqual(state.cycle_used, 5.0)
        self.assertEqual(state.shift_driving, 5.0)

    def test_6_pickup_dropoff(self):
        """Test 6: Trip with origin pickup and destination dropoff service tasks."""
        start = datetime(2026, 9, 20, 8, 0, 0)
        tasks = [
            ServiceTask(
                duration_hours=1.0,
                route_mile=0.0,
                location="Shipper A",
                service_type=ServiceType.PICKUP,
            ),
            DriveTask(
                duration_hours=6.0,
                distance_miles=300.0,
                start_mile=0.0,
                end_mile=300.0,
                origin="Shipper A",
                destination="Receiver B",
            ),
            ServiceTask(
                duration_hours=1.0,
                route_mile=300.0,
                location="Receiver B",
                service_type=ServiceType.DROPOFF,
            ),
        ]
        state = schedule_trip(tasks, start_time=start, initial_cycle_used=0.0)

        self.assertEqual(len(state.events), 3)
        self.assertEqual(state.events[0].status, DutyStatus.ON_DUTY_NOT_DRIVING)
        self.assertEqual(state.events[0].event_type, "PICKUP")
        self.assertEqual(state.events[1].status, DutyStatus.DRIVING)
        self.assertEqual(state.events[2].status, DutyStatus.ON_DUTY_NOT_DRIVING)
        self.assertEqual(state.events[2].event_type, "DROPOFF")

        # Total on-duty/driving = 8.0h
        self.assertEqual(state.cycle_used, 8.0)
        self.assertEqual(state.current_time, start + timedelta(hours=8))

    def test_7_fuel_stops(self):
        """Test 7: Fuel stops automatically injected at 1,000-mile intervals."""
        tasks = build_tasks(
            origin="Seattle, WA",
            destination="Miami, FL",
            distance_miles=2500.0,
            duration_hours=50.0,
        )

        fuel_tasks = [t for t in tasks if isinstance(t, ServiceTask) and t.service_type == ServiceType.FUEL]
        self.assertEqual(len(fuel_tasks), 2)
        self.assertEqual(fuel_tasks[0].route_mile, 1000.0)
        self.assertEqual(fuel_tasks[1].route_mile, 2000.0)

        # First task is Pickup, last is Dropoff
        self.assertEqual(tasks[0].service_type, ServiceType.PICKUP)
        self.assertEqual(tasks[-1].service_type, ServiceType.DROPOFF)

    def test_8_long_multi_day_trip(self):
        """Test 8: Full 2,200-mile multi-day cross-country trip with all HOS constraints."""
        tasks = build_tasks(
            origin="Los Angeles, CA",
            destination="Chicago, IL",
            distance_miles=2200.0,
            duration_hours=40.0,
        )

        start = datetime(2026, 9, 20, 6, 0, 0)
        state = schedule_trip(tasks, start_time=start, initial_cycle_used=0.0)

        # Verifies mile and driving time conservation
        self.assertAlmostEqual(state.current_mile, 2200.0, places=1)
        total_driving = sum(e.duration_hours for e in state.events if e.status == DutyStatus.DRIVING)
        self.assertAlmostEqual(total_driving, 40.0, places=1)

        # Verifies physical stops
        fuel_stops = [s for s in state.stops if s.stop_type == ServiceType.FUEL]
        self.assertEqual(len(fuel_stops), 2)
        rest_stops = [s for s in state.stops if s.stop_type == ServiceType.REST]
        self.assertTrue(len(rest_stops) >= 3)

        fuel_events = [event for event in state.events if event.event_type == "FUEL"]
        self.assertEqual([event.route_mile for event in fuel_events], [1000.0, 2000.0])

        daily_logs = generate_daily_logs(state.events)
        fuel_remarks = [remark for log in daily_logs for remark in log.remarks if remark.status == DutyStatus.ON_DUTY_NOT_DRIVING and "Fuel" in remark.annotation]
        self.assertEqual([remark.route_mile for remark in fuel_remarks], [1000.0, 2000.0])

    def test_route_result_builds_drive_pickup_drive_dropoff_tasks(self):
        """RouteResult segments should convert cleanly into the scheduler's ordered task stream."""
        route = RouteResult(
            current_location=GeocodedLocation(name="Current City", latitude=0.0, longitude=0.0),
            pickup_location=GeocodedLocation(name="Pickup City", latitude=1.0, longitude=1.0),
            dropoff_location=GeocodedLocation(name="Dropoff City", latitude=3.0, longitude=3.0),
            total_distance_miles=200.0,
            total_duration_hours=4.0,
            geometry=[(0.0, 0.0), (1.0, 1.0), (3.0, 3.0)],
            segments=[
                RouteSegment(
                    origin="Current City",
                    destination="Pickup City",
                    origin_coordinates=(0.0, 0.0),
                    destination_coordinates=(1.0, 1.0),
                    distance_miles=100.0,
                    duration_hours=2.0,
                    geometry=[(0.0, 0.0), (1.0, 1.0)],
                ),
                RouteSegment(
                    origin="Pickup City",
                    destination="Dropoff City",
                    origin_coordinates=(1.0, 1.0),
                    destination_coordinates=(3.0, 3.0),
                    distance_miles=100.0,
                    duration_hours=2.0,
                    geometry=[(1.0, 1.0), (3.0, 3.0)],
                ),
            ],
        )

        tasks = build_tasks_from_route(route)

        self.assertEqual(len(tasks), 4)
        self.assertIsInstance(tasks[0], DriveTask)
        self.assertEqual(tasks[0].origin, "Current City")
        self.assertEqual(tasks[0].destination, "Pickup City")
        self.assertEqual(tasks[0].distance_miles, 100.0)
        self.assertAlmostEqual(tasks[0].duration_hours, 100.0 / 55.0)

        self.assertIsInstance(tasks[1], ServiceTask)
        self.assertEqual(tasks[1].service_type, ServiceType.PICKUP)
        self.assertEqual(tasks[1].route_mile, 100.0)

        self.assertIsInstance(tasks[2], DriveTask)
        self.assertEqual(tasks[2].origin, "Pickup City")
        self.assertEqual(tasks[2].destination, "Dropoff City")
        self.assertEqual(tasks[2].start_mile, 100.0)
        self.assertEqual(tasks[2].end_mile, 200.0)
        self.assertAlmostEqual(tasks[2].duration_hours, 100.0 / 55.0)

        self.assertIsInstance(tasks[3], ServiceTask)
        self.assertEqual(tasks[3].service_type, ServiceType.DROPOFF)
        self.assertEqual(tasks[3].route_mile, 200.0)

    def test_route_result_inserts_fuel_at_every_1000_mile_boundary(self):
        """Fuel stops must span both route segments and repeat beyond 2,000 miles."""
        route = RouteResult(
            current_location=GeocodedLocation(name="Current City", latitude=0.0, longitude=0.0),
            pickup_location=GeocodedLocation(name="Pickup City", latitude=1.0, longitude=1.0),
            dropoff_location=GeocodedLocation(name="Dropoff City", latitude=3.0, longitude=3.0),
            total_distance_miles=2300.0,
            total_duration_hours=42.0,
            geometry=[],
            segments=[
                RouteSegment(
                    origin="Current City",
                    destination="Pickup City",
                    origin_coordinates=(0.0, 0.0),
                    destination_coordinates=(1.0, 1.0),
                    distance_miles=1200.0,
                    duration_hours=22.0,
                    geometry=[],
                ),
                RouteSegment(
                    origin="Pickup City",
                    destination="Dropoff City",
                    origin_coordinates=(1.0, 1.0),
                    destination_coordinates=(3.0, 3.0),
                    distance_miles=1100.0,
                    duration_hours=20.0,
                    geometry=[],
                ),
            ],
        )

        tasks = build_tasks_from_route(route)
        fuel_tasks = [task for task in tasks if isinstance(task, ServiceTask) and task.service_type == ServiceType.FUEL]

        self.assertEqual([task.route_mile for task in fuel_tasks], [1000.0, 2000.0])
        self.assertAlmostEqual(
            sum(task.distance_miles for task in tasks if isinstance(task, DriveTask)),
            2300.0,
        )


if __name__ == "__main__":
    unittest.main()
