import logging
import re
import time
from urllib.error import HTTPError

from SPARQLWrapper import SPARQLWrapper, JSON

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WWII_QID = "Q362"
MAX_RETRIES = 3
DEFAULT_RETRY_SECONDS = 60

WIKIDATA_TIME_PRECISION = {
    9: "year",
    10: "month",
    11: "day",
    12: "hour",
    13: "minute",
    14: "second",
}


def extract_wikidata_id(uri: str) -> str | None:
    if not uri:
        return None
    m = re.search(r"entity/(Q\d+)$", uri)
    return m.group(1) if m else None


def extract_wikipedia_title(url: str) -> str | None:
    if not url or "/wiki/" not in url:
        return None
    path = url.split("/wiki/", 1)[-1]
    return path.split("#")[0] or None


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


def _get_http_error(exc: BaseException) -> HTTPError | None:
    if isinstance(exc, HTTPError):
        return exc
    cause = getattr(exc, "__cause__", None)
    return cause if isinstance(cause, HTTPError) else None


class WikidataSparqlClient:
    def __init__(
        self,
        endpoint: str = WIKIDATA_SPARQL,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.endpoint = endpoint
        self.max_retries = max_retries

    def _build_query(
        self,
        start_year: int | None,
        end_year: int | None,
        limit: int,
    ) -> str:
        year_filter = ""
        if start_year is not None or end_year is not None:
            sort_date_expr = (
                "COALESCE(?start_time, ?start_time_q, ?point_in_time, "
                "?point_in_time_q, ?end_time, ?end_time_q)"
            )
            parts = [
                "(BOUND(?point_in_time) || BOUND(?point_in_time_q) || "
                "BOUND(?start_time) || BOUND(?start_time_q) || "
                "BOUND(?end_time) || BOUND(?end_time_q))"
            ]
            if start_year is not None:
                parts.append(f"(YEAR({sort_date_expr}) >= {start_year})")
            if end_year is not None:
                parts.append(f"(YEAR({sort_date_expr}) <= {end_year})")
            year_filter = " FILTER(" + " && ".join(parts) + ")"

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

    def _execute(self, sparql: SPARQLWrapper) -> dict:
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                result = sparql.query().convert()
                if attempt > 0:
                    logger.info("SPARQL query succeeded on attempt %d", attempt + 1)
                return result
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    logger.info(
                        "SPARQL request failed (attempt %d/%d): %s",
                        attempt + 1,
                        self.max_retries + 1,
                        e,
                    )
                http_err = _get_http_error(e)
                if http_err is None:
                    raise
                if http_err.code == 429:
                    seconds = DEFAULT_RETRY_SECONDS
                    ra = http_err.headers.get("Retry-After")
                    if ra is not None:
                        try:
                            seconds = int(ra)
                        except (ValueError, TypeError):
                            pass
                    if attempt < self.max_retries:
                        time.sleep(seconds)
                    else:
                        raise
                elif http_err.code == 403:
                    raise RuntimeError(
                        "Wikidata returned 403 (rate limit abuse). Wait before retrying."
                    ) from e
                else:
                    raise
        raise last_exc  # type: ignore[misc]

    def fetch_location_coordinates(
        self,
        location_qids: list[str],
    ) -> dict[str, tuple[float, float]]:
        if not location_qids:
            return {}
        result: dict[str, tuple[float, float]] = {}
        sparql = SPARQLWrapper(self.endpoint)
        batch_size = 50
        for i in range(0, len(location_qids), batch_size):
            batch = location_qids[i : i + batch_size]
            values = " ".join(f"wd:{q}" for q in batch)
            query = f"""
            PREFIX wd: <http://www.wikidata.org/entity/>
            PREFIX p: <http://www.wikidata.org/prop/>
            PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
            PREFIX wikibase: <http://wikiba.se/ontology#>
            SELECT ?location ?lat ?lon
            WHERE {{
              VALUES ?location {{ {values} }}
              ?location p:P625/psv:P625 [
                wikibase:geoLatitude ?lat ;
                wikibase:geoLongitude ?lon
              ] .
            }}
            """
            sparql.setQuery(query)
            sparql.setReturnFormat(JSON)
            raw = self._execute(sparql)
            for b in raw.get("results", {}).get("bindings", []):
                qid = extract_wikidata_id(b.get("location", {}).get("value", ""))
                lat_s = b.get("lat", {}).get("value")
                lon_s = b.get("lon", {}).get("value")
                if qid and lat_s is not None and lon_s is not None:
                    try:
                        result[qid] = (float(lat_s), float(lon_s))
                    except (ValueError, TypeError):
                        pass
        return result

    def fetch_sitelink_counts(self, qids: list[str]) -> dict[str, int]:
        if not qids:
            return {}
        result = {q: 0 for q in qids}
        sparql = SPARQLWrapper(self.endpoint)
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
            raw = self._execute(sparql)
            for b in raw.get("results", {}).get("bindings", []):
                qid = extract_wikidata_id(b.get("item", {}).get("value", ""))
                if qid and b.get("sitelink"):
                    result[qid] = result.get(qid, 0) + 1
        return result

    def run_query(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        logger.info(
            "Querying Wikidata (start_year=%s, end_year=%s, limit=%d)",
            start_year,
            end_year,
            limit,
        )
        sparql = SPARQLWrapper(self.endpoint)
        sparql.setQuery(self._build_query(start_year, end_year, limit))
        sparql.setReturnFormat(JSON)
        raw = self._execute(sparql)

        def get_val(row: dict, key: str) -> str | None:
            b = row.get(key)
            return b.get("value") if b else None

        def pick_raw_and_precision(
            rows: list[dict],
            val_key: str,
            precision_key: str,
            qual_key: str,
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

        rows = raw.get("results", {}).get("bindings", [])
        logger.info("Retrieved %d bindings from Wikidata", len(rows))
        by_qid: dict[str, list[dict]] = {}
        for row in rows:
            item_uri = row.get("item", {}).get("value", "")
            qid = extract_wikidata_id(item_uri) or ""
            by_qid.setdefault(qid, []).append(row)

        events = []
        for qid, qid_rows in by_qid.items():
            pt_raw, pt_prec = pick_raw_and_precision(
                qid_rows,
                "point_in_time",
                "point_in_time_precision",
                "point_in_time_q",
            )
            st_raw, st_prec = pick_raw_and_precision(
                qid_rows,
                "start_time",
                "start_time_precision",
                "start_time_q",
            )
            et_raw, et_prec = pick_raw_and_precision(
                qid_rows,
                "end_time",
                "end_time_precision",
                "end_time_q",
            )
            point_in_time = normalize_date(pt_raw, pt_prec)
            start_time = normalize_date(st_raw, st_prec)
            end_time = normalize_date(et_raw, et_prec)
            r0 = qid_rows[0]
            article_val = get_val(r0, "article")
            wikidata_url = f"https://www.wikidata.org/wiki/{qid}" if qid else None
            location_qid = extract_wikidata_id(get_val(r0, "location") or "")
            events.append(
                {
                    "wikidata_id": qid or None,
                    "wikidata_url": wikidata_url,
                    "label": get_val(r0, "itemLabel"),
                    "description": get_val(r0, "itemDescription"),
                    "point_in_time": point_in_time,
                    "start_time": start_time,
                    "end_time": end_time,
                    "location_name": get_val(r0, "locationLabel"),
                    "location_qid": location_qid or None,
                    "location_lat": None,
                    "location_lon": None,
                    "wikipedia_url": article_val,
                    "wikipedia_title": extract_wikipedia_title(article_val or ""),
                }
            )

        location_qids = list(
            {e["location_qid"] for e in events if e.get("location_qid")}
        )
        logger.info("Fetching coordinates for %d location(s)", len(location_qids))
        coords = self.fetch_location_coordinates(location_qids)
        for e in events:
            lqid = e.get("location_qid")
            if lqid and lqid in coords:
                e["location_lat"], e["location_lon"] = coords[lqid]

        qids = [e["wikidata_id"] for e in events if e.get("wikidata_id")]
        logger.info("Fetching sitelink counts for %d items", len(qids))
        sitelink_counts = self.fetch_sitelink_counts(qids)
        for e in events:
            e["sitelink_count"] = sitelink_counts.get(e.get("wikidata_id") or "", 0)

        events.sort(
            key=lambda e: (
                sortable_date(e["start_time"])
                or sortable_date(e["point_in_time"])
                or sortable_date(e["end_time"])
            )
        )
        # Expose sortable_date for use by loader
        for e in events:
            e["_sort_date"] = (
                sortable_date(e["start_time"])
                or sortable_date(e["point_in_time"])
                or sortable_date(e["end_time"])
            )
        logger.info("Built %d events from Wikidata", len(events))
        return events
