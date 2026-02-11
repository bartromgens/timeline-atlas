import logging
import re
import time
from urllib.error import HTTPError

from SPARQLWrapper import SPARQLWrapper, JSON

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
MAX_RETRIES = 3
DEFAULT_RETRY_SECONDS = 60

HISTORICAL_EVENT_TYPES: list[dict[str, str]] = [
    {"qid": "Q198", "label": "war"},
    {"qid": "Q178561", "label": "battle"},
    {"qid": "Q131569", "label": "treaty"},
    {"qid": "Q8690", "label": "revolution"},
    {"qid": "Q188055", "label": "siege"},
    {"qid": "Q891854", "label": "military campaign"},
    {"qid": "Q12184", "label": "pandemic"},
    {"qid": "Q3839081", "label": "disaster"},
    {"qid": "Q35127", "label": "genocide"},
    {"qid": "Q3024240", "label": "historical event"},
    {"qid": "Q2401485", "label": "expedition"},
    {"qid": "Q1361567", "label": "coronation"},
    {"qid": "Q3882219", "label": "assassination"},
    {"qid": "Q2133344", "label": "space mission"},
    {"qid": "Q45382", "label": "coup d'état"},
    {"qid": "Q1464916", "label": "declaration of independence"},
    {"qid": "Q40231", "label": "election"},
    {"qid": "Q168247", "label": "famine"},
    {"qid": "Q5389", "label": "Olympic Games"},
    {"qid": "Q124734", "label": "rebellion"},
    {"qid": "Q3199915", "label": "massacre"},
    {"qid": "Q184211", "label": "referendum"},
    {"qid": "Q273120", "label": "protest"},
    {"qid": "Q124757", "label": "riot"},
]
DEFAULT_MIN_SITELINKS = 2

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


# Unicode minus (U+2212) is used by Wikidata for BCE; normalize to ASCII minus.


def _parse_year_from_raw(raw_value: str) -> str | None:
    m = re.match(r"^([+\-\u2212]?\d{1,4})", raw_value)
    if not m:
        return None
    year = m.group(1)
    if year.startswith("\u2212"):
        year = "-" + year[1:]
    return year


def _year_to_canonical(year_str: str) -> str:
    """Zero-pad negative years to 4 digits for correct ISO-style parsing."""
    if not year_str or year_str[0] != "-":
        return year_str
    digits = year_str[1:].lstrip("0") or "0"
    return "-" + digits.zfill(4)


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
        if re.match(r"^[+\-\u2212]?\d{1,4}-01-01T00:00:00Z$", raw_value):
            precision = "year"
        elif re.match(r"^[+\-\u2212]?\d{1,4}-\d{2}-01T00:00:00Z$", raw_value):
            precision = "month"
        else:
            precision = "day"
    if precision == "year":
        year = _parse_year_from_raw(raw_value)
        if not year and raw_value and raw_value[0].isdigit():
            year = raw_value[:4]
        if not year:
            year = ""
        if year:
            year = _year_to_canonical(year)
        return {"value": year, "resolution": "year"} if year else None
    if precision == "month":
        m = re.match(r"^([+\-\u2212]?\d{4}-\d{2})", raw_value)
        month_val = (
            m.group(1) if m else (raw_value[:7] if len(raw_value) >= 7 else raw_value)
        )
        if month_val.startswith("\u2212"):
            month_val = "-" + month_val[1:]
        return {"value": month_val, "resolution": "month"}
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
        category_qid: str,
        start_year: int | None,
        end_year: int | None,
        limit: int,
    ) -> str:
        year_filter = ""
        if start_year is not None or end_year is not None:
            sort_date_expr = (
                "COALESCE(?start_time, ?start_time_q, ?date_of_birth, "
                "?point_in_time, ?point_in_time_q, ?point_in_time_p793, "
                "?end_time, ?end_time_q, ?date_of_death)"
            )
            parts = [
                "(BOUND(?point_in_time) || BOUND(?point_in_time_q) || "
                "BOUND(?point_in_time_p793) || BOUND(?start_time) || "
                "BOUND(?start_time_q) || BOUND(?date_of_birth) || "
                "BOUND(?end_time) || BOUND(?end_time_q) || BOUND(?date_of_death))"
            ]
            if start_year is not None:
                parts.append(f"(YEAR({sort_date_expr}) >= {start_year})")
            if end_year is not None:
                parts.append(f"(YEAR({sort_date_expr}) <= {end_year})")
            year_filter = " FILTER(" + " && ".join(parts) + ")"

        day_precision_filter = (
            " FILTER(?point_in_time_precision = 11 || "
            "?start_time_precision = 11 || ?end_time_precision = 11 || "
            "?date_of_birth_precision = 11 || ?date_of_death_precision = 11 || "
            "BOUND(?point_in_time_q) || BOUND(?start_time_q) || BOUND(?end_time_q) || "
            "BOUND(?point_in_time_p793) || BOUND(?date_of_birth) || BOUND(?date_of_death))"
        )

        return f"""
PREFIX schema: <http://schema.org/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX pqv: <http://www.wikidata.org/prop/qualifier/value/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT DISTINCT ?item ?itemLabel ?itemDescription ?point_in_time ?start_time ?end_time ?point_in_time_precision ?start_time_precision ?end_time_precision ?point_in_time_q ?start_time_q ?end_time_q ?point_in_time_p793 ?date_of_birth ?date_of_birth_precision ?date_of_death ?date_of_death_precision ?location ?locationLabel ?article
WHERE {{
  {{
    ?item wdt:P361* wd:{category_qid} .
  }} UNION {{
    ?item wdt:P31 ?type .
    ?type wdt:P279* wd:{category_qid} .
  }} UNION {{
    ?item wdt:P2348 ?period .
    ?period wdt:P361* wd:{category_qid} .
  }}
  OPTIONAL {{ ?item p:P585/psv:P585 [wikibase:timeValue ?point_in_time; wikibase:timePrecision ?point_in_time_precision] . }}
  OPTIONAL {{ ?item p:P580/psv:P580 [wikibase:timeValue ?start_time; wikibase:timePrecision ?start_time_precision] . }}
  OPTIONAL {{ ?item p:P582/psv:P582 [wikibase:timeValue ?end_time; wikibase:timePrecision ?end_time_precision] . }}
  OPTIONAL {{ ?item p:P361/pq:P585 ?point_in_time_q . }}
  OPTIONAL {{ ?item p:P361/pq:P580 ?start_time_q . }}
  OPTIONAL {{ ?item p:P361/pq:P582 ?end_time_q . }}
  OPTIONAL {{ ?item p:P793/pqv:P585 [wikibase:timeValue ?point_in_time_p793] . }}
  OPTIONAL {{ ?item p:P569/psv:P569 [wikibase:timeValue ?date_of_birth; wikibase:timePrecision ?date_of_birth_precision] . }}
  OPTIONAL {{ ?item p:P570/psv:P570 [wikibase:timeValue ?date_of_death; wikibase:timePrecision ?date_of_death_precision] . }}
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
ORDER BY DESC(BOUND(?start_time) || BOUND(?start_time_q) || BOUND(?date_of_birth) || BOUND(?point_in_time) || BOUND(?point_in_time_q) || BOUND(?point_in_time_p793) || BOUND(?end_time) || BOUND(?end_time_q) || BOUND(?date_of_death)) ASC(COALESCE(?start_time, ?start_time_q, ?date_of_birth, ?point_in_time, ?point_in_time_q, ?point_in_time_p793, ?end_time, ?end_time_q, ?date_of_death))
LIMIT {limit}
"""

    def _build_type_discovery_query(
        self,
        type_qids: list[str],
        start_year: int | None,
        end_year: int | None,
        min_sitelinks: int,
        limit: int,
    ) -> str:
        values = " ".join(f"wd:{q}" for q in type_qids)
        year_filter = ""
        if start_year is not None or end_year is not None:
            date_expr = "COALESCE(?start_time, ?point_in_time, ?end_time, ?launch_time, ?landing_time)"
            parts: list[str] = []
            if start_year is not None:
                parts.append(f"(YEAR({date_expr}) >= {start_year})")
            if end_year is not None:
                parts.append(f"(YEAR({date_expr}) <= {end_year})")
            year_filter = " FILTER(" + " && ".join(parts) + ")"

        return f"""
PREFIX schema: <http://schema.org/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT DISTINCT ?item ?itemLabel ?itemDescription
  ?point_in_time ?point_in_time_precision
  ?start_time ?start_time_precision
  ?end_time ?end_time_precision
  ?launch_time ?launch_time_precision
  ?landing_time ?landing_time_precision
  ?location ?locationLabel ?article ?sitelinks ?part_of
WHERE {{
  VALUES ?type {{ {values} }}
  ?item wdt:P31/wdt:P279* ?type .
  ?item wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= {min_sitelinks})
  ?article schema:about ?item .
  ?article schema:inLanguage "en" .
  ?article schema:isPartOf <https://en.wikipedia.org/> .
  OPTIONAL {{ ?item p:P585/psv:P585 [wikibase:timeValue ?point_in_time; wikibase:timePrecision ?point_in_time_precision] . }}
  OPTIONAL {{ ?item p:P580/psv:P580 [wikibase:timeValue ?start_time; wikibase:timePrecision ?start_time_precision] . }}
  OPTIONAL {{ ?item p:P582/psv:P582 [wikibase:timeValue ?end_time; wikibase:timePrecision ?end_time_precision] . }}
  OPTIONAL {{ ?item p:P619/psv:P619 [wikibase:timeValue ?launch_time; wikibase:timePrecision ?launch_time_precision] . }}
  OPTIONAL {{ ?item p:P620/psv:P620 [wikibase:timeValue ?landing_time; wikibase:timePrecision ?landing_time_precision] . }}
  OPTIONAL {{ ?item wdt:P276 ?location . }}
  OPTIONAL {{ ?item wdt:P361 ?part_of . }}
  FILTER(BOUND(?point_in_time) || BOUND(?start_time) || BOUND(?end_time) || BOUND(?launch_time) || BOUND(?landing_time))
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
  {year_filter}
}}
ORDER BY DESC(?sitelinks)
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
                    logger.warning(
                        "Too many requests (429) from Wikidata SPARQL endpoint"
                    )
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
                    logger.warning(
                        "Too many requests (403 rate limit) from Wikidata SPARQL"
                    )
                    raise RuntimeError(
                        "Wikidata returned 403 (rate limit abuse). Wait before retrying."
                    ) from e
                else:
                    raise
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _get_val(row: dict, key: str) -> str | None:
        b = row.get(key)
        return b.get("value") if b else None

    @staticmethod
    def _pick_raw_and_precision(
        rows: list[dict],
        val_key: str,
        precision_key: str,
        *qual_keys: str,
    ) -> tuple[str | None, str | None]:
        for r in rows:
            v = WikidataSparqlClient._get_val(r, val_key)
            if v is None:
                for qk in qual_keys:
                    v = WikidataSparqlClient._get_val(r, qk)
                    if v is not None:
                        break
            if v is not None:
                p = WikidataSparqlClient._get_val(r, precision_key)
                return (v, p)
        return (None, None)

    @staticmethod
    def _pick_primary_location(rows: list[dict]) -> tuple[str | None, str | None]:
        """Pick (location_qid, location_name) from rows; uses first P276 location."""
        for r in rows:
            uri = WikidataSparqlClient._get_val(r, "location")
            if uri:
                qid = extract_wikidata_id(uri) or ""
                if qid:
                    label = WikidataSparqlClient._get_val(r, "locationLabel")
                    return (qid, label or None)
        return (None, None)

    @staticmethod
    def _collect_part_of_qids(rows: list[dict]) -> list[str]:
        """Collect P361 (part of) QIDs from rows, order preserved, deduplicated."""
        seen: set[str] = set()
        result: list[str] = []
        for r in rows:
            uri = r.get("part_of", {}).get("value", "")
            qid = extract_wikidata_id(uri) or ""
            if qid and qid not in seen:
                seen.add(qid)
                result.append(qid)
        return result

    def _parse_bindings(self, rows: list[dict]) -> list[dict]:
        by_qid: dict[str, list[dict]] = {}
        for row in rows:
            item_uri = row.get("item", {}).get("value", "")
            qid = extract_wikidata_id(item_uri) or ""
            by_qid.setdefault(qid, []).append(row)

        events: list[dict] = []
        for qid, qid_rows in by_qid.items():
            pt_raw, pt_prec = self._pick_raw_and_precision(
                qid_rows,
                "point_in_time",
                "point_in_time_precision",
                "point_in_time_q",
                "point_in_time_p793",
                "launch_time",
            )
            st_raw, st_prec = self._pick_raw_and_precision(
                qid_rows,
                "start_time",
                "start_time_precision",
                "start_time_q",
                "date_of_birth",
                "launch_time",
            )
            et_raw, et_prec = self._pick_raw_and_precision(
                qid_rows,
                "end_time",
                "end_time_precision",
                "end_time_q",
                "date_of_death",
                "landing_time",
            )
            point_in_time = normalize_date(pt_raw, pt_prec)
            start_time = normalize_date(st_raw, st_prec)
            end_time = normalize_date(et_raw, et_prec)
            r0 = qid_rows[0]
            article_val = self._get_val(r0, "article")
            wikidata_url = f"https://www.wikidata.org/wiki/{qid}" if qid else None
            location_qid, location_name = self._pick_primary_location(qid_rows)
            part_of_qids = self._collect_part_of_qids(qid_rows)
            sitelinks_val = self._get_val(r0, "sitelinks")
            sitelink_count = 0
            if sitelinks_val:
                try:
                    sitelink_count = int(sitelinks_val)
                except (ValueError, TypeError):
                    pass
            events.append(
                {
                    "wikidata_id": qid or None,
                    "wikidata_url": wikidata_url,
                    "label": self._get_val(r0, "itemLabel"),
                    "description": self._get_val(r0, "itemDescription"),
                    "point_in_time": point_in_time,
                    "start_time": start_time,
                    "end_time": end_time,
                    "location_name": location_name,
                    "location_qid": location_qid,
                    "location_lat": None,
                    "location_lon": None,
                    "wikipedia_url": article_val,
                    "wikipedia_title": extract_wikipedia_title(article_val or ""),
                    "sitelink_count": sitelink_count,
                    "part_of": part_of_qids,
                }
            )
        return events

    def _enrich_events(
        self,
        events: list[dict],
        fetch_sitelinks: bool = True,
    ) -> None:
        location_qids = list(
            {e["location_qid"] for e in events if e.get("location_qid")}
        )
        if location_qids:
            logger.info("Fetching coordinates for %d location(s)", len(location_qids))
            coords = self.fetch_location_coordinates(location_qids)
            for e in events:
                lqid = e.get("location_qid")
                if lqid and lqid in coords:
                    e["location_lat"], e["location_lon"] = coords[lqid]
        if fetch_sitelinks:
            qids = [e["wikidata_id"] for e in events if e.get("wikidata_id")]
            if qids:
                logger.info("Fetching sitelink counts for %d items", len(qids))
                sitelink_counts = self.fetch_sitelink_counts(qids)
                for e in events:
                    e["sitelink_count"] = sitelink_counts.get(
                        e.get("wikidata_id") or "", 0
                    )
        events.sort(
            key=lambda e: (
                sortable_date(e["start_time"])
                or sortable_date(e["point_in_time"])
                or sortable_date(e["end_time"])
            )
        )
        for e in events:
            e["_sort_date"] = (
                sortable_date(e["start_time"])
                or sortable_date(e["point_in_time"])
                or sortable_date(e["end_time"])
            )

    def fetch_item_label(self, qid: str) -> str | None:
        if not qid or not re.match(r"^Q\d+$", qid):
            return None
        sparql = SPARQLWrapper(self.endpoint)
        query = f"""
        PREFIX wd: <http://www.wikidata.org/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?label
        WHERE {{
          wd:{qid} rdfs:label ?label .
          FILTER(LANG(?label) = "en")
        }}
        LIMIT 1
        """
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        raw = self._execute(sparql)
        bindings = raw.get("results", {}).get("bindings", [])
        if bindings and bindings[0].get("label", {}).get("value"):
            return bindings[0]["label"]["value"]
        return None

    def fetch_category_properties(
        self, qid: str
    ) -> dict[str, str | list[dict[str, str]]]:
        if not qid or not re.match(r"^Q\d+$", qid):
            return {"label": "", "instance_of": [], "subclass_of": []}
        sparql = SPARQLWrapper(self.endpoint)
        query = f"""
        PREFIX wd: <http://www.wikidata.org/entity/>
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?label ?p31 ?p31Label ?p279 ?p279Label
        WHERE {{
          wd:{qid} rdfs:label ?label .
          FILTER(LANG(?label) = "en")
          OPTIONAL {{
            wd:{qid} wdt:P31 ?p31 .
            ?p31 rdfs:label ?p31Label .
            FILTER(LANG(?p31Label) = "en")
          }}
          OPTIONAL {{
            wd:{qid} wdt:P279 ?p279 .
            ?p279 rdfs:label ?p279Label .
            FILTER(LANG(?p279Label) = "en")
          }}
        }}
        """
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        raw = self._execute(sparql)
        bindings = raw.get("results", {}).get("bindings", [])
        label = ""
        instance_of: list[dict[str, str]] = []
        subclass_of: list[dict[str, str]] = []
        seen_p31: set[str] = set()
        seen_p279: set[str] = set()
        for b in bindings:
            if not label and b.get("label", {}).get("value"):
                label = b["label"]["value"]
            p31_val = b.get("p31", {}).get("value", "")
            p31_qid = extract_wikidata_id(p31_val)
            if p31_qid and p31_qid not in seen_p31:
                seen_p31.add(p31_qid)
                instance_of.append(
                    {
                        "qid": p31_qid,
                        "label": b.get("p31Label", {}).get("value", ""),
                    }
                )
            p279_val = b.get("p279", {}).get("value", "")
            p279_qid = extract_wikidata_id(p279_val)
            if p279_qid and p279_qid not in seen_p279:
                seen_p279.add(p279_qid)
                subclass_of.append(
                    {
                        "qid": p279_qid,
                        "label": b.get("p279Label", {}).get("value", ""),
                    }
                )
        return {"label": label, "instance_of": instance_of, "subclass_of": subclass_of}

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

    def fetch_events_part_of(
        self, event_qids: list[str], batch_size: int = 50
    ) -> dict[str, list[str]]:
        if not event_qids:
            return {}
        result: dict[str, list[str]] = {qid: [] for qid in event_qids}
        valid_qids = [q for q in event_qids if q and re.match(r"^Q\d+$", q)]
        for i in range(0, len(valid_qids), batch_size):
            batch = valid_qids[i : i + batch_size]
            values = " ".join(f"wd:{q}" for q in batch)
            direct: dict[str, list[str]] = {q: [] for q in batch}
            sparql = SPARQLWrapper(self.endpoint)
            query_direct = f"""
            PREFIX wd: <http://www.wikidata.org/entity/>
            PREFIX wdt: <http://www.wikidata.org/prop/direct/>
            SELECT ?item ?cat
            WHERE {{
              VALUES ?item {{ {values} }}
              ?item wdt:P361 ?cat .
            }}
            """
            sparql.setQuery(query_direct)
            sparql.setReturnFormat(JSON)
            raw = self._execute(sparql)
            for b in raw.get("results", {}).get("bindings", []):
                item_qid = extract_wikidata_id(b.get("item", {}).get("value", ""))
                cat_qid = extract_wikidata_id(b.get("cat", {}).get("value", ""))
                if item_qid and cat_qid and cat_qid not in direct.get(item_qid, []):
                    direct[item_qid].append(cat_qid)

            transitive: dict[str, list[str]] = {q: [] for q in batch}
            query_transitive = f"""
            PREFIX wd: <http://www.wikidata.org/entity/>
            PREFIX wdt: <http://www.wikidata.org/prop/direct/>
            SELECT ?item ?cat
            WHERE {{
              VALUES ?item {{ {values} }}
              ?item wdt:P361* ?cat .
            }}
            """
            sparql.setQuery(query_transitive)
            raw = self._execute(sparql)
            for b in raw.get("results", {}).get("bindings", []):
                item_qid = extract_wikidata_id(b.get("item", {}).get("value", ""))
                cat_qid = extract_wikidata_id(b.get("cat", {}).get("value", ""))
                if (
                    item_qid
                    and cat_qid
                    and cat_qid != item_qid
                    and cat_qid not in transitive.get(item_qid, [])
                ):
                    transitive[item_qid].append(cat_qid)

            for qid in batch:
                direct_list = direct.get(qid, [])
                direct_set = set(direct_list)
                rest = [c for c in transitive.get(qid, []) if c not in direct_set]
                result[qid] = direct_list + rest
        return result

    def run_query(
        self,
        category_qid: str,
        start_year: int | None = None,
        end_year: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        logger.info(
            "Querying Wikidata (category=%s, start_year=%s, end_year=%s, limit=%d)",
            category_qid,
            start_year,
            end_year,
            limit,
        )
        sparql = SPARQLWrapper(self.endpoint)
        sparql.setQuery(self._build_query(category_qid, start_year, end_year, limit))
        sparql.setReturnFormat(JSON)
        raw = self._execute(sparql)

        rows = raw.get("results", {}).get("bindings", [])
        logger.info("Retrieved %d bindings from Wikidata", len(rows))
        events = self._parse_bindings(rows)
        self._enrich_events(events, fetch_sitelinks=True)
        logger.info("Built %d events from Wikidata", len(events))
        return events

    def run_type_discovery_query(
        self,
        type_qids: list[str] | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        min_sitelinks: int = DEFAULT_MIN_SITELINKS,
        limit: int = 500,
    ) -> list[dict]:
        if type_qids is None:
            type_qids = [t["qid"] for t in HISTORICAL_EVENT_TYPES]
        logger.info(
            "Type discovery query (types=%d, start_year=%s, end_year=%s, "
            "min_sitelinks=%d, limit=%d)",
            len(type_qids),
            start_year,
            end_year,
            min_sitelinks,
            limit,
        )
        sparql = SPARQLWrapper(self.endpoint)
        sparql.setQuery(
            self._build_type_discovery_query(
                type_qids, start_year, end_year, min_sitelinks, limit
            )
        )
        sparql.setReturnFormat(JSON)
        raw = self._execute(sparql)
        rows = raw.get("results", {}).get("bindings", [])
        logger.info("Retrieved %d bindings from type discovery", len(rows))
        events = self._parse_bindings(rows)
        self._enrich_events(events, fetch_sitelinks=False)
        logger.info("Built %d events from type discovery", len(events))
        return events
