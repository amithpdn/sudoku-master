"""
Django Admin Configuration for Sudoku Game Application

This module customizes the Django admin interface for managing Sudoku puzzles
and results. It provides rich visual representations of puzzle grids, enhanced
filtering capabilities, and user-friendly data presentation for administrators.

Key Features:
- Visual HTML grid previews for puzzles and solutions
- Color-coded user input validation display
- Advanced filtering and searching capabilities
- Read-only field formatting for better data presentation
- Responsive grid styling with proper Sudoku subgrid borders

The admin interface is essential for:
- Debugging puzzle generation and validation logic
- Monitoring user gameplay patterns and performance
- Analyzing solution accuracy and common mistakes
- System administration and data management

Author: Sudoku Game Team
License: MIT
"""

from django.contrib import admin
from .models import PuzzleResult, SudokuPuzzle
import json

# =============================================================================
# SUDOKU PUZZLE ADMIN CONFIGURATION
# =============================================================================

class SudokuPuzzleAdmin(admin.ModelAdmin):
    """
    Custom admin interface for SudokuPuzzle model.
    
    This admin class enhances the default Django admin interface with:
    - Visual HTML grid previews of puzzles and solutions
    - Custom date/time formatting for better readability
    - Advanced filtering and search capabilities
    - Read-only fields to prevent accidental data corruption
    
    The admin interface is particularly useful for:
    - Debugging puzzle generation algorithms
    - Verifying puzzle difficulty and uniqueness
    - Monitoring puzzle creation patterns
    - Quality assurance testing
    """
    
    # =============================================================================
    # ADMIN INTERFACE CONFIGURATION
    # =============================================================================
    
    # Fields that cannot be edited (prevents accidental data corruption)
    readonly_fields = ("custom_start_time", "board_preview", "solution_preview")
    
    # Columns displayed in the admin list view (main puzzle overview)
    list_display = ("trx_id", "difficulty", "custom_start_time")
    
    # Fields that can be searched (enables quick puzzle lookup)
    search_fields = ("trx_id", "difficulty")
    
    # Sidebar filters for data exploration and analysis
    list_filter = ("difficulty", "start_time")
    
    # Ordering of records in list view (most recent first)
    ordering = ["-start_time"]
    
    # Number of records per page (performance optimization)
    list_per_page = 25
    
    # =============================================================================
    # CUSTOM FIELD FORMATTERS
    # =============================================================================
    
    def custom_start_time(self, obj):
        """
        Format the start_time field for consistent display in admin interface.
        
        Provides a standardized datetime format that's easy to read and compare
        across different puzzle records.
        
        Args:
            obj (SudokuPuzzle): The puzzle instance being displayed
            
        Returns:
            str: Formatted datetime string (YYYY-MM-DD HH:MM:SS) or '-' if None
            
        Example Output: "2025-05-26 14:30:45"
        """
        if obj.start_time:
            return obj.start_time.strftime("%Y-%m-%d %H:%M:%S")
        return "-"
    
    # Set column header in admin interface
    custom_start_time.short_description = "Start Time"
    
    # =============================================================================
    # VISUAL GRID PREVIEW METHODS
    # =============================================================================
    
    def board_preview(self, obj):
        """
        Generate an HTML table preview of the puzzle board.
        
        Creates a visual representation of the Sudoku puzzle with:
        - Proper 3x3 subgrid borders (thick black lines)
        - Cell borders for individual squares
        - Empty cells displayed as blank spaces
        - Filled cells showing the pre-placed numbers
        - Responsive styling that works in admin interface
        
        This is invaluable for:
        - Quickly visualizing puzzle layouts
        - Verifying puzzle generation correctness
        - Debugging grid parsing issues
        - Quality assurance and testing
        
        Args:
            obj (SudokuPuzzle): The puzzle instance
            
        Returns:
            str: HTML table representing the puzzle board
        """
        try:
            # Parse the JSON board data using model method
            board = obj.get_board()
            
            # Start building HTML table with collapsed borders
            html = '<table style="border-collapse: collapse; font-family: monospace;">'
            
            # Iterate through each row of the 9x9 grid
            for i, row in enumerate(board):
                html += "<tr>"
                
                # Iterate through each cell in the row
                for j, cell in enumerate(row):
                    # Build border styling for 3x3 subgrid visualization
                    border_style = "border: 1px solid #ddd;"
                    
                    # Add thick borders for 3x3 subgrid boundaries
                    if i % 3 == 0:  # Top border of subgrid
                        border_style += "border-top: 2px solid #333;"
                    if i % 3 == 2:  # Bottom border of subgrid
                        border_style += "border-bottom: 2px solid #333;"
                    if j % 3 == 0:  # Left border of subgrid
                        border_style += "border-left: 2px solid #333;"
                    if j % 3 == 2:  # Right border of subgrid
                        border_style += "border-right: 2px solid #333;"
                    
                    # Complete cell styling
                    cell_style = (
                        f'style="{border_style} padding: 5px; text-align: center; '
                        f'width: 25px; height: 25px; font-weight: bold;"'
                    )
                    
                    # Render cell content
                    if cell == 0:
                        # Empty cell - show as non-breaking space
                        html += f"<td {cell_style}>&nbsp;</td>"
                    else:
                        # Filled cell - show the number
                        html += f"<td {cell_style}>{cell}</td>"
                
                html += "</tr>"
            
            html += "</table>"
            return html
            
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            # Handle corrupted or invalid data gracefully
            return f"Error: Could not parse board data ({str(e)})"
    
    # Configure admin interface display
    board_preview.short_description = "Puzzle Board"
    board_preview.allow_tags = True  # Allow HTML rendering
    
    def solution_preview(self, obj):
        """
        Generate an HTML table preview of the complete solution.
        
        Similar to board_preview but shows the complete solved puzzle.
        This is useful for:
        - Verifying solution correctness
        - Debugging solving algorithms
        - Understanding puzzle difficulty
        - Quality assurance testing
        
        Args:
            obj (SudokuPuzzle): The puzzle instance
            
        Returns:
            str: HTML table representing the complete solution
        """
        try:
            # Parse the JSON solution data
            solution = obj.get_solution()
            
            # Build HTML table (similar structure to board_preview)
            html = '<table style="border-collapse: collapse; font-family: monospace;">'
            
            for i, row in enumerate(solution):
                html += "<tr>"
                for j, cell in enumerate(row):
                    # Apply same border styling as board preview
                    border_style = "border: 1px solid #ddd;"
                    
                    if i % 3 == 0:
                        border_style += "border-top: 2px solid #333;"
                    if i % 3 == 2:
                        border_style += "border-bottom: 2px solid #333;"
                    if j % 3 == 0:
                        border_style += "border-left: 2px solid #333;"
                    if j % 3 == 2:
                        border_style += "border-right: 2px solid #333;"
                    
                    cell_style = (
                        f'style="{border_style} padding: 5px; text-align: center; '
                    )
                    
                    # All solution cells should be filled (1-9)
                    html += f"<td {cell_style}>{cell}</td>"
                
                html += "</tr>"
            
            html += "</table>"
            return html
            
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            return f"Error: Could not parse solution data ({str(e)})"
    
    solution_preview.short_description = "Complete Solution"
    solution_preview.allow_tags = True


# =============================================================================
# PUZZLE RESULT ADMIN CONFIGURATION
# =============================================================================

class PuzzleResultAdmin(admin.ModelAdmin):
    """
    Custom admin interface for PuzzleResult model.
    
    This admin class provides comprehensive management of completed puzzle
    attempts with enhanced visualization and analysis capabilities:
    
    - Color-coded user input validation display
    - Side-by-side comparison of user input vs. correct solution
    - Performance metrics and timing analysis
    - Advanced filtering by success rate and difficulty
    - Detailed error analysis for incorrect solutions
    
    Essential for:
    - Analyzing user performance patterns
    - Identifying common mistake patterns
    - Debugging validation logic
    - Performance optimization insights
    - User experience research
    """
    
    # =============================================================================
    # ADMIN INTERFACE CONFIGURATION
    # =============================================================================
    
    # Read-only fields to prevent data corruption
    readonly_fields = (
        "custom_start_time",
        "custom_date_completed", 
        "board_preview",
        "user_input_preview",
        "solution_preview",
    )
    
    # List view columns for quick overview of results
    list_display = (
        "trx_id",                    # Transaction identifier
        "difficulty",                # Puzzle difficulty level
        "solution_status",           # Success/failure indicator
        "formatted_time",            # Time taken to complete
        "custom_start_time",         # When puzzle was started
        "custom_date_completed",     # When puzzle was completed
    )
    
    # Searchable fields for quick lookup
    search_fields = ("trx_id", "difficulty")
    
    # Filtering options for data analysis
    list_filter = (
        "solution_status",           # Filter by success/failure
        "difficulty",                # Filter by difficulty level
        "date_completed",            # Filter by completion date
    )
    
    # Default ordering (most recent completions first)
    ordering = ["-date_completed"]
    
    # Pagination for performance
    list_per_page = 20
    
    # =============================================================================
    # CUSTOM FIELD FORMATTERS
    # =============================================================================
    
    def custom_start_time(self, obj):
        """Format start time for consistent display."""
        if obj.start_time:
            return obj.start_time.strftime("%Y-%m-%d %H:%M:%S")
        return "-"
    
    custom_start_time.short_description = "Started At"
    
    def custom_date_completed(self, obj):
        """Format completion time for consistent display."""
        if obj.date_completed:
            return obj.date_completed.strftime("%Y-%m-%d %H:%M:%S")
        return "-"
    
    custom_date_completed.short_description = "Completed At"
    
    # =============================================================================
    # VISUAL GRID PREVIEW METHODS
    # =============================================================================
    
    def board_preview(self, obj):
        """
        Generate HTML preview of the original puzzle board.
        
        Shows the initial puzzle state before user interaction.
        Useful for understanding the difficulty and layout of the puzzle
        the user was attempting to solve.
        """
        try:
            board = obj.get_board()
            
            html = '<table style="border-collapse: collapse; font-family: monospace;">'
            for i, row in enumerate(board):
                html += "<tr>"
                for j, cell in enumerate(row):
                    # Standard Sudoku grid styling
                    border_style = "border: 1px solid #ddd;"
                    if i % 3 == 0:
                        border_style += "border-top: 2px solid #333;"
                    if i % 3 == 2:
                        border_style += "border-bottom: 2px solid #333;"
                    if j % 3 == 0:
                        border_style += "border-left: 2px solid #333;"
                    if j % 3 == 2:
                        border_style += "border-right: 2px solid #333;"
                    
                    cell_style = (
                        f'style="{border_style} padding: 5px; text-align: center;"'
                    )
                    
                    if cell == 0:
                        html += f"<td {cell_style}>&nbsp;</td>"
                    else:
                        html += f"<td {cell_style}>{cell}</td>"
                
                html += "</tr>"
            html += "</table>"
            return html
            
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            return f"Error: Could not parse board data ({str(e)})"
    
    board_preview.short_description = "Original Puzzle"
    board_preview.allow_tags = True
    
    def user_input_preview(self, obj):
        """
        Generate color-coded HTML preview of user's solution attempt.
        
        This is the most valuable admin feature for analyzing user performance.
        Uses color coding to show:
        - Green: Correct user input
        - Red: Incorrect user input  
        - Yellow: Cells not attempted by user
        - Gray: Pre-filled cells from original puzzle
        
        This visualization helps identify:
        - Common mistake patterns
        - Areas where users struggle
        - Validation logic issues
        - User interface problems
        
        Args:
            obj (PuzzleResult): The result instance
            
        Returns:
            str: HTML table with color-coded user input validation
        """
        try:
            # Get user input and validation state data
            user_input = obj.get_user_input()
            user_input_state = obj.get_user_input_state()
            
            html = '<table style="border-collapse: collapse; font-family: monospace;">'
            
            for i, row in enumerate(user_input):
                html += "<tr>"
                for j, cell in enumerate(row):
                    # Standard border styling
                    border_style = "border: 1px solid #ddd;"
                    if i % 3 == 0:
                        border_style += "border-top: 2px solid #333;"
                    if i % 3 == 2:
                        border_style += "border-bottom: 2px solid #333;"
                    if j % 3 == 0:
                        border_style += "border-left: 2px solid #333;"
                    if j % 3 == 2:
                        border_style += "border-right: 2px solid #333;"
                    
                    # Color coding based on validation status
                    cell_status = user_input_state[i][j]
                    
                    # Define color scheme for different cell states
                    if cell_status == "C":      # Correct user input
                        bg_color = "#d4edda"    # Light green
                        text_color = "#155724"  # Dark green
                    elif cell_status == "W":   # Wrong user input
                        bg_color = "#f8d7da"    # Light red  
                        text_color = "#721c24"  # Dark red
                    elif cell_status == "M":   # Missing (not attempted)
                        bg_color = "#fff3cd"    # Light yellow
                        text_color = "#856404"  # Dark yellow
                    elif cell_status == "P":   # Pre-filled (original puzzle)
                        bg_color = "#e2e3e5"    # Light gray
                        text_color = "#383d41"  # Dark gray
                    else:                       # Unknown status
                        bg_color = "#fff"       # White
                        text_color = "#000"     # Black
                    
                    cell_style = f'style="{border_style} padding: 5px; text-align: center; background-color: {bg_color};"'
                    
                    if cell == 0:
                        html += f"<td {cell_style}>&nbsp;</td>"
                    else:
                        html += f"<td {cell_style}>{cell}</td>"
                
                html += "</tr>"
            
            html += "</table>"
            
            # Add legend for color coding
            html += '<div style="margin-top: 10px; font-size: 12px;">'
            html += '<span style="background: #d4edda; padding: 2px 5px; margin-right: 10px;">Correct</span>'
            html += '<span style="background: #f8d7da; padding: 2px 5px; margin-right: 10px;">Wrong</span>'
            html += '<span style="background: #fff3cd; padding: 2px 5px; margin-right: 10px;">Missing</span>'
            html += '<span style="background: #e2e3e5; padding: 2px 5px;">Pre-filled</span>'
            html += '</div>'
            
            return html
            
        except (json.JSONDecodeError, TypeError, AttributeError, IndexError) as e:
            return f"Error: Could not parse user input data ({str(e)})"
    
    user_input_preview.short_description = "User Solution (Color-Coded)"
    user_input_preview.allow_tags = True
    
    def solution_preview(self, obj):
        """
        Generate HTML preview of the correct solution.
        
        Shows what the correct answer should have been, useful for
        comparison with user input to understand where mistakes occurred.
        """
        try:
            solution = obj.get_solution()
            
            html = '<table style="border-collapse: collapse; font-family: monospace;">'
            for i, row in enumerate(solution):
                html += "<tr>"
                for j, cell in enumerate(row):
                    border_style = "border: 1px solid #ddd;"
                    if i % 3 == 0:
                        border_style += "border-top: 2px solid #333;"
                    if i % 3 == 2:
                        border_style += "border-bottom: 2px solid #333;"
                    if j % 3 == 0:
                        border_style += "border-left: 2px solid #333;"
                    if j % 3 == 2:
                        border_style += "border-right: 2px solid #333;"
                    
                    cell_style = (
                        f'style="{border_style} padding: 5px; text-align: center; '
                        f'width: 25px; height: 25px; font-weight: bold; '
                        f'background-color: #e8f5e8;"'  # Light green background
                    )
                    
                    html += f"<td {cell_style}>{cell}</td>"
                
                html += "</tr>"
            html += "</table>"
            return html
            
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            return f"Error: Could not parse solution data ({str(e)})"
    
    solution_preview.short_description = "Correct Solution"
    solution_preview.allow_tags = True


# =============================================================================
# ADMIN SITE REGISTRATION
# =============================================================================

# Register models with their custom admin classes
# This enables the enhanced admin interface for both models
admin.site.register(SudokuPuzzle, SudokuPuzzleAdmin)
admin.site.register(PuzzleResult, PuzzleResultAdmin)
