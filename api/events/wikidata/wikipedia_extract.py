import json
import logging
import time
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

WIKIPEDIA_REST_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary"
REQUEST_DELAY_SECONDS = 0.5
REQUEST_TIMEOUT = 15


def _user_agent() -> str:
    contact = getattr(
        settings,
        "WIKIPEDIA_USER_AGENT_CONTACT",
        "https://github.com/timeline-atlas",
    )
    return f"TimelineAtlas/1.0 (Python; +{contact})"


def _title_from_wikipedia_url(wikipedia_url: str) -> str | None:
    if not wikipedia_url or not wikipedia_url.strip():
        return None
    parsed = urlparse(wikipedia_url.strip())
    path = parsed.path or ""
    if "/wiki/" not in path:
        return None
    segment = path.split("/wiki/", 1)[-1].strip()
    if not segment:
        return None
    return unquote(segment).replace(" ", "_")


def fetch_wikipedia_extract(wikipedia_url: str) -> str | None:
    title = _title_from_wikipedia_url(wikipedia_url)
    if not title:
        return None
    title_encoded = quote(title, safe="-_.~()")
    api_url = f"{WIKIPEDIA_REST_SUMMARY}/{title_encoded}"
    time.sleep(REQUEST_DELAY_SECONDS)
    try:
        req = Request(api_url, headers={"User-Agent": _user_agent()})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        extract = data.get("extract")
        if isinstance(extract, str) and extract.strip():
            logger.info(
                "Successfully fetched Wikipedia extract for %s", wikipedia_url
            )
            return extract.strip()
        return None
    except (HTTPError, OSError, json.JSONDecodeError, KeyError) as e:
        logger.warning(
            "Failed to fetch Wikipedia extract for %s: %s", wikipedia_url, e
        )
        return None
