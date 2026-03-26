"""
In ra CLI mỗi HTTP request (method, path, status, thời gian).

Dùng print(..., flush=True) ra stderr để trên Windows / IDE không bị buffer
khiến logging không hiện (runserver vẫn in dòng [API] ngay lập tức).
"""

import logging
import sys
import time

from django.conf import settings

logger = logging.getLogger("api.request")


def _cli_log(line: str) -> None:
    """Luôn hiện trong terminal (không phụ thuộc cấu hình logging)."""
    print(line, file=sys.stderr, flush=True)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "APP_LOG_REQUESTS", True):
            return self.get_response(request)

        t0 = time.monotonic()
        path = request.get_full_path()
        method = request.method
        _cli_log(f"[API] >>> {method} {path}")

        response = self.get_response(request)

        elapsed_ms = (time.monotonic() - t0) * 1000
        status = getattr(response, "status_code", "?")
        line = f"[API] <<< {method} {path} -> {status} {elapsed_ms:.1f}ms"
        _cli_log(line)
        logger.info("%s %s -> %s %.1fms", method, path, status, elapsed_ms)
        return response
