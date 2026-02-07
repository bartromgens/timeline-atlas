from django.contrib import admin
from django.db.models import Q

from api.events.models import Event


class HasCoordsFilter(admin.SimpleListFilter):
    title = "has coordinates"
    parameter_name = "has_coords"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                location_lat__isnull=False, location_lon__isnull=False
            )
        if self.value() == "no":
            return queryset.filter(
                Q(location_lat__isnull=True) | Q(location_lon__isnull=True)
            )
        return queryset


def _date_display(obj: Event, field: str) -> str:
    d = getattr(obj, field, None) or {}
    if not d:
        return "—"
    val = d.get("value", "")
    res = d.get("resolution", "")
    return f"{val} ({res})" if res else val


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "wikidata_id",
        "title",
        "sort_date",
        "date_point_in_time",
        "date_start_end",
        "location_name",
        "has_coords",
        "sitelink_count",
        "pageviews_30d",
        "backlink_count",
    ]
    list_display_links = ["wikidata_id", "title"]
    list_filter = [HasCoordsFilter]
    list_per_page = 50
    search_fields = ["title", "description", "wikidata_id", "wikipedia_title"]
    readonly_fields = [
        "wikidata_id",
        "wikidata_url",
        "wikipedia_url",
        "wikipedia_title",
        "point_in_time",
        "start_time",
        "end_time",
    ]

    fieldsets = (
        (None, {"fields": ("title", "description", "wikidata_id", "wikidata_url")}),
        (
            "Dates",
            {
                "fields": ("sort_date", "point_in_time", "start_time", "end_time"),
            },
        ),
        (
            "Location",
            {"fields": ("location_name", "location_qid", "location_lat", "location_lon")},
        ),
        (
            "Wikipedia",
            {"fields": ("wikipedia_url", "wikipedia_title")},
        ),
        (
            "Metrics",
            {"fields": ("sitelink_count", "pageviews_30d", "backlink_count")},
        ),
    )

    @admin.display(boolean=True, description="Coords")
    def has_coords(self, obj: Event) -> bool:
        return obj.location_lat is not None and obj.location_lon is not None

    @admin.display(description="Point in time")
    def date_point_in_time(self, obj: Event) -> str:
        return _date_display(obj, "point_in_time")

    @admin.display(description="Start / End")
    def date_start_end(self, obj: Event) -> str:
        s = _date_display(obj, "start_time")
        e = _date_display(obj, "end_time")
        if s == "—" and e == "—":
            return "—"
        return f"{s} → {e}"
