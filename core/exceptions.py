from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    """
    Returns all errors in a consistent format:
    {
        "error": true,
        "code": "ERROR_CODE",
        "message": "Human-readable message",
        "details": {}
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            "error": True,
            "code": _get_error_code(response.status_code),
            "message": _extract_message(response.data),
            "details": response.data if isinstance(response.data, dict) else {},
        }
        response.data = error_data

    return response


def _get_error_code(status_code: int) -> str:
    codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        402: "PAYMENT_REQUIRED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        429: "RATE_LIMITED",
        500: "SERVER_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    return codes.get(status_code, "ERROR")


def _extract_message(data) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("detail", "error", "message", "non_field_errors"):
            if key in data:
                val = data[key]
                if isinstance(val, list) and val:
                    return str(val[0])
                return str(val)
        first = next(iter(data.values()), "An error occurred")
        if isinstance(first, list) and first:
            return str(first[0])
        return str(first)
    if isinstance(data, list) and data:
        return str(data[0])
    return "An error occurred"