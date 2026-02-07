from django.contrib import admin
from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape, format_html

from api.events.models import Category, Event


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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "wikidata_id",
        "instance_of_display",
        "subclass_of_display",
        "event_count",
    ]
    list_display_links = ["name", "wikidata_id"]
    search_fields = ["name", "wikidata_id"]
    readonly_fields = ["wikidata_id", "wikidata_url", "instance_of", "subclass_of"]

    @admin.display(description="Instance of")
    def instance_of_display(self, obj: Category) -> str:
        return _json_property_display(obj.instance_of)

    @admin.display(description="Subclass of")
    def subclass_of_display(self, obj: Category) -> str:
        return _json_property_display(obj.subclass_of)

    @admin.display(description="Events")
    def event_count(self, obj: Category) -> int:
        return obj.events.count()


def _json_property_display(items: list) -> str:
    if not items:
        return "—"
    parts = [f"{x.get('label', '') or x.get('qid', '')}" for x in items]
    return ", ".join(parts)[:200] + ("..." if len(", ".join(parts)) > 200 else "")


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
        "wikidata_link",
        "title_link",
        "category_link",
        "sort_date",
        "date_point_in_time",
        "date_start_end",
        "location_name",
        "has_coords",
        "importance_score",
        "sitelink_count",
        "pageviews_30d",
        "backlink_count",
    ]
    list_display_links = ["wikidata_id"]
    list_filter = [HasCoordsFilter]
    list_per_page = 50
    search_fields = [
        "title",
        "category__name",
        "description",
        "wikidata_id",
        "wikipedia_title",
    ]
    readonly_fields = [
        "wikidata_id",
        "wikidata_url",
        "wikipedia_url",
        "wikipedia_title",
        "point_in_time",
        "start_time",
        "end_time",
        "importance_score",
    ]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "description",
                    "category",
                    "wikidata_id",
                    "wikidata_url",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": ("sort_date", "point_in_time", "start_time", "end_time"),
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "location_name",
                    "location_qid",
                    "location_lat",
                    "location_lon",
                )
            },
        ),
        (
            "Wikipedia",
            {"fields": ("wikipedia_url", "wikipedia_title")},
        ),
        (
            "Metrics",
            {
                "fields": (
                    "sitelink_count",
                    "pageviews_30d",
                    "backlink_count",
                    "importance_score",
                )
            },
        ),
    )

    @admin.display(description="Category")
    def category_link(self, obj: Event) -> str:
        if not obj.category_id:
            return "—"
        url = reverse("admin:events_category_change", args=[obj.category_id])
        label = escape(obj.category.name or obj.category.wikidata_id)
        return format_html('<a href="{}">{}</a>', url, label)

    @admin.display(boolean=True, description="Coords")
    def has_coords(self, obj: Event) -> bool:
        return obj.location_lat is not None and obj.location_lon is not None

    @admin.display(description="Wikidata")
    def wikidata_link(self, obj: Event) -> str:
        if not obj.wikidata_url:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            obj.wikidata_url,
            escape(obj.wikidata_id),
        )

    @admin.display(description="Title")
    def title_link(self, obj: Event) -> str:
        title = obj.title or "—"
        if obj.wikipedia_url:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">{}</a>',
                obj.wikipedia_url,
                escape(title),
            )
        return title

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
