from __future__ import annotations

from rest_framework import serializers


ROLE_CHOICES = ("ROLE_USER", "ROLE_AUTHENTICATED", "ROLE_ADMIN")


class UserCreateSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=120, trim_whitespace=True)
    email = serializers.EmailField(max_length=160)
    password = serializers.CharField(min_length=6, trim_whitespace=False)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, required=False, default="ROLE_AUTHENTICATED")
    roleIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )


class UserUpdateSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=120, trim_whitespace=True)
    email = serializers.EmailField(max_length=160)
    password = serializers.CharField(required=False, allow_blank=True, allow_null=True, min_length=6, trim_whitespace=False)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, required=False, default="ROLE_AUTHENTICATED")
    roleIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )


class UserRolePatchSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ROLE_CHOICES)


class UserRbacPatchSerializer(serializers.Serializer):
    roleIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )
