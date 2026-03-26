from __future__ import annotations

from decimal import Decimal

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.models import Product
from common.auth_user import AuthUser
from common.jwt_auth import get_current_user
from common.response import api_error, api_ok
from django.utils import timezone


def _product_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "ownerId": p.owner_id,
        "ownerName": p.owner.full_name,
        "name": p.name,
        "description": p.description,
        "price": float(p.price) if p.price is not None else None,
        "createdAt": p.created_at.isoformat() if p.created_at else None,
        "updatedAt": p.updated_at.isoformat() if p.updated_at else None,
    }


class ProductListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = [_product_dict(p) for p in Product.objects.select_related("owner").order_by("id")]
        return Response(api_ok("Fetched products successfully", data))

    def post(self, request):
        u = get_current_user(request)
        if not isinstance(u, AuthUser):
            return Response(api_error("Unauthorized"), status=401)
        d = request.data or {}
        from apps.users.models import User

        owner = User.objects.get(pk=u.id)
        now = timezone.now()
        p = Product(
            owner=owner,
            name=(d.get("name") or "").strip(),
            description=d.get("description"),
            price=Decimal(str(d.get("price") or "0")),
            created_at=now,
            updated_at=now,
        )
        p.save()
        return Response(api_ok("Product created successfully", _product_dict(p)))


class ProductDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        try:
            p = Product.objects.select_related("owner").get(pk=pk)
            return Response(api_ok("Fetched product successfully", _product_dict(p)))
        except Product.DoesNotExist:
            return Response(api_error("Product not found"), status=404)

    def put(self, request, pk: int):
        u = get_current_user(request)
        if not isinstance(u, AuthUser):
            return Response(api_error("Unauthorized"), status=401)
        try:
            p = Product.objects.select_related("owner").get(pk=pk)
        except Product.DoesNotExist:
            return Response(api_error("Product not found"), status=404)
        if p.owner_id != u.id and u.role != "ROLE_ADMIN":
            return Response(api_error("You do not have permission to update this product"), status=403)
        d = request.data or {}
        p.name = (d.get("name") or "").strip()
        p.description = d.get("description")
        p.price = Decimal(str(d.get("price") or "0"))
        p.updated_at = timezone.now()
        p.save()
        return Response(api_ok("Product updated successfully", _product_dict(p)))

    def delete(self, request, pk: int):
        u = get_current_user(request)
        if not isinstance(u, AuthUser):
            return Response(api_error("Unauthorized"), status=401)
        try:
            p = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response(api_error("Product not found"), status=404)
        if p.owner_id != u.id and u.role != "ROLE_ADMIN":
            return Response(api_error("You do not have permission to delete this product"), status=403)
        p.delete()
        return Response(api_ok("Product deleted successfully"))
