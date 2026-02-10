import logging
from typing import Any

from django.db import transaction

from api.events.importance import get_scorer
from api.events.models import Category, Event
from api.events.wikidata.pageviews_backlinks import PageviewsBacklinksFetcher
from api.events.wikidata.sparql import WikidataSparqlClient

logger = logging.getLogger(__name__)


def _event_dict_to_model_data(
    data: dict[str, Any],
    category: Category | None = None,
) -> dict[str, Any]:
    sort_date = (data.get("_sort_date") or "")[:32]
    sitelink_count = data.get("sitelink_count") or 0
    pageviews_30d = data.get("pageviews_30d") or 0
    backlink_count = data.get("backlink_count") or 0
    importance_score = get_scorer().score_from_values(
        sitelink_count, pageviews_30d, backlink_count
    )
    return {
        "category": category,
        "title": (data.get("label") or "")[:500],
        "description": (data.get("description") or "")[:50000],
        "point_in_time": data.get("point_in_time"),
        "start_time": data.get("start_time"),
        "end_time": data.get("end_time"),
        "location_name": (data.get("location_name") or "")[:500],
        "location_qid": (data.get("location_qid") or "")[:20],
        "location_lat": data.get("location_lat"),
        "location_lon": data.get("location_lon"),
        "wikidata_id": data.get("wikidata_id") or "",
        "wikidata_url": (data.get("wikidata_url") or "")[:500],
        "wikipedia_url": (data.get("wikipedia_url") or "")[:500],
        "wikipedia_title": (data.get("wikipedia_title") or "")[:500],
        "sitelink_count": sitelink_count,
        "pageviews_30d": pageviews_30d,
        "backlink_count": backlink_count,
        "sort_date": sort_date,
        "importance_score": importance_score,
    }


class EventLoader:
    def __init__(
        self,
        sparql_client: WikidataSparqlClient | None = None,
        pageviews_fetcher: PageviewsBacklinksFetcher | None = None,
    ) -> None:
        self.sparql_client = sparql_client or WikidataSparqlClient()
        self.pageviews_fetcher = pageviews_fetcher or PageviewsBacklinksFetcher()

    def _fetch_pageviews_backlinks(
        self,
        events_data: list[dict[str, Any]],
    ) -> list[tuple[str, str, str]]:
        errors: list[tuple[str, str, str]] = []
        total = len(events_data)
        last_logged_pct = -1
        with_title = sum(1 for e in events_data if e.get("wikipedia_title"))
        logger.info(
            "Fetching pageviews and backlinks for %d events with "
            "Wikipedia title (of %d total)",
            with_title,
            total,
        )
        for i, e in enumerate(events_data):
            pct = (i + 1) * 100 // total if total else 0
            if pct != last_logged_pct and pct % 10 == 0:
                logger.info(
                    "Pageviews/backlinks: %d%% (%d/%d)",
                    pct,
                    i + 1,
                    total,
                )
                last_logged_pct = pct
            title = e.get("wikipedia_title")
            if not title:
                e["pageviews_30d"] = 0
                e["backlink_count"] = 0
                continue
            label_or_id = e.get("label") or e.get("wikidata_id") or "?"
            try:
                pv, bl = self.pageviews_fetcher.fetch_for_event(title)
                e["pageviews_30d"] = pv
                e["backlink_count"] = bl
            except Exception as err:
                errors.append((label_or_id, "pageviews/backlinks", str(err)))
                logger.warning(
                    "Event %r: pageviews/backlinks fetch failed: %s",
                    label_or_id,
                    err,
                )
                e["pageviews_30d"] = 0
                e["backlink_count"] = 0
        return errors

    @staticmethod
    def _save_events(
        events_data: list[dict[str, Any]],
        category: Category | None = None,
    ) -> tuple[int, int]:
        created = 0
        updated = 0
        with transaction.atomic():
            for data in events_data:
                qid = data.get("wikidata_id")
                if not qid:
                    continue
                payload = _event_dict_to_model_data(data, category=category)
                _, was_created = Event.objects.update_or_create(
                    wikidata_id=qid,
                    defaults=payload,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
        return created, updated

    def load(
        self,
        category_qid: str,
        start_year: int | None = None,
        end_year: int | None = None,
        limit: int = 50,
        fetch_pageviews_backlinks: bool = True,
    ) -> tuple[int, int, list[tuple[str, str, str]]]:
        props = self.sparql_client.fetch_category_properties(category_qid)
        category_name = (props.get("label") or "")[:500]
        if category_name:
            logger.info(
                "Category %s: %s (instance_of=%d, subclass_of=%d)",
                category_qid,
                category_name,
                len(props.get("instance_of") or []),
                len(props.get("subclass_of") or []),
            )
        category_obj, _ = Category.objects.update_or_create(
            wikidata_id=category_qid,
            defaults={
                "name": category_name,
                "wikidata_url": f"https://www.wikidata.org/wiki/{category_qid}",
                "instance_of": props.get("instance_of") or [],
                "subclass_of": props.get("subclass_of") or [],
            },
        )
        events_data = self.sparql_client.run_query(
            category_qid=category_qid,
            start_year=start_year,
            end_year=end_year,
            limit=limit,
        )
        errors: list[tuple[str, str, str]] = []
        if fetch_pageviews_backlinks:
            errors = self._fetch_pageviews_backlinks(events_data)
        created, updated = self._save_events(events_data, category=category_obj)
        logger.info(
            "Loaded events: %d created, %d updated, %d fetch errors",
            created,
            updated,
            len(errors),
        )
        return created, updated, errors

    def load_by_type(
        self,
        type_qids: list[str] | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        min_sitelinks: int = 20,
        limit: int = 500,
        fetch_pageviews_backlinks: bool = True,
    ) -> tuple[int, int, list[tuple[str, str, str]]]:
        events_data = self.sparql_client.run_type_discovery_query(
            type_qids=type_qids,
            start_year=start_year,
            end_year=end_year,
            min_sitelinks=min_sitelinks,
            limit=limit,
        )
        errors: list[tuple[str, str, str]] = []
        if fetch_pageviews_backlinks:
            errors = self._fetch_pageviews_backlinks(events_data)
        created, updated = self._save_events(events_data, category=None)
        logger.info(
            "Loaded events by type: %d created, %d updated, %d fetch errors",
            created,
            updated,
            len(errors),
        )
        return created, updated, errors
