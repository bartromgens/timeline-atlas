import logging
from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand

from api.events.event_category import update_categories_from_wikidata
from api.events.models import Category, Event

if TYPE_CHECKING:
    from django.db.models import QuerySet


class Command(BaseCommand):
    help = (
        "Set event category: from Wikidata (P361 part-of) when no category_qid is given, "
        "or assign all to the given category QID."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "category_qid",
            nargs="?",
            default=None,
            help=(
                "If set, assign all matching events to this category QID. "
                "If omitted, determine category from each event's Wikidata P361 (part of)."
            ),
        )
        parser.add_argument(
            "--event-qids",
            nargs="*",
            metavar="QID",
            help="Only update these event wikidata IDs. If omitted, all events are updated.",
        )
        parser.add_argument(
            "--only-unset",
            action="store_true",
            help="Only update events that currently have no category.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="When determining from Wikidata: only report what would be done.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Batch size for Wikidata SPARQL requests (default 50).",
        )

    def handle(self, *args, **options):
        category_qid = options["category_qid"]
        event_qids = options["event_qids"]
        only_unset = options["only_unset"]
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        qs = Event.objects.all()
        if event_qids is not None and len(event_qids) > 0:
            qs = qs.filter(wikidata_id__in=event_qids)
        if only_unset:
            qs = qs.filter(category__isnull=True)

        if category_qid is not None:
            self._assign_category(qs, category_qid)
        else:
            self._determine_from_wikidata(qs, dry_run, batch_size)

    def _assign_category(self, qs: "QuerySet[Event]", category_qid: str) -> None:
        try:
            category = Category.objects.get(wikidata_id=category_qid)
        except Category.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    f"Category with wikidata_id={category_qid!r} not found."
                )
            )
            return
        count = qs.update(category=category)
        self.stdout.write(
            self.style.SUCCESS(f"Updated category to {category} for {count} event(s).")
        )

    def _determine_from_wikidata(
        self,
        qs,
        dry_run: bool,
        batch_size: int,
    ) -> None:
        events = list(qs.only("pk", "wikidata_id", "category_id"))
        if not events:
            self.stdout.write("No events to update.")
            return

        categories_by_qid = {
            c.wikidata_id: c for c in Category.objects.only("pk", "wikidata_id")
        }
        if not categories_by_qid:
            self.stderr.write(
                self.style.ERROR("No categories in database to match against.")
            )
            return

        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s: %(message)s",
        )
        event_qids = [e.wikidata_id for e in events if e.wikidata_id]
        self.stdout.write(
            f"Fetching P361 (part of) from Wikidata for {len(event_qids)} event(s)..."
        )
        updated, already_correct, no_match = update_categories_from_wikidata(
            qs, batch_size=batch_size, dry_run=dry_run
        )
        matched = updated + already_correct

        if dry_run:
            self.stdout.write(
                f"{matched} event(s) would match a category; "
                f"{already_correct} already correct, {updated} would be updated."
            )
        else:
            self.stdout.write(
                f"{matched} event(s) matched a category in the DB; "
                f"{already_correct} already had the correct category."
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated category for {updated} event(s) from Wikidata."
                )
            )
        if no_match:
            self.stdout.write(
                f"No matching category in DB for {len(no_match)} event(s): "
                f"{', '.join(no_match[:10])}{'...' if len(no_match) > 10 else ''}"
            )
