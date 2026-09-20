"""
Unit tests for 24-hour Daily Log generation, midnight event clipping, and compliance summaries.
"""
from datetime import date, datetime, timedelta
import unittest

from planner.logs import DailyLog, DailyLogRemark, generate_daily_logs
from planner.scheduler import HOSScheduler, schedule_trip
from planner.task_builder import build_tasks
from planner.tasks import DriveTask, DutyEvent, DutyStatus, ServiceTask, ServiceType


class TestDailyLogGeneration(unittest.TestCase):
    """Step 14: Unit tests for Daily Logs across single-day, 36-hour, and multi-day trips."""

    def test_single_day_trip_log_padding(self):
        # Trip starts at 08:00 AM on Day 1: Pickup 1h -> Drive 6h -> Dropoff 1h -> Ends at 16:00
        start = datetime(2026, 9, 20, 8, 0, 0)
        tasks = [
            ServiceTask(
                duration_hours=1.0,
                route_mile=0.0,
                location="Origin Warehouse",
                service_type=ServiceType.PICKUP,
            ),
            DriveTask(
                duration_hours=6.0,
                distance_miles=330.0,
                start_mile=0.0,
                end_mile=330.0,
                origin="Origin Warehouse",
                destination="Destination Depot",
            ),
            ServiceTask(
                duration_hours=1.0,
                route_mile=330.0,
                location="Destination Depot",
                service_type=ServiceType.DROPOFF,
            ),
        ]
        state = schedule_trip(tasks, start_time=start)
        daily_logs = generate_daily_logs(state.events, pad_24h=True)

        self.assertEqual(len(daily_logs), 1)
        log_day1 = daily_logs[0]

        self.assertEqual(log_day1.day_number, 1)
        self.assertEqual(log_day1.date, date(2026, 9, 20))
        self.assertEqual(log_day1.total_hours, 24.0)
        self.assertEqual(log_day1.total_minutes, 1440.0)

        # Pre-trip (00:00 to 08:00 = 8h off duty) + Post-trip (16:00 to 24:00 = 8h off duty) = 16h off duty
        self.assertEqual(log_day1.off_duty_hours, 16.0)
        self.assertEqual(log_day1.driving_hours, 6.0)
        self.assertEqual(log_day1.on_duty_not_driving_hours, 2.0)
        self.assertEqual(log_day1.sleeper_berth_hours, 0.0)

    def test_36_hour_trip_midnight_splitting(self):
        # Trip starts at 14:00 (2:00 PM) on Sept 20
        # Pickup 1h (14:00-15:00)
        # Drive 8h (15:00-23:00)
        # 10h rest (23:00 Sept 20 to 09:00 Sept 21) -> Spans midnight!
        # Drive 4h (09:00-13:00 Sept 21)
        # Dropoff 1h (13:00-14:00 Sept 21)
        start = datetime(2026, 9, 20, 14, 0, 0)
        tasks = [
            ServiceTask(
                duration_hours=1.0,
                route_mile=0.0,
                location="Shipper A",
                service_type=ServiceType.PICKUP,
            ),
            DriveTask(
                duration_hours=8.0,
                distance_miles=440.0,
                start_mile=0.0,
                end_mile=440.0,
                origin="Shipper A",
                destination="Waypoint B",
            ),
            ServiceTask(
                duration_hours=10.0,
                route_mile=440.0,
                location="Waypoint B",
                service_type=ServiceType.REST,
            ),
            DriveTask(
                duration_hours=4.0,
                distance_miles=220.0,
                start_mile=440.0,
                end_mile=660.0,
                origin="Waypoint B",
                destination="Receiver C",
            ),
            ServiceTask(
                duration_hours=1.0,
                route_mile=660.0,
                location="Receiver C",
                service_type=ServiceType.DROPOFF,
            ),
        ]
        state = schedule_trip(tasks, start_time=start)
        daily_logs = generate_daily_logs(state.events, pad_24h=True)

        # Spans across 2 calendar days (Sept 20 & Sept 21)
        self.assertEqual(len(daily_logs), 2)

        # Day 1 checks
        log1 = daily_logs[0]
        self.assertEqual(log1.date, date(2026, 9, 20))
        self.assertEqual(log1.total_hours, 24.0)
        self.assertEqual(log1.driving_hours, 8.0)
        self.assertEqual(log1.on_duty_not_driving_hours, 1.0)
        # Day 1 off-duty: 00:00 to 14:00 (14h) + 23:00 to 24:00 (1h rest before midnight) = 15h
        self.assertEqual(log1.off_duty_hours, 15.0)

        # Day 2 checks
        log2 = daily_logs[1]
        self.assertEqual(log2.date, date(2026, 9, 21))
        self.assertEqual(log2.total_hours, 24.0)
        self.assertEqual(log2.driving_hours, 4.0)
        self.assertEqual(log2.on_duty_not_driving_hours, 1.0)
        # Day 2 off-duty: 00:00 to 09:00 (9h rest after midnight) + 14:00 to 24:00 (10h post-trip) = 19h
        self.assertEqual(log2.off_duty_hours, 19.0)

        # Total driving across both days = 8h + 4h = 12h
        total_driving = log1.driving_hours + log2.driving_hours
        self.assertEqual(total_driving, 12.0)

    def test_multi_day_cross_country_trip(self):
        # Full 2,400-mile trip across 4+ days
        tasks = build_tasks(
            origin="Atlanta, GA",
            destination="San Francisco, CA",
            distance_miles=2400.0,
            duration_hours=44.0, # ~55 mph
        )

        start = datetime(2026, 9, 20, 6, 0, 0)
        state = schedule_trip(tasks, start_time=start)
        daily_logs = generate_daily_logs(state.events, pad_24h=True)

        self.assertTrue(len(daily_logs) >= 3)

        # Every day must total exactly 24.0 hours (1,440 minutes)
        total_driving_logged = 0.0
        for log in daily_logs:
            self.assertEqual(log.total_hours, 24.0)
            self.assertEqual(log.total_minutes, 1440.0)
            self.assertTrue(len(log.events) > 0)
            total_driving_logged += log.driving_hours

            # Verify events within the log are strictly within the day's boundaries
            for evt in log.events:
                self.assertEqual(evt.start_time.date(), log.date)
                # end_time can be up to 00:00 next day
                self.assertTrue(
                    evt.end_time.date() == log.date
                    or (
                        evt.end_time.date() == log.date + timedelta(days=1)
                        and evt.end_time.time() == datetime.min.time()
                    )
                )

        # Sum of driving hours on all log sheets must equal the total scheduled driving time (~44h)
        self.assertAlmostEqual(total_driving_logged, 44.0, places=1)


if __name__ == "__main__":
    unittest.main()
