from __future__ import annotations

from rest_framework import serializers

from common.serializers import PageQuerySerializer


class FinanceChartSyncStartQuerySerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=("missing", "sync_missing", "SYNC_MISSING", "reset", "reset_and_sync", "RESET_AND_SYNC"), required=False, default="missing")


class FinanceChartTickerListQuerySerializer(PageQuerySerializer):
    ticker = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class FinanceChartAssessmentWriteSerializer(serializers.Serializer):
    overviewAssessment = serializers.CharField(required=False, allow_blank=True, allow_null=True)
