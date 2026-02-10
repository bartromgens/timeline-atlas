import json
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

PAGEVIEWS_BASE = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia.org/all-access/all-agents"
)
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
BACKLINKS_LIMIT = 500
USER_AGENT = "TimelineAtlas/1.0 (Python; timeline-atlas)"
REQUEST_DELAY_SECONDS = 0.35
MAX_429_RETRIES = 3
BACKOFF_429_SECONDS = 10.5


def _request_with_429_retry(url: str) -> bytes:
    for attempt in range(MAX_429_RETRIES):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=15) as resp:
                return resp.read()
        except HTTPError as e:
            if e.code == 429:
                logger.warning(
                    "Too many requests (429) from Wikimedia/Wikipedia API: %s", url
                )
                if attempt < MAX_429_RETRIES - 1:
                    logger.info(
                        "Rate limited (429), waiting %ds before retry %d/%d",
                        BACKOFF_429_SECONDS,
                        attempt + 2,
                        MAX_429_RETRIES,
                    )
                    time.sleep(BACKOFF_429_SECONDS)
                else:
                    raise
            else:
                raise
    return b""


class PageviewsBacklinksFetcher:
    def __init__(
        self,
        delay_seconds: float = REQUEST_DELAY_SECONDS,
    ) -> None:
        self.delay_seconds = delay_seconds

    def fetch_pageviews_last_30_days(self, title: str) -> int:
        if not title:
            return 0
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=30)
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")
        title_decoded = unquote(title)
        article_encoded = quote(title_decoded.replace(" ", "_"), safe="-_.~()")
        url = f"{PAGEVIEWS_BASE}/{article_encoded}/daily/{start_str}/{end_str}"
        data = json.loads(_request_with_429_retry(url).decode())
        items = data.get("items") or []
        return sum(item.get("views", 0) for item in items)

    def fetch_backlink_count(self, title: str) -> int:
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
        data = json.loads(_request_with_429_retry(url).decode())
        bl = data.get("query", {}).get("backlinks") or []
        return len(bl)

    def fetch_for_event(self, wikipedia_title: str | None) -> tuple[int, int]:
        if not wikipedia_title:
            return 0, 0
        time.sleep(self.delay_seconds)
        pageviews = self.fetch_pageviews_last_30_days(wikipedia_title)
        time.sleep(self.delay_seconds)
        backlinks = self.fetch_backlink_count(wikipedia_title)
        return pageviews, backlinks
