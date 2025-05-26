"""
Custom Django Middleware for Sudoku Game Application

This module implements custom middleware components that provide cross-cutting
functionality for the Sudoku application, including performance monitoring,
request/response logging, and exception handling.

Middleware in Django processes requests and responses globally across all views,
making it ideal for monitoring, logging, security, and performance optimization.

Key Features:
- Performance monitoring with configurable slow request detection
- Comprehensive exception logging with contextual information
- Security-conscious logging (no sensitive data exposure)
- JSON-structured logs for analytics and monitoring
- User and session context tracking
"""

import time as time_module
import logging
import json
import traceback
from django.conf import settings

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Configure logger for the Sudoku application
# This logger should be configured in Django settings.py with appropriate
# handlers, formatters, and log levels for different environments
logger = logging.getLogger("sudoku")

# =============================================================================
# PERFORMANCE MONITORING MIDDLEWARE
# =============================================================================

class PerformanceMonitoringMiddleware:
    """
    Middleware to monitor request/response performance and identify slow requests.
    
    This middleware measures the time taken to process each request and logs
    requests that exceed a configurable threshold. This helps identify performance
    bottlenecks, slow database queries, and optimization opportunities.
    
    Features:
    - Configurable slow request threshold
    - Request timing measurement
    - Contextual logging with user and session information
    - Exception logging with full context
    - Security-conscious data handling
    
    Configuration:
    Add to MIDDLEWARE in settings.py:
        MIDDLEWARE = [
            ...
            'sudoku.middleware.PerformanceMonitoringMiddleware',
            ...
        ]
    
    Optional setting in settings.py:
        SLOW_REQUEST_THRESHOLD = 2.0  # seconds
    """
    
    def __init__(self, get_response):
        """
        Initialize the middleware with the next middleware/view in the chain.
        
        This method is called once when Django starts up, not for each request.
        Use it for one-time configuration and setup.
        
        Args:
            get_response (callable): The next middleware or view in the chain
        """
        self.get_response = get_response
        
        # Configure slow request threshold from Django settings
        # Default to 1.0 second if not specified
        self.slow_threshold = getattr(
            settings, "SLOW_REQUEST_THRESHOLD", 1.0
        )
        
        # Log initialization for debugging
        logger.info(
            f"PerformanceMonitoringMiddleware initialized with "
            f"slow_threshold={self.slow_threshold}s"
        )

    def __call__(self, request):
        """
        Process each request and measure performance.
        
        This method is called for every request to the application.
        It measures request processing time and logs slow requests.
        
        Args:
            request (HttpRequest): The incoming Django request
            
        Returns:
            HttpResponse: The response from the view/middleware chain
        """
        # Record start time for performance measurement
        start_time = time_module.time()
        
        # Process the request through the middleware/view chain
        response = self.get_response(request)
        
        # Calculate total request processing duration
        duration = time_module.time() - start_time
        
        # Log slow requests with comprehensive context
        if duration > self.slow_threshold:
            # Prepare structured log data
            log_data = {
                "duration": round(duration, 3),          # Request processing time
                "path": request.path,                    # URL path
                "method": request.method,                # HTTP method (GET, POST, etc.)
                "status_code": response.status_code,     # HTTP response status
                "query_params": bool(request.GET),       # Whether query parameters exist
                "post_data": bool(request.POST),         # Whether POST data exists
                "content_length": len(getattr(response, 'content', b'')),  # Response size
            }
            
            # Add user context if authenticated (for debugging user-specific issues)
            if hasattr(request, 'user') and request.user.is_authenticated:
                log_data["user_id"] = request.user.id
                log_data["user_is_staff"] = request.user.is_staff
                log_data["user_is_superuser"] = request.user.is_superuser
            
            # Add session context (safely, without exposing session data)
            if hasattr(request, "session") and hasattr(request.session, "session_key"):
                # Don't log the actual session key for security reasons
                log_data["has_session"] = bool(request.session.session_key)
                log_data["session_items_count"] = len(request.session.keys())
                
                # Log transaction ID if available (safe to log)
                if "trx-id" in request.session:
                    log_data["transaction_id"] = request.session["trx-id"]
            
            # Add request metadata
            log_data.update({
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:100],  # Truncated
                "remote_addr": self._get_client_ip(request),
                "server_name": request.META.get("SERVER_NAME", ""),
                "is_ajax": request.headers.get('X-Requested-With') == 'XMLHttpRequest',
            })
            
            # Log the slow request with structured data
            logger.warning(f"Slow request detected: {json.dumps(log_data, indent=2)}")
        
        return response

    def process_exception(self, request, exception):
        """
        Log exceptions with comprehensive contextual information.
        
        This method is called whenever a view raises an exception.
        It logs detailed information about the exception and request
        context to aid in debugging and error analysis.
        
        Args:
            request (HttpRequest): The request that caused the exception
            exception (Exception): The exception that was raised
            
        Returns:
            None: Let Django handle the exception normally
        """
        # Prepare comprehensive exception log data
        log_data = {
            "path": request.path,
            "method": request.method,
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "traceback": traceback.format_exc(),
            "request_data": {
                "get_params": dict(request.GET),
                "post_params": {k: "***" if "password" in k.lower() else v 
                              for k, v in request.POST.items()},  # Hide passwords
                "files": list(request.FILES.keys()),
            }
        }
        
        # Add user context for authenticated users
        if hasattr(request, 'user') and request.user.is_authenticated:
            log_data["user_context"] = {
                "user_id": request.user.id,
                "username": request.user.username,
                "is_staff": request.user.is_staff,
                "is_superuser": request.user.is_superuser,
            }
        
        # Add session context (safely)
        if hasattr(request, "session") and hasattr(request.session, "session_key"):
            log_data["session_context"] = {
                "has_session": bool(request.session.session_key),
                "session_keys": list(request.session.keys()),
                "transaction_id": request.session.get("trx-id"),
            }
        
        # Add request metadata
        log_data["request_metadata"] = {
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
            "remote_addr": self._get_client_ip(request),
            "referer": request.META.get("HTTP_REFERER", ""),
            "content_type": request.META.get("CONTENT_TYPE", ""),
            "content_length": request.META.get("CONTENT_LENGTH", 0),
        }
        
        # Log the exception with full context
        logger.error(f"Exception in request processing: {json.dumps(log_data, indent=2)}")
        
        # Return None to let Django's default exception handling take over
        # This ensures proper error pages are shown to users
        return None

    def _get_client_ip(self, request):
        """
        Extract the client's IP address from the request.
        
        This method handles various proxy configurations and headers
        to accurately determine the client's real IP address.
        
        Args:
            request (HttpRequest): The Django request object
            
        Returns:
            str: The client's IP address
        """
        # Check for IP forwarded by proxies (common in production deployments)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP in the chain (original client)
            ip = x_forwarded_for.split(',')[0].strip()
            return ip
        
        # Check for real IP header (used by some load balancers)
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip.strip()
        
        # Fall back to direct connection IP
        return request.META.get('REMOTE_ADDR', 'unknown')

