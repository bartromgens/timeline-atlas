import logging
import sys

from django.core.management.base import BaseCommand

from api.events.wikidata import EventLoader


class Command(BaseCommand):
    help = "Extract events from a Wikidata category or type and load them into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "category_qid",
            nargs="?",
            default="Q362",
            help="Wikidata QID: 'part of' category (e.g. Q362 World War II) or type (e.g. Q69502940 polar expedition). Default: Q362.",
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
            "--limit",
            type=int,
            default=50,
            help="Max number of events to fetch (default 50).",
        )
        parser.add_argument(
            "--no-pageviews",
            action="store_true",
            help="Skip fetching pageviews and backlinks (faster, values stay 0).",
        )

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s: %(message)s",
        )
        loader = EventLoader()
        created, updated, errors = loader.load(
            category_qid=options["category_qid"],
            start_year=options["start_year"],
            end_year=options["end_year"],
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
