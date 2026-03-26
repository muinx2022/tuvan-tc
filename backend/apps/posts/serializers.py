from __future__ import annotations

from rest_framework import serializers


class PostWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, trim_whitespace=True)
    content = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    published = serializers.BooleanField(required=False, default=False)
    categoryIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )
    authorId = serializers.IntegerField(required=False, allow_null=True, min_value=1)
