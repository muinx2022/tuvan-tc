from __future__ import annotations

from rest_framework.response import Response

from apps.categories import services as cat_services
from apps.categories.serializers import (
    CategoryReorderItemSerializer,
    CategoryStatusSerializer,
    CategoryWriteSerializer,
)
from common.admin_api import AdminOnlyAPIView
from common.response import api_ok


class CategoryListView(AdminOnlyAPIView):
    def get(self, request):
        return Response(api_ok("Fetched categories successfully", cat_services.find_all()))

    def post(self, request):
        d = self.validate_body(CategoryWriteSerializer)
        return Response(
            api_ok(
                "Category created successfully",
                cat_services.create_cat(d["name"], d.get("parentId")),
            )
        )


class CategoryTreeView(AdminOnlyAPIView):
    def get(self, request):
        return Response(api_ok("Fetched category tree successfully", cat_services.find_tree()))

    def put(self, request):
        items = request.data or []
        if not isinstance(items, list):
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Expected a list of category reorder items.")
        serializer = CategoryReorderItemSerializer(data=items, many=True)
        serializer.is_valid(raise_exception=True)
        cat_services.reorder(serializer.validated_data)
        return Response(api_ok("Category tree updated successfully"))


class CategoryDetailView(AdminOnlyAPIView):
    def get(self, request, pk: int):
        return Response(api_ok("Fetched category successfully", cat_services.find_one(pk)))

    def put(self, request, pk: int):
        d = self.validate_body(CategoryWriteSerializer)
        return Response(
            api_ok(
                "Category updated successfully",
                cat_services.update_cat(pk, d["name"], d.get("parentId")),
            )
        )

    def delete(self, request, pk: int):
        cat_services.delete_cat(pk)
        return Response(api_ok("Category deleted successfully"))


class CategoryStatusView(AdminOnlyAPIView):
    def patch(self, request, pk: int):
        d = self.validate_body(CategoryStatusSerializer)
        return Response(
            api_ok(
                "Category status updated successfully",
                cat_services.update_publish(pk, d["published"]),
            )
        )
