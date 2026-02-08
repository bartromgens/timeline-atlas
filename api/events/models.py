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

    objects = EventManager()

    class Meta:
        ordering = ["sort_date", "wikidata_id"]
