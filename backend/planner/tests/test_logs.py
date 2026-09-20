"""
Unit tests for 24-hour Daily Log generation, midnight event clipping,
event merging, and compliance summaries.
"""
from datetime import date, datetime, timedelta
import unittest

from planner.logs import DailyLog, DailyLogRemark, _merge_adjacent_events, generate_daily_logs
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


class TestEventMerging(unittest.TestCase):
    """Unit tests for _merge_adjacent_events: the event-stream compactor."""

    def _make_event(
        self,
        start_h: float,
        end_h: float,
        status: DutyStatus,
        route_mile: float = 0.0,
        end_route_mile=None,
        annotation: str = "test",
    ) -> DutyEvent:
        """Helper: build a DutyEvent anchored at 2026-09-20 00:00 + offset hours."""
        base = datetime(2026, 9, 20, 0, 0, 0)
        start = base + timedelta(hours=start_h)
        end = base + timedelta(hours=end_h)
        return DutyEvent(
            start_time=start,
            end_time=end,
            duration_hours=end_h - start_h,
            status=status,
            annotation=annotation,
            route_mile=route_mile,
            end_route_mile=end_route_mile,
            event_type=status.value,
        )

    def test_merge_two_adjacent_same_status(self):
        """Two touching OFF_DUTY events → one merged event."""
        events = [
            self._make_event(8.0, 9.0, DutyStatus.OFF_DUTY, annotation="Off Duty"),
            self._make_event(9.0, 10.0, DutyStatus.OFF_DUTY, annotation="Off Duty"),
        ]
        merged = _merge_adjacent_events(events)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].status, DutyStatus.OFF_DUTY)
        self.assertEqual(merged[0].duration_hours, 2.0)
        self.assertEqual(merged[0].start_time, events[0].start_time)
        self.assertEqual(merged[0].end_time, events[1].end_time)

    def test_no_merge_different_status(self):
        """Touching events with different statuses must NOT be merged."""
        events = [
            self._make_event(8.0, 9.0, DutyStatus.OFF_DUTY),
            self._make_event(9.0, 10.0, DutyStatus.DRIVING,
                             route_mile=0.0, end_route_mile=55.0),
        ]
        merged = _merge_adjacent_events(events)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].status, DutyStatus.OFF_DUTY)
        self.assertEqual(merged[1].status, DutyStatus.DRIVING)

    def test_no_merge_non_touching(self):
        """Events with a gap between them must NOT be merged even if same status."""
        events = [
            self._make_event(8.0, 9.0, DutyStatus.OFF_DUTY),
            # gap: 09:00 → 09:30
            self._make_event(9.5, 10.0, DutyStatus.OFF_DUTY),
        ]
        merged = _merge_adjacent_events(events)

        self.assertEqual(len(merged), 2)

    def test_merge_driving_carries_end_route_mile(self):
        """Three consecutive DRIVING chunks → one event with correct start/end mile."""
        events = [
            self._make_event(8.0, 10.0, DutyStatus.DRIVING,
                             route_mile=0.0,   end_route_mile=110.0),
            self._make_event(10.0, 12.0, DutyStatus.DRIVING,
                             route_mile=110.0, end_route_mile=220.0),
            self._make_event(12.0, 14.0, DutyStatus.DRIVING,
                             route_mile=220.0, end_route_mile=330.0),
        ]
        merged = _merge_adjacent_events(events)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].route_mile, 0.0)      # from first chunk
        self.assertEqual(merged[0].end_route_mile, 330.0) # from last chunk
        self.assertEqual(merged[0].duration_hours, 6.0)

    def test_merge_produces_correct_event_count_for_day(self):
        """
        Integration: a single-day trip whose daily log has exactly 3 merged
        events (pre-OFF_DUTY, DRIVING, post-OFF_DUTY) after merging.
        """
        start = datetime(2026, 9, 20, 10, 0, 0)
        tasks = [
            DriveTask(
                duration_hours=4.0,
                distance_miles=220.0,
                start_mile=0.0,
                end_mile=220.0,
                origin="City A",
                destination="City B",
            )
        ]
        state = schedule_trip(tasks, start_time=start)
        daily_logs = generate_daily_logs(state.events, pad_24h=True)

        self.assertEqual(len(daily_logs), 1)
        log = daily_logs[0]

        # Expect exactly 3 events: pre-OFF_DUTY | DRIVING | post-OFF_DUTY
        self.assertEqual(len(log.events), 3)
        self.assertEqual(log.events[0].status, DutyStatus.OFF_DUTY)   # 00:00-10:00
        self.assertEqual(log.events[1].status, DutyStatus.DRIVING)    # 10:00-14:00
        self.assertEqual(log.events[2].status, DutyStatus.OFF_DUTY)   # 14:00-24:00

        # Merged OFF_DUTY blocks have correct durations
        self.assertEqual(log.events[0].duration_hours, 10.0)
        self.assertEqual(log.events[1].duration_hours, 4.0)
        self.assertEqual(log.events[2].duration_hours, 10.0)
        self.assertEqual(log.total_hours, 24.0)


class TestDailyLogMileageAndEdgeCases(unittest.TestCase):
    """
    Five targeted regression tests that protect the new end_route_mile data model
    and cover previously untested branches of generate_daily_logs.
    """

    # ── Test 1: end-to-end mileage conservation ──────────────────────────────

    def test_total_miles_conserved_across_all_days(self):
        """
        End-to-end guarantee: sum of DailyLog.miles_driven across every day
        equals the total distance scheduled by the task builder.

        Chain exercised:
            DriveTask → Scheduler → DutyEvent → midnight split → merge → DailyLog
        """
        tasks = build_tasks(
            origin="Atlanta, GA",
            destination="San Francisco, CA",
            distance_miles=2400.0,
            duration_hours=44.0,  # ~55 mph
        )
        start = datetime(2026, 9, 20, 6, 0, 0)
        state = schedule_trip(tasks, start_time=start)
        daily_logs = generate_daily_logs(state.events, pad_24h=True)

        total_logged_miles = sum(log.miles_driven for log in daily_logs)
        self.assertAlmostEqual(total_logged_miles, 2400.0, places=1)

    # ── Test 2: proportional mileage split at midnight ────────────────────────

    def test_midnight_driving_mileage_split_proportionally(self):
        """
        A single DRIVING event that crosses midnight must have its mileage
        split proportionally between the two calendar days.

        Scenario:
            23:00 → 03:00  (4 hours total)
            route_mile 100 → 320  (220 miles total)

        Expected split:
            Day 1  23:00 → 00:00  (1 h = 25 % of 4 h)  →  55 miles  (100 → 155)
            Day 2  00:00 → 03:00  (3 h = 75 % of 4 h)  → 165 miles  (155 → 320)
        """
        base = datetime(2026, 9, 20, 23, 0, 0)
        events = [
            DutyEvent(
                start_time=base,
                end_time=base + timedelta(hours=4),
                duration_hours=4.0,
                status=DutyStatus.DRIVING,
                annotation="Night run",
                route_mile=100.0,
                end_route_mile=320.0,
                location_name="Highway",
                event_type="DRIVE",
            )
        ]
        daily_logs = generate_daily_logs(events, pad_24h=False)

        self.assertEqual(len(daily_logs), 2)
        day1 = daily_logs[0]
        day2 = daily_logs[1]

        self.assertEqual(day1.date, date(2026, 9, 20))
        self.assertEqual(day2.date, date(2026, 9, 21))

        # Proportional split: 1/4 of 220 miles = 55.0, 3/4 = 165.0
        self.assertAlmostEqual(day1.miles_driven, 55.0, places=1)
        self.assertAlmostEqual(day2.miles_driven, 165.0, places=1)

        # Combined mileage must equal the original 220 miles
        self.assertAlmostEqual(day1.miles_driven + day2.miles_driven, 220.0, places=1)

    # ── Test 3: pad_24h=False ─────────────────────────────────────────────────

    def test_pad_24h_false_does_not_manufacture_off_duty(self):
        """
        When pad_24h=False, generate_daily_logs must NOT add pre- or post-trip
        OFF_DUTY padding.  The day sheet should only contain the actual events.
        """
        start = datetime(2026, 9, 20, 9, 0, 0)
        tasks = [
            DriveTask(
                duration_hours=4.0,
                distance_miles=220.0,
                start_mile=0.0,
                end_mile=220.0,
                origin="City A",
                destination="City B",
            )
        ]
        state = schedule_trip(tasks, start_time=start)
        daily_logs = generate_daily_logs(state.events, pad_24h=False)

        self.assertEqual(len(daily_logs), 1)
        log = daily_logs[0]

        # Only the single DRIVING event; no manufactured OFF_DUTY blocks
        self.assertEqual(log.driving_hours, 4.0)
        self.assertEqual(log.off_duty_hours, 0.0)
        self.assertEqual(log.total_hours, 4.0)

    # ── Test 4: sleeper berth ─────────────────────────────────────────────────

    def test_sleeper_berth_hours_counted_correctly(self):
        """
        DailyLog.sleeper_berth_hours must accumulate SLEEPER_BERTH events.
        Verifies the field is wired correctly and not silently ignored.
        """
        base = datetime(2026, 9, 20, 22, 0, 0)
        events = [
            DutyEvent(
                start_time=base,
                end_time=base + timedelta(hours=8),
                duration_hours=8.0,
                status=DutyStatus.SLEEPER_BERTH,
                annotation="Sleeper berth rest",
                route_mile=500.0,
                end_route_mile=None,
                location_name="Truck Stop",
                event_type="SLEEPER_BERTH",
            )
        ]
        daily_logs = generate_daily_logs(events, pad_24h=False)

        # The 8-hour block crosses midnight: Day 1 gets 2h, Day 2 gets 6h
        self.assertEqual(len(daily_logs), 2)
        total_sleeper = sum(log.sleeper_berth_hours for log in daily_logs)
        self.assertAlmostEqual(total_sleeper, 8.0, places=2)

        # Sleeper hours must NOT bleed into driving or on-duty counters
        for log in daily_logs:
            self.assertEqual(log.driving_hours, 0.0)
            self.assertEqual(log.on_duty_not_driving_hours, 0.0)

    # ── Test 5: remarks generation ────────────────────────────────────────────

    def test_remarks_generated_for_service_events(self):
        """
        DailyLogRemark entries must be generated for events that carry
        an annotation or location_name, with correct timestamps and metadata.
        """
        start = datetime(2026, 9, 20, 8, 0, 0)
        tasks = [
            ServiceTask(
                duration_hours=1.0,
                route_mile=0.0,
                location="Shipper A",
                service_type=ServiceType.PICKUP,
                annotation="Pickup at Shipper A",
            ),
            DriveTask(
                duration_hours=5.0,
                distance_miles=275.0,
                start_mile=0.0,
                end_mile=275.0,
                origin="Shipper A",
                destination="Receiver B",
            ),
            ServiceTask(
                duration_hours=1.0,
                route_mile=275.0,
                location="Receiver B",
                service_type=ServiceType.DROPOFF,
                annotation="Dropoff at Receiver B",
            ),
        ]
        state = schedule_trip(tasks, start_time=start)
        daily_logs = generate_daily_logs(state.events, pad_24h=True)

        self.assertEqual(len(daily_logs), 1)
        remarks = daily_logs[0].remarks

        # Must have at least one remark for Pickup and one for Dropoff
        self.assertTrue(len(remarks) >= 2)

        pickup_remarks = [r for r in remarks if "Pickup" in r.annotation]
        dropoff_remarks = [r for r in remarks if "Dropoff" in r.annotation]
        self.assertEqual(len(pickup_remarks), 1)
        self.assertEqual(len(dropoff_remarks), 1)

        # Pickup remark: correct time, location, status
        p = pickup_remarks[0]
        self.assertEqual(p.time, start)
        self.assertEqual(p.location, "Shipper A")
        self.assertEqual(p.status, DutyStatus.ON_DUTY_NOT_DRIVING)
        self.assertEqual(p.route_mile, 0.0)

        # Dropoff remark: starts at 08:00 + 1h pickup + 5h drive = 14:00
        d = dropoff_remarks[0]
        self.assertEqual(d.time, datetime(2026, 9, 20, 14, 0, 0))
        self.assertEqual(d.location, "Receiver B")
        self.assertEqual(d.status, DutyStatus.ON_DUTY_NOT_DRIVING)
        self.assertEqual(d.route_mile, 275.0)


if __name__ == "__main__":
    unittest.main()
