from rest_framework import serializers

from api.events.models import Event


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
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
            "sitelink_count",
            "pageviews_30d",
            "backlink_count",
            "sort_date",
            "importance_score",
        ]
        read_only_fields = fields
