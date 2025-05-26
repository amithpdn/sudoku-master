import random
import json
import uuid
import logging
from logging.handlers import TimedRotatingFileHandler
from django.utils import timezone
import socket
import os
from typing import List, Tuple, Optional, Dict, Any
from django.http import HttpRequest
from django.conf import settings


is_production = getattr(settings, "IS_PRODUCTION", False)


# Constants for improved readability and maintenance
GRID_SIZE = 9
SUBGRID_SIZE = 3
DIFFICULTY_LEVELS = {
    "easy": (25, 35),
    "medium": (35, 45),
    "hard": (45, 55),
    "ex-hard": (55, 60),
}


def is_valid(
    request: HttpRequest, grid: List[List[int]], row: int, col: int, num: int
) -> bool:
    """
    Check if placing a number in a specific cell is valid according to Sudoku rules.

    Verifies that the number doesn't appear in the same row, column, or 3x3 subgrid.

    Args:
        request: Django HttpRequest object (unused but kept for consistent interface)
        grid: 2D list representing the Sudoku board
        row: Row index (0-8)
        col: Column index (0-8)
        num: Number to check (1-9)

    Returns:
        bool: True if placing the number is valid, False otherwise
    """
    # Check if number exists in the row
    for i in range(GRID_SIZE):
        if grid[row][i] == num:
            return False

    # Check if number exists in the column
    for i in range(GRID_SIZE):
        if grid[i][col] == num:
            return False

    # Check if number exists in the 3x3 subgrid
    start_row, start_col = (
        SUBGRID_SIZE * (row // SUBGRID_SIZE),
        SUBGRID_SIZE * (col // SUBGRID_SIZE),
    )
    for i in range(SUBGRID_SIZE):
        for j in range(SUBGRID_SIZE):
            if grid[start_row + i][start_col + j] == num:
                return False

    # Number is valid if it doesn't violate any constraints
    return True


def is_valid_complete_grid(grid):
    """
    Check if a completed Sudoku grid is valid according to Sudoku rules.

    A valid Sudoku grid must have:
    - Each row containing digits 1-9 without repetition
    - Each column containing digits 1-9 without repetition
    - Each 3x3 subgrid containing digits 1-9 without repetition

    Args:
        grid: 2D list representing the completed Sudoku board

    Returns:
        bool: True if the grid is valid, False otherwise
    """
    # Check that grid is 9x9 and contains only digits 1-9

    if len(grid) != 9 or any(len(row) != 9 for row in grid):
        return False

    if any(not all(1 <= cell <= 9 for cell in row) for row in grid):
        return False

    # Check rows
    for row in grid:
        if len(set(row)) != 9:
            return False

    # Check columns
    for col in range(9):
        column = [grid[row][col] for row in range(9)]
        if len(set(column)) != 9:
            return False

    # Check 3x3 subgrids
    for box_row in range(0, 9, 3):
        for box_col in range(0, 9, 3):
            # Extract the 3x3 box
            box = []
            for r in range(box_row, box_row + 3):
                for c in range(box_col, box_col + 3):
                    box.append(grid[r][c])
            if len(set(box)) != 9:
                return False

    return True


def solve_sudoku(request: HttpRequest, grid: List[List[int]]) -> bool:
    """
    Solve a Sudoku puzzle using backtracking algorithm.

    Recursively attempts to fill each empty cell with valid numbers.
    Modifies the grid in-place with the solution.

    Args:
        request: Django HttpRequest object (passed to helper functions)
        grid: 2D list representing the Sudoku board (modified in-place)

    Returns:
        bool: True if a solution was found, False if no solution exists
    """
    # Iterate through each cell in the grid
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if grid[row][col] == 0:  # Found an empty cell
                # Try each possible number (1-9)
                for num in range(1, GRID_SIZE + 1):
                    if is_valid(request, grid, row, col, num):
                        # Place the number if valid
                        grid[row][col] = num

                        # Recursively try to solve the rest of the grid
                        if solve_sudoku(request, grid):
                            return True  # Solution found

                        # If we reach here, this path didn't work
                        grid[row][col] = 0  # Reset and backtrack

                # If no number works in this cell, the puzzle is unsolvable
                return False

    # If we've filled all cells, we've found a solution
    return True


def generate_sudoku(request: HttpRequest, empty_cells: int = 40) -> List[List[int]]:
    """
    Generate a valid Sudoku puzzle with the specified number of empty cells.

    Creates a complete Sudoku grid and removes numbers to create a puzzle.

    Args:
        request: Django HttpRequest object (passed to helper functions)
        empty_cells: Number of cells to leave empty (default: 40)

    Returns:
        list: 2D list representing the generated Sudoku puzzle
    """

    # Initialize empty 9x9 grid
    grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

    # Seed the grid with some random valid numbers to ensure uniqueness
    for _ in range(11):  # 11 random seeds for good puzzle generation
        row, col = random.randint(0, GRID_SIZE - 1), random.randint(0, GRID_SIZE - 1)
        num = random.randint(1, GRID_SIZE)

        # Keep trying until we find a valid placement
        while not is_valid(request, grid, row, col, num) or grid[row][col] != 0:
            row, col = (
                random.randint(0, GRID_SIZE - 1),
                random.randint(0, GRID_SIZE - 1),
            )
            num = random.randint(1, GRID_SIZE)

        # Place the valid number
        grid[row][col] = num

    # Solve the grid to get a complete valid Sudoku
    solve_sudoku(request, grid)

    # Create a list of all filled positions
    filled_positions = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)]

    # Randomly remove numbers to create the puzzle with the desired difficulty
    # Shuffle to ensure random distribution of empty cells
    random.shuffle(filled_positions)

    # Only use the first 'empty_cells' positions
    for r, c in filled_positions[:empty_cells]:
        grid[r][c] = 0

    return grid


class JsonLogFilter(logging.Filter):
    """Filter to exclude sensitive information from logs in production."""

    def __init__(self, is_production=False):
        super().__init__()
        self.is_production = is_production

    def filter(self, record):
        if self.is_production and hasattr(record, "msg"):
            # Parse JSON if possible
            try:
                log_data = json.loads(record.msg)
                # Remove sensitive data in production
                if "sessionid" in log_data:
                    log_data["sessionid"] = log_data["sessionid"][:4] + "..."
                if "client_ip" in log_data:
                    # Redact last octet of IP
                    parts = log_data["client_ip"].split(".")
                    if len(parts) == 4:
                        parts[3] = "xxx"
                        log_data["client_ip"] = ".".join(parts)
                # Rejoin JSON
                record.msg = json.dumps(log_data)
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        return True


def setup_json_logger(is_production: bool = False) -> logging.Logger:
    """
    Set up a JSON-formatted logging system with daily rotation.

    Creates two log files: one for DEBUG+ levels and another for INFO+ levels.
    Logs are stored in a 'logs' directory relative to the current file.

    Args:
        is_production: Whether to enable production mode with sensitive data filtering

    Returns:
        logging.Logger: Configured logger object
    """
    # Get the directory containing the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Create path for logs directory
    log_dir = os.path.join(current_dir, "logs")

    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Create logger
    logger = logging.getLogger("json_logger")
    # Set to lowest level to capture all logs
    if is_production:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)

    # Clear existing handlers (in case of module reload)
    if logger.handlers:
        logger.handlers = []

    # Create formatter for raw JSON output
    formatter = logging.Formatter("%(message)s")

    # Create privacy filter for production
    log_filter = JsonLogFilter(is_production)

    # Create handler for INFO and higher level logs
    info_log_file = os.path.join(log_dir, "sudoku_app_info.log")
    info_handler = TimedRotatingFileHandler(
        filename=info_log_file,
        when="midnight",  # Rotate at midnight
        interval=1,  # Daily rotation
        backupCount=30,  # Keep 30 days of logs
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    info_handler.addFilter(log_filter)

    # Create handler for DEBUG and higher level logs
    debug_log_file = os.path.join(log_dir, "sudoku_app_debug.log")
    debug_handler = TimedRotatingFileHandler(
        filename=debug_log_file,
        when="midnight",  # Rotate at midnight
        interval=1,  # Daily rotation
        backupCount=7,  # Keep 7 days of debug logs
    )

    if is_production:
        debug_handler.setLevel(logging.INFO)
    else:
        debug_handler.setLevel(logging.DEBUG)

    debug_handler.setFormatter(formatter)
    debug_handler.addFilter(log_filter)

    # Add both handlers to logger
    logger.addHandler(info_handler)
    logger.addHandler(debug_handler)

    return logger


# Initialize the JSON logger
# Use environment variable or setting to determine if in production
json_logger = setup_json_logger(is_production)


def log_to_json(
    request: Optional[HttpRequest],
    module_name: str,
    message: str,
    log_level: str = "INFO",
    transaction_id: Optional[str] = None,
    **additional_data,
) -> Tuple[str, str]:
    """
    Create and write a JSON-formatted log entry.

    Captures contextual information like session ID, transaction ID, timestamp,
    client IP, and HTTP request details along with the log message.

    Args:
        request: Django HttpRequest object
        module_name: Name of the module/function logging the message
        message: Log message text
        log_level: Logging level (INFO, WARNING, ERROR, DEBUG)
        transaction_id: Optional transaction ID (generated if not provided)
        **additional_data: Any additional contextual data to include in the log

    Returns:
        tuple: (JSON string, transaction_id)
    """
    # Get current timestamp in ISO format with millisecond precision
    timestamp = timezone.now().isoformat(timespec="milliseconds")

    # Extract session ID from request if available
    session_id = ""
    if (
        request
        and hasattr(request, "session")
        and hasattr(request.session, "session_key")
    ):
        session_id = request.session.session_key

    # Get or generate transaction ID
    if request and request.session.get("trx-id"):
        transaction_id = request.session.get("trx-id")
    elif not transaction_id:
        transaction_id = str(uuid.uuid4())
        if request and hasattr(request, "session"):
            request.session["trx-id"] = transaction_id

    # Extract client IP address with privacy consideration
    client_ip = ""
    if request:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.META.get("REMOTE_ADDR", "")

    # Get request URL path
    url_path = ""
    if request:
        url_path = request.path

    # Get HTTP method
    http_method = ""
    if request:
        http_method = request.method

    # Get hostname for distributed system identification
    hostname = socket.gethostname()

    # Construct log data dictionary
    log_data = {
        "timestamp": timestamp,
        "sessionid": session_id,
        "transactionid": transaction_id,
        "hostname": hostname,
        "client_ip": client_ip,
        "loglevel": log_level,
        "module": module_name,
        "message": message,
        "url_path": url_path,
        "http_method": http_method,
        "user_agent": request.META.get("HTTP_USER_AGENT", "") if request else "",
    }

    # Add any additional data provided by the caller
    if additional_data:
        # If there's an 'exception_details' key, format it nicely
        if (
            "exception_details" in additional_data
            and additional_data["exception_details"]
        ):
            # Limit exception details to a reasonable length to avoid massive log entries
            exception_text = str(additional_data["exception_details"])
            if len(exception_text) > 4000:  # Limit to ~4KB
                additional_data["exception_details"] = (
                    exception_text[:4000] + "... [truncated]"
                )

        # Add a dedicated 'context' field for additional data
        log_data["context"] = additional_data

    # Convert to JSON string
    json_log = json.dumps(log_data)

    # Log with appropriate log level
    if log_level == "ERROR":
        json_logger.error(json_log)
    elif log_level == "WARNING":
        json_logger.warning(json_log)
    elif log_level == "DEBUG":
        json_logger.debug(json_log)
    else:  # Default to INFO
        json_logger.info(json_log)

    return json_log, transaction_id
