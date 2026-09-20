"""
Centralized HOS regulatory and operational constants for the trip planner.
Single source of truth for all scheduling constraints and default parameters.
"""

# -----------------------------------------------------------------------------
# FMCSA Property-Carrying (70h / 8-day) HOS Regulatory Constants
# -----------------------------------------------------------------------------
MAX_DRIVING_HOURS: float = 11.0            # Max driving hours per shift
MAX_SHIFT_WINDOW_HOURS: float = 14.0       # Max consecutive duty window per shift
BREAK_AFTER_DRIVING_HOURS: float = 8.0     # Max cumulative driving before 30-min break
BREAK_DURATION_HOURS: float = 0.5          # 30-minute rest break duration
REST_DURATION_HOURS: float = 10.0          # 10 consecutive hours off-duty for shift reset
CYCLE_LIMIT_HOURS: float = 70.0            # 70-hour / 8-day cycle limit
RESTART_DURATION_HOURS: float = 34.0       # 34 consecutive hours off-duty for cycle restart
CYCLE_RESTART_DURATION_HOURS: float = 34.0 # Alias for 34-hour restart

# -----------------------------------------------------------------------------
# Operational Defaults & Assumptions
# -----------------------------------------------------------------------------
PICKUP_DURATION_HOURS: float = 1.0         # Default time for pickup operations (1 hour)
DROPOFF_DURATION_HOURS: float = 1.0        # Default time for dropoff operations (1 hour)
FUEL_INTERVAL_MILES: float = 1000.0        # Mandatory fuel stop interval (miles)
FUEL_DURATION_HOURS: float = 0.5           # Default time spent fueling (30 mins)
AVERAGE_DRIVE_SPEED_MPH: float = 55.0      # Default estimation speed (mph)

# Numerical tolerance for floating-point comparisons
EPSILON: float = 1e-6
