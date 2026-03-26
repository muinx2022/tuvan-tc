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


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            detail = response.data
            if isinstance(detail, dict):
                if "detail" in detail:
                    msg = str(detail["detail"])
                else:
                    parts = []
                    for k, v in detail.items():
                        if isinstance(v, list):
                            parts.extend(str(x) for x in v)
                        else:
                            parts.append(str(v))
                    msg = ", ".join(parts) if parts else "Bad request"
            else:
                msg = str(detail)
            return Response(api_error(msg), status=status.HTTP_400_BAD_REQUEST)
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            return Response(
                api_error(getattr(exc, "detail", str(exc)) or "Unauthorized"),
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if response.status_code == status.HTTP_403_FORBIDDEN:
            return Response(api_error(str(response.data.get("detail", "Forbidden"))), status=status.HTTP_403_FORBIDDEN)
        return Response(api_error(str(response.data)), status=response.status_code)

    if isinstance(exc, NotFoundError):
        return Response(api_error(str(exc)), status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, BadRequestError):
        return Response(api_error(str(exc)), status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, ForbiddenError):
        return Response(api_error(str(exc)), status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, ValueError):
        return Response(api_error(str(exc)), status=status.HTTP_400_BAD_REQUEST)

    return None
