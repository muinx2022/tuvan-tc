from __future__ import annotations

from rest_framework import serializers


class RoleWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64, trim_whitespace=True)
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    permissionIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )
