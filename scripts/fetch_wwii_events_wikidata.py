#!/usr/bin/env python3

import argparse
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen

from SPARQLWrapper import SPARQLWrapper, JSON

WIKIDATA_MAX_RETRIES = 3
WIKIDATA_DEFAULT_RETRY_SECONDS = 60


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

    # Wikidata time precision: 9=year, 10=month, 11=day, 12=hour, 13=minute, 14=second
    day_precision_filter = (
        " FILTER(?point_in_time_precision = 11 || "
        "?start_time_precision = 11 || ?end_time_precision = 11)"
    )

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
  {day_precision_filter}
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


def _get_http_error(exc: BaseException) -> HTTPError | None:
    if isinstance(exc, HTTPError):
        return exc
    cause = getattr(exc, "__cause__", None)
    return cause if isinstance(cause, HTTPError) else None


def execute_sparql_with_retry(
    sparql: SPARQLWrapper,
    max_retries: int = WIKIDATA_MAX_RETRIES,
) -> dict:
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return sparql.query().convert()
        except Exception as e:
            last_exc = e
            http_err = _get_http_error(e)
            if http_err is None:
                raise
            if http_err.code == 429:
                seconds = WIKIDATA_DEFAULT_RETRY_SECONDS
                ra = http_err.headers.get("Retry-After")
                if ra is not None:
                    try:
                        seconds = int(ra)
                    except (ValueError, TypeError):
                        pass
                if attempt < max_retries:
                    time.sleep(seconds)
                else:
                    raise
            elif http_err.code == 403:
                raise RuntimeError(
                    "Wikidata returned 403 (rate limit abuse). Wait before retrying."
                ) from e
            else:
                raise
    assert last_exc is not None
    raise last_exc


def fetch_sitelink_counts(sparql: SPARQLWrapper, qids: list[str]) -> dict[str, int]:
    if not qids:
        return {}
    result = {q: 0 for q in qids}
    batch_size = 50
    for i in range(0, len(qids), batch_size):
        batch = qids[i : i + batch_size]
        values = " ".join(f"wd:{q}" for q in batch)
        query = f"""
        PREFIX schema: <http://schema.org/>
        PREFIX wd: <http://www.wikidata.org/entity/>
        SELECT ?item ?sitelink
        WHERE {{
          VALUES ?item {{ {values} }}
          OPTIONAL {{ ?sitelink schema:about ?item . }}
        }}
        """
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        raw = execute_sparql_with_retry(sparql)
        for b in raw.get("results", {}).get("bindings", []):
            qid = extract_wikidata_id(b.get("item", {}).get("value", ""))
            if qid and b.get("sitelink"):
                result[qid] = result.get(qid, 0) + 1
    return result


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
    raw = execute_sparql_with_retry(sparql)

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
    qids = [e["wikidata_id"] for e in events if e.get("wikidata_id")]
    sitelink_counts = fetch_sitelink_counts(sparql, qids)
    for e in events:
        e["sitelink_count"] = sitelink_counts.get(e.get("wikidata_id") or "", 0)

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


PAGEVIEWS_BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia.org/all-access/all-agents"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
BACKLINKS_LIMIT = 500
USER_AGENT = "TimelineAtlas/1.0 (Python; timeline-atlas)"


def fetch_pageviews_last_30_days(title: str) -> int:
    if not title:
        return 0
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=30)
    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")
    title_decoded = unquote(title)
    article_encoded = quote(
        title_decoded.replace(" ", "_"), safe="-_.~()"
    )
    url = f"{PAGEVIEWS_BASE}/{article_encoded}/daily/{start_str}/{end_str}"
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items") or []
        return sum(item.get("views", 0) for item in items)
    except Exception:
        return 0


def fetch_backlink_count(title: str) -> int:
    if not title:
        return 0
    params = {
        "action": "query",
        "list": "backlinks",
        "bltitle": unquote(title).replace("_", " "),
        "bllimit": BACKLINKS_LIMIT,
        "format": "json",
    }
    url = f"{WIKIPEDIA_API}?{urlencode(params)}"
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        bl = data.get("query", {}).get("backlinks") or []
        return len(bl)
    except Exception:
        return 0


def add_importance(events: list[dict]) -> None:
    max_sitelinks = max((e.get("sitelink_count") or 0) for e in events) or 1
    max_pageviews = 0
    max_backlinks = 0
    for e in events:
        title = e.get("wikipedia_title")
        if title:
            pv = fetch_pageviews_last_30_days(title)
            bl = fetch_backlink_count(title)
            e["pageviews_30d"] = pv
            e["backlink_count"] = bl
            max_pageviews = max(max_pageviews, pv)
            max_backlinks = max(max_backlinks, min(bl, BACKLINKS_LIMIT))
        else:
            e["pageviews_30d"] = 0
            e["backlink_count"] = 0
    max_pageviews = max_pageviews or 1
    max_backlinks = max_backlinks or 1
    for e in events:
        s = (e.get("sitelink_count") or 0) / max_sitelinks
        p = (e.get("pageviews_30d") or 0) / max_pageviews
        b = min(e.get("backlink_count") or 0, BACKLINKS_LIMIT) / max_backlinks
        e["importance_score"] = round((s + p + b) / 3, 4)


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
    add_importance(events)

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
            print(
                f"  importance_score: {e['importance_score']} "
                f"(sitelinks={e['sitelink_count']}, pageviews_30d={e['pageviews_30d']}, "
                f"backlinks={e['backlink_count']})"
            )
            print()


if __name__ == "__main__":
    main()
