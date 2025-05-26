"""
Error Handling Utilities for Sudoku Application

This module provides centralized error handling functionality to ensure
consistent error reporting, logging, and user experience across the entire
Sudoku application. It implements a structured approach to exception management
with detailed logging and user-friendly error pages.

Key Features:
- Centralized error handling for consistent UX
- Detailed error logging with JSON structure for analytics
- Context-aware error messages and recovery suggestions
- Security-conscious error reporting (no sensitive data exposure)
- Integration with Django's template system for branded error pages

Usage:
    from .error_utils import handle_view_exception, missing_session_data_error
    
    try:
        # risky operation
        process_puzzle_data()
    except Exception as e:
        return handle_view_exception(request, e, "Puzzle Processing Error")
"""

import traceback
from django.shortcuts import render
from django.http import HttpResponseServerError
from .utils import log_to_json

# =============================================================================
# CORE ERROR HANDLING FUNCTIONS
# =============================================================================

def handle_view_exception(
    request, exception, error_title="Error", error_code=None, retry_url=None
):
    """
    Centralized error handling function for Django views.
    
    This function provides consistent error handling across all views,
    ensuring that exceptions are properly logged, users receive helpful
    error messages, and the application maintains a professional appearance
    even when things go wrong.
    
    Features:
    - Automatic error logging with contextual information
    - User-friendly error page rendering
    - Optional retry functionality for recoverable errors
    - Security-conscious error reporting
    
    Args:
        request (HttpRequest): Django request object for context
        exception (Exception): The caught exception object
        error_title (str): Human-readable title for the error page
        error_code (str, optional): Error code for tracking and debugging
        retry_url (str, optional): URL to retry the failed operation
        
    Returns:
        HttpResponse: Rendered error page with appropriate context
        
    Example Usage:
        try:
            puzzle = generate_sudoku_puzzle()
        except PuzzleGenerationError as e:
            return handle_view_exception(
                request, 
                e, 
                "Puzzle Generation Failed",
                error_code="PUZZLE_GEN_001",
                retry_url="/sudoku/new/"
            )
    """
    # Extract exception details for logging and display
    error_message = str(exception)
    error_traceback = traceback.format_exc()

    # Log comprehensive error information for debugging
    # Uses JSON logging for structured log analysis
    log_to_json(
        request,
        "error_handler",
        f"Error: {error_title} - {error_message}",
        log_level="ERROR",
        transaction_id=request.session.get("trx-id"),
        details=error_traceback,
    )

    # Prepare context for error template rendering
    context = {
        "error_title": error_title,           # Main error heading
        "error_message": error_message,       # Brief error description
        "error_details": error_traceback,     # Technical details for debugging
        "error_code": error_code,             # Tracking code for support
        "retry_url": retry_url,               # Recovery action URL
        "trx_id": request.session.get("trx-id"),  # Transaction context
    }

    # Render the branded error template with error context
    return render(request, "sudoku/error.html", context)


# =============================================================================
# SPECIFIC ERROR HANDLERS
# =============================================================================

def missing_session_data_error(request, missing_keys=None):
    """
    Handle the specific case of missing or corrupted session data.
    
    Session data is critical for the Sudoku game as it maintains puzzle
    state, user progress, and transaction context. This function provides
    specialized handling for session-related errors with appropriate
    user guidance and recovery suggestions.
    
    Common Causes:
    - Session expiration due to inactivity
    - Browser cookie deletion or blocking
    - Server-side session cleanup
    - Session storage corruption
    
    Args:
        request (HttpRequest): Django request object
        missing_keys (list, optional): Specific session keys that are missing
        
    Returns:
        HttpResponse: Rendered error page with session-specific guidance
        
    Example Usage:
        if 'puzzle_grid' not in request.session:
            return missing_session_data_error(
                request, 
                missing_keys=['puzzle_grid', 'start_time']
            )
    """
    # Handle missing keys parameter
    if missing_keys is None:
        missing_keys = []

    # Generate contextual error message based on missing data
    if missing_keys:
        error_message = (
            f"Session data is missing the following keys: {', '.join(missing_keys)}"
        )
    else:
        error_message = "Required session data is missing"

    # Log session error with debugging context
    log_to_json(
        request,
        "session_error",
        f"Missing session data: {error_message}",
        log_level="ERROR",
        transaction_id=request.session.get("trx-id"),
        session_id=request.session.session_key,  # Safe to log session key for debugging
    )

    # Prepare user-friendly error context
    context = {
        "error_title": "Session Data Error",
        "error_message": error_message,
        "error_details": (
            f"The application requires certain data to be stored in your session. "
            f"This data appears to be missing or invalid.\n\n"
            f"Missing keys: {', '.join(missing_keys)}\n\n"
            f"This may happen if your session expired or cookies were cleared. "
            f"Please try starting a new puzzle or refreshing the page."
        ),
        "error_code": "SESSION_DATA_MISSING",
        "retry_url": None,  # No automatic retry for session errors
        "trx_id": request.session.get("trx-id"),
    }

    return render(request, "sudoku/error.html", context)


def data_validation_error(request, validation_errors):
    """
    Handle data validation errors with detailed field-level feedback.
    
    This function processes validation errors from form submissions,
    puzzle data validation, or any other data integrity checks. It
    provides detailed feedback to help users understand and correct
    validation issues.
    
    Features:
    - Field-level error reporting
    - User-friendly validation feedback
    - Automatic retry suggestion with previous page
    - Structured logging for validation analytics
    
    Args:
        request (HttpRequest): Django request object
        validation_errors (dict): Field names mapped to error messages
            Example: {
                'cell_0_0': 'Value must be between 1 and 9',
                'difficulty': 'Invalid difficulty level selected'
            }
            
    Returns:
        HttpResponse: Rendered error page with validation details
        
    Example Usage:
        validation_errors = validate_puzzle_submission(user_data)
        if validation_errors:
            return data_validation_error(request, validation_errors)
    """
    # Format validation errors for user display
    error_details = "\n".join(
        [f"{field}: {error}" for field, error in validation_errors.items()]
    )

    # Log validation errors for analytics and debugging
    # Use WARNING level since these are user errors, not system errors
    log_to_json(
        request,
        "validation_error",
        f"Data validation error: {error_details}",
        log_level="WARNING",
        transaction_id=request.session.get("trx-id"),
        validation_details=validation_errors,
    )

    # Prepare error context for template rendering
    context = {
        "error_title": "Invalid Data",
        "error_message": "The data you submitted contains errors",
        "error_details": error_details,
        "error_code": "VALIDATION_ERROR",
        "retry_url": request.META.get("HTTP_REFERER"),  # Go back to previous page
        "trx_id": request.session.get("trx-id"),
    }

    return render(request, "sudoku/error.html", context)


# =============================================================================
# ADDITIONAL ERROR HANDLING UTILITIES
# =============================================================================

def puzzle_generation_error(request, generation_type="standard"):
    """
    Handle errors specific to Sudoku puzzle generation.
    
    Puzzle generation can fail due to algorithmic constraints, random seed
    issues, or difficulty parameter problems. This function provides
    specialized handling for generation failures.
    
    Args:
        request (HttpRequest): Django request object
        generation_type (str): Type of generation that failed
        
    Returns:
        HttpResponse: Rendered error page with generation-specific guidance
    """
    error_message = f"Failed to generate {generation_type} Sudoku puzzle"
    
    log_to_json(
        request,
        "puzzle_generation_error", 
        error_message,
        log_level="ERROR",
        transaction_id=request.session.get("trx-id"),
        generation_type=generation_type,
    )
    
    context = {
        "error_title": "Puzzle Generation Failed",
        "error_message": error_message,
        "error_details": (
            "The system was unable to generate a valid Sudoku puzzle. "
            "This is usually a temporary issue. Please try again with "
            "the same or different difficulty settings."
        ),
        "error_code": "PUZZLE_GENERATION_FAILED",
        "retry_url": "/sudoku/new/",
        "trx_id": request.session.get("trx-id"),
    }
    
    return render(request, "sudoku/error.html", context)


def database_error(request, operation="database operation"):
    """
    Handle database-related errors with appropriate user messaging.
    
    Database errors should not expose internal system details to users
    while still providing enough information for debugging and recovery.
    
    Args:
        request (HttpRequest): Django request object
        operation (str): Description of the failed database operation
        
    Returns:
        HttpResponse: Rendered error page with database error handling
    """
    error_message = f"Database error during {operation}"
    
    log_to_json(
        request,
        "database_error",
        error_message,
        log_level="ERROR", 
        transaction_id=request.session.get("trx-id"),
        operation=operation,
    )
    
    context = {
        "error_title": "System Temporarily Unavailable",
        "error_message": "The system is experiencing technical difficulties",
        "error_details": (
            "We're experiencing temporary database issues. Your progress "
            "may be temporarily unavailable, but should be restored soon. "
            "Please try again in a few moments."
        ),
        "error_code": "DATABASE_ERROR",
        "retry_url": request.META.get("HTTP_REFERER"),
        "trx_id": request.session.get("trx-id"),
    }
    
    return render(request, "sudoku/error.html", context)


def permission_denied_error(request, resource="this resource"):
    """
    Handle permission and access control errors.
    
    Args:
        request (HttpRequest): Django request object
        resource (str): Description of the protected resource
        
    Returns:
        HttpResponse: Rendered error page with permission guidance
    """
    error_message = f"Access denied to {resource}"
    
    log_to_json(
        request,
        "permission_denied",
        error_message,
        log_level="WARNING",
        transaction_id=request.session.get("trx-id"),
        resource=resource,
        user_authenticated=request.user.is_authenticated,
    )
    
    context = {
        "error_title": "Access Denied",
        "error_message": f"You don't have permission to access {resource}",
        "error_details": (
            "This resource requires special permissions that your account "
            "doesn't currently have. If you believe this is an error, "
            "please contact support."
        ),
        "error_code": "PERMISSION_DENIED",
        "retry_url": "/sudoku/",
        "trx_id": request.session.get("trx-id"),
    }
    
    return render(request, "sudoku/error.html", context)


# =============================================================================
# ERROR RECOVERY UTILITIES
# =============================================================================

def attempt_session_recovery(request):
    """
    Attempt to recover from session-related errors by initializing defaults.
    
    This function tries to restore the session to a valid state by setting
    reasonable default values for critical session variables.
    
    Args:
        request (HttpRequest): Django request object
        
    Returns:
        bool: True if recovery was successful, False otherwise
    """
    try:
        # Ensure session has a key
        if not request.session.session_key:
            request.session.create()
        
        # Set default session values if missing
        session_defaults = {
            'puzzle_preferences': {
                'difficulty': 'medium',
                'timer_enabled': True,
            },
            'user_stats': {
                'puzzles_attempted': 0,
                'puzzles_completed': 0,
            }
        }
        
        for key, default_value in session_defaults.items():
            if key not in request.session:
                request.session[key] = default_value
        
        request.session.save()
        
        log_to_json(
            request,
            "session_recovery",
            "Successfully recovered session state",
            log_level="INFO",
        )
        
        return True
        
    except Exception as e:
        log_to_json(
            request,
            "session_recovery_failed",
            f"Failed to recover session: {str(e)}",
            log_level="ERROR",
        )
        return False
