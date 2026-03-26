from django.db import models


class MediaSetting(models.Model):
    id = models.BigAutoField(primary_key=True)
    provider = models.CharField(max_length=50)
    local_root_path = models.CharField(max_length=500, null=True, blank=True, db_column="local_root_path")
    local_public_base_url = models.CharField(max_length=500, null=True, blank=True, db_column="local_public_base_url")
    cloudinary_cloud_name = models.CharField(max_length=255, null=True, blank=True, db_column="cloudinary_cloud_name")
    cloudinary_api_key = models.CharField(max_length=255, null=True, blank=True, db_column="cloudinary_api_key")
    cloudinary_api_secret = models.CharField(max_length=255, null=True, blank=True, db_column="cloudinary_api_secret")
    cloudinary_folder = models.CharField(max_length=255, null=True, blank=True, db_column="cloudinary_folder")
    cloudflare_s3_endpoint = models.CharField(max_length=500, null=True, blank=True, db_column="cloudflare_s3_endpoint")
    cloudflare_s3_access_key = models.CharField(max_length=255, null=True, blank=True, db_column="cloudflare_s3_access_key")
    cloudflare_s3_secret_key = models.CharField(max_length=255, null=True, blank=True, db_column="cloudflare_s3_secret_key")
    cloudflare_s3_bucket = models.CharField(max_length=255, null=True, blank=True, db_column="cloudflare_s3_bucket")
    cloudflare_s3_region = models.CharField(max_length=100, null=True, blank=True, db_column="cloudflare_s3_region")
    cloudflare_s3_public_base_url = models.CharField(max_length=500, null=True, blank=True, db_column="cloudflare_s3_public_base_url")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "media_settings"


class DnseSetting(models.Model):
    id = models.BigAutoField(primary_key=True)
    api_key = models.CharField(max_length=255, null=True, blank=True, db_column="api_key")
    api_secret = models.CharField(max_length=255, null=True, blank=True, db_column="api_secret")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "dnse_settings"


class AppSetting(models.Model):
    id = models.BigAutoField(primary_key=True)
    setting_key = models.CharField(max_length=255, unique=True, db_column="setting_key")
    setting_value = models.TextField(null=True, blank=True, db_column="setting_value")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "app_settings"
