"""
URL routing for events API.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.events.views import (
    CategoryViewSet,
    EventTypeViewSet,
    EventViewSet,
)

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"event-types", EventTypeViewSet, basename="eventtype")
router.register(r"events", EventViewSet, basename="event")

app_name = "events"

urlpatterns = [
    path("", include(router.urls)),
]
