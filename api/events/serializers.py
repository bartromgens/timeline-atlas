from rest_framework import serializers

from api.events.models import Category, Event, EventType


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "wikidata_id"]
        read_only_fields = fields


class EventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventType
        fields = ["id", "name", "wikidata_id"]
        read_only_fields = fields


class EventSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        read_only=True, source="category", allow_null=True
    )
    event_type_id = serializers.PrimaryKeyRelatedField(
        read_only=True, source="event_type", allow_null=True
    )

    class Meta:
        model = Event
        fields = [
            "id",
            "category_id",
            "event_type_id",
            "title",
            "description",
            "point_in_time",
            "start_time",
            "end_time",
            "location_name",
            "location_qid",
            "location_lat",
            "location_lon",
            "wikidata_id",
            "wikidata_url",
            "wikipedia_url",
            "wikipedia_title",
            "wikipedia_extract",
            "sitelink_count",
            "pageviews_30d",
            "backlink_count",
            "sort_date",
            "importance_score",
        ]
        read_only_fields = fields
