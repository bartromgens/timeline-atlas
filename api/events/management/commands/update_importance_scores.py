from django.core.management.base import BaseCommand

from api.events.importance import get_scorer
from api.events.models import Event


class Command(BaseCommand):
    help = "Recompute and save importance scores for all events (e.g. after changing weights)."

    def handle(self, *args, **options):
        scorer = get_scorer()
        events = list(
            Event.objects.all().only(
                "pk",
                "sitelink_count",
                "pageviews_30d",
                "backlink_count",
                "importance_score",
            )
        )
        for event in events:
            event.importance_score = scorer.score_from_values(
                sitelink_count=event.sitelink_count or 0,
                pageviews_30d=event.pageviews_30d or 0,
                backlink_count=event.backlink_count or 0,
            )
        Event.objects.bulk_update(events, ["importance_score"])
        self.stdout.write(
            self.style.SUCCESS(f"Updated importance_score for {len(events)} events.")
        )
