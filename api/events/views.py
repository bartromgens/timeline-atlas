from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from api.events.models import Category, Event, EventType
from api.events.serializers import (
    CategorySerializer,
    EventSerializer,
    EventTypeSerializer,
)


class EventPagination(PageNumberPagination):
    page_size = 1000


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = []
    pagination_class = None


class EventTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EventType.objects.all().order_by("name")
    serializer_class = EventTypeSerializer
    permission_classes = []
    pagination_class = None


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EventSerializer
    permission_classes = []
    pagination_class = EventPagination

    def get_queryset(self):
        qs = Event.objects.all()
        raw = self.request.query_params.get("category")
        if raw not in (None, ""):
            if raw == "uncategorized":
                qs = qs.filter(category_id__isnull=True)
            else:
                try:
                    qs = qs.filter(category_id=int(raw))
                except (TypeError, ValueError):
                    pass
        raw_type = self.request.query_params.get("event_type")
        if raw_type not in (None, ""):
            try:
                qs = qs.filter(event_type_id=int(raw_type))
            except (TypeError, ValueError):
                pass
        return qs
