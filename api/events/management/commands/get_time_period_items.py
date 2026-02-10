import re

from django.core.management.base import BaseCommand

from api.events.wikidata.sparql import WikidataSparqlClient


class Command(BaseCommand):
    help = (
        "List Wikidata items with time period property (P2348) set to the "
        "given time period QID."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "period_qid",
            help="Wikidata time period QID (e.g. Q3938059).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Max number of items to fetch (default 500).",
        )

    def handle(self, *args, **options):
        period_qid = options["period_qid"].strip()
        if not re.match(r"^Q\d+$", period_qid):
            self.stderr.write(
                self.style.ERROR(f"Invalid QID: {period_qid}. Use format Q12345.")
            )
            return
        client = WikidataSparqlClient()
        items = client.fetch_items_by_time_period(
            period_qid=period_qid,
            limit=options["limit"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Found {len(items)} item(s) for time period {period_qid}:"
            )
        )
        for item in items:
            self.stdout.write(f"  {item['qid']}\t{item['label']}")
