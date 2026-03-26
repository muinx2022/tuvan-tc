from django.db import models

from apps.stocks.models import StockSymbol


class StockFinanceChartSnapshot(models.Model):
    id = models.BigAutoField(primary_key=True)
    stock_symbol = models.ForeignKey(
        StockSymbol,
        models.CASCADE,
        db_column="stock_symbol_id",
        related_name="finance_snapshots",
    )
    ticker = models.CharField(max_length=20)
    chart_menu_id = models.BigIntegerField(db_column="chart_menu_id")
    chart_name = models.CharField(max_length=255, db_column="chart_name")
    report_type = models.CharField(max_length=20, db_column="report_type")
    report_period = models.CharField(max_length=50, null=True, blank=True, db_column="report_period")
    company_assessment = models.TextField(null=True, blank=True, db_column="company_assessment")
    processing_status = models.CharField(max_length=30, db_column="processing_status")
    data_json = models.TextField(db_column="data_json")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "stock_finance_chart_snapshots"


class StockFinanceChartAssessment(models.Model):
    id = models.BigAutoField(primary_key=True)
    stock_symbol = models.OneToOneField(
        StockSymbol,
        models.CASCADE,
        db_column="stock_symbol_id",
        related_name="finance_assessment",
    )
    ticker = models.CharField(max_length=20)
    overview_assessment = models.TextField(db_column="overview_assessment")
    assessment_status = models.CharField(max_length=30, db_column="assessment_status")
    source_synced_at = models.DateTimeField(null=True, blank=True, db_column="source_synced_at")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "stock_finance_chart_assessments"


class StockFinanceChartSyncJob(models.Model):
    id = models.BigAutoField(primary_key=True)
    mode = models.CharField(max_length=30)
    status = models.CharField(max_length=30)
    batch_no = models.IntegerField(db_column="batch_no")
    batch_size = models.IntegerField(db_column="batch_size")
    eligible_count = models.IntegerField(db_column="eligible_count")
    processed_count = models.IntegerField(db_column="processed_count")
    success_count = models.IntegerField(db_column="success_count")
    failed_count = models.IntegerField(db_column="failed_count")
    skipped_count = models.IntegerField(db_column="skipped_count")
    started_at = models.DateTimeField(null=True, blank=True, db_column="started_at")
    finished_at = models.DateTimeField(null=True, blank=True, db_column="finished_at")
    last_error = models.TextField(null=True, blank=True, db_column="last_error")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "stock_finance_chart_sync_jobs"


class StockFinanceChartSyncJobItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    job = models.ForeignKey(
        StockFinanceChartSyncJob,
        models.CASCADE,
        db_column="job_id",
        related_name="items",
    )
    stock_symbol = models.ForeignKey(
        StockSymbol,
        models.CASCADE,
        db_column="stock_symbol_id",
        related_name="finance_sync_job_items",
    )
    ticker = models.CharField(max_length=20)
    status = models.CharField(max_length=30)
    attempt_count = models.IntegerField(db_column="attempt_count")
    last_error = models.TextField(null=True, blank=True, db_column="last_error")
    started_at = models.DateTimeField(null=True, blank=True, db_column="started_at")
    finished_at = models.DateTimeField(null=True, blank=True, db_column="finished_at")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "stock_finance_chart_sync_job_items"
