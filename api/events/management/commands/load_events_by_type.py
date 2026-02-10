import logging
import sys

from django.core.management.base import BaseCommand

from api.events.wikidata import EventLoader
from api.events.wikidata.sparql import (
    DEFAULT_MIN_SITELINKS,
    HISTORICAL_EVENT_TYPES,
)


class Command(BaseCommand):
    help = (
        "Discover important historical events from Wikidata by event type "
        "(war, battle, treaty, etc.) and load them into the database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--types",
            nargs="*",
            default=None,
            help=(
                "Wikidata QIDs of event types to query "
                "(e.g. Q198 Q178561). Defaults to a curated list of "
                "historical event types."
            ),
        )
        parser.add_argument(
            "--start-year",
            type=int,
            default=None,
            help="Filter events from this year (inclusive).",
        )
        parser.add_argument(
            "--end-year",
            type=int,
            default=None,
            help="Filter events until this year (inclusive).",
        )
        parser.add_argument(
            "--min-sitelinks",
            type=int,
            default=DEFAULT_MIN_SITELINKS,
            help=(
                f"Minimum sitelink count for importance filtering "
                f"(default {DEFAULT_MIN_SITELINKS})."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Max number of events to fetch (default 500).",
        )
        parser.add_argument(
            "--no-pageviews",
            action="store_true",
            help="Skip fetching pageviews and backlinks (faster, values stay 0).",
        )
        parser.add_argument(
            "--list-types",
            action="store_true",
            help="List the default event types and exit.",
        )

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s: %(message)s",
        )

        if options["list_types"]:
            self.stdout.write("Default historical event types:")
            for t in HISTORICAL_EVENT_TYPES:
                self.stdout.write(f"  {t['qid']:>12s}  {t['label']}")
            return

        loader = EventLoader()
        created, updated, errors = loader.load_by_type(
            type_qids=options["types"],
            start_year=options["start_year"],
            end_year=options["end_year"],
            min_sitelinks=options["min_sitelinks"],
            limit=options["limit"],
            fetch_pageviews_backlinks=not options["no_pageviews"],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Loaded: {created} created, {updated} updated.")
        )
        if errors:
            self.stderr.write("Events with fetch errors (pageviews/backlinks):\n")
            for label_or_id, fetch_type, msg in errors:
                self.stderr.write(f"  {label_or_id} ({fetch_type}): {msg}\n")
            sys.stderr.flush()
