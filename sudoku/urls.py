"""
URL Configuration for Sudoku Game Application

This module defines the URL routing patterns for the Sudoku game application.
Each URL pattern maps incoming requests to specific view functions that handle
the game logic, puzzle generation, validation, and result management.

URL Structure and Flow:
1. /sudoku/          -> Game homepage (index view)
2. /sudoku/new/      -> Generate new puzzle (new_puzzle view)  
3. /sudoku/check/    -> Validate solution (check_puzzle view)
4. /sudoku/view/     -> View past results (view_puzzle view)
5. /sudoku/health/   -> System health check (health_check view)

The URL patterns follow RESTful conventions where possible and provide
intuitive navigation for users and developers.

Author: Sudoku Game Team
License: MIT
"""

from django.urls import path
from . import views

# =============================================================================
# URL PATTERN DEFINITIONS
# =============================================================================

urlpatterns = [
    # =============================================================================
    # MAIN GAME URLS
    # =============================================================================
    
    # Homepage/Index - Main entry point for the application
    # URL: /sudoku/
    # Method: GET
    # Purpose: Display welcome page, game statistics, and navigation options
    # Template: sudoku/index.html
    # Context: User stats, recent games, navigation links
    path("", views.index, name="index"),
    
    # New Puzzle Generation
    # URL: /sudoku/new/
    # Methods: GET (show form), POST (generate puzzle)
    # Purpose: Generate new Sudoku puzzles with configurable difficulty
    # Template: sudoku/new_puzzle.html
    # Parameters: 
    #   - difficulty (query param): easy, medium, hard, ex-hard
    # Features: 
    #   - Difficulty selection
    #   - Puzzle state persistence
    #   - Timer functionality
    #   - Session management
    path("new/", views.new_puzzle, name="new_puzzle"),
    
    # Solution Checking and Validation
    # URL: /sudoku/check/
    # Method: POST
    # Purpose: Validate user's puzzle solution and provide feedback
    # Form Data:
    #   - cell_X_Y: User input for each grid cell
    #   - trx_id: Transaction ID linking to original puzzle
    #   - timer_value: Time taken to complete puzzle
    # Response: Redirects to results page with validation feedback
    # Security: CSRF protection, session validation, input sanitization
    path("check/", views.check_puzzle, name="check_puzzle"),
    
    # Results and History Viewing
    # URL: /sudoku/view/
    # Methods: GET (search form), POST (search results)
    # Purpose: View previous puzzle attempts and results
    # Parameters:
    #   - trx_id (POST): Transaction ID to lookup specific result
    # Features:
    #   - Result history browsing
    #   - Performance analytics
    #   - Solution comparison
    #   - Session-based filtering
    path("view/", views.view_puzzle, name="view_puzzle"),
    
    # =============================================================================
    # SYSTEM ADMINISTRATION URLS
    # =============================================================================
    
    # System Health Check Endpoint
    # URL: /sudoku/health/
    # Method: GET
    # Purpose: Monitor application health and system status
    # Access: Admin/superuser only (configured in view)
    # Response: JSON status report with system metrics
    # Use Cases:
    #   - Load balancer health checks
    #   - Monitoring system integration
    #   - Development debugging
    #   - Performance monitoring
    path("health/", views.health_check, name="health_check"),
]
