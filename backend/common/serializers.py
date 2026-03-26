from __future__ import annotations

from rest_framework import serializers


class FlexibleIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if data in ("", None):
            if self.allow_null:
                return None
        return super().to_internal_value(data)


class CsvOrListIntegerField(serializers.Field):
    default_error_messages = {"invalid": "Expected a list of integers."}

    def to_internal_value(self, data):
        if data in (None, ""):
            return []
        if isinstance(data, str):
            values = [item.strip() for item in data.split(",") if item.strip()]
        elif isinstance(data, list):
            values = data
        else:
            self.fail("invalid")

        result: list[int] = []
        for value in values:
            try:
                result.append(int(value))
            except (TypeError, ValueError):
                self.fail("invalid")
        return result

    def to_representation(self, value):
        return value


class PageQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=0, min_value=0)
    size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=200)
