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
    Helper function to standardize puzzle action logging with enhanced error context.

    Args:
        request: Django HttpRequest object
        action: Short action description
        detail: Detailed description
        level: Log level (INFO, DEBUG, WARNING, ERROR)
        **additional_data: Any additional data to include in the log
    """
    # Format the message
    msg = f"{action}: {detail}"

    # Get transaction ID from session if available
    trx_id = request.session.get("trx-id", "no-transaction-id")

    # Log with all contextual information
    log_to_json(
        request,
        "puzzle_management",
        msg,
        log_level=level,
        transaction_id=trx_id,
        **additional_data,  # Pass through any additional data
    )


@csrf_protect
def new_puzzle(request):
    """
    Generate a new Sudoku puzzle based on the requested difficulty level.

    Handles session management, puzzle generation, and database storage of the new puzzle.

    Args:
        request: Django HttpRequest object containing session and query parameters

    Returns:
        HttpResponse: Rendered puzzle template with the generated grid

    Request Parameters:
        difficulty (str, optional): Puzzle difficulty level ('easy', 'medium', 'hard' or 'ex-hard').
                                   Defaults to 'medium' if not specified.
    """
    try:
        # Log the start of the request
        log_puzzle_action(
            request,
            "New puzzle request",
            f"Method: {request.method}, Path: {request.path}",
            "INFO",
        )

        # Ensure the session is active
        if not request.session.session_key:
            request.session.create()
            # request.session["last_activity"] = timezone.now().isoformat()
            log_puzzle_action(
                request,
                "Session created",
                f"New session created with key: {request.session.session_key}",
                "INFO",
            )
        else:
            old_key = request.session.session_key
            request.session.cycle_key()  # Regenerate session key for enhanced security
            log_puzzle_action(
                request,
                "Session key cycled",
                f"Session key changed from {old_key} to {request.session.session_key}",
                "DEBUG",
            )

        # Store UTC-aware timestamp for calculating puzzle completion time later
        start_time = timezone.now()
        request.session["puzzle_start_time"] = start_time.isoformat()

        # Generate a unique transaction ID for tracking this puzzle instance
        trx_id = str(uuid.uuid4())
        session_id = request.session.session_key
        request.session["trx-id"] = trx_id

        # Log the start of a new puzzle transaction
        log_puzzle_action(
            request,
            "New puzzle",
            f"Transaction ID: {trx_id}, Session ID: {session_id}",
            "INFO",
        )

        # Get and validate difficulty from request parameters
        difficulty = request.GET.get("difficulty", "medium")

        if difficulty not in DIFFICULTY_LEVELS:
            log_puzzle_action(
                request,
                "Invalid difficulty",
                f"Requested difficulty '{difficulty}' is invalid, defaulting to 'medium'",
                "WARNING",
            )
            difficulty = "medium"  # Default to medium if invalid

        # Get the number of empty cells for the selected difficulty
        empty_cells_range = DIFFICULTY_LEVELS[difficulty]
        empty_cells = random.randint(*empty_cells_range)

        # Log puzzle generation with difficulty details
        log_puzzle_action(
            request,
            "Generating puzzle",
            f"Difficulty: {difficulty} with {empty_cells} empty cells",
            "INFO",
        )

        # Generate the puzzle with the appropriate difficulty
        try:
            grid = generate_sudoku(request, empty_cells)
        except Exception as e:
            log_puzzle_action(
                request,
                "Puzzle generation failed",
                f"Error generating puzzle: {str(e)}",
                "ERROR",
                exception_details=traceback.format_exc(),
            )
            raise Exception(f"Failed to generate puzzle: {str(e)}")

        # Store puzzle in session as JSON for consistency
        try:
            request.session["puzzle"] = json.dumps(grid)
        except Exception as e:
            log_puzzle_action(
                request,
                "JSON serialization error",
                f"Error serializing puzzle to JSON: {str(e)}",
                "ERROR",
                grid_data=str(grid)[:1000],  # Log partial grid data for debugging
            )
            raise Exception(f"Failed to serialize puzzle: {str(e)}")

        # Log generation of puzzle board (debug level)
        log_puzzle_action(request, "Generated puzzle board", f"Board: {grid}", "DEBUG")

        # Create a deep copy of the grid for solving
        solved_grid = [row[:] for row in grid]

        # Generate the solution for checking later
        try:
            solve_result = solve_sudoku(request, grid=solved_grid)
            if not solve_result:
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

        # Store solution in session as JSON for consistency
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

        # Log solved puzzle (debug level)
        log_puzzle_action(
            request, "Generated solution", f"Solution: {solved_grid}", "DEBUG"
        )

        # Log database operation
        log_puzzle_action(request, "Storing puzzle", "Saving to database", "INFO")

        # Store the puzzle and solution in the database with secure session handling
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
            # Continue even if database storage fails, to provide puzzle to user
            # Just log the error but don't raise exception

        # Log generated puzzle board
        print("*" * 50)
        # msg = f"generated {difficulty} difficulty Sudoku puzzle {json.dumps(grid)}."
        # print(
        #    f"{datetime.now()}: {request.session.session_key}: {msg}"
        # )
        # log_puzzle_action(request, msg, "Generating puzzle", "INFO")
        # Log solved puzzle for debugging
        msg = f"generated {difficulty} difficulty solved Sudoku puzzle {json.dumps(solved_grid)}."
        print(f"{datetime.now()}: {request.session.session_key}: {msg}")
        log_puzzle_action(request, msg, "Generating puzzle", "INFO")
        # Create expected_user_inputs which shows expected values where necessary and "_" for pre-filled cells
        expected_user_inputs = []
        for i in range(9):
            row = []
            for j in range(9):
                if grid[i][j] == 0:  # Empty cell (user needs to fill)
                    row.append(solved_grid[i][j])  # Expected value from solution
                else:
                    row.append("-")  # Pre-filled cell
            expected_user_inputs.append(row)
        # Log expected user inputs
        msg = f"generated {difficulty} difficulty expected user inputs {json.dumps(expected_user_inputs)}."
        print(f"{datetime.now()}: {request.session.session_key}: {msg}")
        log_puzzle_action(request, msg, "Generating puzzle", "INFO")
        print("*" * 50)

        # Log puzzle start
        log_puzzle_action(
            request, "Starting puzzle", "Puzzle ready for solving", "INFO"
        )

        # Render the puzzle template with the generated grid
        return render(
            request, "sudoku/new_puzzle.html", {"grid": grid, "difficulty": difficulty}
        )
    except Exception as e:
        # Handle any exceptions that occur during puzzle generation
        return handle_view_exception(
            request,
            e,
            error_title="Error Generating Puzzle",
            error_code="PUZZLE_GENERATION_ERROR",
            retry_url="/sudoku/new_puzzle/",
        )


@csrf_protect
def check_puzzle(request):
    """
    Check the user's solution against the correct solution and calculate performance metrics.
    Enhanced with database-first recovery approach when session data is missing.
    """
    # Log incoming request for debugging
    log_puzzle_action(
        request,
        "Check puzzle request",
        f"Method: {request.method}, Session: {request.session.session_key}, Session exists: {request.session.exists(request.session.session_key) if request.session.session_key else False}",
        "DEBUG",
        post_data_count=len(request.POST) if request.method == "POST" else 0,
        post_keys=list(request.POST.keys())[:10],  # Log first 10 keys
    )

    try:
        # Verify HTTP method
        if request.method != "POST":
            log_puzzle_action(
                request,
                "Invalid method",
                f"Expected POST, got {request.method}",
                "WARNING",
            )
            return redirect("new_puzzle")  # Redirect non-POST requests

        # Validate CSRF token is present (handled by decorator)
        log_puzzle_action(
            request, "CSRF validation", "CSRF token validated successfully", "DEBUG"
        )

        # Check if all required session data exists
        required_keys = ["puzzle", "solution", "puzzle_start_time", "trx-id"]
        missing_keys = [key for key in required_keys if key not in request.session]

        # DATABASE RECOVERY - Try database recovery first (more reliable)
        if missing_keys and "trx_id" in request.POST:
            trx_id = request.POST.get("trx_id")
            log_puzzle_action(
                request,
                "Database recovery",
                f"Attempting to recover session from database with trx_id: {trx_id}",
                "WARNING",
            )

            try:
                # Try to find puzzle in database
                puzzle_obj = SudokuPuzzle.objects.filter(trx_id=trx_id).first()
                if puzzle_obj:
                    # Set missing session data from database
                    if "puzzle" not in request.session:
                        request.session["puzzle"] = puzzle_obj.board

                    if "solution" not in request.session:
                        request.session["solution"] = puzzle_obj.solution

                    if "puzzle_start_time" not in request.session:
                        # If we have a timer value in the POST data, use it to calculate start time
                        if "timer_value" in request.POST and request.POST.get(
                            "timer_value"
                        ):
                            try:
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

                    # Save session to ensure persistence
                    request.session.modified = True
                    request.session.save()

                    # Re-check for missing keys
                    missing_keys = [
                        key for key in required_keys if key not in request.session
                    ]

                    log_puzzle_action(
                        request,
                        "Database recovery",
                        f"Database recovery status: {len(missing_keys)} keys still missing",
                        "INFO",
                        recovered_keys=[
                            k for k in required_keys if k not in missing_keys
                        ],
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
    View a previously attempted puzzle using the transaction ID.

    This allows users to review their past puzzles or retry ones they didn't complete.

    Args:
        request: Django HttpRequest object containing the transaction ID

    Returns:
        HttpResponse: Rendered template with puzzle data or search form
    """
    try:
        # Log the initial request
        log_puzzle_action(
            request,
            "View puzzle request",
            f"Method: {request.method}, Path: {request.path}",
            "INFO",
        )

        # Get transaction ID from request parameters
        trx_id = request.GET.get("trx_id")

        # If no transaction ID provided, show the search form
        if not trx_id:
            log_puzzle_action(
                request, "No transaction ID", "Displaying search form", "DEBUG"
            )
            return render(
                request,
                "sudoku/view_puzzle.html",
                {"error": None, "form_display": True},
            )

        # Log the puzzle view request with transaction ID
        log_puzzle_action(
            request, "View puzzle request", f"Transaction ID: {trx_id}", "INFO"
        )

        # Validate transaction ID format (basic UUID format check)
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

        # Try to find a puzzle result with this transaction ID
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
                retry_url="/sudoku/view_puzzle/",
            )

        if puzzle_result:
            # Puzzle was previously attempted
            log_puzzle_action(
                request,
                "Found puzzle result",
                f"Transaction ID: {trx_id}, Completed on: {puzzle_result.date_completed}",
                "INFO",
            )

            try:
                # Parse JSON data from the database
                board = json.loads(puzzle_result.board)
                user_input = json.loads(puzzle_result.user_input)
                user_input_state = json.loads(puzzle_result.user_input_state)
                solution = json.loads(puzzle_result.solution)

                # Validate parsed data structures
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
                    retry_url="/sudoku/view_puzzle/",
                )

            # Format completion date for display
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

            return render(
                request,
                "sudoku/view_puzzle.html",
                {
                    "grid": board,
                    "input_grid": user_input,
                    "user_input_status": user_input_state,
                    "solution": solution,
                    "success": puzzle_result.solution_status,
                    "time_taken": puzzle_result.formatted_time,
                    "trx_id": puzzle_result.trx_id,
                    "readonly": True,  # Indicate this is a view-only mode
                    "form_display": False,
                    "completed": True,
                    "date_completed": formatted_date,
                },
            )

        # If no result found, try to find an unsolved puzzle
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
                retry_url="/sudoku/view_puzzle/",
            )

        if puzzle:
            # Puzzle was started but not completed - allow retrying
            log_puzzle_action(
                request,
                "Found uncompleted puzzle",
                f"Transaction ID: {trx_id}, Started on: {puzzle.start_time}",
                "INFO",
            )

            try:
                # Parse the board and solution
                board = json.loads(puzzle.board)
                solution = json.loads(puzzle.solution)

                # Validate parsed data
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

                # Store in session for the check_puzzle view to work
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
                    retry_url="/sudoku/view_puzzle/",
                )

            return render(
                request,
                "sudoku/new_puzzle.html",
                {
                    "grid": board,
                    "trx_id": puzzle.trx_id,
                    "retry": True,
                    "form_display": False,
                },
            )

        # No puzzle found with this transaction ID
        log_puzzle_action(
            request,
            "Puzzle not found",
            f"Transaction ID: {trx_id} not found in database",
            "WARNING",
        )

        return render(
            request,
            "sudoku/view_puzzle.html",
            {"error": "No puzzle found with this transaction ID", "form_display": True},
        )

    except Exception as e:
        # Handle any unexpected exceptions
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
            retry_url="/sudoku/view_puzzle/",
        )


def index(request):
    """
    Index page view that displays the main landing page with game statistics.

    Fetches recent game statistics to display on the homepage for user engagement.

    Args:
        request: Django HttpRequest object

    Returns:
        HttpResponse: Rendered index page with statistics
    """
    try:
        # Log the index page access
        log_puzzle_action(
            request,
            "Index page access",
            f"Method: {request.method}, Path: {request.path}",
            "INFO",
        )

        # Get current time for calculations
        now = timezone.now()
        log_puzzle_action(
            request, "Time reference", f"Current time: {now.isoformat()}", "DEBUG"
        )

        # Initialize statistics dictionary
        stats = {
            "total_puzzles": 0,
            "total_completed": 0,
            "recent_players": 0,
            "avg_minutes": 15,  # Default value
            "completion_rate": 0,
            "daily_stats": [],
        }

        # Calculate basic statistics for display
        try:
            # Get total puzzles count
            stats["total_puzzles"] = SudokuPuzzle.objects.count()

            # Get completed puzzles count
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
            # Continue with default values

        # Get puzzles from last 24 hours for "active players" metric
        try:
            yesterday = now - timedelta(hours=24)
            stats["recent_players"] = (
                PuzzleResult.objects.filter(date_completed__gte=yesterday)
                .values("session_id_hash")
                .distinct()
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
            # Continue with default value

        # Calculate average completion time from recent results
        try:
            recent_results = PuzzleResult.objects.filter(
                solution_status=True, date_completed__gte=now - timedelta(days=7)
            )

            if recent_results.exists():
                # Calculate average time in minutes
                total_seconds = sum(
                    [result.time_taken.total_seconds() for result in recent_results]
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
            # Continue with default value

        # Get completion rate
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
            # Continue with default value

        # Daily puzzle stats for the last 3 days
        daily_stats = []

        try:
            for days_ago in range(3):
                try:
                    day_date = now.date() - timedelta(days=days_ago)
                    day_start = timezone.make_aware(
                        datetime.combine(day_date, datetime.min.time())
                    )
                    day_end = timezone.make_aware(
                        datetime.combine(day_date, datetime.max.time())
                    )

                    puzzles_created = SudokuPuzzle.objects.filter(
                        start_time__gte=day_start, start_time__lte=day_end
                    ).count()

                    puzzles_completed = PuzzleResult.objects.filter(
                        date_completed__gte=day_start, date_completed__lte=day_end
                    ).count()

                    daily_stats.append(
                        {
                            "date": day_date.strftime("%Y-%m-%d"),
                            "created": puzzles_created,
                            "completed": puzzles_completed,
                        }
                    )

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

        # Check if we're using any default values due to errors
        using_defaults = any(
            [
                stats["total_puzzles"] == 0 and stats["total_completed"] == 0,
                stats["recent_players"] == 0,
                stats["avg_minutes"] == 15
                and stats["total_completed"] > 0,  # Default time with completed puzzles
                len(stats["daily_stats"]) < 3,  # Missing some daily stats
            ]
        )

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

        # Log the successful stats collection
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

        # Render the template with statistics
        return render(request, "sudoku/index.html", stats)

    except Exception as e:
        # Log the unexpected error
        log_puzzle_action(
            request,
            "Index page error",
            f"Unexpected error generating index page: {str(e)}",
            "ERROR",
            exception_details=traceback.format_exc(),
        )

        # Provide fallback statistics to ensure the page still renders
        fallback_stats = {
            "total_puzzles": 1000,  # Default values
            "total_completed": 750,
            "recent_players": 50,
            "avg_minutes": 15,
            "completion_rate": 75.0,
            "daily_stats": [],
            "stats_error": "Using placeholder statistics due to a temporary system issue. Please refresh later.",
        }

        # Still render the page with fallback data
        return render(request, "sudoku/index.html", fallback_stats)


@user_passes_test(lambda u: u.is_superuser)
def health_check(request):
    """
    Enhanced health check endpoint - RESTRICTED TO SUPERUSERS ONLY.
    Provides detailed metrics including daily puzzle counts and active sessions.
    """

    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if row[0] != 1:
                return HttpResponse("Database check failed", status=500)
    except Exception as e:
        return HttpResponse(f"Database error: {str(e)}", status=500)

    # Get current time for calculations
    now = timezone.now()

    # Check model access with enhanced metrics
    try:
        # General counts
        puzzle_count = SudokuPuzzle.objects.count()
        result_count = PuzzleResult.objects.count()

        # Daily puzzle counts for last 3 days
        daily_puzzle_counts = []
        for days_ago in range(3):
            day_date = now.date() - timedelta(days=days_ago)
            day_start = timezone.make_aware(
                datetime.combine(day_date, datetime.min.time())
            )
            day_end = timezone.make_aware(
                datetime.combine(day_date, datetime.max.time())
            )

            puzzles_created = SudokuPuzzle.objects.filter(
                start_time__gte=day_start, start_time__lte=day_end
            ).count()

            puzzles_completed = PuzzleResult.objects.filter(
                date_completed__gte=day_start, date_completed__lte=day_end
            ).count()

            daily_puzzle_counts.append(
                {
                    "date": day_date.strftime("%Y-%m-%d"),
                    "puzzles_created": puzzles_created,
                    "puzzles_completed": puzzles_completed,
                    "completion_rate": (
                        round(puzzles_completed / puzzles_created * 100, 2)
                        if puzzles_created > 0
                        else 0
                    ),
                }
            )

        # Active sessions count
        from django.contrib.sessions.models import Session

        active_sessions = Session.objects.filter(expire_date__gt=now).count()

        # Active puzzles (not yet completed)
        completed_trx_ids = set(PuzzleResult.objects.values_list("trx_id", flat=True))
        active_puzzles = SudokuPuzzle.objects.exclude(
            trx_id__in=completed_trx_ids
        ).filter(start_time__gte=now - timedelta(days=1))
        active_puzzle_sessions = len(
            set(active_puzzles.values_list("session_id_hash", flat=True))
        )

        # Log the health check access
        log_to_json(
            request,
            "health_check",
            f"Health check accessed by superuser: {request.user.username if request.user.is_authenticated else 'Anonymous'}",
            "INFO",
        )

    except Exception as e:
        return HttpResponse(f"Model access error: {str(e)}", status=500)

    # Check session functionality
    if not request.session.session_key:
        request.session.create()

    return JsonResponse(
        {
            "status": "healthy",
            "accessed_by": request.user.username
            if request.user.is_authenticated
            else "Anonymous",
            "user_is_superuser": request.user.is_superuser
            if request.user.is_authenticated
            else False,
            "puzzle_count": puzzle_count,
            "result_count": result_count,
            "daily_counts": daily_puzzle_counts,
            "active_sessions": {
                "total": active_sessions,
                "with_active_puzzles": active_puzzle_sessions,
            },
            "session": bool(request.session.session_key),
            "time": now.isoformat(),
        }
    )
