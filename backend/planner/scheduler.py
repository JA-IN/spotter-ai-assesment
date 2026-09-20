"""
Pure Python HOS Scheduler Engine.

Contains:
- SchedulerState: Conceptual state machine representation for a commercial driver
- HOSScheduler: Deterministic HOS scheduler implementing federal Property-Carrying rules
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Union

from planner.constants import (
    AVERAGE_DRIVE_SPEED_MPH,
    BREAK_AFTER_DRIVING_HOURS,
    BREAK_DURATION_HOURS,
    CYCLE_LIMIT_HOURS,
    CYCLE_RESTART_DURATION_HOURS,
    DROPOFF_DURATION_HOURS,
    EPSILON,
    FUEL_DURATION_HOURS,
    FUEL_INTERVAL_MILES,
    MAX_DRIVING_HOURS,
    MAX_SHIFT_WINDOW_HOURS,
    PICKUP_DURATION_HOURS,
    RESTART_DURATION_HOURS,
    REST_DURATION_HOURS,
)
from planner.tasks import (
    DriveTask,
    DutyEvent,
    DutyStatus,
    ServiceTask,
    ServiceType,
    Stop,
)

__all__ = [
    "HOSScheduler",
    "SchedulerState",
    "schedule_trip",
    "MAX_DRIVING_HOURS",
    "MAX_SHIFT_WINDOW_HOURS",
    "BREAK_AFTER_DRIVING_HOURS",
    "BREAK_DURATION_HOURS",
    "REST_DURATION_HOURS",
    "CYCLE_LIMIT_HOURS",
    "RESTART_DURATION_HOURS",
    "CYCLE_RESTART_DURATION_HOURS",
    "PICKUP_DURATION_HOURS",
    "DROPOFF_DURATION_HOURS",
    "FUEL_INTERVAL_MILES",
    "FUEL_DURATION_HOURS",
    "AVERAGE_DRIVE_SPEED_MPH",
    "EPSILON",
]


@dataclass
class SchedulerState:
    """
    Tracks the complete deterministic HOS state of a commercial driver along a route.
    
    Attributes:
        current_time: The active timeline cursor (advances with each event).
        current_mile: Cumulative route distance covered so far (in miles).
        shift_start: Timestamp when the current 14-hour shift window started (None if off-duty).
        shift_driving: Cumulative driving hours logged in the current shift (resets after 10h rest).
        driving_since_break: Cumulative driving hours logged since last 30+ min break (resets after 30m break or 10h rest).
        cycle_used: Cumulative on-duty + driving hours used in current 70h cycle (resets after 34h restart).
        events: Chronological sequence of generated DutyEvent objects.
        stops: Chronological list of generated physical Stop objects (pickup, dropoff, fuel, rest, break).
    """
    current_time: datetime
    current_mile: float = 0.0
    shift_start: Optional[datetime] = None
    shift_driving: float = 0.0
    driving_since_break: float = 0.0
    cycle_used: float = 0.0
    events: List[DutyEvent] = field(default_factory=list)
    stops: List[Stop] = field(default_factory=list)

    @property
    def shift_elapsed_hours(self) -> float:
        """Elapsed hours since the start of the current 14-hour shift window."""
        if self.shift_start is None:
            return 0.0
        return max(0.0, (self.current_time - self.shift_start).total_seconds() / 3600.0)

    @property
    def remaining_shift_driving(self) -> float:
        """Remaining driving hours available in the current shift (out of 11.0 max)."""
        return max(0.0, MAX_DRIVING_HOURS - self.shift_driving)

    @property
    def remaining_shift_window(self) -> float:
        """Remaining hours in the 14-hour consecutive shift window."""
        if self.shift_start is None:
            return MAX_SHIFT_WINDOW_HOURS
        return max(0.0, MAX_SHIFT_WINDOW_HOURS - self.shift_elapsed_hours)

    @property
    def remaining_driving_before_break(self) -> float:
        """Remaining driving hours before a mandatory 30-minute break is required (out of 8.0 max)."""
        return max(0.0, BREAK_AFTER_DRIVING_HOURS - self.driving_since_break)

    @property
    def remaining_cycle(self) -> float:
        """Remaining on-duty/driving hours available in the 70-hour cycle."""
        return max(0.0, CYCLE_LIMIT_HOURS - self.cycle_used)


class HOSScheduler:
    """
    Pure Python deterministic HOS scheduler implementing federal Property-Carrying regulations:
    - 11-Hour Driving Limit (after 10 consecutive hours off duty)
    - 14-Hour Consecutive Driving Window Limit
    - 30-Minute Break (after 8 cumulative hours of driving)
    - 70-Hour / 8-Day Cycle Limit
    - 34-Hour Cycle Restart
    """

    def __init__(self, start_time: Optional[datetime] = None, initial_cycle_used: float = 0.0):
        self.initial_start_time = start_time or datetime.now()
        self.initial_cycle_used = initial_cycle_used

    def schedule(self, tasks: List[Union[DriveTask, ServiceTask]]) -> SchedulerState:
        """
        Executes scheduling over an ordered sequence of DriveTasks and ServiceTasks.
        Returns the finalized SchedulerState containing the complete event stream and stops.
        """
        state = SchedulerState(
            current_time=self.initial_start_time,
            current_mile=0.0,
            shift_start=None,
            shift_driving=0.0,
            driving_since_break=0.0,
            cycle_used=self.initial_cycle_used,
        )

        for task in tasks:
            if isinstance(task, ServiceTask):
                self._schedule_service_task(state, task)
            elif isinstance(task, DriveTask):
                self._schedule_drive_task(state, task)

        return state

    def _apply_34h_restart(self, state: SchedulerState) -> None:
        """Inserts a 34-hour off-duty cycle restart."""
        start = state.current_time
        end = start + timedelta(hours=RESTART_DURATION_HOURS)
        state.events.append(
            DutyEvent(
                start_time=start,
                end_time=end,
                duration_hours=RESTART_DURATION_HOURS,
                status=DutyStatus.OFF_DUTY,
                annotation="34-hour cycle restart",
                route_mile=state.current_mile,
                end_route_mile=None,
                location_name=f"Restart Stop @ Mile {int(round(state.current_mile))}",
                event_type="RESTART",
            )
        )
        state.stops.append(
            Stop(
                stop_type=ServiceType.REST,
                name=f"Cycle Restart @ Mile {int(round(state.current_mile))}",
                route_mile=state.current_mile,
                arrival_time=start,
                departure_time=end,
                duration_hours=RESTART_DURATION_HOURS,
                annotation="34-hour off-duty cycle restart",
            )
        )
        state.current_time = end
        state.cycle_used = 0.0
        state.shift_start = None
        state.shift_driving = 0.0
        state.driving_since_break = 0.0

    def _apply_10h_rest(self, state: SchedulerState) -> None:
        """Inserts a 10-hour consecutive off-duty shift reset."""
        start = state.current_time
        end = start + timedelta(hours=REST_DURATION_HOURS)
        state.events.append(
            DutyEvent(
                start_time=start,
                end_time=end,
                duration_hours=REST_DURATION_HOURS,
                status=DutyStatus.OFF_DUTY,
                annotation="10-hour mandatory shift rest",
                route_mile=state.current_mile,
                end_route_mile=None,
                location_name=f"Rest Area @ Mile {int(round(state.current_mile))}",
                event_type="REST",
            )
        )
        state.stops.append(
            Stop(
                stop_type=ServiceType.REST,
                name=f"Rest Stop @ Mile {int(round(state.current_mile))}",
                route_mile=state.current_mile,
                arrival_time=start,
                departure_time=end,
                duration_hours=REST_DURATION_HOURS,
                annotation="10-hour consecutive off-duty rest",
            )
        )
        state.current_time = end
        state.shift_start = None
        state.shift_driving = 0.0
        state.driving_since_break = 0.0

    def _apply_30m_break(self, state: SchedulerState) -> None:
        """Inserts a 30-minute off-duty rest break."""
        start = state.current_time
        end = start + timedelta(hours=BREAK_DURATION_HOURS)
        state.events.append(
            DutyEvent(
                start_time=start,
                end_time=end,
                duration_hours=BREAK_DURATION_HOURS,
                status=DutyStatus.OFF_DUTY,
                annotation="30-minute rest break",
                route_mile=state.current_mile,
                end_route_mile=None,
                location_name=f"Break Stop @ Mile {int(round(state.current_mile))}",
                event_type="BREAK",
            )
        )
        state.stops.append(
            Stop(
                stop_type=ServiceType.BREAK,
                name=f"Break Stop @ Mile {int(round(state.current_mile))}",
                route_mile=state.current_mile,
                arrival_time=start,
                departure_time=end,
                duration_hours=BREAK_DURATION_HOURS,
                annotation="30-minute mandatory driving break",
            )
        )
        state.current_time = end
        state.driving_since_break = 0.0

    def _schedule_service_task(self, state: SchedulerState, task: ServiceTask) -> None:
        """
        Schedules a service task (e.g. Pickup, Dropoff, Fuel, planned Rest/Break).
        Enforces:
        - Planned REST / BREAK tasks trigger appropriate state resets.
        - 70-hour cycle limit check (triggers 34h restart if exceeded).
        - 14-hour shift window & 11-hour driving exhaustion checks (triggers 10h rest if service exceeds window).
        """
        if task.service_type == ServiceType.REST:
            self._apply_10h_rest(state)
            return
        if task.service_type == ServiceType.BREAK:
            self._apply_30m_break(state)
            return

        # 1. Check if 70-hour cycle limit would be exceeded
        if state.cycle_used + task.duration_hours > CYCLE_LIMIT_HOURS + EPSILON:
            self._apply_34h_restart(state)

        # 2. Check if service cannot fit in the active 14-hour window or driving was already exhausted
        if state.shift_start is not None:
            will_exceed_window = (state.shift_elapsed_hours + task.duration_hours > MAX_SHIFT_WINDOW_HOURS + EPSILON)
            driving_exhausted = (state.shift_driving >= MAX_DRIVING_HOURS - EPSILON)
            if will_exceed_window or driving_exhausted:
                self._apply_10h_rest(state)

        # Start new shift window if driver was off-duty
        if state.shift_start is None:
            state.shift_start = state.current_time

        start = state.current_time
        end = start + timedelta(hours=task.duration_hours)
        annotation = task.annotation or f"{task.service_type.value} at {task.location}"

        state.events.append(
            DutyEvent(
                start_time=start,
                end_time=end,
                duration_hours=task.duration_hours,
                status=DutyStatus.ON_DUTY_NOT_DRIVING,
                annotation=annotation,
                route_mile=task.route_mile,
                end_route_mile=None,
                location_name=task.location,
                event_type=task.service_type.value,
            )
        )

        state.stops.append(
            Stop(
                stop_type=task.service_type,
                name=task.location,
                route_mile=task.route_mile,
                arrival_time=start,
                departure_time=end,
                duration_hours=task.duration_hours,
                annotation=annotation,
            )
        )

        state.cycle_used += task.duration_hours
        state.current_time = end

    def _schedule_drive_task(self, state: SchedulerState, task: DriveTask) -> None:
        """
        Schedules a driving leg, slicing it dynamically as HOS constraints are encountered:
        - 70-hour cycle -> 34h restart
        - 14-hour window or 11-hour driving limit -> 10h rest
        - 8-hour cumulative driving limit -> 30-minute break
        """
        remaining_hours = task.duration_hours
        if remaining_hours <= EPSILON:
            return

        miles_per_hour = (task.distance_miles / task.duration_hours) if task.duration_hours > 0 else AVERAGE_DRIVE_SPEED_MPH

        while remaining_hours > EPSILON:
            # 1. Check 70-hour cycle
            avail_cycle = CYCLE_LIMIT_HOURS - state.cycle_used
            if avail_cycle <= EPSILON:
                self._apply_34h_restart(state)
                continue

            # 2. Check 14-hour shift window & 11-hour driving limit
            if state.shift_start is None:
                state.shift_start = state.current_time

            avail_window = MAX_SHIFT_WINDOW_HOURS - state.shift_elapsed_hours
            avail_shift_drive = MAX_DRIVING_HOURS - state.shift_driving

            if avail_window <= EPSILON or avail_shift_drive <= EPSILON:
                self._apply_10h_rest(state)
                continue

            # 3. Check 8-hour cumulative driving break
            avail_break = BREAK_AFTER_DRIVING_HOURS - state.driving_since_break
            if avail_break <= EPSILON:
                self._apply_30m_break(state)
                continue

            # 4. Drive the minimum chunk allowed by all simultaneous constraints
            chunk_hours = min(remaining_hours, avail_cycle, avail_window, avail_shift_drive, avail_break)
            chunk_miles = chunk_hours * miles_per_hour

            start = state.current_time
            end = start + timedelta(hours=chunk_hours)
            start_mile = state.current_mile
            end_mile = start_mile + chunk_miles

            state.events.append(
                DutyEvent(
                    start_time=start,
                    end_time=end,
                    duration_hours=chunk_hours,
                    status=DutyStatus.DRIVING,
                    annotation=f"Driving towards {task.destination}",
                    route_mile=start_mile,
                    end_route_mile=end_mile,
                    location_name=task.destination,
                    event_type="DRIVE",
                )
            )

            # Advance state
            state.current_time = end
            state.current_mile = end_mile
            state.shift_driving += chunk_hours
            state.driving_since_break += chunk_hours
            state.cycle_used += chunk_hours
            remaining_hours -= chunk_hours


def schedule_trip(tasks: List[Union[DriveTask, ServiceTask]], start_time: Optional[datetime] = None, initial_cycle_used: float = 0.0) -> SchedulerState:
    """Convenience helper function to run the HOS Scheduler on a list of tasks."""
    scheduler = HOSScheduler(start_time=start_time, initial_cycle_used=initial_cycle_used)
    return scheduler.schedule(tasks)
