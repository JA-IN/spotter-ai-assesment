"""
Daily Log Builder: Splits continuous duty-event streams into 24-hour calendar days.

Calculates totals for Off Duty, Sleeper Berth, Driving, On Duty (Not Driving),
miles driven, and generates location/activity remarks for FMCSA Daily Log grids.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from planner.tasks import DutyEvent, DutyStatus


@dataclass
class DailyLogRemark:
    """A log remark tied to a duty status change or location milestone."""
    time: datetime
    location: str
    annotation: str
    status: DutyStatus
    route_mile: float


@dataclass
class DailyLog:
    """
    Represents a 24-hour FMCSA Driver's Daily Log sheet (00:00 to 24:00).
    
    Attributes:
        date: Calendar date of the log sheet.
        day_number: 1-indexed day sequence (e.g. Day 1, Day 2, ...).
        events: Chronological duty events strictly within this calendar day.
        off_duty_hours: Total Off Duty hours.
        sleeper_berth_hours: Total Sleeper Berth hours.
        driving_hours: Total Driving hours.
        on_duty_not_driving_hours: Total On Duty (Not Driving) hours.
        total_hours: Total hours for the day (sums to 24.0 for a full standard sheet).
        miles_driven: Total driving miles logged on this calendar day.
        remarks: List of remarks for status changes and milestones.
    """
    date: date
    day_number: int
    events: List[DutyEvent] = field(default_factory=list)
    off_duty_hours: float = 0.0
    sleeper_berth_hours: float = 0.0
    driving_hours: float = 0.0
    on_duty_not_driving_hours: float = 0.0
    total_hours: float = 0.0
    miles_driven: float = 0.0
    remarks: List[DailyLogRemark] = field(default_factory=list)

    @property
    def driving_minutes(self) -> float:
        """Total driving duration in minutes."""
        return round(self.driving_hours * 60.0, 2)

    @property
    def on_duty_minutes(self) -> float:
        """Total on-duty (not driving) duration in minutes."""
        return round(self.on_duty_not_driving_hours * 60.0, 2)

    @property
    def off_duty_minutes(self) -> float:
        """Total off-duty duration in minutes."""
        return round(self.off_duty_hours * 60.0, 2)

    @property
    def sleeper_berth_minutes(self) -> float:
        """Total sleeper berth duration in minutes."""
        return round(self.sleeper_berth_hours * 60.0, 2)

    @property
    def total_minutes(self) -> float:
        """Total day duration in minutes (1,440 minutes = 24 hours)."""
        return round(self.total_hours * 60.0, 2)


def _split_events_at_midnight(events: List[DutyEvent]) -> List[DutyEvent]:
    """
    Splits any event that crosses midnight (00:00:00) into distinct sub-events,
    ensuring each sub-event belongs to exactly one calendar day.

    For DRIVING events with a known end_route_mile, the mileage is proportionally
    split so each sub-event carries accurate route_mile → end_route_mile bounds.
    """
    split_events: List[DutyEvent] = []

    for event in events:
        cur_start = event.start_time
        cur_end = event.end_time
        cur_mile = event.route_mile
        # Track the running end_route_mile for proportional splits
        cur_end_mile: Optional[float] = event.end_route_mile
        total_seconds = (event.end_time - event.start_time).total_seconds()

        if cur_start >= cur_end:
            continue

        while cur_start.date() < cur_end.date():
            next_midnight = datetime.combine(cur_start.date() + timedelta(days=1), time.min)
            chunk_seconds = (next_midnight - cur_start).total_seconds()
            chunk_hours = chunk_seconds / 3600.0

            # Proportionally compute the end mile for this chunk
            if event.end_route_mile is not None and total_seconds > 0:
                fraction = chunk_seconds / total_seconds
                chunk_end_mile: Optional[float] = event.route_mile + fraction * (event.end_route_mile - event.route_mile)
            else:
                chunk_end_mile = None

            split_events.append(
                DutyEvent(
                    start_time=cur_start,
                    end_time=next_midnight,
                    duration_hours=round(chunk_hours, 4),
                    status=event.status,
                    annotation=event.annotation,
                    route_mile=cur_mile,
                    end_route_mile=round(chunk_end_mile, 4) if chunk_end_mile is not None else None,
                    location_name=event.location_name,
                    event_type=event.event_type,
                )
            )

            cur_start = next_midnight
            cur_mile = chunk_end_mile if chunk_end_mile is not None else cur_mile

        # Remaining piece within the final day
        final_hours = (cur_end - cur_start).total_seconds() / 3600.0
        if final_hours > 1e-6:
            split_events.append(
                DutyEvent(
                    start_time=cur_start,
                    end_time=cur_end,
                    duration_hours=round(final_hours, 4),
                    status=event.status,
                    annotation=event.annotation,
                    route_mile=cur_mile,
                    end_route_mile=cur_end_mile,
                    location_name=event.location_name,
                    event_type=event.event_type,
                )
            )

    return split_events


def _merge_adjacent_events(events: List[DutyEvent]) -> List[DutyEvent]:
    """
    Collapses consecutive events that share the same DutyStatus and have
    directly touching timestamps into a single merged event.

    Rules:
    - Two events are mergeable when:
        event[i].status == event[i+1].status
        AND event[i].end_time == event[i+1].start_time
    - For DRIVING events, the merged event inherits:
        route_mile      from the FIRST segment
        end_route_mile  from the LAST  segment
    - For non-driving events, end_route_mile stays None.
    - The merged event keeps the annotation and location_name of the
      FIRST event in the run (preserving meaningful labels like
      "10-hour mandatory shift rest" rather than a later generic "Off Duty").
    """
    if not events:
        return []

    merged: List[DutyEvent] = []
    # Start with a copy of the first event so we can mutate safely
    current = DutyEvent(
        start_time=events[0].start_time,
        end_time=events[0].end_time,
        duration_hours=events[0].duration_hours,
        status=events[0].status,
        annotation=events[0].annotation,
        route_mile=events[0].route_mile,
        end_route_mile=events[0].end_route_mile,
        location_name=events[0].location_name,
        event_type=events[0].event_type,
    )

    for nxt in events[1:]:
        can_merge = (
            nxt.status == current.status
            and nxt.start_time == current.end_time
        )
        if can_merge:
            # Extend the current event's window
            current.end_time = nxt.end_time
            current.duration_hours = round(
                current.duration_hours + nxt.duration_hours, 4
            )
            # For driving events, advance the ending mile marker
            if nxt.end_route_mile is not None:
                current.end_route_mile = nxt.end_route_mile
        else:
            merged.append(current)
            current = DutyEvent(
                start_time=nxt.start_time,
                end_time=nxt.end_time,
                duration_hours=nxt.duration_hours,
                status=nxt.status,
                annotation=nxt.annotation,
                route_mile=nxt.route_mile,
                end_route_mile=nxt.end_route_mile,
                location_name=nxt.location_name,
                event_type=nxt.event_type,
            )

    merged.append(current)
    return merged


def generate_daily_logs(events: List[DutyEvent], pad_24h: bool = True) -> List[DailyLog]:
    """
    Transforms a continuous HOS DutyEvent stream into FMCSA 24-hour Driver's Daily Log sheets.
    
    Args:
        events: Chronological list of DutyEvents generated by HOSScheduler.
        pad_24h: If True (default), fills pre-trip and post-trip intervals with OFF_DUTY
                 so that every daily log sheet totals exactly 24.0 hours (1,440 mins).
                 
    Returns:
        List of DailyLog objects, one per calendar day.
    """
    if not events:
        return []

    # 1. Split events at midnight boundaries
    clipped_events = _split_events_at_midnight(events)
    if not clipped_events:
        return []

    # 2. Identify calendar day range
    min_date = clipped_events[0].start_time.date()
    max_date = clipped_events[-1].end_time.date()

    # Group events by calendar date
    events_by_date = {}
    for event in clipped_events:
        d = event.start_time.date()
        events_by_date.setdefault(d, []).append(event)

    daily_logs: List[DailyLog] = []
    day_count = (max_date - min_date).days + 1

    for day_idx in range(day_count):
        cur_date = min_date + timedelta(days=day_idx)
        day_number = day_idx + 1
        day_events = events_by_date.get(cur_date, [])

        day_start = datetime.combine(cur_date, time.min)
        day_end = datetime.combine(cur_date + timedelta(days=1), time.min)

        processed_events: List[DutyEvent] = []

        if pad_24h:
            # Check if we need pre-trip padding from 00:00
            if not day_events:
                # Entire day off duty
                processed_events.append(
                    DutyEvent(
                        start_time=day_start,
                        end_time=day_end,
                        duration_hours=24.0,
                        status=DutyStatus.OFF_DUTY,
                        annotation="Off Duty",
                        route_mile=0.0,
                        end_route_mile=None,
                        event_type="OFF_DUTY",
                    )
                )
            else:
                first_event = day_events[0]
                if first_event.start_time > day_start:
                    pre_hours = (first_event.start_time - day_start).total_seconds() / 3600.0
                    processed_events.append(
                        DutyEvent(
                            start_time=day_start,
                            end_time=first_event.start_time,
                            duration_hours=round(pre_hours, 4),
                            status=DutyStatus.OFF_DUTY,
                            annotation="Off Duty",
                            route_mile=first_event.route_mile,
                            end_route_mile=None,
                            location_name=first_event.location_name,
                            event_type="OFF_DUTY",
                        )
                    )

                # Add actual day events and fill any internal micro-gaps if needed
                for i, evt in enumerate(day_events):
                    if i > 0:
                        prev_evt = day_events[i - 1]
                        if evt.start_time > prev_evt.end_time:
                            gap_hours = (evt.start_time - prev_evt.end_time).total_seconds() / 3600.0
                            processed_events.append(
                                DutyEvent(
                                    start_time=prev_evt.end_time,
                                    end_time=evt.start_time,
                                    duration_hours=round(gap_hours, 4),
                                    status=DutyStatus.OFF_DUTY,
                                    annotation="Off Duty",
                                    route_mile=prev_evt.route_mile,
                                    end_route_mile=None,
                                    event_type="OFF_DUTY",
                                )
                            )
                    processed_events.append(evt)

                # Check if we need post-trip padding to 24:00 (next day 00:00)
                last_event = day_events[-1]
                if last_event.end_time < day_end:
                    post_hours = (day_end - last_event.end_time).total_seconds() / 3600.0
                    processed_events.append(
                        DutyEvent(
                            start_time=last_event.end_time,
                            end_time=day_end,
                            duration_hours=round(post_hours, 4),
                            status=DutyStatus.OFF_DUTY,
                            annotation="Off Duty",
                            route_mile=last_event.route_mile,
                            end_route_mile=None,
                            location_name=last_event.location_name,
                            event_type="OFF_DUTY",
                        )
                    )
        else:
            processed_events = day_events

        # Merge adjacent events that share the same status (e.g. two OFF_DUTY
        # blocks that were independently generated but touch each other).
        processed_events = _merge_adjacent_events(processed_events)

        # 3. Calculate category totals
        off_duty = sum(e.duration_hours for e in processed_events if e.status == DutyStatus.OFF_DUTY)
        sleeper = sum(e.duration_hours for e in processed_events if e.status == DutyStatus.SLEEPER_BERTH)
        driving = sum(e.duration_hours for e in processed_events if e.status == DutyStatus.DRIVING)
        on_duty = sum(e.duration_hours for e in processed_events if e.status == DutyStatus.ON_DUTY_NOT_DRIVING)
        total = off_duty + sleeper + driving + on_duty

        # 4. Calculate day miles from driving events using exact start/end mile markers
        day_drive_events = [e for e in processed_events if e.status == DutyStatus.DRIVING]
        day_miles = sum(
            e.end_route_mile - e.route_mile
            for e in day_drive_events
            if e.end_route_mile is not None
        )

        # Build remarks
        remarks: List[DailyLogRemark] = []
        for evt in processed_events:
            if evt.annotation or evt.location_name:
                remarks.append(
                    DailyLogRemark(
                        time=evt.start_time,
                        location=evt.location_name or f"Mile {int(round(evt.route_mile))}",
                        annotation=evt.annotation or evt.status.value,
                        status=evt.status,
                        route_mile=evt.route_mile,
                    )
                )

        daily_logs.append(
            DailyLog(
                date=cur_date,
                day_number=day_number,
                events=processed_events,
                off_duty_hours=round(off_duty, 2),
                sleeper_berth_hours=round(sleeper, 2),
                driving_hours=round(driving, 2),
                on_duty_not_driving_hours=round(on_duty, 2),
                total_hours=round(total, 2),
                miles_driven=round(day_miles, 1),
                remarks=remarks,
            )
        )

    return daily_logs
