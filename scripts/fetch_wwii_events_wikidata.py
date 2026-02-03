#!/usr/bin/env python3

import argparse
import json
import re

from SPARQLWrapper import SPARQLWrapper, JSON


WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WWII_QID = "Q362"


def build_query(start_year: int | None, end_year: int | None, limit: int) -> str:
    year_filter = ""
    if start_year is not None or end_year is not None:
        parts = ["BOUND(?date)"]
        if start_year is not None:
            parts.append(f"YEAR(?date) >= {start_year}")
        if end_year is not None:
            parts.append(f"YEAR(?date) <= {end_year}")
        year_filter = " FILTER(" + " && ".join(parts) + ")"

    return f"""
PREFIX schema: <http://schema.org/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT DISTINCT ?item ?itemLabel ?itemDescription ?date ?location ?locationLabel ?article
WHERE {{
  ?item wdt:P361* wd:{WWII_QID} .
  OPTIONAL {{
    {{ ?item wdt:P585 ?date . }} UNION {{ ?item wdt:P580 ?date . }}
    UNION {{ ?item p:P361/pq:P585 ?date . }}
  }}
  OPTIONAL {{ ?item wdt:P276 ?location . }}
  OPTIONAL {{
    ?article schema:about ?item .
    ?article schema:inLanguage "en" .
    ?article schema:isPartOf <https://en.wikipedia.org/> .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
  {year_filter}
}}
ORDER BY DESC(BOUND(?date)) ASC(?date)
LIMIT {limit}
"""


def extract_wikidata_id(uri: str) -> str | None:
    if not uri:
        return None
    m = re.search(r"entity/(Q\d+)$", uri)
    return m.group(1) if m else None


def extract_wikipedia_title(url: str) -> str | None:
    if not url:
        return None
    if "/wiki/" not in url:
        return None
    path = url.split("/wiki/", 1)[-1]
    return path.split("#")[0] or None


def run_query(
    start_year: int | None = None,
    end_year: int | None = None,
    limit: int = 50,
) -> list[dict]:
    sparql = SPARQLWrapper(WIKIDATA_SPARQL)
    sparql.setQuery(build_query(start_year, end_year, limit))
    sparql.setReturnFormat(JSON)
    raw = sparql.query().convert()

    rows = raw.get("results", {}).get("bindings", [])
    events = []
    seen = set()
    for row in rows:
        item_uri = row.get("item", {}).get("value", "")
        qid = extract_wikidata_id(item_uri)
        if qid and qid in seen:
            continue
        if qid:
            seen.add(qid)
        date_val = row.get("date", {}).get("value") if row.get("date") else None
        article_val = row.get("article", {}).get("value") if row.get("article") else None
        wikidata_url = f"https://www.wikidata.org/wiki/{qid}" if qid else None
        events.append(
            {
                "wikidata_id": qid,
                "wikidata_url": wikidata_url,
                "label": row.get("itemLabel", {}).get("value") if row.get("itemLabel") else None,
                "description": (
                    row.get("itemDescription", {}).get("value")
                    if row.get("itemDescription")
                    else None
                ),
                "date": date_val,
                "location": (
                    row.get("locationLabel", {}).get("value")
                    if row.get("locationLabel")
                    else None
                ),
                "wikipedia_url": article_val,
                "wikipedia_title": extract_wikipedia_title(article_val or ""),
            }
        )
    return events


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch WWII events from Wikidata (date, location, description, Wikipedia link)."
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
        help="Max number of events to return (default 50).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON.",
    )
    args = parser.parse_args()

    events = run_query(
        start_year=args.start_year,
        end_year=args.end_year,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(events, indent=2))
    else:
        for e in events:
            print(f"[{e['wikidata_id']}] {e['label']}")
            print(f"  date: {e['date']}  location: {e['location']}")
            print(f"  description: {e['description']}")
            print(f"  wikidata: {e['wikidata_url']}")
            print(f"  wikipedia: {e['wikipedia_url']}")
            print()


if __name__ == "__main__":
    main()
