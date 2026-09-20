"""
Unit tests for the HOS Scheduler Engine and Task Builder.

Covers:
- Step 1-4: Basic data structures, constants, and state
- Step 5-6: Basic driving and service scheduling
- Step 7: 11-hour driving limit per shift (10-hour rest insertion)
- Step 8: 14-hour consecutive shift window limit
- Step 9: 30-minute rest break after 8 cumulative driving hours
- Step 10: 70-hour / 8-day cycle limit
- Step 11: 34-hour off-duty cycle restart
- Step 12: Fuel stop injection and multi-day trip scheduling
"""
from datetime import datetime, timedelta
import unittest

from planner.scheduler import (
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
    HOSScheduler,
    SchedulerState,
    schedule_trip,
)
from planner.task_builder import build_tasks
from planner.tasks import (
    DriveTask,
    DutyEvent,
    DutyStatus,
    Location,
    ServiceTask,
    ServiceType,
    Stop,
)


class TestHOSDataStructuresAndConstants(unittest.TestCase):
    """Step 1 - 4: Data structures, constants, and state tracking."""

    def test_hos_constants(self):
        self.assertEqual(MAX_DRIVING_HOURS, 11.0)
        self.assertEqual(MAX_SHIFT_WINDOW_HOURS, 14.0)
        self.assertEqual(BREAK_AFTER_DRIVING_HOURS, 8.0)
        self.assertEqual(BREAK_DURATION_HOURS, 0.5)
        self.assertEqual(REST_DURATION_HOURS, 10.0)
        self.assertEqual(CYCLE_LIMIT_HOURS, 70.0)
        self.assertEqual(RESTART_DURATION_HOURS, 34.0)
        self.assertEqual(CYCLE_RESTART_DURATION_HOURS, 34.0)
        self.assertEqual(PICKUP_DURATION_HOURS, 1.0)
        self.assertEqual(DROPOFF_DURATION_HOURS, 1.0)
        self.assertEqual(FUEL_INTERVAL_MILES, 1000.0)
        self.assertEqual(FUEL_DURATION_HOURS, 0.5)
        self.assertEqual(AVERAGE_DRIVE_SPEED_MPH, 55.0)

    def test_drive_and_service_tasks(self):
        drive = DriveTask(
            duration_hours=4.0,
            distance_miles=220.0,
            start_mile=0.0,
            end_mile=220.0,
            destination="Austin, TX",
            origin="Dallas, TX",
        )
        self.assertEqual(drive.distance_miles, 220.0)
        self.assertEqual(drive.duration_hours, 4.0)

        service = ServiceTask(
            duration_hours=1.0,
            route_mile=0.0,
            location="Dallas Shipper",
            service_type=ServiceType.PICKUP,
            annotation="Loading freight",
        )
        self.assertEqual(service.service_type, ServiceType.PICKUP)


class TestBasicScheduling(unittest.TestCase):
    """Step 5 & 6: Basic driving and service scheduling within single shift limits."""

    def test_simple_driving_under_limits(self):
        # 300 miles, 6 hours driving, start at 08:00
        start = datetime(2026, 9, 20, 8, 0, 0)
        tasks = [
            DriveTask(
                duration_hours=6.0,
                distance_miles=300.0,
                start_mile=0.0,
                end_mile=300.0,
                origin="City A",
                destination="City B",
            )
        ]
        scheduler = HOSScheduler(start_time=start, initial_cycle_used=0.0)
        state = scheduler.schedule(tasks)

        self.assertEqual(len(state.events), 1)
        event = state.events[0]
        self.assertEqual(event.status, DutyStatus.DRIVING)
        self.assertEqual(event.duration_hours, 6.0)
        self.assertEqual(event.start_time, start)
        self.assertEqual(event.end_time, start + timedelta(hours=6))
        self.assertEqual(state.shift_driving, 6.0)
        self.assertEqual(state.cycle_used, 6.0)
        self.assertEqual(state.current_mile, 300.0)

    def test_trip_with_pickup_and_dropoff(self):
        # Pickup (1h) -> Drive 6h -> Dropoff (1h)
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

        # 3 events: Pickup (ON_DUTY), Drive (DRIVING), Dropoff (ON_DUTY)
        self.assertEqual(len(state.events), 3)
        self.assertEqual(state.events[0].status, DutyStatus.ON_DUTY_NOT_DRIVING)
        self.assertEqual(state.events[1].status, DutyStatus.DRIVING)
        self.assertEqual(state.events[2].status, DutyStatus.ON_DUTY_NOT_DRIVING)

        # Total on-duty/driving = 1h + 6h + 1h = 8h
        self.assertEqual(state.cycle_used, 8.0)
        self.assertEqual(state.shift_driving, 6.0)
        self.assertEqual(state.current_time, start + timedelta(hours=8))


class Test11HourDrivingLimit(unittest.TestCase):
    """Step 7: 11-hour driving limit per shift forces 10-hour rest."""

    def test_15_hour_drive_splits_with_10h_rest(self):
        # 15 hours continuous driving task
        # Must split into: 8h drive -> 0.5h break -> 3h drive (total 11h driving) -> 10h rest -> 4h drive
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

        # Filter driving events and rest events
        driving_events = [e for e in state.events if e.status == DutyStatus.DRIVING]
        rest_events = [e for e in state.events if e.status == DutyStatus.OFF_DUTY and e.duration_hours == 10.0]

        total_driving_hours = sum(e.duration_hours for e in driving_events)
        self.assertEqual(total_driving_hours, 15.0)

        # Must have at least one 10-hour rest
        self.assertEqual(len(rest_events), 1)
        self.assertEqual(rest_events[0].duration_hours, 10.0)

        # In second shift, driving should be 4.0h
        self.assertEqual(state.shift_driving, 4.0)


class Test14HourShiftWindow(unittest.TestCase):
    """Step 8: 14-hour consecutive driving window independent of driving hours."""

    def test_on_duty_time_eats_shift_window(self):
        # Driver starts shift at 06:00
        # 5h driving + 4h on-duty service + 6h driving requested
        # Shift elapsed before 2nd drive = 5h + 4h = 9h.
        # Remaining shift window = 14h - 9h = 5h!
        # Even though driver has only 5h driving (6h remaining under 11h limit),
        # the 14h window caps the 2nd drive at 5h, forcing a 10h rest before the remaining 1h!
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

        rest_events = [e for e in state.events if e.status == DutyStatus.OFF_DUTY and e.duration_hours == 10.0]
        self.assertEqual(len(rest_events), 1)

        # In 1st shift: 5h drive + 4h service + 3h drive (hits 8h driving) + 0.5h break + 1.5h drive (hits 14h window)
        # Remaining drive in 2nd shift after 10h rest: 6.0 - (3.0 + 1.5) = 1.5h
        self.assertEqual(state.shift_driving, 1.5)


class Test30MinuteBreakRule(unittest.TestCase):
    """Step 9: 30-minute break after 8 cumulative driving hours."""

    def test_10_hour_drive_inserts_30_min_break(self):
        # 10 hours driving within 11h limit -> triggers 30-min break at exactly 8.0h driving
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

        # Events expected: Drive 8h -> Break 0.5h -> Drive 2h
        self.assertEqual(len(state.events), 3)
        self.assertEqual(state.events[0].status, DutyStatus.DRIVING)
        self.assertEqual(state.events[0].duration_hours, 8.0)

        self.assertEqual(state.events[1].status, DutyStatus.OFF_DUTY)
        self.assertEqual(state.events[1].duration_hours, 0.5)
        self.assertEqual(state.events[1].event_type, "BREAK")

        self.assertEqual(state.events[2].status, DutyStatus.DRIVING)
        self.assertEqual(state.events[2].duration_hours, 2.0)

        # Total shift driving = 10.0h, shift elapsed = 10.5h
        self.assertEqual(state.shift_driving, 10.0)
        self.assertEqual(state.driving_since_break, 2.0)


class Test70HourCycleAnd34HourRestart(unittest.TestCase):
    """Step 10 & 11: 70-hour cycle limit and 34-hour restart."""

    def test_cycle_exhaustion_triggers_34h_restart(self):
        # Driver starts with 69.0 hours used in current 70h cycle
        # Driver requests 5 hours of driving
        # Expected:
        # 1. Drive 1.0h (cycle hits 70.0h)
        # 2. 34.0h cycle restart (cycle resets to 0.0h)
        # 3. Drive remaining 4.0h
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
        state = schedule_trip(tasks, start_time=start, initial_cycle_used=69.0)

        restart_events = [e for e in state.events if e.duration_hours == 34.0]
        self.assertEqual(len(restart_events), 1)
        self.assertEqual(restart_events[0].event_type, "RESTART")

        # After restart, the remaining 4 hours are driven
        self.assertEqual(state.cycle_used, 4.0)
        self.assertEqual(state.shift_driving, 4.0)


class TestFuelStopsAndTaskBuilder(unittest.TestCase):
    """Step 12: Fuel stops injected at 1,000-mile intervals and full multi-day planning."""

    def test_task_builder_fuel_stops_injection(self):
        # 2,500 mile trip -> should have fuel stops at 1,000 and 2,000 miles
        tasks = build_tasks(
            origin="Seattle, WA",
            destination="Miami, FL",
            distance_miles=2500.0,
            duration_hours=50.0, # 50 mph
        )

        fuel_tasks = [t for t in tasks if isinstance(t, ServiceTask) and t.service_type == ServiceType.FUEL]
        self.assertEqual(len(fuel_tasks), 2)
        self.assertEqual(fuel_tasks[0].route_mile, 1000.0)
        self.assertEqual(fuel_tasks[1].route_mile, 2000.0)

        # First task must be PICKUP, last task must be DROPOFF
        self.assertEqual(tasks[0].service_type, ServiceType.PICKUP)
        self.assertEqual(tasks[-1].service_type, ServiceType.DROPOFF)

    def test_full_cross_country_trip_scheduling(self):
        # 2,200 mile cross-country run
        tasks = build_tasks(
            origin="Los Angeles, CA",
            destination="Chicago, IL",
            distance_miles=2200.0,
            duration_hours=40.0, # 55 mph
        )

        start = datetime(2026, 9, 20, 6, 0, 0)
        state = schedule_trip(tasks, start_time=start, initial_cycle_used=0.0)

        # Check that miles match
        self.assertAlmostEqual(state.current_mile, 2200.0, places=1)

        # Check total driving time matches exactly 40.0 hours
        driving_time = sum(e.duration_hours for e in state.events if e.status == DutyStatus.DRIVING)
        self.assertAlmostEqual(driving_time, 40.0, places=1)

        # Verify fuel stops in stops list
        fuel_stops = [s for s in state.stops if s.stop_type == ServiceType.FUEL]
        self.assertEqual(len(fuel_stops), 2)

        # Verify pickup and dropoff stops
        pickup_stops = [s for s in state.stops if s.stop_type == ServiceType.PICKUP]
        dropoff_stops = [s for s in state.stops if s.stop_type == ServiceType.DROPOFF]
        self.assertEqual(len(pickup_stops), 1)
        self.assertEqual(len(dropoff_stops), 1)

        # Verify rest stops were scheduled
        rest_stops = [s for s in state.stops if s.stop_type == ServiceType.REST]
        self.assertTrue(len(rest_stops) >= 3) # ~40h driving requires multiple 10h rests


if __name__ == "__main__":
    unittest.main()
