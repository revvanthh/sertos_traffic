"""
Custom Django REST Framework Exception Handler for SERTOS.

Enforces:
1. Uniform JSON response envelope across all framework-level API errors:
   - success: False
   - data: {}
   - message: Human-readable error description
   - errors: Structured dictionary of field-level or general errors
   - detail: Backwards-compatible string for legacy/DRF clients
   - timestamp: ISO 8601 UTC timestamp
2. Exact preservation of HTTP status codes (400, 401, 403, 404, 405, etc.).
3. Safe delegation of unhandled server errors (500) to Django's standard error logger.
4. Protection against leaking secrets, passwords, or raw stack traces in error envelopes.
"""

from django.utils import timezone
from rest_framework.views import exception_handler


def sertos_exception_handler(exc, context):
    """
    Custom exception handler that wraps DRF APIException responses into
    the uniform SERTOS standard response envelope.
    """
    # 1. Call REST framework's default exception handler to get the standard response
    response = exception_handler(exc, context)

    # 2. If response is None, an unhandled exception (e.g. 500 Internal Server Error) occurred.
    # Return None so Django's standard 500 handling, logging, and error tracking take effect.
    if response is None:
        return None

    # 3. Normalize errors and message from response.data
    errors = {}
    message = "An error occurred while processing the request."

    raw_data = response.data

    if isinstance(raw_data, dict):
        errors = raw_data
        if "detail" in raw_data:
            message = str(raw_data["detail"])
        elif "non_field_errors" in raw_data:
            message = str(raw_data["non_field_errors"][0])
        else:
            # Field-level validation error
            first_key = next(iter(raw_data))
            first_err = raw_data[first_key]
            if isinstance(first_err, list) and len(first_err) > 0:
                message = f"{first_key}: {first_err[0]}"
            else:
                message = f"Validation failed on field '{first_key}'."
    elif isinstance(raw_data, list):
        errors = {"detail": raw_data}
        message = str(raw_data[0]) if raw_data else "Validation error occurred."
    else:
        errors = {"detail": [str(raw_data)]}
        message = str(raw_data)

    # 4. Construct uniform envelope while preserving backwards compatibility
    response.data = {
        "success": False,
        "data": {},
        "message": message,
        "errors": errors,
        "detail": message,  # Preserves DRF client compatibility
        "timestamp": timezone.now().isoformat(),
    }

    return response
