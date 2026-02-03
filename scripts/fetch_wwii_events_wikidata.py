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
        sort_date_expr = "COALESCE(?start_time, ?start_time_q, ?point_in_time, ?point_in_time_q, ?end_time, ?end_time_q)"
        parts = [
            "(BOUND(?point_in_time) || BOUND(?point_in_time_q) || BOUND(?start_time) || BOUND(?start_time_q) || BOUND(?end_time) || BOUND(?end_time_q))"
        ]
        if start_year is not None:
            parts.append(f"(YEAR({sort_date_expr}) >= {start_year})")
        if end_year is not None:
            parts.append(f"(YEAR({sort_date_expr}) <= {end_year})")
        year_filter = " FILTER(" + " && ".join(parts) + ")"

    return f"""
PREFIX schema: <http://schema.org/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT DISTINCT ?item ?itemLabel ?itemDescription ?point_in_time ?start_time ?end_time ?point_in_time_precision ?start_time_precision ?end_time_precision ?point_in_time_q ?start_time_q ?end_time_q ?location ?locationLabel ?article
WHERE {{
  ?item wdt:P361* wd:{WWII_QID} .
  OPTIONAL {{ ?item p:P585/psv:P585 [wikibase:timeValue ?point_in_time; wikibase:timePrecision ?point_in_time_precision] . }}
  OPTIONAL {{ ?item p:P580/psv:P580 [wikibase:timeValue ?start_time; wikibase:timePrecision ?start_time_precision] . }}
  OPTIONAL {{ ?item p:P582/psv:P582 [wikibase:timeValue ?end_time; wikibase:timePrecision ?end_time_precision] . }}
  OPTIONAL {{ ?item p:P361/pq:P585 ?point_in_time_q . }}
  OPTIONAL {{ ?item p:P361/pq:P580 ?start_time_q . }}
  OPTIONAL {{ ?item p:P361/pq:P582 ?end_time_q . }}
  OPTIONAL {{ ?item wdt:P276 ?location . }}
  OPTIONAL {{
    ?article schema:about ?item .
    ?article schema:inLanguage "en" .
    ?article schema:isPartOf <https://en.wikipedia.org/> .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
  {year_filter}
}}
ORDER BY DESC(BOUND(?start_time) || BOUND(?start_time_q) || BOUND(?point_in_time) || BOUND(?point_in_time_q) || BOUND(?end_time) || BOUND(?end_time_q)) ASC(COALESCE(?start_time, ?start_time_q, ?point_in_time, ?point_in_time_q, ?end_time, ?end_time_q))
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


WIKIDATA_TIME_PRECISION = {
    9: "year",
    10: "month",
    11: "day",
    12: "hour",
    13: "minute",
    14: "second",
}


def normalize_date(
    raw_value: str | None,
    precision_raw: str | None = None,
) -> dict | None:
    if not raw_value:
        return None
    precision = None
    if precision_raw is not None:
        try:
            p = int(precision_raw)
            precision = WIKIDATA_TIME_PRECISION.get(p)
        except (ValueError, TypeError):
            pass
    if precision is None:
        if re.match(r"^\d{4}-01-01T00:00:00Z$", raw_value):
            precision = "year"
        elif re.match(r"^\d{4}-\d{2}-01T00:00:00Z$", raw_value):
            precision = "month"
        else:
            precision = "day"
    if precision == "year":
        year = raw_value[:4] if len(raw_value) >= 4 else raw_value
        return {"value": year, "resolution": "year"}
    if precision == "month":
        return {"value": raw_value[:7], "resolution": "month"}
    return {"value": raw_value, "resolution": precision}


def run_query(
    start_year: int | None = None,
    end_year: int | None = None,
    limit: int = 50,
) -> list[dict]:
    sparql = SPARQLWrapper(WIKIDATA_SPARQL)
    sparql.setQuery(build_query(start_year, end_year, limit))
    sparql.setReturnFormat(JSON)
    raw = sparql.query().convert()

    def get_val(row: dict, key: str) -> str | None:
        b = row.get(key)
        return b.get("value") if b else None

    def pick(*vals: str | None) -> str | None:
        for v in vals:
            if v is not None:
                return v
        return None

    rows = raw.get("results", {}).get("bindings", [])
    by_qid: dict[str, list[dict]] = {}
    for row in rows:
        item_uri = row.get("item", {}).get("value", "")
        qid = extract_wikidata_id(item_uri) or ""
        by_qid.setdefault(qid, []).append(row)
    def pick_raw_and_precision(
        rows: list[dict], val_key: str, precision_key: str, qual_key: str
    ) -> tuple[str | None, str | None]:
        raw = None
        prec = None
        for r in rows:
            v = get_val(r, val_key) or get_val(r, qual_key)
            if v is not None:
                raw = v
                p = get_val(r, precision_key)
                if p is not None:
                    prec = p
                break
        return (raw, prec)

    events = []
    for qid, qid_rows in by_qid.items():
        pt_raw, pt_prec = pick_raw_and_precision(
            qid_rows, "point_in_time", "point_in_time_precision", "point_in_time_q"
        )
        st_raw, st_prec = pick_raw_and_precision(
            qid_rows, "start_time", "start_time_precision", "start_time_q"
        )
        et_raw, et_prec = pick_raw_and_precision(
            qid_rows, "end_time", "end_time_precision", "end_time_q"
        )
        point_in_time = normalize_date(pt_raw, pt_prec)
        start_time = normalize_date(st_raw, st_prec)
        end_time = normalize_date(et_raw, et_prec)
        r0 = qid_rows[0]
        article_val = get_val(r0, "article")
        wikidata_url = f"https://www.wikidata.org/wiki/{qid}" if qid else None
        events.append(
            {
                "wikidata_id": qid or None,
                "wikidata_url": wikidata_url,
                "label": get_val(r0, "itemLabel"),
                "description": get_val(r0, "itemDescription"),
                "point_in_time": point_in_time,
                "start_time": start_time,
                "end_time": end_time,
                "location": get_val(r0, "locationLabel"),
                "wikipedia_url": article_val,
                "wikipedia_title": extract_wikipedia_title(article_val or ""),
            }
        )

    def sortable_date(d: dict | None) -> str:
        if not d:
            return ""
        v = d.get("value") or ""
        res = d.get("resolution") or "day"
        if res == "year":
            return v + "-01-01T00:00:00Z"
        if res == "month":
            return v + "-01T00:00:00Z" if len(v) >= 7 else v + "-01-01T00:00:00Z"
        return v if "T" in v else v + "T00:00:00Z"

    events.sort(
        key=lambda e: (
            sortable_date(e["start_time"])
            or sortable_date(e["point_in_time"])
            or sortable_date(e["end_time"])
        )
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
            pt = e["point_in_time"]
            st = e["start_time"]
            et = e["end_time"]
            pt_s = f"{pt['value']} ({pt['resolution']})" if pt else "None"
            st_s = f"{st['value']} ({st['resolution']})" if st else "None"
            et_s = f"{et['value']} ({et['resolution']})" if et else "None"
            print(f"  point_in_time: {pt_s}  start_time: {st_s}  end_time: {et_s}")
            print(f"  location: {e['location']}")
            print(f"  description: {e['description']}")
            print(f"  wikidata: {e['wikidata_url']}")
            print(f"  wikipedia: {e['wikipedia_url']}")
            print()


if __name__ == "__main__":
    main()
