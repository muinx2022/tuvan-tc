from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from common.response import api_error


class BadRequestError(Exception):
    pass


class NotFoundError(Exception):
    pass


class ForbiddenError(Exception):
    pass


def _coerce_error_message(detail) -> str:
    if isinstance(detail, dict):
        if "detail" in detail:
            return _coerce_error_message(detail["detail"])
        parts: list[str] = []
        for _, value in detail.items():
            if isinstance(value, list):
                parts.extend(str(item) for item in value)
            else:
                parts.append(str(value))
        return ", ".join(parts) if parts else "Request failed"
    if isinstance(detail, list):
        return ", ".join(str(item) for item in detail) if detail else "Request failed"
    return str(detail)


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            msg = _coerce_error_message(response.data) or "Bad request"
            return Response(api_error(msg), status=status.HTTP_400_BAD_REQUEST)
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            return Response(
                api_error(_coerce_error_message(getattr(exc, "detail", response.data)) or "Unauthorized"),
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if response.status_code == status.HTTP_403_FORBIDDEN:
            return Response(api_error(_coerce_error_message(response.data) or "Forbidden"), status=status.HTTP_403_FORBIDDEN)
        return Response(api_error(_coerce_error_message(response.data)), status=response.status_code)

    if isinstance(exc, NotFoundError):
        return Response(api_error(str(exc)), status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, BadRequestError):
        return Response(api_error(str(exc)), status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, ForbiddenError):
        return Response(api_error(str(exc)), status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, ValueError):
        return Response(api_error(str(exc)), status=status.HTTP_400_BAD_REQUEST)

    return None
