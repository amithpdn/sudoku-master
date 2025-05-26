# middleware.py
import time as time_module
import logging
import json
import traceback
from django.conf import settings

logger = logging.getLogger("sudoku")


class PerformanceMonitoringMiddleware:
    """
    Middleware to monitor request/response performance and log slow requests.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.slow_threshold = getattr(
            settings, "SLOW_REQUEST_THRESHOLD", 1.0
        )  # seconds

    def __call__(self, request):
        # Start timer
        start_time = time_module.time()

        # Process the request
        response = self.get_response(request)

        # Calculate request time
        duration = time_module.time() - start_time

        # Log slow requests
        if duration > self.slow_threshold:
            log_data = {
                "duration": duration,
                "path": request.path,
                "method": request.method,
                "status_code": response.status_code,
            }

            # Add user info if authenticated
            if request.user.is_authenticated:
                log_data["user_id"] = request.user.id

            # Add session info (safely)
            if hasattr(request, "session") and hasattr(request.session, "session_key"):
                # Don't log the actual session key for security
                log_data["has_session"] = bool(request.session.session_key)

            logger.warning(f"Slow request: {json.dumps(log_data)}")

        return response

    def process_exception(self, request, exception):
        """Log exceptions with contextual information."""
        log_data = {
            "path": request.path,
            "method": request.method,
            "exception": str(exception),
            "traceback": traceback.format_exc(),
        }

        # Add user info if authenticated
        if request.user.is_authenticated:
            log_data["user_id"] = request.user.id

        # Add session info (safely)
        if hasattr(request, "session") and hasattr(request.session, "session_key"):
            # Don't log the actual session key for security
            log_data["has_session"] = bool(request.session.session_key)

        logger.error(f"Exception in request: {json.dumps(log_data)}")
        return None  # Let Django handle the exception
