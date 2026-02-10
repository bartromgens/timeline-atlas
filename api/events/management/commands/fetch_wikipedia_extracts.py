import logging

from django.core.management.base import BaseCommand

from api.events.models import Event
from api.events.wikidata.wikipedia_extract import fetch_wikipedia_extract

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch and store the first paragraph from Wikipedia for events."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help=(
                "Refresh extract for all events with a Wikipedia link "
                "(default: only events missing extract)."
            ),
        )

    def handle(self, *args, **options):
        qs = Event.objects.filter(wikipedia_url__isnull=False).exclude(wikipedia_url="")
        if not options["all"]:
            qs = qs.filter(wikipedia_extract="")
        qs = qs.order_by("-importance_score")
        events = list(qs.only("id", "wikipedia_url", "wikipedia_extract"))
        updated = 0
        failed = 0
        for event in events:
            extract = fetch_wikipedia_extract(event.wikipedia_url)
            if extract is not None:
                event.wikipedia_extract = extract
                event.save(update_fields=["wikipedia_extract"])
                logger.info(
                    "Event id=%s: extract saved for %s",
                    event.id,
                    event.wikipedia_url,
                )
                updated += 1
            else:
                failed += 1
        self.stdout.write(
            self.style.SUCCESS(f"Fetched {updated} extracts; {failed} failed or empty.")
        )
