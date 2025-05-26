"""
Sudoku Game Database Models

This module defines the database models for storing Sudoku puzzles and results.
The models implement security best practices including session ID hashing and
proper data serialization for complex game state storage.

Key Features:
- Secure session tracking using hashed session IDs
- Puzzle state persistence across browser sessions
- Performance optimized with database indexes
- JSON serialization for complex data structures
- Legacy data format support for backwards compatibility

Database Tables:
- SudokuPuzzle: Stores active/unsolved puzzles
- PuzzleResult: Stores completed puzzle attempts and solutions
"""

from django.db import models
import json
import hashlib
from django.conf import settings

# =============================================================================
# SUDOKU PUZZLE MODEL
# =============================================================================

class SudokuPuzzle(models.Model):
    """
    Model for storing active Sudoku puzzles.
    
    This table stores puzzles that are currently being played or were
    generated but not yet completed. It enables puzzle persistence across
    browser sessions and provides puzzle resumption functionality.
    
    Security Features:
    - Session IDs are hashed using SHA-256 with Django's SECRET_KEY as salt
    - No raw session data is stored in the database
    - Transaction IDs provide additional tracking without exposing session info
    
    Performance Features:
    - Database indexes on session_id_hash and trx_id for fast queries
    - JSON serialization for efficient storage of grid data
    - Optimized for quick retrieval by session or transaction ID
    """
    
    # =============================================================================
    # MODEL FIELDS
    # =============================================================================
    
    # Security: Hashed session ID instead of raw session key
    # Index: Enables fast lookups by session
    session_id_hash = models.CharField(
        max_length=64, 
        db_index=True,
        help_text="SHA-256 hash of session ID for secure session tracking"
    )
    
    # Business Logic: Unique transaction identifier for each puzzle
    # Index: Enables fast lookups by transaction ID
    trx_id = models.CharField(
        max_length=36, 
        db_index=True,
        help_text="Unique transaction ID for puzzle tracking"
    )
    
    # Game Data: Puzzle board state (9x9 grid with some cells pre-filled)
    board = models.TextField(
        help_text="JSON serialized 9x9 grid representing the puzzle state"
    )
    
    # Game Data: Complete solution for validation
    solution = models.TextField(
        help_text="JSON serialized 9x9 grid representing the complete solution"
    )
    
    # Timing: When the puzzle was first generated/started
    start_time = models.DateTimeField(
        help_text="Timestamp when the puzzle was first created"
    )
    
    # Game Configuration: Difficulty level for analytics and filtering
    difficulty = models.CharField(
        max_length=10, 
        default="medium",
        help_text="Difficulty level of the puzzle"
    )

    # =============================================================================
    # SECURITY METHODS
    # =============================================================================

    @classmethod
    def hash_session_id(cls, session_id):
        """
        Create a secure hash of the session ID using Django's secret key as salt.
        
        This method ensures that even if the database is compromised, actual
        session IDs cannot be recovered. The SECRET_KEY provides additional
        security through salting.
        
        Args:
            session_id (str): The raw session ID from Django's session framework
            
        Returns:
            str: 64-character hexadecimal SHA-256 hash
            
        Security Notes:
            - Uses Django's SECRET_KEY as salt to prevent rainbow table attacks
            - SHA-256 provides strong cryptographic hashing
            - Hash is deterministic for the same session ID + salt combination
        """
        # Combine session ID with Django's secret key for additional security
        salted_session_id = f"{session_id}{settings.SECRET_KEY}"
        return hashlib.sha256(salted_session_id.encode()).hexdigest()

    # =============================================================================
    # FACTORY METHODS
    # =============================================================================

    @classmethod
    def create_from_session(
        cls, request, board, solution, trx_id, start_time, difficulty="medium"
    ):
        """
        Factory method to create a new puzzle with automatic session handling.
        
        This method handles the complexity of session ID hashing and data
        serialization, providing a clean interface for puzzle creation.
        
        Args:
            request (HttpRequest): Django request object containing session
            board (list|str): 9x9 puzzle grid or JSON string
            solution (list|str): 9x9 solution grid or JSON string  
            trx_id (str): Unique transaction identifier
            start_time (datetime): When the puzzle was started
            difficulty (str): Puzzle difficulty level
            
        Returns:
            SudokuPuzzle: The newly created puzzle instance
            
        Example:
            puzzle = SudokuPuzzle.create_from_session(
                request=request,
                board=[[0,1,2,...], [3,4,5,...], ...],
                solution=[[9,1,2,...], [3,4,5,...], ...],
                trx_id="abc-123-def",
                start_time=timezone.now(),
                difficulty="hard"
            )
        """
        # Extract and hash the session ID for secure storage
        session_id = request.session.session_key
        session_hash = cls.hash_session_id(session_id)

        # Ensure board and solution are properly serialized as JSON strings
        board_json = board if isinstance(board, str) else json.dumps(board)
        solution_json = solution if isinstance(solution, str) else json.dumps(solution)

        # Create and return the puzzle instance
        return cls.objects.create(
            session_id_hash=session_hash,
            board=board_json,
            solution=solution_json,
            trx_id=trx_id,
            start_time=start_time,
            difficulty=difficulty,
        )

    # =============================================================================
    # QUERY METHODS
    # =============================================================================

    @classmethod
    def get_session_puzzles(cls, request):
        """
        Retrieve all puzzles associated with the current session.
        
        This method provides a secure way to query puzzles without exposing
        the actual session ID. Only puzzles belonging to the current session
        will be returned.
        
        Args:
            request (HttpRequest): Django request object containing session
            
        Returns:
            QuerySet: Django QuerySet of puzzles for the current session
            
        Usage:
            puzzles = SudokuPuzzle.get_session_puzzles(request)
            for puzzle in puzzles:
                print(f"Puzzle {puzzle.trx_id}: {puzzle.difficulty}")
        """
        session_id = request.session.session_key
        session_hash = cls.hash_session_id(session_id)
        
        return cls.objects.filter(session_id_hash=session_hash)

    # =============================================================================
    # DATA ACCESS METHODS
    # =============================================================================

    def get_board(self):
        """
        Deserialize and return the puzzle board as a Python object.
        
        Handles both modern JSON format and legacy eval() format for
        backwards compatibility with older puzzle data.
        
        Returns:
            list: 9x9 nested list representing the puzzle board
            
        Example Return:
            [
                [5, 3, 0, 0, 7, 0, 0, 0, 0],
                [6, 0, 0, 1, 9, 5, 0, 0, 0],
                ...
            ]
        """
        try:
            # Try modern JSON deserialization first
            return json.loads(self.board)
        except json.JSONDecodeError:
            # Fallback to legacy eval() for old data
            # Note: This is generally unsafe but needed for backwards compatibility
            return eval(self.board)

    def get_solution(self):
        """
        Deserialize and return the puzzle solution as a Python object.
        
        Returns:
            list: 9x9 nested list representing the complete solution
        """
        try:
            return json.loads(self.solution)
        except json.JSONDecodeError:
            # Legacy data handling
            return eval(self.solution)

    # =============================================================================
    # ADMIN AND DEBUGGING
    # =============================================================================

    def __str__(self):
        """
        String representation for Django admin and debugging.
        
        Returns:
            str: Human-readable puzzle identifier with timestamp and transaction ID
        """
        return f"{self.start_time.strftime('%Y-%m-%d %H:%M:%S')} - {self.trx_id}"

    class Meta:
        """Model metadata for Django ORM optimization."""
        # Add compound index for common query patterns
        indexes = [
            models.Index(fields=['session_id_hash', 'start_time']),
            models.Index(fields=['difficulty', 'start_time']),
        ]
        # Order by most recent puzzles first
        ordering = ['-start_time']


# =============================================================================
# PUZZLE RESULT MODEL
# =============================================================================

class PuzzleResult(models.Model):
    """
    Model for storing completed Sudoku puzzle attempts and results.
    
    This table stores the outcome of puzzle solving attempts, including
    user inputs, validation results, timing data, and solution analysis.
    It provides comprehensive data for game analytics and user progress tracking.
    
    Key Features:
    - Complete puzzle state preservation (original, user input, solution)
    - Performance metrics (time taken, completion status)
    - User input validation and error tracking
    - Support for alternative solution validation
    - Rich metadata for analytics and reporting
    """
    
    # =============================================================================
    # MODEL FIELDS
    # =============================================================================
    
    # Security: Hashed session ID (same pattern as SudokuPuzzle)
    session_id_hash = models.CharField(
        max_length=64, 
        db_index=True,
        help_text="SHA-256 hash of session ID for secure session tracking"
    )
    
    # Business Logic: Links result to original puzzle
    trx_id = models.CharField(
        max_length=36, 
        db_index=True,
        help_text="Transaction ID linking to original puzzle"
    )
    
    # Game State: Original puzzle board
    board = models.TextField(
        help_text="JSON serialized original puzzle state"
    )
    
    # Game State: Official solution
    solution = models.TextField(
        help_text="JSON serialized official solution"
    )
    
    # User Data: What the user submitted
    user_input = models.TextField(
        help_text="JSON serialized user's solution attempt"
    )
    
    # Validation Data: Cell-by-cell validation results
    user_input_state = models.TextField(
        help_text="JSON serialized validation state (C=correct, W=wrong, M=missing)"
    )
    
    # Timing Data: When puzzle was started
    start_time = models.DateTimeField(
        help_text="When the puzzle was originally started"
    )
    
    # Results: Overall success/failure
    solution_status = models.BooleanField(
        help_text="True if puzzle was solved correctly"
    )
    
    # Performance: Time taken to complete
    time_taken = models.DurationField(
        help_text="Duration from start to completion"
    )
    
    # Display: Human-readable time format
    formatted_time = models.TextField(
        blank=True,
        help_text="Human-readable formatted time (HH:MM:SS)"
    )
    
    # Metadata: When result was recorded
    date_completed = models.DateTimeField(
        auto_now_add=True,
        help_text="When the puzzle attempt was completed"
    )
    
    # Configuration: Puzzle difficulty
    difficulty = models.CharField(
        max_length=10, 
        default="medium",
        help_text="Difficulty level of the completed puzzle"
    )
    
    # Advanced: Alternative valid solutions
    alternative_solution = models.TextField(
        blank=True,
        help_text="JSON serialized alternative valid solution if applicable"
    )

    # =============================================================================
    # SECURITY METHODS (Shared with SudokuPuzzle)
    # =============================================================================

    @classmethod
    def hash_session_id(cls, session_id):
        """
        Create a secure hash of the session ID.
        
        Identical implementation to SudokuPuzzle for consistency.
        """
        salted_session_id = f"{session_id}{settings.SECRET_KEY}"
        return hashlib.sha256(salted_session_id.encode()).hexdigest()

    # =============================================================================
    # FACTORY METHODS
    # =============================================================================

    @classmethod
    def create_from_session(cls, request, puzzle_data):
        """
        Factory method to create a puzzle result with automatic session handling.
        
        Args:
            request (HttpRequest): Django request object
            puzzle_data (dict): Dictionary containing all result data
            
        Returns:
            PuzzleResult: The created result instance
            
        Example:
            result = PuzzleResult.create_from_session(request, {
                'trx_id': 'abc-123',
                'board': [[0,1,2,...], ...],
                'solution': [[9,1,2,...], ...], 
                'user_input': [[9,1,3,...], ...],
                'user_input_state': [['C','C','W',...], ...],
                'start_time': puzzle_start,
                'solution_status': False,
                'time_taken': timedelta(minutes=15),
                'formatted_time': '00:15:30',
                'difficulty': 'medium'
            })
        """
        # Hash the session ID for secure storage
        session_id = request.session.session_key
        session_hash = cls.hash_session_id(session_id)

        # Ensure complex data structures are properly serialized
        serializable_fields = ["board", "solution", "user_input", "user_input_state"]
        for field in serializable_fields:
            if field in puzzle_data and not isinstance(puzzle_data[field], str):
                puzzle_data[field] = json.dumps(puzzle_data[field])

        # Create the result with hashed session ID
        return cls.objects.create(session_id_hash=session_hash, **puzzle_data)

    # =============================================================================
    # QUERY METHODS  
    # =============================================================================

    @classmethod
    def get_session_results(cls, request):
        """
        Retrieve all puzzle results for the current session.
        
        Args:
            request (HttpRequest): Django request object
            
        Returns:
            QuerySet: Results associated with the current session
        """
        session_id = request.session.session_key
        session_hash = cls.hash_session_id(session_id)
        
        return cls.objects.filter(session_id_hash=session_hash)

    # =============================================================================
    # DATA ACCESS METHODS
    # =============================================================================

    def get_board(self):
        """Get the original board as a Python object."""
        try:
            return json.loads(self.board)
        except json.JSONDecodeError:
            return eval(self.board)

    def get_solution(self):
        """Get the official solution as a Python object."""
        try:
            return json.loads(self.solution)
        except json.JSONDecodeError:
            return eval(self.solution)

    def get_user_input(self):
        """Get the user's input as a Python object."""
        try:
            return json.loads(self.user_input)
        except json.JSONDecodeError:
            return eval(self.user_input)

    def get_user_input_state(self):
        """
        Get the validation state as a Python object.
        
        Returns:
            list: 9x9 grid where each cell contains:
                'C' = Correct answer
                'W' = Wrong answer  
                'M' = Missing/not attempted
        """
        try:
            return json.loads(self.user_input_state)
        except json.JSONDecodeError:
            return eval(self.user_input_state)

    # =============================================================================
    # ADMIN AND DEBUGGING
    # =============================================================================

    def __str__(self):
        """String representation for admin interface."""
        status = "✓" if self.solution_status else "✗"
        return f"{status} {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} - {self.trx_id}"

    class Meta:
        """Model metadata for Django ORM optimization."""
        indexes = [
            models.Index(fields=['session_id_hash', 'date_completed']),
            models.Index(fields=['difficulty', 'solution_status']),
            models.Index(fields=['date_completed']),
        ]
        ordering = ['-date_completed']
