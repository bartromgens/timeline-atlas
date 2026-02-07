"""Tests for Wikidata extraction and storage in Event model."""

from unittest.mock import MagicMock

from django.test import TestCase

from api.events.models import Category, Event
from api.events.wikidata.loader import EventLoader

# Stub data from real Wikidata API responses (fetch_category_properties + run_query for Q362, limit=2).
STUB_CATEGORY_LABEL = "World War II"
STUB_CATEGORY_PROPS = {
    "label": STUB_CATEGORY_LABEL,
    "instance_of": [{"qid": "Q198", "label": "historical period"}],
    "subclass_of": [],
}

STUB_EVENTS_RUN_QUERY = [
    {
        "wikidata_id": "Q133696273",
        "wikidata_url": "https://www.wikidata.org/wiki/Q133696273",
        "label": "Skirmish at Tegalreja",
        "description": "1825 skirmish",
        "point_in_time": {"value": "1825-07-20T00:00:00Z", "resolution": "day"},
        "start_time": None,
        "end_time": None,
        "location_name": "Yogyakarta Sultanate",
        "location_qid": "Q2114397",
        "location_lat": None,
        "location_lon": None,
        "wikipedia_url": "https://en.wikipedia.org/wiki/Skirmish_at_Tegalreja",
        "wikipedia_title": "Skirmish_at_Tegalreja",
        "sitelink_count": 2,
        "_sort_date": "1825-07-20T00:00:00Z",
    },
    {
        "wikidata_id": "Q133287944",
        "wikidata_url": "https://www.wikidata.org/wiki/Q133287944",
        "label": "Attack on Selarong",
        "description": "1825 battle",
        "point_in_time": None,
        "start_time": {"value": "1825-07-25T00:00:00Z", "resolution": "day"},
        "end_time": {"value": "1825-11-04T00:00:00Z", "resolution": "day"},
        "location_name": "Selarong Cave",
        "location_qid": "Q7343030",
        "location_lat": -7.871682,
        "location_lon": 110.2951364,
        "wikipedia_url": "https://en.wikipedia.org/wiki/Attack_on_Selarong",
        "wikipedia_title": "Attack_on_Selarong",
        "sitelink_count": 2,
        "_sort_date": "1825-07-25T00:00:00Z",
    },
]


class EventLoaderStubbedTest(TestCase):
    def test_load_extracts_wikidata_and_stores_events(self) -> None:
        sparql_client = MagicMock()
        sparql_client.fetch_category_properties.return_value = STUB_CATEGORY_PROPS
        sparql_client.run_query.return_value = STUB_EVENTS_RUN_QUERY.copy()

        pageviews_fetcher = MagicMock()
        pageviews_fetcher.fetch_for_event.return_value = (100, 25)

        loader = EventLoader(
            sparql_client=sparql_client,
            pageviews_fetcher=pageviews_fetcher,
        )
        created, updated, errors = loader.load(
            category_qid="Q362",
            limit=50,
            fetch_pageviews_backlinks=True,
        )

        self.assertEqual(created, 2)
        self.assertEqual(updated, 0)
        self.assertEqual(errors, [])

        sparql_client.fetch_category_properties.assert_called_once_with("Q362")
        sparql_client.run_query.assert_called_once_with(
            category_qid="Q362",
            start_year=None,
            end_year=None,
            limit=50,
        )
        self.assertEqual(pageviews_fetcher.fetch_for_event.call_count, 2)

        events = list(Event.objects.order_by("sort_date"))
        self.assertEqual(len(events), 2)

        e0 = events[0]
        self.assertEqual(e0.wikidata_id, "Q133696273")
        self.assertEqual(e0.title, "Skirmish at Tegalreja")
        self.assertEqual(e0.description, "1825 skirmish")
        self.assertIsNotNone(e0.category)
        self.assertEqual(e0.category.name, STUB_CATEGORY_LABEL)
        self.assertEqual(e0.category.wikidata_id, "Q362")
        self.assertEqual(e0.category.instance_of, STUB_CATEGORY_PROPS["instance_of"])
        self.assertEqual(e0.sort_date, "1825-07-20T00:00:00Z")
        self.assertEqual(e0.location_name, "Yogyakarta Sultanate")
        self.assertEqual(e0.location_qid, "Q2114397")
        self.assertIsNone(e0.location_lat)
        self.assertIsNone(e0.location_lon)
        self.assertEqual(e0.wikipedia_title, "Skirmish_at_Tegalreja")
        self.assertEqual(e0.sitelink_count, 2)
        self.assertEqual(e0.pageviews_30d, 100)
        self.assertEqual(e0.backlink_count, 25)
        self.assertIsNotNone(e0.importance_score)

        e1 = events[1]
        self.assertEqual(e1.wikidata_id, "Q133287944")
        self.assertEqual(e1.title, "Attack on Selarong")
        self.assertEqual(e1.location_lat, -7.871682)
        self.assertEqual(e1.location_lon, 110.2951364)
        self.assertEqual(e1.sort_date, "1825-07-25T00:00:00Z")

    def test_load_updates_existing_event_by_wikidata_id(self) -> None:
        sparql_client = MagicMock()
        sparql_client.fetch_category_properties.return_value = {
            "label": "Category",
            "instance_of": [],
            "subclass_of": [],
        }
        one_event = [STUB_EVENTS_RUN_QUERY[0].copy()]
        sparql_client.run_query.return_value = one_event

        pageviews_fetcher = MagicMock()
        pageviews_fetcher.fetch_for_event.return_value = (0, 0)

        loader = EventLoader(
            sparql_client=sparql_client,
            pageviews_fetcher=pageviews_fetcher,
        )
        created1, _, _ = loader.load(
            category_qid="Q362",
            limit=1,
            fetch_pageviews_backlinks=False,
        )
        self.assertEqual(created1, 1)
        event = Event.objects.get(wikidata_id="Q133696273")
        self.assertEqual(event.title, "Skirmish at Tegalreja")

        one_event[0]["label"] = "Skirmish at Tegalreja (updated)"
        sparql_client.run_query.return_value = one_event
        created2, updated2, _ = loader.load(
            category_qid="Q362",
            limit=1,
            fetch_pageviews_backlinks=False,
        )
        self.assertEqual(created2, 0)
        self.assertEqual(updated2, 1)
        event.refresh_from_db()
        self.assertEqual(event.title, "Skirmish at Tegalreja (updated)")
