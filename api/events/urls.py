"""
URL routing for events API.
"""

from django.urls import path

app_name = "events"

urlpatterns = [
    # GET /api/events/  -> add EventList view
    # GET /api/events/<id>/  -> add EventDetail view
]
