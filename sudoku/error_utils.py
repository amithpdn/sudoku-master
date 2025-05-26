"""
Utility functions for handling errors and exceptions in the Sudoku application.
"""

import traceback
from django.shortcuts import render
from django.http import HttpResponseServerError
from .utils import log_to_json


def handle_view_exception(
    request, exception, error_title="Error", error_code=None, retry_url=None
):
    """
    Centralized error handling function for views.

    Args:
        request: Django HttpRequest object
        exception: The exception that was caught
        error_title: Human-readable title for the error page
        error_code: Optional error code for tracking purposes
        retry_url: Optional URL to try the action again

    Returns:
        HttpResponse: Rendered error page
    """
    # Get the exception details
    error_message = str(exception)
    error_traceback = traceback.format_exc()

    # Log the error with detailed information
    log_to_json(
        request,
        "error_handler",
        f"Error: {error_title} - {error_message}",
        log_level="ERROR",
        transaction_id=request.session.get("trx-id"),
        details=error_traceback,
    )

    # Create context for the error template
    context = {
        "error_title": error_title,
        "error_message": error_message,
        "error_details": error_traceback,
        "error_code": error_code,
        "retry_url": retry_url,
        "trx_id": request.session.get("trx-id"),
    }

    # Render the error template
    return render(request, "sudoku/error.html", context)


def missing_session_data_error(request, missing_keys=None):
    """
    Handle the specific case of missing session data.

    Args:
        request: Django HttpRequest object
        missing_keys: List of session keys that are missing

    Returns:
        HttpResponse: Rendered error page
    """
    if missing_keys is None:
        missing_keys = []

    # Prepare error message based on missing keys
    if missing_keys:
        error_message = (
            f"Session data is missing the following keys: {', '.join(missing_keys)}"
        )
    else:
        error_message = "Required session data is missing"

    # Log the error
    log_to_json(
        request,
        "session_error",
        f"Missing session data: {error_message}",
        log_level="ERROR",
        transaction_id=request.session.get("trx-id"),
        session_id=request.session.session_key,
    )

    # Create context for the error template
    context = {
        "error_title": "Session Data Error",
        "error_message": error_message,
        "error_details": f"The application requires certain data to be stored in your session. This data appears to be missing or invalid.\n\nMissing keys: {', '.join(missing_keys)}\n\nThis may happen if your session expired or cookies were cleared.",
        "error_code": "SESSION_DATA_MISSING",
        "retry_url": None,
        "trx_id": request.session.get("trx-id"),
    }

    # Render the error template
    return render(request, "sudoku/error.html", context)


def data_validation_error(request, validation_errors):
    """
    Handle data validation errors.

    Args:
        request: Django HttpRequest object
        validation_errors: Dictionary of field names and their error messages

    Returns:
        HttpResponse: Rendered error page
    """
    # Format the validation errors for display
    error_details = "\n".join(
        [f"{field}: {error}" for field, error in validation_errors.items()]
    )

    # Log the validation error
    log_to_json(
        request,
        "validation_error",
        f"Data validation error: {error_details}",
        log_level="WARNING",
        transaction_id=request.session.get("trx-id"),
    )

    # Create context for the error template
    context = {
        "error_title": "Invalid Data",
        "error_message": "The data you submitted contains errors",
        "error_details": error_details,
        "error_code": "VALIDATION_ERROR",
        "retry_url": request.META.get("HTTP_REFERER"),  # Go back to previous page
        "trx_id": request.session.get("trx-id"),
    }

    # Render the error template
    return render(request, "sudoku/error.html", context)
