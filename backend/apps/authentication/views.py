from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication import services as auth_services
from common.response import api_error, api_ok


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data or {}
        full_name = (data.get("fullName") or data.get("full_name") or "").strip()
        email = (data.get("email") or "").strip()
        password = data.get("password") or ""
        if not full_name:
            return Response(api_error("Full name is required"), status=400)
        if not email:
            return Response(api_error("Email is required"), status=400)
        if len(password) < 6:
            return Response(api_error("Password must be at least 6 chars"), status=400)
        try:
            result = auth_services.register_user(full_name, email, password)
            return Response(api_ok("Registered successfully", result))
        except ValueError as e:
            return Response(api_error(str(e)), status=400)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data or {}
        email = (data.get("email") or "").strip()
        password = data.get("password") or ""
        if not email:
            return Response(api_error("Email is required"), status=400)
        if len(password) < 6:
            return Response(api_error("Password must be at least 6 chars"), status=400)
        try:
            result = auth_services.login_user(email, password)
            return Response(api_ok("Logged in successfully", result))
        except ValueError as e:
            return Response(api_error(str(e)), status=400)


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data or {}
        id_token = data.get("idToken") or data.get("id_token")
        if not id_token:
            return Response(api_error("idToken is required"), status=400)
        try:
            result = auth_services.google_login(id_token)
            return Response(api_ok("Logged in with Google successfully", result))
        except ValueError as e:
            return Response(api_error(str(e)), status=400)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data or {}
        email = (data.get("email") or "").strip()
        if not email:
            return Response(api_error("Email is required"), status=400)
        result = auth_services.forgot_password(email)
        # Serialize expiresAt for JSON
        if result.get("expiresAt") is not None:
            result = {**result, "expiresAt": result["expiresAt"].isoformat()}
        return Response(api_ok("Password reset instructions prepared", result))


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data or {}
        token = data.get("token") or ""
        password = data.get("password") or ""
        if len(password) < 6:
            return Response(api_error("Password must be at least 6 chars"), status=400)
        try:
            auth_services.reset_password(token, password)
            return Response(api_ok("Password updated successfully"))
        except ValueError as e:
            return Response(api_error(str(e)), status=400)


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data or {}
        refresh = data.get("refreshToken") or data.get("refresh_token")
        if not refresh:
            return Response(api_error("Refresh token is required"), status=400)
        try:
            result = auth_services.refresh_tokens(refresh)
            return Response(api_ok("Token refreshed successfully", result))
        except ValueError as e:
            return Response(api_error(str(e)), status=400)
