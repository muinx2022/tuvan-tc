from __future__ import annotations

from rest_framework import serializers


class CategoryWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, trim_whitespace=True)
    parentId = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class CategoryStatusSerializer(serializers.Serializer):
    published = serializers.BooleanField()


class CategoryReorderItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
    parentId = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    sortOrder = serializers.IntegerField(min_value=0)


class CategoryTreeReorderSerializer(serializers.Serializer):
    items = CategoryReorderItemSerializer(many=True)
