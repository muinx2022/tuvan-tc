from typing import Any, Generic, TypeVar

T = TypeVar("T")


class ApiResponse(Generic[T]):
    __slots__ = ("success", "message", "data")

    def __init__(self, success: bool, message: str, data: T | None = None):
        self.success = success
        self.message = message
        self.data = data

    def as_dict(self) -> dict[str, Any]:
        return {"success": self.success, "message": self.message, "data": self.data}

    @staticmethod
    def ok(message: str, data: T | None = None) -> "ApiResponse[T]":
        return ApiResponse(True, message, data)

    @staticmethod
    def error(message: str) -> "ApiResponse[None]":
        return ApiResponse(False, message, None)


def api_ok(message: str, data: Any = None) -> dict[str, Any]:
    return ApiResponse.ok(message, data).as_dict()


def api_error(message: str) -> dict[str, Any]:
    return ApiResponse.error(message).as_dict()
