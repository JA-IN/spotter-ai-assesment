"""
Unit tests for TripPlanRequestSerializer.

Tests are grouped into four sections:
    1. Valid inputs that should pass cleanly.
    2. Missing / blank required fields.
    3. Invalid current_cycle_used values.
    4. Cross-field validation (pickup == dropoff).
"""
import django
import os
import unittest

# Minimal Django setup so DRF serializers can be instantiated outside
# a full manage.py environment.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from planner.serializers import TripPlanRequestSerializer


class TestTripPlanRequestSerializerValid(unittest.TestCase):
    """Inputs that must be accepted without errors."""

    def _valid_payload(self, **overrides) -> dict:
        base = {
            "current_location": "Chicago, IL",
            "pickup_location": "Memphis, TN",
            "dropoff_location": "Houston, TX",
            "current_cycle_used": 12.5,
        }
        base.update(overrides)
        return base

    def test_valid_full_payload(self):
        """A well-formed payload with all fields present must be valid."""
        s = TripPlanRequestSerializer(data=self._valid_payload())
        self.assertTrue(s.is_valid(), s.errors)

    def test_cycle_used_zero(self):
        """current_cycle_used = 0 (fresh driver) must be accepted."""
        s = TripPlanRequestSerializer(data=self._valid_payload(current_cycle_used=0.0))
        self.assertTrue(s.is_valid(), s.errors)

    def test_cycle_used_exactly_70(self):
        """current_cycle_used = 70.0 (exactly at the cap) must be accepted."""
        s = TripPlanRequestSerializer(data=self._valid_payload(current_cycle_used=70.0))
        self.assertTrue(s.is_valid(), s.errors)

    def test_validated_data_passthrough(self):
        """validated_data must expose the original cleaned values."""
        payload = self._valid_payload()
        s = TripPlanRequestSerializer(data=payload)
        self.assertTrue(s.is_valid())
        self.assertEqual(s.validated_data["current_location"], "Chicago, IL")
        self.assertEqual(s.validated_data["pickup_location"], "Memphis, TN")
        self.assertEqual(s.validated_data["dropoff_location"], "Houston, TX")
        self.assertAlmostEqual(s.validated_data["current_cycle_used"], 12.5)


class TestTripPlanRequestSerializerMissingFields(unittest.TestCase):
    """Missing or blank required fields must be rejected."""

    def test_missing_current_location(self):
        data = {
            "pickup_location": "Memphis, TN",
            "dropoff_location": "Houston, TX",
            "current_cycle_used": 10.0,
        }
        s = TripPlanRequestSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("current_location", s.errors)

    def test_missing_pickup_location(self):
        data = {
            "current_location": "Chicago, IL",
            "dropoff_location": "Houston, TX",
            "current_cycle_used": 10.0,
        }
        s = TripPlanRequestSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("pickup_location", s.errors)

    def test_missing_dropoff_location(self):
        data = {
            "current_location": "Chicago, IL",
            "pickup_location": "Memphis, TN",
            "current_cycle_used": 10.0,
        }
        s = TripPlanRequestSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("dropoff_location", s.errors)

    def test_missing_current_cycle_used(self):
        data = {
            "current_location": "Chicago, IL",
            "pickup_location": "Memphis, TN",
            "dropoff_location": "Houston, TX",
        }
        s = TripPlanRequestSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("current_cycle_used", s.errors)

    def test_blank_current_location(self):
        s = TripPlanRequestSerializer(data={
            "current_location": "",
            "pickup_location": "Memphis, TN",
            "dropoff_location": "Houston, TX",
            "current_cycle_used": 10.0,
        })
        self.assertFalse(s.is_valid())
        self.assertIn("current_location", s.errors)

    def test_blank_pickup_location(self):
        s = TripPlanRequestSerializer(data={
            "current_location": "Chicago, IL",
            "pickup_location": "   ",
            "dropoff_location": "Houston, TX",
            "current_cycle_used": 10.0,
        })
        self.assertFalse(s.is_valid())
        self.assertIn("pickup_location", s.errors)


class TestTripPlanRequestSerializerCycleValidation(unittest.TestCase):
    """current_cycle_used boundary and type checks."""

    def _base(self, cycle_used) -> dict:
        return {
            "current_location": "Chicago, IL",
            "pickup_location": "Memphis, TN",
            "dropoff_location": "Houston, TX",
            "current_cycle_used": cycle_used,
        }

    def test_negative_cycle_used_rejected(self):
        s = TripPlanRequestSerializer(data=self._base(-1.0))
        self.assertFalse(s.is_valid())
        self.assertIn("current_cycle_used", s.errors)

    def test_cycle_above_70_rejected(self):
        s = TripPlanRequestSerializer(data=self._base(70.1))
        self.assertFalse(s.is_valid())
        self.assertIn("current_cycle_used", s.errors)

    def test_cycle_far_above_70_rejected(self):
        s = TripPlanRequestSerializer(data=self._base(999.0))
        self.assertFalse(s.is_valid())
        self.assertIn("current_cycle_used", s.errors)

    def test_non_numeric_cycle_rejected(self):
        s = TripPlanRequestSerializer(data=self._base("lots"))
        self.assertFalse(s.is_valid())
        self.assertIn("current_cycle_used", s.errors)

    def test_cycle_as_integer_coerced(self):
        """An integer value (e.g. 10) should be accepted and coerced to float."""
        s = TripPlanRequestSerializer(data=self._base(10))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsInstance(s.validated_data["current_cycle_used"], float)


class TestTripPlanRequestSerializerCrossField(unittest.TestCase):
    """Cross-field validation: pickup and dropoff must not be identical."""

    def test_identical_pickup_and_dropoff_rejected(self):
        s = TripPlanRequestSerializer(data={
            "current_location": "Chicago, IL",
            "pickup_location": "Memphis, TN",
            "dropoff_location": "Memphis, TN",
            "current_cycle_used": 10.0,
        })
        self.assertFalse(s.is_valid())
        # Error is placed on the non_field_errors key or the dropoff_location key
        has_dropoff_error = "dropoff_location" in s.errors
        has_non_field_error = "non_field_errors" in s.errors
        self.assertTrue(
            has_dropoff_error or has_non_field_error,
            f"Expected a cross-field error, got: {s.errors}",
        )

    def test_identical_case_insensitive_rejected(self):
        """Matching is case-insensitive: 'dallas, tx' == 'Dallas, TX'."""
        s = TripPlanRequestSerializer(data={
            "current_location": "Chicago, IL",
            "pickup_location": "dallas, tx",
            "dropoff_location": "Dallas, TX",
            "current_cycle_used": 10.0,
        })
        self.assertFalse(s.is_valid())

    def test_different_pickup_and_dropoff_accepted(self):
        s = TripPlanRequestSerializer(data={
            "current_location": "Chicago, IL",
            "pickup_location": "Memphis, TN",
            "dropoff_location": "Houston, TX",
            "current_cycle_used": 10.0,
        })
        self.assertTrue(s.is_valid(), s.errors)


if __name__ == "__main__":
    unittest.main()
