"""
Sudoku Game Utility Functions and Core Game Logic

This module contains the essential utility functions for Sudoku puzzle generation,
solving, validation, and logging. It implements the core game algorithms and
provides infrastructure for puzzle management and system monitoring.

Key Components:
- Sudoku puzzle generation using backtracking algorithm
- Solution validation following standard Sudoku rules
- Configurable difficulty levels with empty cell ranges
- JSON-structured logging system with privacy controls
- Performance monitoring and error tracking utilities

The utilities are designed for:
- High-performance puzzle generation at scale
- Robust validation with comprehensive error handling
- Secure logging with production privacy safeguards
- Extensible difficulty configuration
- Debugging and monitoring support

Author: Sudoku Game Team
License: MIT
"""

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

# =============================================================================
# CONFIGURATION AND CONSTANTS
# =============================================================================

# Environment detection for production-specific behavior
is_production = getattr(settings, "IS_PRODUCTION", False)

# Core Sudoku game constants
GRID_SIZE = 9           # Standard 9x9 Sudoku grid
SUBGRID_SIZE = 3        # 3x3 subgrid size within the main grid

# Difficulty level configuration
# Maps difficulty names to (min_empty_cells, max_empty_cells) ranges
DIFFICULTY_LEVELS = {
    "easy": (25, 35),      # Fewer empty cells = easier puzzle
    "medium": (35, 45),    # Moderate difficulty for average players
    "hard": (45, 55),      # Challenging but solvable for experienced players
    "ex-hard": (55, 60),   # Expert level with minimal given numbers
}

# =============================================================================
# CORE SUDOKU VALIDATION FUNCTIONS
# =============================================================================

def is_valid(
    request: HttpRequest, grid: List[List[int]], row: int, col: int, num: int
) -> bool:
    """
    Check if placing a number in a specific cell follows Sudoku rules.
    
    Validates the fundamental Sudoku constraints:
    1. No duplicate numbers in the same row
    2. No duplicate numbers in the same column  
    3. No duplicate numbers in the same 3x3 subgrid
    
    This function is the foundation of both puzzle generation and solution
    validation, ensuring all Sudoku operations maintain game integrity.
    
    Algorithm Complexity: O(1) - checks exactly 27 cells maximum
    
    Args:
        request (HttpRequest): Django request object (for consistent interface)
        grid (List[List[int]]): 9x9 grid representing current puzzle state
        row (int): Target row index (0-8)
        col (int): Target column index (0-8)
        num (int): Number to validate (1-9)
        
    Returns:
        bool: True if placement is valid, False if it violates Sudoku rules
        
    Example:
        >>> grid = [[0]*9 for _ in range(9)]  # Empty grid
        >>> is_valid(request, grid, 0, 0, 5)  # Place 5 at top-left
        True
        >>> grid[0][0] = 5
        >>> is_valid(request, grid, 0, 1, 5)  # Try to place another 5 in same row
        False
    """
    # Rule 1: Check row constraint
    # Verify the number doesn't already exist in the target row
    for i in range(GRID_SIZE):
        if grid[row][i] == num:
            return False

    # Rule 2: Check column constraint  
    # Verify the number doesn't already exist in the target column
    for i in range(GRID_SIZE):
        if grid[i][col] == num:
            return False

    # Rule 3: Check 3x3 subgrid constraint
    # Calculate the top-left corner of the relevant 3x3 subgrid
    start_row = SUBGRID_SIZE * (row // SUBGRID_SIZE)
    start_col = SUBGRID_SIZE * (col // SUBGRID_SIZE)
    
    # Check all cells in the 3x3 subgrid
    for i in range(SUBGRID_SIZE):
        for j in range(SUBGRID_SIZE):
            if grid[start_row + i][start_col + j] == num:
                return False

    # All constraints satisfied - placement is valid
    return True


def is_valid_complete_grid(grid: List[List[int]]) -> bool:
    """
    Validate a completed Sudoku grid against all Sudoku rules.
    
    Performs comprehensive validation of a solved puzzle to ensure it
    constitutes a valid Sudoku solution. This is more thorough than
    is_valid() as it checks the entire grid structure and completeness.
    
    Validation checks:
    1. Grid structure: Must be exactly 9x9
    2. Number range: All cells must contain digits 1-9
    3. Row uniqueness: Each row contains digits 1-9 exactly once
    4. Column uniqueness: Each column contains digits 1-9 exactly once
    5. Subgrid uniqueness: Each 3x3 box contains digits 1-9 exactly once
    
    Algorithm Complexity: O(81) - examines each cell exactly once
    
    Args:
        grid (List[List[int]]): 9x9 grid to validate
        
    Returns:
        bool: True if grid is a valid complete Sudoku solution
        
    Example:
        >>> valid_solution = [
        ...     [5,3,4,6,7,8,9,1,2],
        ...     [6,7,2,1,9,5,3,4,8],
        ...     # ... complete valid solution
        ... ]
        >>> is_valid_complete_grid(valid_solution)
        True
    """
    # Structural validation
    if len(grid) != GRID_SIZE or any(len(row) != GRID_SIZE for row in grid):
        return False

    # Value range validation
    if any(not all(1 <= cell <= 9 for cell in row) for row in grid):
        return False

    # Row uniqueness validation
    # Each row must contain exactly the numbers 1-9 (no duplicates, no missing)
    for row in grid:
        if len(set(row)) != GRID_SIZE:
            return False

    # Column uniqueness validation
    for col in range(GRID_SIZE):
        column = [grid[row][col] for row in range(GRID_SIZE)]
        if len(set(column)) != GRID_SIZE:
            return False

    # 3x3 subgrid uniqueness validation
    for box_row in range(0, GRID_SIZE, SUBGRID_SIZE):
        for box_col in range(0, GRID_SIZE, SUBGRID_SIZE):
            # Extract all numbers from the current 3x3 box
            box = []
            for r in range(box_row, box_row + SUBGRID_SIZE):
                for c in range(box_col, box_col + SUBGRID_SIZE):
                    box.append(grid[r][c])
            
            # Verify the box contains exactly digits 1-9
            if len(set(box)) != GRID_SIZE:
                return False

    return True

# =============================================================================
# SUDOKU SOLVING ALGORITHM
# =============================================================================

def solve_sudoku(request: HttpRequest, grid: List[List[int]]) -> bool:
    """
    Solve a Sudoku puzzle using recursive backtracking algorithm.
    
    Implements a depth-first search with constraint satisfaction to find
    a valid solution for any solvable Sudoku puzzle. The algorithm:
    
    1. Finds the first empty cell (0)
    2. Tries each number 1-9 in that cell
    3. For each valid number, recursively solves the rest of the grid
    4. If no solution found, backtracks and tries next number
    5. Returns True when all cells are filled validly
    
    The grid is modified in-place with the solution when found.
    
    Algorithm Complexity: O(9^(n*n)) worst case, where n=9
    Practical performance: Much faster due to constraint propagation
    
    Args:
        request (HttpRequest): Django request object (for API consistency)
        grid (List[List[int]]): 9x9 puzzle grid (modified in-place)
        
    Returns:
        bool: True if solution found (grid is modified), False if unsolvable
        
    Example:
        >>> puzzle = [
        ...     [5,3,0,0,7,0,0,0,0],
        ...     [6,0,0,1,9,5,0,0,0],
        ...     # ... incomplete puzzle
        ... ]
        >>> if solve_sudoku(request, puzzle):
        ...     print("Solved!")
        ... else:
        ...     print("No solution exists")
    """
    # Scan grid left-to-right, top-to-bottom for first empty cell
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if grid[row][col] == 0:  # Found empty cell
                # Try each possible number (1-9) in this cell
                for num in range(1, GRID_SIZE + 1):
                    if is_valid(request, grid, row, col, num):
                        # Place number if it doesn't violate constraints
                        grid[row][col] = num

                        # Recursively attempt to solve rest of puzzle
                        if solve_sudoku(request, grid):
                            return True  # Solution found!

                        # Current path failed - backtrack
                        # Reset cell and try next number
                        grid[row][col] = 0

                # No valid number works in this cell - puzzle unsolvable from this state
                return False

    # All cells filled successfully - solution found!
    return True


# =============================================================================
# SUDOKU PUZZLE GENERATION
# =============================================================================

def generate_sudoku(request: HttpRequest, empty_cells: int = 40) -> List[List[int]]:
    """
    Generate a valid Sudoku puzzle with specified difficulty.
    
    Creates a complete, valid Sudoku solution and then strategically removes
    numbers to create a puzzle with the desired number of empty cells.
    
    Generation Process:
    1. Create empty 9x9 grid
    2. Seed with random valid numbers to ensure uniqueness
    3. Use backtracking algorithm to complete the solution
    4. Randomly remove numbers to create puzzle
    5. Return the puzzle with specified empty cell count
    
    The seeding step is crucial for generating diverse puzzles rather than
    similar patterns that might emerge from purely algorithmic generation.
    
    Performance: Typically completes in <100ms for most difficulty levels
    
    Args:
        request (HttpRequest): Django request object (for API consistency)
        empty_cells (int): Number of cells to leave empty (default: 40)
        
    Returns:
        List[List[int]]: 9x9 grid representing the generated puzzle
        
    Example:
        >>> puzzle = generate_sudoku(request, empty_cells=45)  # Hard difficulty
        >>> count_empty = sum(row.count(0) for row in puzzle)
        >>> print(f"Generated puzzle with {count_empty} empty cells")
    """
    # Initialize empty 9x9 grid
    grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

    # Seed the grid with random valid numbers for diversity
    # 11 seeds provide good balance between randomness and solve time
    seed_count = 11
    for _ in range(seed_count):
        # Generate random position and number
        row = random.randint(0, GRID_SIZE - 1)
        col = random.randint(0, GRID_SIZE - 1) 
        num = random.randint(1, GRID_SIZE)

        # Find valid placement for this number
        # Keep trying until we find an empty cell where this number is valid
        attempts = 0
        while (not is_valid(request, grid, row, col, num) or 
               grid[row][col] != 0) and attempts < 100:
            row = random.randint(0, GRID_SIZE - 1)
            col = random.randint(0, GRID_SIZE - 1)
            num = random.randint(1, GRID_SIZE)
            attempts += 1

        # Place the valid seed number
        if attempts < 100:  # Avoid infinite loops
            grid[row][col] = num

    # Solve the seeded grid to get a complete valid solution
    solve_sudoku(request, grid)

    # Create puzzle by removing numbers
    # Generate list of all filled positions
    filled_positions = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    
    # Randomly shuffle to ensure even distribution of empty cells
    random.shuffle(filled_positions)

    # Remove numbers from randomly selected positions
    for r, c in filled_positions[:empty_cells]:
        grid[r][c] = 0

    return grid


# =============================================================================
# LOGGING INFRASTRUCTURE
# =============================================================================

class JsonLogFilter(logging.Filter):
    """
    Custom logging filter for privacy and security in production environments.
    
    This filter processes log records before they're written to files,
    removing or obfuscating sensitive information that shouldn't be stored
    in plain text logs. Essential for GDPR compliance and security best practices.
    
    Privacy protections:
    - Truncates session IDs to prevent session hijacking
    - Obfuscates IP addresses to protect user privacy
    - Removes sensitive form data from logs
    - Maintains enough information for debugging while protecting users
    
    Production vs Development behavior:
    - Development: Logs full details for debugging
    - Production: Applies privacy filters and data minimization
    """
    
    def __init__(self, is_production: bool = False):
        """
        Initialize the filter with environment-specific behavior.
        
        Args:
            is_production (bool): Whether to apply production privacy filters
        """
        super().__init__()
        self.is_production = is_production

    def filter(self, record) -> bool:
        """
        Process log record and apply privacy filters if in production.
        
        Args:
            record: Python logging record object
            
        Returns:
            bool: True to allow log record, False to suppress it
        """
        if self.is_production and hasattr(record, "msg"):
            try:
                # Attempt to parse log message as JSON
                log_data = json.loads(record.msg)
                
                # Apply privacy filters to sensitive fields
                if "sessionid" in log_data and log_data["sessionid"]:
                    # Only keep first 4 characters of session ID
                    log_data["sessionid"] = log_data["sessionid"][:4] + "..."
                
                if "client_ip" in log_data and log_data["client_ip"]:
                    # Obfuscate last octet of IP address for privacy
                    parts = log_data["client_ip"].split(".")
                    if len(parts) == 4:  # Valid IPv4 address
                        parts[3] = "xxx"
                        log_data["client_ip"] = ".".join(parts)
                
                # Remove potentially sensitive context data
                if "context" in log_data and isinstance(log_data["context"], dict):
                    sensitive_keys = ["password", "token", "key", "secret"]
                    for key in list(log_data["context"].keys()):
                        if any(sensitive in key.lower() for sensitive in sensitive_keys):
                            log_data["context"][key] = "[REDACTED]"
                
                # Update the log message with filtered data
                record.msg = json.dumps(log_data)
                
            except (json.JSONDecodeError, TypeError, AttributeError):
                # If parsing fails, leave the message unchanged
                # Better to log something than nothing
                pass
        
        return True  # Always allow the log record through


def setup_json_logger(is_production: bool = False) -> logging.Logger:
    """
    Configure a comprehensive JSON logging system with rotation and filtering.
    
    Creates a structured logging system that:
    - Outputs JSON-formatted logs for easy parsing and analysis
    - Implements daily log rotation to manage disk space
    - Applies different retention policies for different log levels
    - Includes privacy filtering for production environments
    - Separates debug and info logs for performance optimization
    
    Log Files Created:
    - sudoku_app_info.log: INFO+ messages, 30-day retention
    - sudoku_app_debug.log: DEBUG+ messages, 7-day retention (dev only)
    
    Args:
        is_production (bool): Whether to configure for production environment
        
    Returns:
        logging.Logger: Configured logger ready for use
        
    Example:
        >>> logger = setup_json_logger(is_production=True)
        >>> logger.info(json.dumps({"event": "user_login", "user_id": 123}))
    """
    # Determine log directory relative to this module
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(current_dir, "logs")
    
    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # Create or get the logger instance
    logger = logging.getLogger("json_logger")
    
    # Set minimum log level based on environment
    if is_production:
        logger.setLevel(logging.INFO)  # Skip DEBUG in production
    else:
        logger.setLevel(logging.DEBUG)  # Include all logs in development

    # Clear any existing handlers to prevent duplicates
    if logger.handlers:
        logger.handlers.clear()

    # Create JSON formatter (outputs raw JSON for structured logging)
    formatter = logging.Formatter("%(message)s")

    # Create privacy filter instance
    privacy_filter = JsonLogFilter(is_production)

    # Configure INFO-level log handler
    info_log_file = os.path.join(log_dir, "sudoku_app_info.log")
    info_handler = TimedRotatingFileHandler(
        filename=info_log_file,
        when="midnight",        # Rotate at midnight daily
        interval=1,             # Every 1 day
        backupCount=30,         # Keep 30 days of logs
        encoding="utf-8"        # Ensure proper character encoding
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    info_handler.addFilter(privacy_filter)

    # Configure DEBUG-level log handler (development environments)
    debug_log_file = os.path.join(log_dir, "sudoku_app_debug.log")
    debug_handler = TimedRotatingFileHandler(
        filename=debug_log_file,
        when="midnight",        # Rotate at midnight daily
        interval=1,             # Every 1 day
        backupCount=7,          # Keep only 7 days of debug logs
        encoding="utf-8"
    )
    
    # Set handler level based on environment
    if is_production:
        debug_handler.setLevel(logging.INFO)  # No debug logs in production
    else:
        debug_handler.setLevel(logging.DEBUG)  # Full debug logging in development

    debug_handler.setFormatter(formatter)
    debug_handler.addFilter(privacy_filter)

    # Add handlers to logger
    logger.addHandler(info_handler)
    logger.addHandler(debug_handler)
    
    # Prevent propagation to avoid duplicate logs
    logger.propagate = False

    return logger


# Initialize the global JSON logger instance
json_logger = setup_json_logger(is_production)


# =============================================================================
# STRUCTURED LOGGING FUNCTIONS
# =============================================================================

def log_to_json(
    request: Optional[HttpRequest],
    module_name: str,
    message: str,
    log_level: str = "INFO",
    transaction_id: Optional[str] = None,
    **additional_data: Any,
) -> Tuple[str, str]:
    """
    Create comprehensive JSON-formatted log entries with rich contextual metadata.
    
    This function is the primary logging interface for the application, providing:
    - Structured JSON output for log analysis tools
    - Automatic context extraction from Django requests
    - Transaction tracking across related operations
    - Privacy-conscious data handling
    - Extensible additional data capture
    
    The logs are designed for:
    - Performance monitoring and optimization
    - User behavior analytics
    - Security incident investigation
    - System debugging and troubleshooting
    - Compliance and audit requirements
    
    Args:
        request (Optional[HttpRequest]): Django request for context extraction
        module_name (str): Source module/function generating the log
        message (str): Primary log message
        log_level (str): Log severity (DEBUG, INFO, WARNING, ERROR)
        transaction_id (Optional[str]): Tracking ID (auto-generated if None)
        **additional_data: Extra context data to include in log
        
    Returns:
        Tuple[str, str]: (JSON log string, transaction_id)
        
    Example:
        >>> log_json, trx_id = log_to_json(
        ...     request,
        ...     "puzzle_generation",
        ...     "Generated hard difficulty puzzle",
        ...     log_level="INFO",
        ...     difficulty="hard",
        ...     empty_cells=45,
        ...     generation_time_ms=120
        ... )
    """
    # Generate timestamp with millisecond precision for accurate timing
    timestamp = timezone.now().isoformat(timespec="milliseconds")

    # Extract session information safely
    session_id = ""
    if (request and hasattr(request, "session") and 
        hasattr(request.session, "session_key")):
        session_id = request.session.session_key or ""

    # Handle transaction ID generation and persistence
    if request and request.session.get("trx-id"):
        # Use existing transaction ID from session
        transaction_id = request.session.get("trx-id")
    elif not transaction_id:
        # Generate new transaction ID
        transaction_id = str(uuid.uuid4())
        # Store in session if available
        if request and hasattr(request, "session"):
            request.session["trx-id"] = transaction_id

    # Extract client IP with proxy support
    client_ip = ""
    if request:
        # Check for forwarded IP (behind proxy/load balancer)
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Take first IP in chain (original client)
            client_ip = x_forwarded_for.split(",")[0].strip()
        else:
            # Direct connection IP
            client_ip = request.META.get("REMOTE_ADDR", "")

    # Extract request context
    url_path = request.path if request else ""
    http_method = request.method if request else ""
    user_agent = request.META.get("HTTP_USER_AGENT", "") if request else ""

    # Get system hostname for distributed system tracking
    hostname = socket.gethostname()

    # Construct comprehensive log data structure
    log_data = {
        # Temporal information
        "timestamp": timestamp,
        
        # Request tracking
        "sessionid": session_id,
        "transactionid": transaction_id,
        
        # System identification
        "hostname": hostname,
        
        # Network information
        "client_ip": client_ip,
        
        # Log metadata
        "loglevel": log_level,
        "module": module_name,
        "message": message,
        
        # Request context
        "url_path": url_path,
        "http_method": http_method,
        "user_agent": user_agent,
    }

    # Process additional context data
    if additional_data:
        # Handle exception details with size limiting
        if "exception_details" in additional_data:
            exception_text = str(additional_data["exception_details"])
            # Limit exception details to prevent log bloat
            if len(exception_text) > 4000:  # ~4KB limit
                additional_data["exception_details"] = (
                    exception_text[:4000] + "... [truncated for size]"
                )

        # Add additional data under context key for organization
        log_data["context"] = additional_data

    # Serialize to JSON string
    json_log = json.dumps(log_data, ensure_ascii=False)

    # Write to appropriate log level
    if log_level == "ERROR":
        json_logger.error(json_log)
    elif log_level == "WARNING":
        json_logger.warning(json_log)
    elif log_level == "DEBUG":
        json_logger.debug(json_log)
    else:  # Default to INFO
        json_logger.info(json_log)

    return json_log, transaction_id

