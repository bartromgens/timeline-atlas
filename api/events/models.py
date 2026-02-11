from __future__ import annotations

from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=500, blank=True)
    wikidata_id = models.CharField(max_length=20, unique=True)
    wikidata_url = models.URLField(max_length=500, blank=True)
    instance_of = models.JSONField(default=list, blank=True)
    subclass_of = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return self.name or self.wikidata_id

    class Meta:
        verbose_name_plural = "categories"


class EventType(models.Model):
    name = models.CharField(max_length=500, blank=True)
    wikidata_id = models.CharField(max_length=20, unique=True)
    wikidata_url = models.URLField(max_length=500, blank=True)

    def __str__(self) -> str:
        return self.name or self.wikidata_id

    class Meta:
        verbose_name_plural = "event types"


class EventTypeLoadProgress(models.Model):
    """Tracks when a (event_type, year_start, year_end) batch was last loaded."""

    event_type = models.ForeignKey(
        EventType,
        on_delete=models.CASCADE,
        related_name="load_progress",
    )
    year_start = models.IntegerField()
    year_end = models.IntegerField()
    last_updated_at = models.DateTimeField()
    events_created = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event_type", "year_start", "year_end"],
                name="events_eventtypeloadprogress_unique_batch",
            )
        ]
        verbose_name_plural = "event type load progress"


class EventQuerySet(models.QuerySet["Event"]):
    def in_date_range(
        self,
        start_iso: str | None = None,
        end_iso: str | None = None,
    ) -> "EventQuerySet":
        qs = self
        if start_iso:
            qs = qs.filter(sort_date__gte=start_iso)
        if end_iso:
            qs = qs.filter(sort_date__lte=end_iso)
        return qs


class EventManager(models.Manager["Event"]):
    def get_queryset(self) -> EventQuerySet:
        return EventQuerySet(self.model, using=self._db)


class Event(models.Model):
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.ForeignKey(
        EventType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    title = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)

    point_in_time = models.JSONField(null=True, blank=True)
    start_time = models.JSONField(null=True, blank=True)
    end_time = models.JSONField(null=True, blank=True)

    location_name = models.CharField(max_length=500, blank=True)
    location_qid = models.CharField(max_length=20, blank=True)
    location_lat = models.FloatField(null=True, blank=True)
    location_lon = models.FloatField(null=True, blank=True)

    wikidata_id = models.CharField(max_length=20, unique=True)
    wikidata_url = models.URLField(max_length=500, blank=True)
    wikipedia_url = models.URLField(max_length=500, blank=True)
    wikipedia_title = models.CharField(max_length=500, blank=True)
    wikipedia_extract = models.TextField(blank=True)

    sitelink_count = models.PositiveIntegerField(default=0)
    pageviews_30d = models.PositiveIntegerField(default=0)
    backlink_count = models.PositiveIntegerField(default=0)

    sort_date = models.CharField(max_length=32, blank=True, db_index=True)
    importance_score = models.FloatField(null=True, blank=True, db_index=True)

    created_datetime = models.DateTimeField(auto_now_add=True, null=True)
    updated_datetime = models.DateTimeField(auto_now=True, null=True)

    objects = EventManager()

    class Meta:
        ordering = ["sort_date", "wikidata_id"]
