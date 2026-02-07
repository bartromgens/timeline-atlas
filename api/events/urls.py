"""
URL routing for events API.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.events.views import EventViewSet

router = DefaultRouter()
router.register(r"events", EventViewSet, basename="event")

app_name = "events"

urlpatterns = [
    path("", include(router.urls)),
]
