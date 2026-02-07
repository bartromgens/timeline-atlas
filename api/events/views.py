from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from api.events.models import Category, Event
from api.events.serializers import CategorySerializer, EventSerializer


class EventPagination(PageNumberPagination):
    page_size = 1000


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
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
            try:
                qs = qs.filter(category_id=int(raw))
            except (TypeError, ValueError):
                pass
        return qs
