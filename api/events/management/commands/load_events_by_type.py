import logging
import sys
from datetime import datetime

from django.core.management.base import BaseCommand

from api.events.models import EventType
from api.events.wikidata import EventLoader
from api.events.wikidata.sparql import (
    DEFAULT_MIN_SITELINKS,
    HISTORICAL_EVENT_TYPES,
)

YEAR_BATCH_SIZE = 50
DEFAULT_ALL_START_YEAR = -3000

_TYPE_SUGGESTIONS = ", ".join(
    f"{t['qid']}={t['label']}" for t in HISTORICAL_EVENT_TYPES
)
_TYPE_HELP = (
    "One event type (QID or label). Omit when using --all. "
    "Suggestions: " + _TYPE_SUGGESTIONS
)


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


def _year_ranges(
    start_year: int, end_year: int, batch_size: int
) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    current = start_year
    while current <= end_year:
        batch_end = min(current + batch_size - 1, end_year)
        ranges.append((current, batch_end))
        current = batch_end + 1
    return ranges


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
            default=None,
            help=_TYPE_HELP,
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="load_all",
            help=(
                "Load all event types in batches: one type per batch, "
                "50-year year ranges per batch. Ignores --type."
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
            default=2000,
            help="Max number of events to fetch (default 2000).",
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

        if options["load_all"]:
            self._handle_all(options)
        else:
            self._handle_single(options)

    def _handle_single(self, options: dict) -> None:
        raw = options["type_qid"]
        if not raw:
            self.stderr.write(
                self.style.ERROR(
                    "Specify exactly one event type with --type, or use --all "
                    "to load all event types."
                )
            )
            sys.exit(1)
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

    def _handle_all(self, options: dict) -> None:
        if options["type_qid"]:
            self.stdout.write(self.style.WARNING("--all is set; ignoring --type."))
        start_year = (
            options["start_year"]
            if options["start_year"] is not None
            else DEFAULT_ALL_START_YEAR
        )
        end_year = (
            options["end_year"]
            if options["end_year"] is not None
            else datetime.now().year
        )
        year_ranges = _year_ranges(start_year, end_year, YEAR_BATCH_SIZE)

        loader = EventLoader()
        total_created = 0
        total_updated = 0
        all_errors: list[tuple[str, str, str]] = []

        for type_info in HISTORICAL_EVENT_TYPES:
            qid = type_info["qid"]
            label = type_info["label"]
            event_type = _get_or_create_event_type(qid, label)

            for batch_start, batch_end in year_ranges:
                created, updated, errors = loader.load_by_type(
                    type_qids=[qid],
                    event_type=event_type,
                    start_year=batch_start,
                    end_year=batch_end,
                    min_sitelinks=options["min_sitelinks"],
                    limit=options["limit"],
                    fetch_pageviews_backlinks=not options["no_pageviews"],
                )
                total_created += created
                total_updated += updated
                all_errors.extend(errors)

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded all types: {total_created} created, "
                f"{total_updated} updated."
            )
        )
        if all_errors:
            self.stderr.write("Events with fetch errors (pageviews/backlinks):\n")
            for label_or_id, fetch_type, msg in all_errors:
                self.stderr.write(f"  {label_or_id} ({fetch_type}): {msg}\n")
            sys.stderr.flush()
