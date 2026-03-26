from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.stock_finance.assessment_service import backfill_generated_assessments


class Command(BaseCommand):
    help = "Generate overview finance assessments for tickers with both QUARTER and YEAR snapshots."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        result = backfill_generated_assessments(limit=options.get("limit"))
        self.stdout.write(self.style.SUCCESS(str(result)))
