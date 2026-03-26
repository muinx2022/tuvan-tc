from django.db import models


class StockIndustryGroup(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "stock_industry_groups"


class StockSymbol(models.Model):
    id = models.BigAutoField(primary_key=True)
    ticker = models.CharField(max_length=20, unique=True)
    organ_code = models.CharField(max_length=50, null=True, blank=True, db_column="organ_code")
    organ_name = models.CharField(max_length=255, null=True, blank=True, db_column="organ_name")
    organ_short_name = models.CharField(max_length=120, null=True, blank=True, db_column="organ_short_name")
    icb_code = models.CharField(max_length=50, null=True, blank=True, db_column="icb_code")
    icb_name2 = models.CharField(max_length=255, null=True, blank=True, db_column="icb_name2")
    industry_group = models.ForeignKey(
        StockIndustryGroup,
        models.SET_NULL,
        null=True,
        blank=True,
        db_column="industry_group_id",
        related_name="stock_symbols",
    )
    listing_date = models.CharField(max_length=50, null=True, blank=True, db_column="listing_date")
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "stock_symbols"


class StockHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    ticker = models.CharField(max_length=20)
    trading_date = models.DateField(db_column="trading_date")
    open_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, db_column="open_price")
    high_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, db_column="high_price")
    low_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, db_column="low_price")
    close_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, db_column="close_price")
    volume = models.BigIntegerField(null=True, blank=True)
    avg_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, db_column="avg_price")
    price_changed = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, db_column="price_changed")
    per_price_change = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, db_column="per_price_change")
    total_match_vol = models.BigIntegerField(null=True, blank=True, db_column="total_match_vol")
    total_match_val = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, db_column="total_match_val")
    foreign_buy_vol_total = models.BigIntegerField(null=True, blank=True, db_column="foreign_buy_vol_total")
    foreign_sell_vol_total = models.BigIntegerField(null=True, blank=True, db_column="foreign_sell_vol_total")
    raw_payload = models.TextField(null=True, blank=True, db_column="raw_payload")
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "stock_histories"


class StockT0RealtimeState(models.Model):
    id = models.BigAutoField(primary_key=True)
    ticker = models.CharField(max_length=20, unique=True)
    trading_date = models.DateField(db_column="trading_date")
    last_message_at = models.DateTimeField(db_column="last_message_at")
    total_match_vol = models.BigIntegerField(null=True, blank=True, db_column="total_match_vol")
    total_match_val = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True, db_column="total_match_val")
    raw_payload = models.TextField(null=True, blank=True, db_column="raw_payload")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "stock_t0_realtime_state"


class StockT0ForeignState(models.Model):
    id = models.BigAutoField(primary_key=True)
    ticker = models.CharField(max_length=20)
    trading_date = models.DateField(db_column="trading_date")
    source_exchange = models.CharField(max_length=20, null=True, blank=True, db_column="source_exchange")
    buy_foreign_qtty = models.BigIntegerField(null=True, blank=True, db_column="buy_foreign_qtty")
    sell_foreign_qtty = models.BigIntegerField(null=True, blank=True, db_column="sell_foreign_qtty")
    buy_foreign_value = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True, db_column="buy_foreign_value")
    sell_foreign_value = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True, db_column="sell_foreign_value")
    fetched_at = models.DateTimeField(db_column="fetched_at")
    raw_payload = models.TextField(null=True, blank=True, db_column="raw_payload")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "stock_t0_foreign_state"


class StockT0Snapshot(models.Model):
    id = models.BigAutoField(primary_key=True)
    ticker = models.CharField(max_length=20)
    trading_date = models.DateField(db_column="trading_date")
    snapshot_slot = models.CharField(max_length=5, db_column="snapshot_slot")
    snapshot_at = models.DateTimeField(db_column="snapshot_at")
    total_match_vol = models.BigIntegerField(null=True, blank=True, db_column="total_match_vol")
    total_match_val = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True, db_column="total_match_val")
    foreign_buy_vol_total = models.BigIntegerField(null=True, blank=True, db_column="foreign_buy_vol_total")
    foreign_sell_vol_total = models.BigIntegerField(null=True, blank=True, db_column="foreign_sell_vol_total")
    foreign_buy_val_total = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True, db_column="foreign_buy_val_total")
    foreign_sell_val_total = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True, db_column="foreign_sell_val_total")
    net_foreign_vol = models.BigIntegerField(null=True, blank=True, db_column="net_foreign_vol")
    net_foreign_val = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True, db_column="net_foreign_val")
    foreign_data_source = models.CharField(max_length=30, null=True, blank=True, db_column="foreign_data_source")
    raw_payload = models.TextField(null=True, blank=True, db_column="raw_payload")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "stock_t0_snapshots"
