"""
Validates trip-planning API request and response data.

Layer contract:
    React  →  serializers.py  →  views.py  →  scheduler  →  logs  →  React

Serializers are responsible for one thing only:
    "Is this API data structurally valid?"

HOS legality (e.g. 11-hour driving limit) is the scheduler's responsibility,
not the serializer's.
"""
from rest_framework import serializers
from planner.constants import CYCLE_LIMIT_HOURS

# ---------------------------------------------------------------------------
# Constants mirrored from FMCSA rules (for field-level boundary validation
# only — do NOT import from scheduler or planner internals here).
# ---------------------------------------------------------------------------
_CYCLE_LIMIT_HOURS = CYCLE_LIMIT_HOURS


class TripPlanRequestSerializer(serializers.Serializer):
    """
    Validates an incoming trip-plan request from the React frontend.

    Expected JSON body:
    {
        "current_location":   "Chicago, IL",
        "pickup_location":    "Memphis, TN",
        "dropoff_location":   "Houston, TX",
        "current_cycle_used": 12.5
    }

    Validation rules:
        - All three location strings are required and may not be blank.
        - current_cycle_used is required, must be a number, and must
          satisfy  0.0 ≤ value ≤ 70.0  (negative hours and an already-
          exhausted cycle are both immediately rejectable at the API
          boundary without touching the scheduler).
    """

    current_location = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=255,
        help_text="Driver's current position (city, address, or coordinates).",
    )
    pickup_location = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=255,
        help_text="Origin / shipper location for the load.",
    )
    dropoff_location = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=255,
        help_text="Destination / receiver location for the load.",
    )
    current_cycle_used = serializers.FloatField(
        required=True,
        help_text=(
            "Hours already consumed in the driver's current 70-hour / 8-day cycle. "
            "Must be between 0.0 and 70.0 inclusive."
        ),
    )

    # ── Field-level validators ──────────────────────────────────────────────

    def validate_current_cycle_used(self, value: float) -> float:
        """Reject negative hours and values exceeding the 70-hour cycle cap."""
        if value < 0.0:
            raise serializers.ValidationError(
                "current_cycle_used cannot be negative."
            )
        if value > _CYCLE_LIMIT_HOURS:
            raise serializers.ValidationError(
                f"current_cycle_used cannot exceed {_CYCLE_LIMIT_HOURS} hours "
                "(70-hour / 8-day cycle limit)."
            )
        return value

    # ── Object-level validator ──────────────────────────────────────────────

    def validate(self, data: dict) -> dict:
        """
        Cross-field validation.

        Rule: pickup and dropoff locations must not be identical strings
        (case-insensitive) — planning a zero-distance trip has no meaning.
        """
        pickup = data.get("pickup_location", "").strip().lower()
        dropoff = data.get("dropoff_location", "").strip().lower()

        if pickup and dropoff and pickup == dropoff:
            raise serializers.ValidationError(
                {
                    "dropoff_location": (
                        "dropoff_location must differ from pickup_location."
                    )
                }
            )

        return data


# ---------------------------------------------------------------------------
# TripPlanResponseSerializer — deferred to Phase 3
# ---------------------------------------------------------------------------
# Will serialize the complete trip plan returned to React, including:
#
#   trip
#   ├── route        { distance, duration, geometry }
#   ├── stops        [ Stop, ... ]
#   ├── events       [ DutyEvent, ... ]
#   ├── daily_logs   [ DailyLog, ... ]
#   ├── summary      { total_driving_hours, total_miles, days_on_road }
#   └── warnings     [ "Approaching 70h cycle limit", ... ]
#
# Deferred because:
#   1. The routing layer (routing.py) has not been connected yet.
#   2. The final DailyLog JSON contract is still being finalised.
#   3. DutyEvent.end_route_mile was only just stabilised — the response
#      shape will be defined once all upstream data is locked.
# ---------------------------------------------------------------------------
