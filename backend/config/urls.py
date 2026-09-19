"""
URL configuration for Spotter AI Trip Planner.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('planner.urls')),
]
