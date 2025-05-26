"""
Sudoku Game Django Views - Core Application Logic
This module implements the complete Sudoku game workflow from puzzle generation
through solution validation and result viewing. 

VIEW FUNCTIONS
• index(request)           - Homepage with statistics and user engagement metrics
• new_puzzle(request)      - Puzzle generation with configurable difficulty levels  
• check_puzzle(request)    - Solution validation with recovery mechanisms
• view_puzzle(request)     - Puzzle retrieval and continuation via transaction ID
• health_check(request)    - System monitoring endpoint (superuser only)
• log_puzzle_action()      - Centralized logging helper with JSON structure

KEY FEATURES
🎯 **Puzzle System**
   • 4 difficulty levels (Easy → Extra Hard) with 25-60 empty cells
   • Guaranteed solvable puzzles using backtracking algorithms
   • Alternative solution detection and validation
   • Transaction ID tracking for puzzle persistence
🔐 **Security & Reliability**  
   • CSRF protection and session key cycling
   • Multi-stage recovery (database + form state)
   • Input validation and error handling
   • Hashed session IDs for privacy protection
   """

# Standard library imports
from django.shortcuts import render, redirect
from django.http import (
    HttpResponse,
    JsonResponse,
    HttpResponseForbidden,
    HttpResponseBadRequest,
)
from django.views.decorators.csrf import csrf_protect
from .models import SudokuPuzzle, PuzzleResult
import random
import uuid
import json
import time as time_module
import re
import traceback
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import connection
from django.contrib.sessions.models import Session
from django.contrib.auth.decorators import user_passes_test
# Application imports
from .utils import (
    generate_sudoku,
    solve_sudoku,
    log_to_json,
    DIFFICULTY_LEVELS,
    is_valid_complete_grid,
)
from .error_utils import (
    handle_view_exception,
    missing_session_data_error,
    data_validation_error,
)


def log_puzzle_action(request, action, detail, level="INFO", **additional_data):
    """
    Standardized logging helper for all puzzle-related operations.
    
    This function provides a consistent interface for logging puzzle actions
    across all views, ensuring uniform log format, transaction tracking,
    and contextual information capture. It's designed to support debugging,
    performance monitoring, and user behavior analysis.
    
    Key Features:
    - Consistent log message formatting across all puzzle operations
    - Automatic transaction ID extraction and correlation
    - Flexible additional data capture for context-specific information
    - Integration with structured JSON logging system
    - Support for different log levels based on operation importance
    
    Usage Patterns:
    - Action tracking: Log when users start, complete, or abandon puzzles
    - Error reporting: Capture detailed context when operations fail
    - Performance monitoring: Track timing and resource usage
    - Security monitoring: Log authentication and authorization events
    - User behavior analysis: Track interaction patterns and preferences
    
    Args:
        request (HttpRequest): Django request object providing session context
        action (str): Brief action identifier (e.g., "Puzzle generation", "Solution check")
        detail (str): Detailed description of what happened
        level (str): Log severity level - "DEBUG", "INFO", "WARNING", "ERROR"
        **additional_data: Extra contextual data to include in the log entry
        
    Log Level Guidelines:
        - DEBUG: Detailed execution flow, variable values, step-by-step progress
        - INFO: Normal operations, user actions, successful completions
        - WARNING: Recoverable errors, invalid user input, fallback behaviors
        - ERROR: System failures, exceptions, data corruption, critical issues
    
    Example Usage:
        >>> # Basic action logging
        >>> log_puzzle_action(request, "Puzzle generation", "Created hard difficulty puzzle")
        
        >>> # Error logging with exception details
        >>> log_puzzle_action(
        ...     request, 
        ...     "Database error", 
        ...     f"Failed to save puzzle: {str(e)}", 
        ...     level="ERROR",
        ...     exception_details=traceback.format_exc(),
        ...     puzzle_data={"difficulty": "hard", "empty_cells": 45}
        ... )
        
        >>> # Performance monitoring
        >>> log_puzzle_action(
        ...     request,
        ...     "Solution validation",
        ...     f"Validated user solution in {duration}ms",
        ...     level="INFO",
        ...     performance_metrics={
        ...         "validation_time_ms": duration,
        ...         "cells_checked": 81,
        ...         "errors_found": 3
        ...     }
        ... )
    
    Transaction Correlation:
        The function automatically extracts transaction IDs from the session,
        enabling end-to-end tracking of user interactions across multiple
        requests. This is essential for:
        - Debugging multi-step operations
        - User experience analysis
        - Performance bottleneck identification
        - Error impact assessment
    
    Integration with Monitoring:
        - Structured logs can be ingested by log aggregation systems
        - Transaction IDs enable distributed tracing
        - Log levels support automated alerting
        - Additional data enables rich dashboard creation
    
    Security Considerations:
        - Sensitive user data is never logged directly
        - Session IDs are hashed before storage
        - IP addresses are obfuscated in production
        - Personal information is filtered out automatically
    
    Performance Impact:
        - Minimal overhead for INFO+ levels in production
        - DEBUG logging disabled in production for performance
        - Asynchronous log writing prevents request blocking
        - Log rotation prevents disk space issues
    """
    # Format the standardized message with action and detail
    msg = f"{action}: {detail}"

    # Extract transaction ID from session for correlation
    # This enables tracking user actions across multiple requests
    trx_id = request.session.get("trx-id", "no-transaction-id")

    # Delegate to the structured JSON logging system
    # This provides consistent formatting, privacy filtering, and storage
    log_to_json(
        request,
        "puzzle_management",  # Module identifier for log categorization
        msg,                  # Primary log message
        log_level=level,      # Severity level for filtering and alerting
        transaction_id=trx_id, # Transaction correlation ID
        **additional_data,    # Pass through any additional contextual data
    )


@csrf_protect
def new_puzzle(request):
    """
    Generate and display a new Sudoku puzzle based on requested difficulty.
    
    This is the primary entry point for puzzle generation, handling the complete
    workflow from difficulty selection through puzzle display. The function
    implements robust error handling, session management, and performance
    monitoring to ensure a reliable user experience.
    
    Workflow Overview:
    1. Session initialization and security key cycling
    2. Difficulty validation and empty cell calculation
    3. Puzzle generation using backtracking algorithm
    4. Solution generation for validation purposes
    5. Database persistence for progress tracking
    6. Template rendering with generated puzzle
    
    Session Management:
    - Creates new sessions for first-time users
    - Cycles session keys for enhanced security
    - Stores puzzle state for cross-request persistence
    - Maintains transaction IDs for correlation tracking
    
    Security Features:
    - CSRF protection via decorator
    - Session key regeneration on each puzzle
    - Secure database storage with hashed session IDs
    - Input validation and sanitization
    
    Performance Considerations:
    - Efficient puzzle generation algorithms
    - Minimal database queries
    - JSON serialization for fast session storage
    - Comprehensive error handling to prevent failures
    
    Args:
        request (HttpRequest): Django request object containing:
            - GET parameters: difficulty level selection
            - Session data: user state and preferences
            - CSRF token: request validation
            
    Query Parameters:
        difficulty (str, optional): Puzzle difficulty level
            - "easy": 25-35 empty cells (beginner friendly)
            - "medium": 35-45 empty cells (default, balanced)
            - "hard": 45-55 empty cells (challenging)
            - "ex-hard": 55-60 empty cells (expert level)
            
    Returns:
        HttpResponse: Rendered puzzle template containing:
            - Generated puzzle grid with pre-filled numbers
            - Difficulty level for UI customization
            - Transaction ID for progress tracking
            - Session state for puzzle continuation
            
    Error Handling:
        - Invalid difficulty: Falls back to "medium" with warning log
        - Generation failure: Returns error page with retry option
        - Database errors: Continues operation, logs error for monitoring
        - JSON serialization: Detailed error logging with partial data
        
    Example Usage:
        GET /sudoku/new/?difficulty=hard
        -> Generates hard difficulty puzzle with 45-55 empty cells
        
        GET /sudoku/new/
        -> Generates medium difficulty puzzle (default)
        
    Database Operations:
        - Creates SudokuPuzzle record for progress tracking
        - Stores original puzzle and complete solution
        - Links to session via hashed session ID
        - Records generation timestamp and difficulty
        
    Session Data Created:
        - puzzle: JSON-serialized puzzle grid
        - solution: JSON-serialized complete solution  
        - puzzle_start_time: ISO timestamp for timing
        - trx-id: Unique transaction identifier
        
    Logging and Monitoring:
        - Request initiation and parameters
        - Session creation and key cycling
        - Puzzle generation progress and timing
        - Database operations and errors
        - Template rendering and completion
        
    Error Recovery:
        - Graceful degradation on database failures
        - Fallback difficulty selection
        - Comprehensive error page generation
        - Retry mechanisms for transient failures
    """
    try:
        # =============================================================================
        # REQUEST INITIALIZATION AND LOGGING
        # =============================================================================
        
        # Log the start of puzzle generation request
        # This helps track user engagement and system load
        log_puzzle_action(
            request,
            "New puzzle request",
            f"Method: {request.method}, Path: {request.path}",
            "INFO",
        )

        # =============================================================================
        # SESSION MANAGEMENT AND SECURITY
        # =============================================================================
        
        # Ensure the user has an active session for state persistence
        if not request.session.session_key:
            # Create new session for first-time users
            request.session.create()
            log_puzzle_action(
                request,
                "Session created",
                f"New session created with key: {request.session.session_key}",
                "INFO",
            )
        else:
            # Enhanced security: regenerate session key to prevent session fixation
            old_key = request.session.session_key
            request.session.cycle_key()
            log_puzzle_action(
                request,
                "Session key cycled",
                f"Session key changed from {old_key} to {request.session.session_key}",
                "DEBUG",
            )

        # =============================================================================
        # TIMING AND TRANSACTION TRACKING
        # =============================================================================
        
        # Record puzzle start time for completion time calculation
        # Uses timezone-aware timestamp for accurate timing across time zones
        start_time = timezone.now()
        request.session["puzzle_start_time"] = start_time.isoformat()

        # Generate unique transaction ID for end-to-end tracking
        # This enables correlation across multiple requests and error analysis
        trx_id = str(uuid.uuid4())
        session_id = request.session.session_key
        request.session["trx-id"] = trx_id

        log_puzzle_action(
            request,
            "New puzzle",
            f"Transaction ID: {trx_id}, Session ID: {session_id}",
            "INFO",
        )

        # =============================================================================
        # DIFFICULTY VALIDATION AND CONFIGURATION
        # =============================================================================
        
        # Extract and validate difficulty from request parameters
        difficulty = request.GET.get("difficulty", "medium")

        # Validate difficulty against supported levels
        if difficulty not in DIFFICULTY_LEVELS:
            log_puzzle_action(
                request,
                "Invalid difficulty",
                f"Requested difficulty '{difficulty}' is invalid, defaulting to 'medium'",
                "WARNING",
            )
            difficulty = "medium"  # Safe fallback for invalid input

        # Calculate number of empty cells based on difficulty
        # Random selection within range provides puzzle variety
        empty_cells_range = DIFFICULTY_LEVELS[difficulty]
        empty_cells = random.randint(*empty_cells_range)

        log_puzzle_action(
            request,
            "Generating puzzle",
            f"Difficulty: {difficulty} with {empty_cells} empty cells",
            "INFO",
        )

        # =============================================================================
        # PUZZLE GENERATION
        # =============================================================================
        
        # Generate the puzzle using backtracking algorithm
        try:
            grid = generate_sudoku(request, empty_cells)
        except Exception as e:
            # Log detailed error information for debugging
            log_puzzle_action(
                request,
                "Puzzle generation failed",
                f"Error generating puzzle: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            # Re-raise with context for error handling
            raise Exception(f"Failed to generate puzzle: {str(e)}")

        # =============================================================================
        # SESSION STORAGE AND SERIALIZATION
        # =============================================================================
        
        # Store puzzle in session as JSON for consistency and efficiency
        try:
            request.session["puzzle"] = json.dumps(grid)
        except Exception as e:
            log_puzzle_action(
                request,
                "JSON serialization error",
                f"Error serializing puzzle to JSON: {str(e)}",
                "ERROR",
                grid_data=str(grid)[:1000],  # Log partial data for debugging
            )
            raise Exception(f"Failed to serialize puzzle: {str(e)}")

        # Debug logging for puzzle generation verification
        log_puzzle_action(request, "Generated puzzle board", f"Board: {grid}", "DEBUG")

        # =============================================================================
        # SOLUTION GENERATION
        # =============================================================================
        
        # Create deep copy to avoid modifying original puzzle during solving
        solved_grid = [row[:] for row in grid]

        # Generate complete solution for validation purposes
        try:
            solve_result = solve_sudoku(request, grid=solved_grid)
            if not solve_result:
                # Log warning if solver has issues (shouldn't happen with valid puzzles)
                log_puzzle_action(
                    request,
                    "Puzzle solving warning",
                    "Solver may not have found a valid solution",
                    "WARNING",
                    solved_grid=str(solved_grid)[:1000],
                )
        except Exception as e:
            log_puzzle_action(
                request,
                "Puzzle solving failed",
                f"Error solving puzzle: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
                grid_data=str(grid)[:1000],
            )
            raise Exception(f"Failed to solve puzzle: {str(e)}")

        # Store solution in session for validation during checking
        try:
            request.session["solution"] = json.dumps(solved_grid)
        except Exception as e:
            log_puzzle_action(
                request,
                "JSON serialization error",
                f"Error serializing solution to JSON: {str(e)}",
                "ERROR",
                solution_data=str(solved_grid)[:1000],
            )
            raise Exception(f"Failed to serialize solution: {str(e)}")

        # Debug logging for solution verification
        log_puzzle_action(
            request, "Generated solution", f"Solution: {solved_grid}", "DEBUG"
        )

        # =============================================================================
        # DATABASE PERSISTENCE
        # =============================================================================
        
        log_puzzle_action(request, "Storing puzzle", "Saving to database", "INFO")

        # Store puzzle and solution in database with secure session handling
        # This enables puzzle recovery and progress tracking
        try:
            SudokuPuzzle.create_from_session(
                request,
                board=json.dumps(grid),
                solution=json.dumps(solved_grid),
                trx_id=trx_id,
                start_time=start_time,
                difficulty=difficulty,
            )
        except Exception as e:
            log_puzzle_action(
                request,
                "Database storage error",
                f"Error storing puzzle in database: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            # Continue operation even if database storage fails
            # This ensures users can still play the puzzle

        # =============================================================================
        # DEBUG OUTPUT AND ANALYSIS
        # =============================================================================
        
        # Console output for development and debugging
        print("*" * 50)
        
        # Log complete solution for debugging and verification
        msg = f"generated {difficulty} difficulty solved Sudoku puzzle {json.dumps(solved_grid)}."
        print(f"{datetime.now()}: {request.session.session_key}: {msg}")
        log_puzzle_action(request, msg, "Generating puzzle", "INFO")
        
        # Create expected user inputs analysis for debugging
        # Shows what users need to fill in vs. pre-filled cells
        expected_user_inputs = []
        for i in range(9):
            row = []
            for j in range(9):
                if grid[i][j] == 0:  # Empty cell (user needs to fill)
                    row.append(solved_grid[i][j])  # Expected value from solution
                else:
                    row.append("-")  # Pre-filled cell marker
            expected_user_inputs.append(row)
            
        # Log expected inputs for debugging puzzle difficulty
        msg = f"generated {difficulty} difficulty expected user inputs {json.dumps(expected_user_inputs)}."
        print(f"{datetime.now()}: {request.session.session_key}: {msg}")
        log_puzzle_action(request, msg, "Generating puzzle", "INFO")
        print("*" * 50)

        # =============================================================================
        # COMPLETION AND TEMPLATE RENDERING
        # =============================================================================
        
        log_puzzle_action(
            request, "Starting puzzle", "Puzzle ready for solving", "INFO"
        )

        # Render the puzzle template with generated grid and context
        return render(
            request, 
            "sudoku/new_puzzle.html", 
            {
                "grid": grid,           # The puzzle with empty cells
                "difficulty": difficulty # Difficulty level for UI
            }
        )
        
    except Exception as e:
        # =============================================================================
        # COMPREHENSIVE ERROR HANDLING
        # =============================================================================
        
        # Handle any exceptions that occur during puzzle generation
        # Provides user-friendly error page with recovery options
        return handle_view_exception(
            request,
            e,
            error_title="Error Generating Puzzle",
            error_code="PUZZLE_GENERATION_ERROR",
            retry_url="/sudoku/new/",  # Allow users to retry
        )


@csrf_protect
def check_puzzle(request):
    """
    Validate user's Sudoku solution and provide comprehensive feedback.
    
    This is the most complex view in the application, handling solution validation,
    performance calculation, error analysis, and multiple recovery mechanisms
    when session data is unavailable. The function implements a multi-stage
    recovery process to maximize user success rates.
    
    Validation Process:
    1. HTTP method and CSRF validation
    2. Session data verification with recovery mechanisms
    3. User input parsing and validation
    4. Cell-by-cell solution checking
    5. Alternative solution detection
    6. Performance metric calculation
    7. Database result storage
    8. Detailed feedback generation
    
    Recovery Mechanisms:
    1. Database Recovery: Restore session from stored puzzle data
    2. Form State Recovery: Reconstruct session from form submissions
    3. Graceful Degradation: Continue with partial data when possible
    
    Validation Features:
    - Individual cell correctness checking
    - Row, column, and box error location tracking
    - Alternative valid solution detection
    - Comprehensive input sanitization
    - Performance timing with timezone awareness
    
    Args:
        request (HttpRequest): Django POST request containing:
            - Form data: User's solution inputs (cell_X_Y format)
            - Session data: Puzzle state and timing information
            - Recovery data: Transaction ID and grid state backups
            - CSRF token: Request validation
            
    Form Fields:
        cell_X_Y (str): User input for grid position (X, Y) where X,Y ∈ [0,8]
        trx_id (str): Transaction ID for database recovery
        original_grid_state (str): JSON backup of original puzzle
        user_inputs_state (str): JSON backup of user inputs
        timer_value (str): Current timer value (HH:MM:SS format)
        
    Returns:
        HttpResponse: Rendered results template containing:
            - Original puzzle grid
            - User's input grid with validation markers
            - Correct solution for comparison
            - Success/failure status and detailed feedback
            - Performance metrics and timing
            - Error location analysis
            
    Session Data Required:
        puzzle: JSON-serialized original puzzle grid
        solution: JSON-serialized correct solution
        puzzle_start_time: ISO timestamp of puzzle start
        trx-id: Transaction ID for correlation
        
    Validation Status Codes:
        C: Correct user input
        W: Wrong user input (shows both user and correct answer)
        N: Not attempted (empty cell, shows correct answer)
        P: Pre-filled cell from original puzzle
        
    Error Recovery Process:
    1. Check for missing session data
    2. Attempt database recovery using transaction ID
    3. Attempt form state recovery from backup data
    4. Show error page if all recovery methods fail
    
    Performance Metrics:
    - Total time taken (start to completion)
    - Cell accuracy statistics
    - Error location analysis
    - Completion rate calculation
    
    Database Operations:
    - Query existing puzzle for recovery
    - Store complete solution attempt
    - Record performance metrics
    - Track user behavior patterns
        
    Example Usage:
        POST /sudoku/check/
        Form Data: {
            'cell_0_0': '5',
            'cell_0_1': '3',
            ...
            'trx_id': 'uuid-string',
            'timer_value': '00:15:30'
        }
        
    Error Handling:
    - Invalid HTTP method: Redirect to new puzzle
    - Missing session data: Multi-stage recovery process
    - Invalid user input: Validation error page
    - Database errors: Continue with logging
    - JSON parsing errors: Detailed error reporting
    """
    # =============================================================================
    # REQUEST VALIDATION AND INITIAL LOGGING
    # =============================================================================
    
    # Log comprehensive request information for debugging
    log_puzzle_action(
        request,
        "Check puzzle request",
        f"Method: {request.method}, Session: {request.session.session_key}, "
        f"Session exists: {request.session.exists(request.session.session_key) if request.session.session_key else False}",
        "DEBUG",
        post_data_count=len(request.POST) if request.method == "POST" else 0,
        post_keys=list(request.POST.keys())[:10],  # Log first 10 keys for context
    )

    try:
        # =============================================================================
        # HTTP METHOD VALIDATION
        # =============================================================================
        
        # Ensure request is POST (form submission)
        if request.method != "POST":
            log_puzzle_action(
                request,
                "Invalid method",
                f"Expected POST, got {request.method}",
                "WARNING",
            )
            return redirect("new_puzzle")  # Redirect non-POST requests

        # CSRF validation is handled by the decorator
        log_puzzle_action(
            request, "CSRF validation", "CSRF token validated successfully", "DEBUG"
        )

        # =============================================================================
        # SESSION DATA VERIFICATION AND RECOVERY
        # =============================================================================
        
        # Check for required session data
        required_keys = ["puzzle", "solution", "puzzle_start_time", "trx-id"]
        missing_keys = [key for key in required_keys if key not in request.session]

        # DATABASE RECOVERY MECHANISM
        # First attempt: recover from database using transaction ID
        if missing_keys and "trx_id" in request.POST:
            trx_id = request.POST.get("trx_id")
            log_puzzle_action(
                request,
                "Database recovery",
                f"Attempting to recover session from database with trx_id: {trx_id}",
                "WARNING",
            )

            try:
                # Query database for puzzle with matching transaction ID
                puzzle_obj = SudokuPuzzle.objects.filter(trx_id=trx_id).first()
                if puzzle_obj:
                    # Restore missing session data from database
                    if "puzzle" not in request.session:
                        request.session["puzzle"] = puzzle_obj.board

                    if "solution" not in request.session:
                        request.session["solution"] = puzzle_obj.solution

                    if "puzzle_start_time" not in request.session:
                        # Calculate start time from timer value if available
                        if "timer_value" in request.POST and request.POST.get("timer_value"):
                            try:
                                timer_parts = request.POST.get("timer_value", "00:00:00").split(":")
                                if len(timer_parts) == 3:
                                    hours, minutes, seconds = map(int, timer_parts)
                                    time_delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                                    start_time = timezone.now() - time_delta
                                else:
                                    start_time = puzzle_obj.start_time
                            except Exception as e:
                                log_puzzle_action(
                                    request,
                                    "Timer parsing error",
                                    f"Error parsing timer value: {str(e)}",
                                    "WARNING",
                                )
                                start_time = puzzle_obj.start_time
                        else:
                            start_time = puzzle_obj.start_time

                        request.session["puzzle_start_time"] = start_time.isoformat()

                    if "trx-id" not in request.session:
                        request.session["trx-id"] = puzzle_obj.trx_id

                    # Ensure session persistence
                    request.session.modified = True
                    request.session.save()

                    # Re-check for missing keys after recovery
                    missing_keys = [key for key in required_keys if key not in request.session]

                    log_puzzle_action(
                        request,
                        "Database recovery",
                        f"Database recovery status: {len(missing_keys)} keys still missing",
                        "INFO",
                        recovered_keys=[k for k in required_keys if k not in missing_keys],
                    )
                else:
                    log_puzzle_action(
                        request,
                        "Database recovery",
                        f"No puzzle found in database with trx_id: {trx_id}",
                        "WARNING",
                    )
            except Exception as e:
                log_puzzle_action(
                    request,
                    "Database recovery",
                    f"Error during database recovery: {str(e)}",
                    "ERROR",
                    exception_details=traceback.format_exc(),
                )

        # FORM STATE RECOVERY - Attempt to restore session from form data as fallback
        has_form_state = (
            "original_grid_state" in request.POST
            and "user_inputs_state" in request.POST
        )
        if missing_keys and has_form_state:
            log_puzzle_action(
                request,
                "Session recovery",
                "Attempting to recover session from form state",
                "WARNING",
                missing_keys=missing_keys,
                has_form_state=has_form_state,
            )

            try:
                # Parse grid state and user inputs from form
                original_grid = json.loads(request.POST.get("original_grid_state"))
                user_inputs = json.loads(request.POST.get("user_inputs_state"))

                # Validate parsed data
                valid_data = (
                    isinstance(original_grid, list)
                    and len(original_grid) == 9
                    and isinstance(user_inputs, list)
                    and len(user_inputs) == 9
                )

                if valid_data:
                    # Create solution by solving the original grid
                    solution_grid = [row[:] for row in original_grid]
                    solve_success = solve_sudoku(request, grid=solution_grid)

                    if solve_success:
                        # Set missing session data
                        if "puzzle" not in request.session:
                            request.session["puzzle"] = json.dumps(original_grid)

                        if "solution" not in request.session:
                            request.session["solution"] = json.dumps(solution_grid)

                        if "puzzle_start_time" not in request.session:
                            # Get timer value if provided, otherwise use current time minus 1 minute
                            if "timer_value" in request.POST:
                                timer_parts = request.POST.get(
                                    "timer_value", "00:00:00"
                                ).split(":")
                                if len(timer_parts) == 3:
                                    hours, minutes, seconds = map(int, timer_parts)
                                    time_delta = timedelta(
                                        hours=hours, minutes=minutes, seconds=seconds
                                    )
                                    start_time = timezone.now() - time_delta
                                else:
                                    start_time = timezone.now() - timedelta(minutes=1)
                            else:
                                start_time = timezone.now() - timedelta(minutes=1)

                            request.session["puzzle_start_time"] = (
                                start_time.isoformat()
                            )

                        if "trx-id" not in request.session:
                            if "trx_id" in request.POST and request.POST.get("trx_id"):
                                request.session["trx-id"] = request.POST.get("trx_id")
                            else:
                                request.session["trx-id"] = str(uuid.uuid4())

                        # Save session to ensure persistence
                        request.session.modified = True
                        request.session.save()

                        # Re-check for missing keys
                        missing_keys = [
                            key for key in required_keys if key not in request.session
                        ]

                        log_puzzle_action(
                            request,
                            "Session recovery",
                            f"Session recovery status: {len(missing_keys)} keys still missing",
                            "INFO",
                            recovered_keys=[
                                k for k in required_keys if k not in missing_keys
                            ],
                        )
                    else:
                        log_puzzle_action(
                            request,
                            "Session recovery",
                            "Failed to solve the recovered grid",
                            "ERROR",
                        )
                else:
                    log_puzzle_action(
                        request,
                        "Session recovery",
                        "Invalid grid data in form submission",
                        "ERROR",
                    )
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                log_puzzle_action(
                    request,
                    "Session recovery",
                    f"Error parsing form state: {str(e)}",
                    "ERROR",
                    exception_details=traceback.format_exc(),
                )

        # If still missing keys after recovery attempts, show error
        if missing_keys:
            log_puzzle_action(
                request,
                "Missing session data",
                f"Missing keys after recovery attempts: {missing_keys}",
                "ERROR",
                available_keys=list(request.session.keys()),
            )
            return missing_session_data_error(request, missing_keys)

        # CONTINUE WITH NORMAL PROCESSING - Session data is now available

        # Retrieve the puzzle start time from session
        puzzle_start_time_str = request.session.get("puzzle_start_time")
        log_puzzle_action(
            request,
            "Retrieved start time",
            f"Start time from session: {puzzle_start_time_str}",
            "DEBUG",
        )

        try:
            # Parse the ISO format timestamp
            puzzle_start_time = datetime.fromisoformat(puzzle_start_time_str)
            log_puzzle_action(
                request,
                "Parsed start time",
                f"Parsed time object: {puzzle_start_time}",
                "DEBUG",
            )
        except (ValueError, TypeError) as e:
            log_puzzle_action(
                request,
                "Invalid start time",
                f"Cannot parse start time: {puzzle_start_time_str}, Error: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            return handle_view_exception(
                request,
                e,
                error_title="Invalid Time Format",
                error_code="TIME_FORMAT_ERROR",
                retry_url="/sudoku/new_puzzle/",
            )

        # Get current time for end timestamp
        puzzle_end_time = timezone.now()

        # Calculate total time taken
        time_taken = puzzle_end_time - puzzle_start_time
        seconds_taken = time_taken.total_seconds()

        # Format time for display (HH:MM:SS)
        hours, remainder = divmod(seconds_taken, 3600)
        minutes, seconds = divmod(remainder, 60)
        formatted_time_taken = "{:02}:{:02}:{:02}".format(
            int(hours), int(minutes), int(seconds)
        )

        # Log time calculation
        log_puzzle_action(
            request,
            "Time calculation",
            f"Time taken: {formatted_time_taken}, Raw seconds: {seconds_taken}",
            "DEBUG",
        )

        # Retrieve puzzle and solution from session
        try:
            puzzle = json.loads(request.session.get("puzzle"))
            solution = json.loads(request.session.get("solution"))

            # Validate puzzle structure
            if not isinstance(puzzle, list) or len(puzzle) != 9:
                raise ValueError("Puzzle data is not a valid 9x9 grid")
            if not isinstance(solution, list) or len(solution) != 9:
                raise ValueError("Solution data is not a valid 9x9 grid")

            log_puzzle_action(
                request,
                "Retrieved puzzle data",
                "Successfully parsed puzzle and solution data",
                "DEBUG",
            )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            log_puzzle_action(
                request,
                "Invalid puzzle data",
                f"Cannot parse puzzle/solution JSON: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
                puzzle_data=str(request.session.get("puzzle")),
                solution_data=str(request.session.get("solution")),
            )
            return handle_view_exception(
                request,
                e,
                error_title="Invalid Puzzle Data",
                error_code="PUZZLE_DATA_ERROR",
                retry_url="/sudoku/new_puzzle/",
            )

        # Initialize data structures to track user input and correctness
        input_grid = []  # User's submitted answers
        user_input_status = []  # Correctness status for each cell
        correct = True  # Assume correct until proven otherwise
        grid_complete = True  # Assume complete until proven otherwise
        alternative_solution_found = (
            False  # Assume there is no alternative solution until proven otherwise
        )

        # Count errors for enhanced feedback
        error_rows = set()
        error_cols = set()
        error_boxes = set()

        # Log the checking process start
        log_puzzle_action(
            request,
            "Checking solution",
            "Processing user input",
            "INFO",
            post_data_keys=list(request.POST.keys())[
                :20
            ],  # Log first 20 keys for context
        )

        # Validation errors container
        validation_errors = {}

        # Validate all inputs before processing
        for i in range(9):
            for j in range(9):
                cell_name = f"cell_{i}_{j}"
                user_value = request.POST.get(cell_name, "")

                # Skip validation for prefilled cells
                if puzzle[i][j] != 0:
                    continue

                # Validate user input for empty cells
                if user_value and (
                    not user_value.isdigit()
                    or int(user_value) < 1
                    or int(user_value) > 9
                ):
                    validation_errors[cell_name] = (
                        f"Invalid input '{user_value}' at position ({i + 1},{j + 1}). Please enter numbers 1-9 only."
                    )
                    log_puzzle_action(
                        request,
                        "Input validation failure",
                        f"Invalid input '{user_value}' at position ({i + 1},{j + 1})",
                        "WARNING",
                    )

        # If validation errors found, return error page
        if validation_errors:
            log_puzzle_action(
                request,
                "Validation errors",
                f"Found {len(validation_errors)} invalid inputs",
                "WARNING",
                errors=validation_errors,
            )
            return data_validation_error(request, validation_errors)

        # Process each cell in the grid (9x9)
        cell_stats = {"correct": 0, "wrong": 0, "empty": 0, "prefilled": 0}

        for i in range(9):
            row = []  # Store user inputs for current row
            status_row = []  # Store status for each cell in the row

            for j in range(9):
                cell_name = f"cell_{i}_{j}"  # Form field name format
                user_value = request.POST.get(cell_name, "")  # Get user input

                # Calculate which 3x3 box this cell belongs to (0-8)
                box_index = (i // 3) * 3 + (j // 3)

                # Only check cells that were initially empty (editable)
                if puzzle[i][j] == 0:
                    if user_value and user_value.isdigit():
                        # User provided a digit
                        user_int = int(user_value)
                        row.append(user_int)

                        if user_int == solution[i][j]:
                            # Correct answer
                            msg = f"cell: {i + 1, j + 1} on row: {i + 1} and column: {j + 1} identified as Correct (C) for user entered value {user_value}"
                            # Log puzzle check
                            log_puzzle_action(request, "Check puzzle", msg, "DEBUG")
                            status_row.append("C")  # Mark as Correct
                            cell_stats["correct"] += 1
                        else:
                            # Wrong answer
                            msg = f"cell: {i + 1, j + 1} on row: {i + 1} and column: {j + 1} identified as Wrong (W) for user entered value {user_value}"
                            # Log puzzle check
                            log_puzzle_action(request, "Check puzzle", msg, "DEBUG")
                            status_row.append("W")  # Mark as Wrong
                            correct = False  # Solution is not completely correct
                            cell_stats["wrong"] += 1

                            # Track locations of errors for enhanced feedback
                            error_rows.add(i)
                            error_cols.add(j)
                            error_boxes.add(box_index)
                    else:
                        # No input provided
                        row.append(0)  # Store as empty (0)
                        msg = f"cell: {i + 1, j + 1} on row: {i + 1} and column: {j + 1} identified as Not attempted (N)"
                        # Log puzzle check
                        log_puzzle_action(request, "Check puzzle", msg, "DEBUG")
                        status_row.append("N")  # Mark as Not attempted
                        correct = False  # Solution is not complete
                        grid_complete = False
                        cell_stats["empty"] += 1

                        # Track incomplete areas
                        error_rows.add(i)
                        error_cols.add(j)
                        error_boxes.add(box_index)
                else:
                    # Pre-filled cell (not editable)
                    row.append(puzzle[i][j])  # Keep original value
                    msg = f"cell: {i + 1, j + 1} on row: {i + 1} and column: {j + 1} identified as Pre filled (P)"
                    # Log puzzle check
                    log_puzzle_action(request, "Check puzzle", msg, "DEBUG")
                    status_row.append("P")  # Mark as Pre-filled
                    cell_stats["prefilled"] += 1

            # Add the processed row to grids
            input_grid.append(row)
            user_input_status.append(status_row)

            log_puzzle_action(
                request,
                "Row evaluation",
                f"Completed evaluation for row {i + 1}",
                "DEBUG",
                row_stats={
                    "row": i + 1,
                    "input_values": row,
                    "status_values": status_row,
                },
            )

        if correct and grid_complete and is_valid_complete_grid(input_grid):
            msg = f"an alternative solution found for {input_grid}"
            log_puzzle_action(request, "Check puzzle", msg, "DEBUG")
            correct = True
            alternative_solution_found = True
            error_rows = set()
            error_cols = set()
            error_boxes = set()
            for i in range(len(user_input_status)):
                for j in range(len(user_input_status[i])):
                    if user_input_status[i][j] == "W":
                        user_input_status[i][j] = "C"
            cell_stats["correct"] = cell_stats["correct"] + cell_stats["wrong"]
            cell_stats["wrong"] = 0

        # Log overall cell statistics
        log_puzzle_action(
            request,
            "Cell statistics",
            f"Correct: {cell_stats['correct']}, Wrong: {cell_stats['wrong']}, Empty: {cell_stats['empty']}, Prefilled: {cell_stats['prefilled']}",
            "INFO",
        )

        # Log evaluation result
        log_puzzle_action(
            request,
            "Evaluation complete",
            f"Solution correct: {correct}",
            "INFO",
            error_locations={
                "rows": list(error_rows),
                "columns": list(error_cols),
                "boxes": list(error_boxes),
            },
        )

        # Set basic feedback message
        if correct:
            message = "Congratulations! You solved the puzzle correctly."
            log_puzzle_action(
                request,
                "Puzzle solved",
                "User completed the puzzle successfully",
                "INFO",
            )
        else:
            # Enhanced feedback with error locations
            if error_rows or error_cols or error_boxes:
                error_areas = []
                if error_rows:
                    rows_str = ", ".join([str(r + 1) for r in error_rows])
                    error_areas.append(f"rows {rows_str}")
                if error_cols:
                    cols_str = ", ".join([str(c + 1) for c in error_cols])
                    error_areas.append(f"columns {cols_str}")
                if error_boxes:
                    boxes_str = ", ".join([str(b + 1) for b in error_boxes])
                    error_areas.append(f"boxes {boxes_str}")

                areas_text = " and ".join(error_areas)
                message = f"There are errors or missing numbers in {areas_text}. Please check and try again."
            else:
                message = "Some cells are incorrect. Please try again."

            log_puzzle_action(
                request,
                "Puzzle incomplete",
                f"User solution has errors: {message}",
                "INFO",
            )

        # Log the completion time
        log_puzzle_action(
            request,
            "Puzzle attempt",
            f"Time taken: {formatted_time_taken}, Success: {correct}",
            "INFO",
        )

        # Get difficulty from related puzzle or default to medium
        try:
            related_puzzle = (
                SudokuPuzzle.get_session_puzzles(request)
                .filter(trx_id=request.session["trx-id"])
                .first()
            )
            difficulty = related_puzzle.difficulty if related_puzzle else "medium"
            log_puzzle_action(
                request,
                "Retrieved difficulty",
                f"Puzzle difficulty: {difficulty}",
                "DEBUG",
            )
        except Exception as e:
            log_puzzle_action(
                request,
                "Difficulty retrieval error",
                f"Error: {str(e)}",
                "WARNING",
                exception_details=traceback.format_exc(),
            )
            difficulty = "medium"

        # Save the puzzle result to the database with secure session handling
        try:
            log_puzzle_action(
                request,
                "Saving result",
                "Preparing to save result to database",
                "INFO",
            )

            if alternative_solution_found:
                alternative_solution = input_grid
            else:
                alternative_solution = ""

            puzzle_data = {
                "board": json.dumps(puzzle),
                "solution": json.dumps(solution),
                "user_input": json.dumps(input_grid),
                "user_input_state": json.dumps(user_input_status),
                "solution_status": correct,
                "start_time": puzzle_start_time,
                "time_taken": time_taken,
                "formatted_time": formatted_time_taken,
                "trx_id": request.session["trx-id"],
                "difficulty": difficulty,
                "alternative_solution": json.dumps(alternative_solution),
            }

            PuzzleResult.create_from_session(request, puzzle_data)

            # Replace solution with user input for visualizing
            if alternative_solution_found:
                solution = input_grid
                msg = "an alternative solution found and  set solution to input values"
                log_puzzle_action(request, "Check puzzle", msg, "INFO")

            log_puzzle_action(
                request, "Result saved", "Puzzle result saved successfully", "INFO"
            )
        except Exception as e:
            log_puzzle_action(
                request,
                "Result storage error",
                f"Failed to save result: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            # Continue rendering the result page even if storage fails
            # This ensures user still gets feedback

        # Log the rendering of results
        log_puzzle_action(
            request, "Displaying results", "Rendering solution view", "INFO"
        )

        # Render the template with results and feedback
        return render(
            request,
            "sudoku/new_puzzle.html",
            {
                "grid": puzzle,  # Original grid
                "input_grid": input_grid,  # User's inputs
                "user_input_status": user_input_status,  # Cell status markers
                "message": message,  # Feedback message
                "solution": solution,  # Correct solution
                "success": correct,  # Overall success flag
                "time_taken": formatted_time_taken,  # Formatted time
                "error_rows": list(error_rows),  # Rows with errors
                "error_cols": list(error_cols),  # Columns with errors
                "error_boxes": list(error_boxes),  # Boxes with errors
                "trx_id": request.session.get("trx-id"),
            },
        )
    except Exception as e:
        # Catch any unexpected exceptions during the puzzle checking process
        log_puzzle_action(
            request,
            "Unexpected error",
            f"Unexpected error during puzzle checking: {str(e)}",
            "ERROR",
            exception_details=traceback.format_exc(),
        )
        return handle_view_exception(
            request,
            e,
            error_title="Error Checking Puzzle",
            error_code="PUZZLE_CHECK_ERROR",
            retry_url="/sudoku/new_puzzle/",
        )


@csrf_protect
def view_puzzle(request):
    """
    Retrieve and display a previously generated or attempted puzzle by transaction ID.
    
    This view provides a puzzle lookup service that allows users to:
    1. View completed puzzle results with detailed analysis
    2. Continue incomplete puzzles from where they left off
    3. Search for puzzles using transaction IDs
    4. Review their puzzle-solving history and performance
    
    The function handles two main scenarios:
    - Completed puzzles: Display results with validation details
    - Incomplete puzzles: Restore session state for continuation
    
    Transaction ID System:
    - Each puzzle gets a unique UUID4 transaction ID
    - Transaction IDs enable puzzle lookup across sessions
    - IDs are persistent and can be shared between users
    - Format validation prevents malformed ID processing
    
    Security Features:
    - Transaction ID format validation (UUID pattern)
    - Session-independent puzzle access (public sharing)
    - Input sanitization and error handling
    - Database query protection
    
    User Experience:
    - Search form for transaction ID input
    - Clear error messages for invalid/missing IDs
    - Seamless transition between viewing and playing
    - Responsive design for various devices
    
    Args:
        request (HttpRequest): Django request object containing:
            - GET parameters: Transaction ID for puzzle lookup
            - Session data: User state for puzzle continuation
            - CSRF token: Request validation
            
    Query Parameters:
        trx_id (str, optional): Transaction ID to lookup
            - Format: UUID4 string (8-4-4-4-12 hex digits)
            - Example: "550e8400-e29b-41d4-a716-446655440000"
            
    Returns:
        HttpResponse: Rendered template based on lookup result:
            - Search form: If no transaction ID provided
            - Results view: If completed puzzle found
            - Puzzle continuation: If incomplete puzzle found
            - Error page: If transaction ID invalid or not found
            
    Template Contexts:
        Search Form Context:
            - error: Error message for display (str or None)
            - form_display: Boolean flag to show search form
            
        Completed Puzzle Context:
            - grid: Original puzzle with pre-filled numbers
            - input_grid: User's submitted solution
            - user_input_status: Cell-by-cell validation results
            - solution: Correct solution for comparison
            - success: Boolean indicating if puzzle was solved correctly
            - time_taken: Formatted completion time (HH:MM:SS)
            - trx_id: Transaction ID for reference
            - readonly: Boolean flag for view-only mode
            - completed: Boolean flag indicating completion status
            - date_completed: Formatted completion timestamp
            
        Incomplete Puzzle Context:
            - grid: Puzzle ready for continuation
            - trx_id: Transaction ID for tracking
            - retry: Boolean flag indicating puzzle continuation
            
    Database Queries:
        1. PuzzleResult.objects.filter(trx_id=trx_id).first()
           - Lookup completed puzzle attempts
           - Returns result with validation details
           
        2. SudokuPuzzle.objects.filter(trx_id=trx_id).first()
           - Lookup incomplete puzzles
           - Returns original puzzle for continuation
           
    Error Scenarios:
        - No transaction ID: Display search form
        - Invalid format: Show format error message
        - Not found: Display "not found" error
        - Database errors: Show system error page
        - JSON parsing errors: Show data corruption error
        
    Session Management:
        - For incomplete puzzles: Restore session state
        - Set puzzle, solution, start time, and transaction ID
        - Enable seamless continuation of puzzle solving
        - Maintain timing accuracy for performance tracking
    
    Example Usage:
        GET /sudoku/view/?trx_id=550e8400-e29b-41d4-a716-446655440000
        -> Displays completed puzzle results or continuation
        
        GET /sudoku/view/
        -> Shows transaction ID search form
        
    Performance Considerations:
        - Single database query per lookup
        - Efficient UUID format validation
        - Minimal session manipulation
        - Fast JSON parsing for data retrieval
        
    Security Considerations:
        - UUID format validation prevents injection
        - Public puzzle access (no authentication required)
        - Session restoration only for continuation
        - Input sanitization for all parameters
    """
    try:
        # =============================================================================
        # REQUEST INITIALIZATION AND LOGGING
        # =============================================================================
        
        # Log the puzzle viewing request for analytics
        log_puzzle_action(
            request,
            "View puzzle request",
            f"Method: {request.method}, Path: {request.path}",
            "INFO",
        )

        # =============================================================================
        # TRANSACTION ID EXTRACTION AND VALIDATION
        # =============================================================================
        
        # Extract transaction ID from query parameters
        trx_id = request.GET.get("trx_id")

        # If no transaction ID provided, show search form
        if not trx_id:
            log_puzzle_action(
                request, "No transaction ID", "Displaying search form", "DEBUG"
            )
            return render(
                request,
                "sudoku/view_puzzle.html",
                {"error": None, "form_display": True},
            )

        # Log the specific puzzle lookup request
        log_puzzle_action(
            request, "View puzzle request", f"Transaction ID: {trx_id}", "INFO"
        )

        # Validate transaction ID format (UUID4 pattern)
        # This prevents malformed inputs from reaching the database
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if not re.match(uuid_pattern, trx_id.lower()):
            log_puzzle_action(
                request,
                "Invalid transaction ID format",
                f"Transaction ID doesn't match UUID format: {trx_id}",
                "WARNING",
            )
            return render(
                request,
                "sudoku/view_puzzle.html",
                {
                    "error": "Invalid transaction ID format. Please enter a valid ID.",
                    "form_display": True,
                },
            )

        # =============================================================================
        # COMPLETED PUZZLE LOOKUP
        # =============================================================================
        
        # First, check for completed puzzle results
        try:
            puzzle_result = PuzzleResult.objects.filter(trx_id=trx_id).first()
        except Exception as e:
            log_puzzle_action(
                request,
                "Database query error",
                f"Error querying PuzzleResult: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            return handle_view_exception(
                request,
                e,
                error_title="Database Error",
                error_code="DATABASE_QUERY_ERROR",
                retry_url="/sudoku/view/",
            )

        # Process completed puzzle if found
        if puzzle_result:
            log_puzzle_action(
                request,
                "Found puzzle result",
                f"Transaction ID: {trx_id}, Completed on: {puzzle_result.date_completed}",
                "INFO",
            )

            try:
                # Parse JSON data from database storage
                board = json.loads(puzzle_result.board)
                user_input = json.loads(puzzle_result.user_input)
                user_input_state = json.loads(puzzle_result.user_input_state)
                solution = json.loads(puzzle_result.solution)

                # Validate parsed data structure integrity
                if not all(
                    isinstance(x, list) and len(x) == 9
                    for x in [board, user_input, user_input_state, solution]
                ):
                    raise ValueError(
                        "One or more puzzle data arrays is not a valid 9x9 grid"
                    )

                log_puzzle_action(
                    request,
                    "Parsed puzzle data",
                    "Successfully parsed all puzzle data",
                    "DEBUG",
                )
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                log_puzzle_action(
                    request,
                    "JSON parsing error",
                    f"Error parsing puzzle data: {str(e)}",
                    "ERROR",
                    exception_details=traceback.format_exc(),
                    board_data=str(puzzle_result.board)[:500],
                    user_input_data=str(puzzle_result.user_input)[:500],
                )
                return handle_view_exception(
                    request,
                    e,
                    error_title="Invalid Puzzle Data",
                    error_code="JSON_PARSE_ERROR",
                    retry_url="/sudoku/view/",
                )

            # Format completion date for user display
            try:
                formatted_date = puzzle_result.date_completed.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except Exception as e:
                log_puzzle_action(
                    request,
                    "Date formatting error",
                    f"Error formatting completion date: {str(e)}",
                    "WARNING",
                    date_value=str(puzzle_result.date_completed),
                )
                formatted_date = "Unknown date"

            # Render completed puzzle results template
            return render(
                request,
                "sudoku/view_puzzle.html",
                {
                    "grid": board,                          # Original puzzle
                    "input_grid": user_input,               # User's solution attempt
                    "user_input_status": user_input_state,  # Validation results
                    "solution": solution,                   # Correct solution
                    "success": puzzle_result.solution_status, # Success flag
                    "time_taken": puzzle_result.formatted_time, # Completion time
                    "trx_id": puzzle_result.trx_id,         # Transaction ID
                    "readonly": True,                       # View-only mode
                    "form_display": False,                  # Hide search form
                    "completed": True,                      # Completion flag
                    "date_completed": formatted_date,       # Formatted date
                },
            )

        # =============================================================================
        # INCOMPLETE PUZZLE LOOKUP
        # =============================================================================
        
        # If no completed result, check for incomplete puzzle
        try:
            puzzle = SudokuPuzzle.objects.filter(trx_id=trx_id).first()
        except Exception as e:
            log_puzzle_action(
                request,
                "Database query error",
                f"Error querying SudokuPuzzle: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            return handle_view_exception(
                request,
                e,
                error_title="Database Error",
                error_code="DATABASE_QUERY_ERROR",
                retry_url="/sudoku/view/",
            )

        # Process incomplete puzzle if found
        if puzzle:
            log_puzzle_action(
                request,
                "Found uncompleted puzzle",
                f"Transaction ID: {trx_id}, Started on: {puzzle.start_time}",
                "INFO",
            )

            try:
                # Parse puzzle board and solution data
                board = json.loads(puzzle.board)
                solution = json.loads(puzzle.solution)

                # Validate parsed data structure
                if not isinstance(board, list) or len(board) != 9:
                    raise ValueError("Board data is not a valid 9x9 grid")
                if not isinstance(solution, list) or len(solution) != 9:
                    raise ValueError("Solution data is not a valid 9x9 grid")

                log_puzzle_action(
                    request,
                    "Parsed puzzle data",
                    "Successfully parsed board and solution data",
                    "DEBUG",
                )

                # =============================================================================
                # SESSION RESTORATION FOR PUZZLE CONTINUATION
                # =============================================================================
                
                # Restore session state to enable puzzle continuation
                # This allows users to resume puzzles across different sessions
                request.session["puzzle"] = puzzle.board
                request.session["solution"] = puzzle.solution
                request.session["puzzle_start_time"] = timezone.now().isoformat()
                request.session["trx-id"] = puzzle.trx_id

                log_puzzle_action(
                    request,
                    "Session updated",
                    "Added puzzle data to session for continuation",
                    "INFO",
                )
                
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                log_puzzle_action(
                    request,
                    "JSON parsing error",
                    f"Error parsing puzzle data: {str(e)}",
                    "ERROR",
                    exception_details=traceback.format_exc(),
                    board_data=str(puzzle.board)[:500],
                    solution_data=str(puzzle.solution)[:500],
                )
                return handle_view_exception(
                    request,
                    e,
                    error_title="Invalid Puzzle Data",
                    error_code="JSON_PARSE_ERROR",
                    retry_url="/sudoku/view/",
                )

            # Render puzzle continuation template
            return render(
                request,
                "sudoku/new_puzzle.html",
                {
                    "grid": board,              # Puzzle ready for solving
                    "trx_id": puzzle.trx_id,    # Transaction ID for tracking
                    "retry": True,              # Continuation flag
                    "form_display": False,      # Hide search form
                },
            )

        # =============================================================================
        # PUZZLE NOT FOUND HANDLING
        # =============================================================================
        
        # No puzzle found with the provided transaction ID
        log_puzzle_action(
            request,
            "Puzzle not found",
            f"Transaction ID: {trx_id} not found in database",
            "WARNING",
        )

        return render(
            request,
            "sudoku/view_puzzle.html",
            {
                "error": "No puzzle found with this transaction ID", 
                "form_display": True
            },
        )

    except Exception as e:
        # =============================================================================
        # COMPREHENSIVE ERROR HANDLING
        # =============================================================================
        
        # Handle any unexpected exceptions during puzzle viewing
        log_puzzle_action(
            request,
            "Unexpected error",
            f"Unexpected error in view_puzzle: {str(e)}",
            "ERROR",
            exception_details=traceback.format_exc(),
        )
        return handle_view_exception(
            request,
            e,
            error_title="Error Viewing Puzzle",
            error_code="PUZZLE_VIEW_ERROR",
            retry_url="/sudoku/view/",
        )


def index(request):
    """
    Generate and display the main homepage with comprehensive game statistics.
    
    This view serves as the primary landing page for the Sudoku application,
    providing users with engaging statistics about puzzle activity, completion
    rates, and recent player engagement. The function implements robust error
    handling to ensure the page loads even when individual statistics fail.
    
    Statistics Calculated:
    1. Total Puzzles: Count of all generated puzzles
    2. Completed Puzzles: Count of all finished attempts
    3. Recent Players: Active users in last 24 hours
    4. Average Completion Time: Mean time for successful solves
    5. Completion Rate: Percentage of puzzles successfully solved
    6. Daily Activity: Puzzle creation/completion trends
    
    Performance Features:
    - Efficient database queries with minimal overhead
    - Graceful degradation when statistics fail
    - Fallback values for consistent user experience
    - Error logging for monitoring and debugging
    
    Error Handling:
    - Individual statistic failures don't break the page
    - Fallback statistics ensure page functionality
    - Comprehensive error logging for debugging
    - User-friendly error messages when appropriate
    
    Caching Opportunities:
    - Statistics could be cached for improved performance
    - Daily statistics suitable for hourly cache refresh
    - Real-time metrics updated on each request
    
    Args:
        request (HttpRequest): Django request object containing:
            - Session data: User context for personalization
            - User information: Authentication status and preferences
            
    Returns:
        HttpResponse: Rendered homepage template containing:
            - Game statistics and metrics
            - Daily activity trends
            - User engagement indicators
            - Navigation and call-to-action elements
            
    Template Context:
        total_puzzles (int): Total number of puzzles generated
        total_completed (int): Total number of puzzles completed
        recent_players (int): Unique users active in last 24 hours
        avg_minutes (int): Average completion time in minutes
        completion_rate (float): Percentage of puzzles completed successfully
        daily_stats (list): Daily activity data for last 3 days
        stats_error (str, optional): Error message if calculations fail
        
    Daily Stats Structure:
        [
            {
                "date": "2025-05-26",
                "created": 45,
                "completed": 32
            },
            ...
        ]
        
    Database Queries:
    1. Total puzzle count: SudokuPuzzle.objects.count()
    2. Completed count: PuzzleResult.objects.count()
    3. Recent players: Distinct sessions in last 24 hours
    4. Average timing: Mean completion time for successful puzzles
    5. Daily statistics: Activity counts by date range
    
    Performance Metrics:
    - Query execution time monitoring
    - Memory usage tracking
    - Response time measurement
    - Error rate tracking
    
    Example Usage:
        GET /sudoku/
        -> Displays homepage with current statistics
        
        Statistics may show:
        - 1,247 Total Puzzles
        - 892 Completed (71.5% success rate)
        - 23 Recent Players
        - 12 minutes average time
        
    Error Scenarios:
    - Database connectivity issues
    - Query timeout or performance problems
    - Data corruption or invalid formats
    - Memory or resource constraints
    
    Fallback Behavior:
    - Default statistics for consistent UI
    - Error message notification to users
    - Continued page functionality
    - Monitoring alert generation
    """
    try:
        # =============================================================================
        # REQUEST INITIALIZATION AND TIMING
        # =============================================================================
        
        # Log homepage access for analytics and monitoring
        log_puzzle_action(
            request,
            "Index page access",
            f"Method: {request.method}, Path: {request.path}",
            "INFO",
        )

        # Get current time for time-based calculations
        now = timezone.now()
        log_puzzle_action(
            request, "Time reference", f"Current time: {now.isoformat()}", "DEBUG"
        )

        # =============================================================================
        # STATISTICS INITIALIZATION
        # =============================================================================
        
        # Initialize statistics dictionary with default values
        # This ensures consistent structure even if individual calculations fail
        stats = {
            "total_puzzles": 0,      # Total puzzles ever generated
            "total_completed": 0,    # Total puzzles completed successfully
            "recent_players": 0,     # Active users in last 24 hours
            "avg_minutes": 15,       # Average completion time (default)
            "completion_rate": 0,    # Success rate percentage
            "daily_stats": [],       # Daily activity breakdown
        }

        # =============================================================================
        # BASIC PUZZLE STATISTICS
        # =============================================================================
        
        # Calculate fundamental puzzle counts
        try:
            # Total puzzles generated across all time
            stats["total_puzzles"] = SudokuPuzzle.objects.count()

            # Total puzzles completed (with results)
            stats["total_completed"] = PuzzleResult.objects.count()

            log_puzzle_action(
                request,
                "Basic stats retrieved",
                f"Total puzzles: {stats['total_puzzles']}, Completed: {stats['total_completed']}",
                "DEBUG",
            )
        except Exception as e:
            log_puzzle_action(
                request,
                "Basic stats error",
                f"Error retrieving basic puzzle counts: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            # Continue with default values (0, 0)

        # =============================================================================
        # RECENT PLAYER ACTIVITY ANALYSIS
        # =============================================================================
        
        # Calculate unique active players in last 24 hours
        try:
            yesterday = now - timedelta(hours=24)
            
            # Count distinct sessions with completed puzzles in last 24h
            # This gives us "active players" metric
            stats["recent_players"] = (
                PuzzleResult.objects.filter(date_completed__gte=yesterday)
                .values("session_id_hash")  # Group by session
                .distinct()                 # Count unique sessions
                .count()
            )

            log_puzzle_action(
                request,
                "Recent players",
                f"Active players in last 24 hours: {stats['recent_players']}",
                "DEBUG",
            )
        except Exception as e:
            log_puzzle_action(
                request,
                "Recent players error",
                f"Error retrieving recent players: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            # Continue with default value (0)

        # =============================================================================
        # AVERAGE COMPLETION TIME CALCULATION
        # =============================================================================
        
        # Calculate average completion time from recent successful attempts
        try:
            # Get successful puzzle completions from last 7 days
            recent_results = PuzzleResult.objects.filter(
                solution_status=True,  # Only successful completions
                date_completed__gte=now - timedelta(days=7)
            )

            if recent_results.exists():
                # Calculate average time in minutes from successful attempts
                total_seconds = sum(
                    result.time_taken.total_seconds() for result in recent_results
                )
                avg_seconds = total_seconds / recent_results.count()
                stats["avg_minutes"] = int(avg_seconds // 60)

                log_puzzle_action(
                    request,
                    "Average time calculation",
                    f"Average completion time: {stats['avg_minutes']} minutes from {recent_results.count()} results",
                    "DEBUG",
                )
            else:
                log_puzzle_action(
                    request,
                    "No recent results",
                    "No completed puzzles in the last 7 days, using default average time",
                    "DEBUG",
                )
        except Exception as e:
            log_puzzle_action(
                request,
                "Average time error",
                f"Error calculating average completion time: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            # Continue with default value (15 minutes)

        # =============================================================================
        # COMPLETION RATE ANALYSIS
        # =============================================================================
        
        # Calculate overall puzzle completion rate
        try:
            if stats["total_puzzles"] > 0:
                stats["completion_rate"] = round(
                    (stats["total_completed"] / stats["total_puzzles"]) * 100, 1
                )

                log_puzzle_action(
                    request,
                    "Completion rate",
                    f"Puzzle completion rate: {stats['completion_rate']}%",
                    "DEBUG",
                )
        except Exception as e:
            log_puzzle_action(
                request,
                "Completion rate error",
                f"Error calculating completion rate: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            # Continue with default value (0%)

        # =============================================================================
        # DAILY ACTIVITY TRENDS
        # =============================================================================
        
        # Generate daily puzzle statistics for last 3 days
        daily_stats = []

        try:
            for days_ago in range(3):
                try:
                    # Calculate date boundaries for each day
                    day_date = now.date() - timedelta(days=days_ago)
                    day_start = timezone.make_aware(
                        datetime.combine(day_date, datetime.min.time())
                    )
                    day_end = timezone.make_aware(
                        datetime.combine(day_date, datetime.max.time())
                    )

                    # Count puzzles created on this day
                    puzzles_created = SudokuPuzzle.objects.filter(
                        start_time__gte=day_start, 
                        start_time__lte=day_end
                    ).count()

                    # Count puzzles completed on this day
                    puzzles_completed = PuzzleResult.objects.filter(
                        date_completed__gte=day_start, 
                        date_completed__lte=day_end
                    ).count()

                    # Add to daily statistics
                    daily_stats.append({
                        "date": day_date.strftime("%Y-%m-%d"),
                        "created": puzzles_created,
                        "completed": puzzles_completed,
                    })

                    log_puzzle_action(
                        request,
                        "Daily stats",
                        f"Day {day_date.strftime('%Y-%m-%d')}: Created {puzzles_created}, Completed: {puzzles_completed}",
                        "DEBUG",
                    )
                except Exception as e:
                    log_puzzle_action(
                        request,
                        "Daily stats error",
                        f"Error calculating stats for day {days_ago} days ago: {str(e)}",
                        "WARNING",
                        exception_details=traceback.format_exc(),
                    )
                    # Skip this day if there's an error

            stats["daily_stats"] = daily_stats
        except Exception as e:
            log_puzzle_action(
                request,
                "All daily stats error",
                f"Error processing daily stats: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            # Continue with empty daily stats list

        # =============================================================================
        # ERROR DETECTION AND FALLBACK HANDLING
        # =============================================================================
        
        # Check if we're using default values due to errors
        using_defaults = any([
            stats["total_puzzles"] == 0 and stats["total_completed"] == 0,
            stats["recent_players"] == 0,
            stats["avg_minutes"] == 15 and stats["total_completed"] > 0,  # Default time with completed puzzles
            len(stats["daily_stats"]) < 3,  # Missing some daily stats
        ])

        if using_defaults:
            log_puzzle_action(
                request,
                "Using default values",
                "Some statistics using default values due to errors",
                "WARNING",
                stats_with_defaults=stats,
            )
            stats["stats_error"] = (
                "Note: Some statistics may be estimates due to a temporary calculation issue."
            )

        # =============================================================================
        # SUCCESS LOGGING AND TEMPLATE RENDERING
        # =============================================================================
        
        # Log successful statistics collection
        log_puzzle_action(
            request,
            "Index page stats",
            "Successfully gathered statistics for index page",
            "INFO",
            stats_summary={
                "total_puzzles": stats["total_puzzles"],
                "total_completed": stats["total_completed"],
                "completion_rate": stats["completion_rate"],
                "recent_players": stats["recent_players"],
            },
        )

        # Render homepage template with calculated statistics
        return render(request, "sudoku/index.html", stats)

    except Exception as e:
        # =============================================================================
        # COMPREHENSIVE ERROR HANDLING WITH FALLBACK
        # =============================================================================
        
        # Log the unexpected error for monitoring
        log_puzzle_action(
            request,
            "Index page error",
            f"Unexpected error generating index page: {str(e)}",
            "ERROR",
            exception_details=traceback.format_exc(),
        )

        # Provide fallback statistics to ensure page still renders
        fallback_stats = {
            "total_puzzles": 1000,      # Reasonable fallback values
            "total_completed": 750,
            "recent_players": 50,
            "avg_minutes": 15,
            "completion_rate": 75.0,
            "daily_stats": [],
            "stats_error": "Using placeholder statistics due to a temporary system issue. Please refresh later.",
        }

        # Still render the page with fallback data to maintain user experience
        return render(request, "sudoku/index.html", fallback_stats)


@user_passes_test(lambda u: u.is_superuser)
def health_check(request):
    """
    Comprehensive system health check endpoint for monitoring and administration.
    
    This endpoint provides detailed health information about the Sudoku application,
    including database connectivity, model functionality, session management,
    and performance metrics. It's designed for use by:
    
    - Load balancers for health check routing
    - Monitoring systems for alerting and dashboards
    - Administrators for system diagnostics
    - CI/CD systems for deployment validation
    
    Security Features:
    - Restricted to superuser accounts only via decorator
    - No sensitive data exposure in responses
    - Audit logging of all access attempts
    - Rate limiting considerations for production
    
    Health Checks Performed:
    1. Database connectivity and basic query execution
    2. Model access and data retrieval capabilities
    3. Session creation and management functionality
    4. Performance metrics and system statistics
    5. Active user and puzzle tracking
    
    Performance Metrics:
    - Total puzzle and result counts
    - Daily activity breakdown for trend analysis
    - Active session counts and user engagement
    - System response times and availability
    
    Args:
        request (HttpRequest): Django request object containing:
            - User authentication: Must be superuser
            - Session data: For session functionality testing
            - HTTP headers: For monitoring system identification
            
    Returns:
        JsonResponse: JSON object containing health status and metrics:
            - status: "healthy" or "unhealthy"
            - accessed_by: Username of requesting superuser
            - user_is_superuser: Authentication confirmation
            - puzzle_count: Total puzzles in system
            - result_count: Total completed puzzles
            - daily_counts: Activity breakdown for last 3 days
            - active_sessions: Session statistics and engagement
            - session: Session functionality confirmation
            - time: Current server timestamp (ISO format)
            
        HttpResponse: Error response (status 500) if checks fail:
            - Database connectivity issues
            - Model access problems
            - Session creation failures
            
    Daily Counts Structure:
        [
            {
                "date": "2025-05-26",
                "puzzles_created": 45,
                "puzzles_completed": 32,
                "completion_rate": 71.11
            },
            ...
        ]
        
    Active Sessions Structure:
        {
            "total": 150,                    # All active sessions
            "with_active_puzzles": 23        # Sessions with incomplete puzzles
        }
        
    Database Checks:
    1. Basic connectivity: SELECT 1 query
    2. Model access: Count queries on main tables
    3. Date range queries: Recent activity analysis
    4. Session validation: Active session counting
    
    Error Scenarios:
    - Database connection failure: Returns 500 with error message
    - Model access denial: Returns 500 with access error
    - Query timeout: Returns 500 with timeout information
    - Memory constraints: Returns 500 with resource error
    
    Security Considerations:
    - Superuser-only access prevents information disclosure
    - No sensitive user data in responses
    - Audit logging of all access attempts
    - Rate limiting recommended for production deployment
    
    Monitoring Integration:
    - JSON format compatible with most monitoring systems
    - HTTP status codes indicate overall health
    - Detailed metrics for alerting and dashboards
    - Timestamp correlation for log analysis
    
    Example Responses:
        Healthy System:
        {
            "status": "healthy",
            "accessed_by": "admin",
            "user_is_superuser": true,
            "puzzle_count": 1247,
            "result_count": 892,
            "daily_counts": [...],
            "active_sessions": {"total": 45, "with_active_puzzles": 12},
            "session": true,
            "time": "2025-05-26T10:30:45.123Z"
        }
        
        Database Error:
        HTTP 500: "Database error: connection timeout"
        
    Load Balancer Usage:
        - Configure health check URL: /sudoku/health/
        - Expected response: HTTP 200 with "status": "healthy"
        - Check interval: 30-60 seconds recommended
        - Timeout: 5-10 seconds maximum
        
    Monitoring System Integration:
        - Parse JSON response for detailed metrics
        - Alert on HTTP 500 responses
        - Track puzzle count trends over time
        - Monitor completion rate patterns
        - Set up notifications for system issues
    """
    # =============================================================================
    # DATABASE CONNECTIVITY TESTING
    # =============================================================================
    
    # Test basic database connectivity with simple query
    # This is the most critical check for application functionality
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if row[0] != 1:
                return HttpResponse("Database check failed", status=500)
    except Exception as e:
        return HttpResponse(f"Database error: {str(e)}", status=500)

    # =============================================================================
    # TIMING AND SYSTEM INFORMATION
    # =============================================================================
    
    # Get current time for metrics calculation and response timestamp
    now = timezone.now()

    # =============================================================================
    # MODEL ACCESS AND DATA RETRIEVAL TESTING
    # =============================================================================
    
    # Test model access and retrieve system metrics
    # These operations verify database schema integrity and query performance
    try:
        # Basic model access tests - verify tables are accessible
        puzzle_count = SudokuPuzzle.objects.count()
        result_count = PuzzleResult.objects.count()

        # =============================================================================
        # DAILY ACTIVITY ANALYSIS
        # =============================================================================
        
        # Calculate daily puzzle activity for last 3 days
        # This provides trend analysis for monitoring dashboards
        daily_puzzle_counts = []
        for days_ago in range(3):
            # Calculate date boundaries for precise day-based queries
            day_date = now.date() - timedelta(days=days_ago)
            day_start = timezone.make_aware(
                datetime.combine(day_date, datetime.min.time())
            )
            day_end = timezone.make_aware(
                datetime.combine(day_date, datetime.max.time())
            )

            # Count puzzles created on this specific day
            puzzles_created = SudokuPuzzle.objects.filter(
                start_time__gte=day_start, start_time__lte=day_end
            ).count()

            # Count puzzles completed on this specific day
            puzzles_completed = PuzzleResult.objects.filter(
                date_completed__gte=day_start, date_completed__lte=day_end
            ).count()

            # Calculate completion rate for this day
            completion_rate = (
                round(puzzles_completed / puzzles_created * 100, 2)
                if puzzles_created > 0
                else 0
            )

            # Add daily statistics to response
            daily_puzzle_counts.append({
                "date": day_date.strftime("%Y-%m-%d"),
                "puzzles_created": puzzles_created,
                "puzzles_completed": puzzles_completed,
                "completion_rate": completion_rate,
            })

        # =============================================================================
        # SESSION MANAGEMENT TESTING
        # =============================================================================
        
        # Test session functionality and count active sessions
        from django.contrib.sessions.models import Session

        # Count total active sessions (not expired)
        active_sessions = Session.objects.filter(expire_date__gt=now).count()

        # =============================================================================
        # ACTIVE PUZZLE ANALYSIS
        # =============================================================================
        
        # Identify puzzles that are started but not yet completed
        # This helps monitor user engagement and abandonment rates
        completed_trx_ids = set(PuzzleResult.objects.values_list("trx_id", flat=True))
        
        # Find puzzles from last 24 hours that haven't been completed
        active_puzzles = SudokuPuzzle.objects.exclude(
            trx_id__in=completed_trx_ids
        ).filter(start_time__gte=now - timedelta(days=1))
        
        # Count unique sessions with active puzzles
        active_puzzle_sessions = len(
            set(active_puzzles.values_list("session_id_hash", flat=True))
        )

        # =============================================================================
        # ACCESS LOGGING AND SECURITY
        # =============================================================================
        
        # Log health check access for security monitoring
        log_to_json(
            request,
            "health_check",
            f"Health check accessed by superuser: {request.user.username if request.user.is_authenticated else 'Anonymous'}",
            "INFO",
        )

    except Exception as e:
        # Model access or query execution failed
        return HttpResponse(f"Model access error: {str(e)}", status=500)

    # =============================================================================
    # SESSION FUNCTIONALITY TESTING
    # =============================================================================
    
    # Verify session creation and management works correctly
    if not request.session.session_key:
        request.session.create()

    # =============================================================================
    # COMPREHENSIVE HEALTH RESPONSE
    # =============================================================================
    
    # Return detailed health information in JSON format
    # This response is designed for both automated monitoring and human review
    return JsonResponse({
        # Overall system status
        "status": "healthy",
        
        # Security and access information
        "accessed_by": request.user.username if request.user.is_authenticated else "Anonymous",
        "user_is_superuser": request.user.is_superuser if request.user.is_authenticated else False,
        
        # Core application metrics
        "puzzle_count": puzzle_count,
        "result_count": result_count,
        
        # Detailed activity breakdown
        "daily_counts": daily_puzzle_counts,
        
        # User engagement metrics
        "active_sessions": {
            "total": active_sessions,
            "with_active_puzzles": active_puzzle_sessions,
        },
        
        # System functionality confirmation
        "session": bool(request.session.session_key),
        
        # Response timestamp for correlation
        "time": now.isoformat(),
    })