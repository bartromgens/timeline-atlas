import logging
import sys

from django.core.management.base import BaseCommand

from api.events.models import EventType
from api.events.wikidata import EventLoader
from api.events.wikidata.sparql import (
    DEFAULT_MIN_SITELINKS,
    HISTORICAL_EVENT_TYPES,
)

_TYPE_SUGGESTIONS = ", ".join(
    f"{t['qid']}={t['label']}" for t in HISTORICAL_EVENT_TYPES
)
_TYPE_HELP = "Exactly one event type (QID or label). Suggestions: " + _TYPE_SUGGESTIONS


def _resolve_type(value: str) -> tuple[str, str] | None:
    value = (value or "").strip()
    if not value:
        return None
    if value.startswith("Q") and value[1:].isdigit():
        label = next(
            (t["label"] for t in HISTORICAL_EVENT_TYPES if t["qid"] == value),
            value,
        )
        return (value, label)
    lower = value.lower()
    for t in HISTORICAL_EVENT_TYPES:
        if t["label"] == lower:
            return (t["qid"], t["label"])
    return None


def _get_or_create_event_type(qid: str, label: str) -> EventType:
    return EventType.objects.get_or_create(
        wikidata_id=qid,
        defaults={
            "name": label,
            "wikidata_url": f"https://www.wikidata.org/wiki/{qid}",
        },
    )[0]


class Command(BaseCommand):
    help = (
        "Discover important historical events from Wikidata by event type "
        "(war, battle, treaty, etc.) and load them into the database. "
        "One event type per run to avoid query timeouts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            dest="type_qid",
            metavar="QID_OR_LABEL",
            required=True,
            help=_TYPE_HELP,
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

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s: %(message)s",
        )

        raw = options["type_qid"]
        resolved = _resolve_type(raw)
        if not resolved:
            self.stderr.write(
                self.style.ERROR(
                    f"Unknown event type: {raw!r}. Use a QID (e.g. Q198) or a "
                    "label from the suggestions in --help."
                )
            )
            sys.exit(1)
        qid, label = resolved
        event_type = _get_or_create_event_type(qid, label)

        loader = EventLoader()
        created, updated, errors = loader.load_by_type(
            type_qids=[qid],
            event_type=event_type,
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
