from __future__ import annotations

from rest_framework import serializers

from common.serializers import PageQuerySerializer


class StockListQuerySerializer(PageQuerySerializer):
    ticker = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    industryGroupId = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class StockHistoryQuerySerializer(PageQuerySerializer):
    pass


class IndustryAnalyticsQuerySerializer(serializers.Serializer):
    industryGroupId = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class TickerAnalyticsQuerySerializer(serializers.Serializer):
    ticker = serializers.CharField()


class AllocationQuerySerializer(serializers.Serializer):
    topN = serializers.IntegerField(required=False, default=8, min_value=1, max_value=20)


class TickerAllocationQuerySerializer(AllocationQuerySerializer):
    ticker = serializers.CharField()


class T0SnapshotListQuerySerializer(PageQuerySerializer):
    ticker = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    tradingDate = serializers.DateField(required=False, allow_null=True)


class T0SnapshotTimelineQuerySerializer(serializers.Serializer):
    tradingDate = serializers.DateField(required=False, allow_null=True)


class ForeignTradingListQuerySerializer(PageQuerySerializer):
    ticker = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    industryGroupId = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    tradingDate = serializers.DateField(required=False, allow_null=True)


class ForeignTradingTimelineQuerySerializer(PageQuerySerializer):
    tradingDateFrom = serializers.DateField(required=False, allow_null=True)
    tradingDateTo = serializers.DateField(required=False, allow_null=True)
