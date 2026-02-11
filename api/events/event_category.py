from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from api.events.models import Category, Event
from api.events.wikidata.sparql import WikidataSparqlClient

if TYPE_CHECKING:
    from django.db.models import QuerySet


def resolve_category_from_part_of(
    part_of_qids: list[str],
    categories_by_qid: dict[str, Category],
    exclude_qid: str | None = None,
) -> Category | None:
    for qid in part_of_qids:
        if qid == exclude_qid:
            continue
        if qid in categories_by_qid:
            return categories_by_qid[qid]
    return None


def update_categories_from_wikidata(
    qs: "QuerySet[Event]",
    batch_size: int = 50,
    dry_run: bool = False,
) -> tuple[int, int, list[str]]:
    """
    Set event category from Wikidata P361 (part of). Returns
    (updated_count, already_correct_count, no_match_qids).
    When dry_run is True, no DB updates are performed.
    """
    events = list(qs.only("pk", "wikidata_id", "category_id"))
    if not events:
        return 0, 0, []

    categories_by_qid = {
        c.wikidata_id: c for c in Category.objects.only("pk", "wikidata_id")
    }
    if not categories_by_qid:
        return 0, 0, []

    client = WikidataSparqlClient()
    event_qids = [e.wikidata_id for e in events if e.wikidata_id]
    part_of_map = client.fetch_events_part_of(event_qids, batch_size=batch_size)

    to_update: list[tuple[int, Category]] = []
    no_match: list[str] = []
    already_correct = 0
    for event in events:
        qid = event.wikidata_id
        if not qid:
            continue
        part_of = part_of_map.get(qid, [])
        category = resolve_category_from_part_of(
            part_of, categories_by_qid, exclude_qid=qid
        )
        if category is not None:
            if event.category_id != category.pk:
                to_update.append((event.pk, category))
            else:
                already_correct += 1
        else:
            no_match.append(qid)

    if not dry_run:
        with transaction.atomic():
            for pk, category in to_update:
                Event.objects.filter(pk=pk).update(category=category)

    return len(to_update), already_correct, no_match
