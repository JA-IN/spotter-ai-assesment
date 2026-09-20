"""URL patterns for the planner API."""

from django.urls import path

from planner.views import PlanTripView

urlpatterns = [
    path("plan-trip/", PlanTripView.as_view(), name="plan-trip"),
]
