from __future__ import annotations

from rest_framework import serializers


class DnseSettingWriteSerializer(serializers.Serializer):
    apiKey = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    apiSecret = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)


class SsiFcSettingWriteSerializer(serializers.Serializer):
    consumerId = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    consumerSecret = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)


class GoogleOauthSettingWriteSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False, default=False)
    clientId = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
    clientSecret = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)


class HistorySyncScheduleWriteSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False, default=False)
    hour = serializers.IntegerField(required=False, min_value=0, max_value=23, default=0)
    minute = serializers.IntegerField(required=False, min_value=0, max_value=59, default=0)


class T0SnapshotScheduleWriteSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False, default=False)
    times = serializers.ListField(
        required=False,
        child=serializers.RegexField(regex=r"^\d{2}:\d{2}$"),
        allow_empty=True,
        default=list,
    )
    foreignRefreshMinutes = serializers.IntegerField(required=False, min_value=1, max_value=240, default=15)
    foreignStartTime = serializers.RegexField(required=False, regex=r"^\d{2}:\d{2}$", default="09:15")
    foreignEndTime = serializers.RegexField(required=False, regex=r"^\d{2}:\d{2}$", default="15:00")
    projectionSlots = serializers.ListField(
        required=False,
        child=serializers.RegexField(regex=r"^\d{2}:\d{2}$"),
        allow_empty=True,
        default=list,
    )
    projectionWindow20 = serializers.IntegerField(required=False, min_value=1, default=20)
    projectionWindow5 = serializers.IntegerField(required=False, min_value=1, default=5)
    projectionWeight20 = serializers.FloatField(required=False, min_value=0, default=0.6)
    projectionWeight5 = serializers.FloatField(required=False, min_value=0, default=0.4)
    projectionFinalSlot = serializers.RegexField(required=False, regex=r"^\d{2}:\d{2}$", default="15:00")


class MediaSettingWriteSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=("local", "cloudinary", "cloudflare_s3"), required=False, default="cloudinary")
    localRootPath = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
    localPublicBaseUrl = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
    cloudinaryCloudName = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    cloudinaryApiKey = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    cloudinaryApiSecret = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    cloudinaryFolder = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    cloudflareS3Endpoint = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
    cloudflareS3AccessKey = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    cloudflareS3SecretKey = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    cloudflareS3Bucket = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    cloudflareS3Region = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
    cloudflareS3PublicBaseUrl = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
