import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.events.models import Event

BACKLINKS_CAP = 500


def _scale(x: float, lo: float, range_val: float) -> float:
    if range_val <= 0:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / range_val))


class ImportanceScorer:
    WEIGHT_PAGEVIEWS = 1.0 / 2.0
    WEIGHT_BACKLINKS = 3.0 / 8.0
    WEIGHT_SITELINKS = 1.0 / 8.0
    DECIMALS = 4
    SITELINKS_MIN_THRESHOLD = 3
    SITELINKS_LOW_MULTIPLIER = 0.5

    NORM_SITELINKS_MIN = 0
    NORM_SITELINKS_MAX = 80
    NORM_PAGEVIEWS_MAX_RAW = 60_000
    NORM_BACKLINKS_MIN = 0
    NORM_BACKLINKS_MAX = 500

    def __init__(
        self,
        weight_sitelinks: float | None = None,
        weight_pageviews: float | None = None,
        weight_backlinks: float | None = None,
        decimals: int | None = None,
    ) -> None:
        self.weight_sitelinks = (
            weight_sitelinks if weight_sitelinks is not None else self.WEIGHT_SITELINKS
        )
        self.weight_pageviews = (
            weight_pageviews if weight_pageviews is not None else self.WEIGHT_PAGEVIEWS
        )
        self.weight_backlinks = (
            weight_backlinks if weight_backlinks is not None else self.WEIGHT_BACKLINKS
        )
        self.decimals = decimals if decimals is not None else self.DECIMALS

    def score_from_values(
        self,
        sitelink_count: int,
        pageviews_30d: int,
        backlink_count: int,
    ) -> float:
        range_s = self.NORM_SITELINKS_MAX - self.NORM_SITELINKS_MIN
        range_log_pv = math.log1p(self.NORM_PAGEVIEWS_MAX_RAW) - math.log1p(0)
        range_b = self.NORM_BACKLINKS_MAX - self.NORM_BACKLINKS_MIN

        s = _scale(
            float(sitelink_count),
            self.NORM_SITELINKS_MIN,
            range_s,
        )
        p = _scale(
            math.log1p(pageviews_30d),
            math.log1p(0),
            range_log_pv,
        )
        bl_capped = min(backlink_count, BACKLINKS_CAP)
        b = _scale(
            float(bl_capped),
            self.NORM_BACKLINKS_MIN,
            range_b,
        )
        value = (
            self.weight_sitelinks * s
            + self.weight_pageviews * p
            + self.weight_backlinks * b
        )
        if sitelink_count < self.SITELINKS_MIN_THRESHOLD:
            value *= self.SITELINKS_LOW_MULTIPLIER
        return round(value, self.decimals)

    def score_for_event(self, event: "Event") -> float:
        return self.score_from_values(
            sitelink_count=event.sitelink_count or 0,
            pageviews_30d=event.pageviews_30d or 0,
            backlink_count=event.backlink_count or 0,
        )


_default_scorer: ImportanceScorer | None = None


def get_scorer() -> ImportanceScorer:
    global _default_scorer
    if _default_scorer is None:
        _default_scorer = ImportanceScorer()
    return _default_scorer
