from django.db import models
import json
import hashlib
from django.conf import settings


class SudokuPuzzle(models.Model):
    """
    Table to save SudokuPuzzle with improved security and data handling
    """

    # Hashed session ID for security
    session_id_hash = models.CharField(max_length=64, db_index=True)
    trx_id = models.CharField(
        max_length=36, db_index=True
    )  # Transaction ID with index for faster queries
    board = models.TextField()  # Store the puzzle as a string of numbers
    solution = models.TextField()  # Store the solution as a string of numbers
    start_time = models.DateTimeField()  # Store the time when the puzzle was started
    difficulty = models.CharField(
        max_length=10, default="medium"
    )  # Track puzzle difficulty

    @classmethod
    def hash_session_id(cls, session_id):
        """
        Create a secure hash of the session ID using Django's secret key as salt

        Args:
            session_id: The raw session ID to hash

        Returns:
            str: Securely hashed session ID
        """
        salted_session_id = f"{session_id}{settings.SECRET_KEY}"
        return hashlib.sha256(salted_session_id.encode()).hexdigest()

    @classmethod
    def create_from_session(
        cls, request, board, solution, trx_id, start_time, difficulty="medium"
    ):
        """
        Create a new puzzle record with hashed session ID

        Args:
            request: The Django request object containing the session
            board: The puzzle board
            solution: The puzzle solution
            trx_id: Transaction ID
            start_time: When the puzzle started
            difficulty: Puzzle difficulty level

        Returns:
            SudokuPuzzle: The created puzzle instance
        """
        session_id = request.session.session_key
        session_hash = cls.hash_session_id(session_id)

        return cls.objects.create(
            session_id_hash=session_hash,
            board=board if isinstance(board, str) else json.dumps(board),
            solution=solution if isinstance(solution, str) else json.dumps(solution),
            trx_id=trx_id,
            start_time=start_time,
            difficulty=difficulty,
        )

    @classmethod
    def get_session_puzzles(cls, request):
        """
        Retrieve puzzles for the current session

        Args:
            request: The Django request object containing the session

        Returns:
            QuerySet: Puzzles associated with the current session
        """
        session_id = request.session.session_key
        session_hash = cls.hash_session_id(session_id)

        return cls.objects.filter(session_id_hash=session_hash)

    def get_board(self):
        """
        Get the board as a Python object

        Returns:
            list: The board as a 2D list
        """
        try:
            return json.loads(self.board)
        except json.JSONDecodeError:
            # Legacy data handling
            return eval(self.board)

    def get_solution(self):
        """
        Get the solution as a Python object

        Returns:
            list: The solution as a 2D list
        """
        try:
            return json.loads(self.solution)
        except json.JSONDecodeError:
            # Legacy data handling
            return eval(self.solution)

    def __str__(self):
        """
        String representation of a puzzle for admin interface and debugging
        """
        return f"{self.start_time.strftime('%Y-%m-%d %H:%M:%S')} - {self.trx_id}"


class PuzzleResult(models.Model):
    """
    Table to save SudokuPuzzleResults with improved security and data handling
    """

    # Hashed session ID for security
    session_id_hash = models.CharField(max_length=64, db_index=True)
    trx_id = models.CharField(
        max_length=36, db_index=True
    )  # Transaction ID with index for faster queries
    board = models.TextField()  # Store the puzzle as a string of numbers
    solution = models.TextField()  # Store the solution as a string of numbers
    user_input = models.TextField()  # Store the user_input as a string of numbers
    user_input_state = (
        models.TextField()
    )  # Store the user_input_state as a string of numbers
    start_time = models.DateTimeField()  # Store the time when the puzzle was started
    solution_status = (
        models.BooleanField()
    )  # Store whether the puzzle was solved correctly
    time_taken = models.DurationField()  # Store the time taken
    formatted_time = models.TextField(blank=True)  # Store the formatted time
    date_completed = models.DateTimeField(
        auto_now_add=True
    )  # When the puzzle was completed
    difficulty = models.CharField(
        max_length=10, default="medium"
    )  # Track puzzle difficulty
    alternative_solution = models.TextField(
        blank=True
    )  # Store the alternative solution as a string of numbers

    @classmethod
    def hash_session_id(cls, session_id):
        """
        Create a secure hash of the session ID using Django's secret key as salt

        Args:
            session_id: The raw session ID to hash

        Returns:
            str: Securely hashed session ID
        """
        salted_session_id = f"{session_id}{settings.SECRET_KEY}"
        return hashlib.sha256(salted_session_id.encode()).hexdigest()

    @classmethod
    def create_from_session(cls, request, puzzle_data):
        """
        Create a new puzzle result with hashed session ID

        Args:
            request: The Django request object containing the session
            puzzle_data: Dictionary containing puzzle result data

        Returns:
            PuzzleResult: The created puzzle result instance
        """
        session_id = request.session.session_key
        session_hash = cls.hash_session_id(session_id)

        # Ensure data is properly serialized
        for field in ["board", "solution", "user_input", "user_input_state"]:
            if field in puzzle_data and not isinstance(puzzle_data[field], str):
                puzzle_data[field] = json.dumps(puzzle_data[field])

        return cls.objects.create(session_id_hash=session_hash, **puzzle_data)

    @classmethod
    def get_session_results(cls, request):
        """
        Retrieve results for the current session

        Args:
            request: The Django request object containing the session

        Returns:
            QuerySet: Puzzle results associated with the current session
        """
        session_id = request.session.session_key
        session_hash = cls.hash_session_id(session_id)

        return cls.objects.filter(session_id_hash=session_hash)

    def get_board(self):
        """Get the board as a Python object"""
        try:
            return json.loads(self.board)
        except json.JSONDecodeError:
            # Legacy data handling
            return eval(self.board)

    def get_solution(self):
        """Get the solution as a Python object"""
        try:
            return json.loads(self.solution)
        except json.JSONDecodeError:
            # Legacy data handling
            return eval(self.solution)

    def get_user_input(self):
        """Get the user input as a Python object"""
        try:
            return json.loads(self.user_input)
        except json.JSONDecodeError:
            # Legacy data handling
            return eval(self.user_input)

    def get_user_input_state(self):
        """Get the user input state as a Python object"""
        try:
            return json.loads(self.user_input_state)
        except json.JSONDecodeError:
            # Legacy data handling
            return eval(self.user_input_state)

    def __str__(self):
        """
        String representation of a puzzle result for admin interface and debugging
        """
        return f"{self.start_time.strftime('%Y-%m-%d %H:%M:%S')} - {self.trx_id}"
