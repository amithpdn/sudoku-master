from django.contrib import admin
from .models import PuzzleResult, SudokuPuzzle
import json


class SudokuPuzzleAdmin(admin.ModelAdmin):
    """
    Admin class for SudokuPuzzle model that customizes the Django admin interface.
    Provides custom display formatting for timestamps and specific field display ordering.
    """

    # Define fields that cannot be edited in the admin interface
    readonly_fields = ("custom_start_time", "board_preview", "solution_preview")

    # Define which fields appear in the admin list view
    list_display = ("trx_id", "difficulty", "custom_start_time")

    # Add search fields for easier record location
    search_fields = ("trx_id", "difficulty")

    # Add filters for enhanced navigation
    list_filter = ("difficulty", "start_time")

    def custom_start_time(self, obj):
        """
        Format the start_time field in a consistent datetime format (YYYY-MM-DD HH:MM:SS).

        Args:
            obj: The SudokuPuzzle instance

        Returns:
            str: Formatted datetime string or '-' if no start_time exists
        """
        if obj.start_time:
            return obj.start_time.strftime("%Y-%m-%d %H:%M:%S")
        return "-"

    custom_start_time.short_description = (
        "Start Time"  # Column header in admin interface
    )

    def board_preview(self, obj):
        """
        Generate a formatted HTML preview of the puzzle board.

        Args:
            obj: The SudokuPuzzle instance

        Returns:
            str: HTML-formatted board preview
        """
        try:
            board = obj.get_board()
            html = '<table style="border-collapse: collapse;">'
            for i, row in enumerate(board):
                html += "<tr>"
                for j, cell in enumerate(row):
                    # Add styling for subgrid borders
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
                        # Empty cell
                        html += f"<td {cell_style}>&nbsp;</td>"
                    else:
                        # Filled cell
                        html += f"<td {cell_style}>{cell}</td>"
                html += "</tr>"
            html += "</table>"
            return html
        except (json.JSONDecodeError, TypeError, AttributeError):
            return "Error: Could not parse board data"

    board_preview.short_description = "Puzzle Board"
    board_preview.allow_tags = True

    def solution_preview(self, obj):
        """
        Generate a formatted HTML preview of the puzzle solution.

        Args:
            obj: The SudokuPuzzle instance

        Returns:
            str: HTML-formatted solution preview
        """
        try:
            solution = obj.get_solution()
            html = '<table style="border-collapse: collapse;">'
            for i, row in enumerate(solution):
                html += "<tr>"
                for j, cell in enumerate(row):
                    # Add styling for subgrid borders
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
                    html += f"<td {cell_style}>{cell}</td>"
                html += "</tr>"
            html += "</table>"
            return html
        except (json.JSONDecodeError, TypeError, AttributeError):
            return "Error: Could not parse solution data"

    solution_preview.short_description = "Solution"
    solution_preview.allow_tags = True


class PuzzleResultAdmin(admin.ModelAdmin):
    """
    Admin class for PuzzleResult model that customizes the Django admin interface.
    Provides custom display formatting for timestamps and specific field display ordering.
    """

    # Define fields that cannot be edited in the admin interface
    readonly_fields = (
        "custom_start_time",
        "custom_date_completed",
        "board_preview",
        "user_input_preview",
        "solution_preview",
    )

    # Define which fields appear in the admin list view
    list_display = (
        "trx_id",
        "difficulty",
        "solution_status",
        "formatted_time",
        "custom_start_time",
        "custom_date_completed",
    )

    # Add search fields for easier record location
    search_fields = ("trx_id", "difficulty")

    # Add filters for enhanced navigation
    list_filter = ("solution_status", "difficulty", "date_completed")

    def custom_start_time(self, obj):
        """
        Format the start_time field in a consistent datetime format (YYYY-MM-DD HH:MM:SS).

        Args:
            obj: The PuzzleResult instance

        Returns:
            str: Formatted datetime string or '-' if no start_time exists
        """
        if obj.start_time:
            return obj.start_time.strftime("%Y-%m-%d %H:%M:%S")
        return "-"

    custom_start_time.short_description = (
        "Start Time"  # Column header in admin interface
    )

    def custom_date_completed(self, obj):
        """
        Format the date_completed field in a consistent datetime format (YYYY-MM-DD HH:MM:SS).

        Args:
            obj: The PuzzleResult instance

        Returns:
            str: Formatted datetime string or '-' if no date_completed exists
        """
        if obj.date_completed:
            return obj.date_completed.strftime("%Y-%m-%d %H:%M:%S")
        return "-"

    # Fixed the incorrect short description
    custom_date_completed.short_description = "Date Completed"

    def board_preview(self, obj):
        """Generate HTML preview of the original puzzle board."""
        try:
            board = obj.get_board()
            html = '<table style="border-collapse: collapse;">'
            for i, row in enumerate(board):
                html += "<tr>"
                for j, cell in enumerate(row):
                    # Add styling for subgrid borders
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
                        # Empty cell
                        html += f"<td {cell_style}>&nbsp;</td>"
                    else:
                        # Filled cell
                        html += f"<td {cell_style}>{cell}</td>"
                html += "</tr>"
            html += "</table>"
            return html
        except (json.JSONDecodeError, TypeError, AttributeError):
            return "Error: Could not parse board data"

    board_preview.short_description = "Original Puzzle"
    board_preview.allow_tags = True

    def user_input_preview(self, obj):
        """Generate HTML preview of the user's input with color-coded correctness."""
        try:
            user_input = obj.get_user_input()
            user_input_state = obj.get_user_input_state()
            html = '<table style="border-collapse: collapse;">'
            for i, row in enumerate(user_input):
                html += "<tr>"
                for j, cell in enumerate(row):
                    # Add styling for subgrid borders
                    border_style = "border: 1px solid #ddd;"
                    if i % 3 == 0:
                        border_style += "border-top: 2px solid #333;"
                    if i % 3 == 2:
                        border_style += "border-bottom: 2px solid #333;"
                    if j % 3 == 0:
                        border_style += "border-left: 2px solid #333;"
                    if j % 3 == 2:
                        border_style += "border-right: 2px solid #333;"

                    # Add color based on cell status
                    cell_status = user_input_state[i][j]
                    bg_color = "#fff"  # Default white
                    if cell_status == "C":  # Correct
                        bg_color = "#d4edda"  # Light green
                    elif cell_status == "W":  # Wrong
                        bg_color = "#f8d7da"  # Light red
                    elif cell_status == "N":  # Not attempted
                        bg_color = "#fff3cd"  # Light yellow
                    elif cell_status == "P":  # Pre-filled
                        bg_color = "#e2e3e5"  # Light gray

                    cell_style = f'style="{border_style} padding: 5px; text-align: center; background-color: {bg_color};"'

                    if cell == 0:
                        # Empty cell
                        html += f"<td {cell_style}>&nbsp;</td>"
                    else:
                        # Filled cell
                        html += f"<td {cell_style}>{cell}</td>"
                html += "</tr>"
            html += "</table>"
            return html
        except (json.JSONDecodeError, TypeError, AttributeError, IndexError):
            return "Error: Could not parse user input data"

    user_input_preview.short_description = "User Solution"
    user_input_preview.allow_tags = True

    def solution_preview(self, obj):
        """Generate HTML preview of the correct solution."""
        try:
            solution = obj.get_solution()
            html = '<table style="border-collapse: collapse;">'
            for i, row in enumerate(solution):
                html += "<tr>"
                for j, cell in enumerate(row):
                    # Add styling for subgrid borders
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
                    html += f"<td {cell_style}>{cell}</td>"
                html += "</tr>"
            html += "</table>"
            return html
        except (json.JSONDecodeError, TypeError, AttributeError):
            return "Error: Could not parse solution data"

    solution_preview.short_description = "Correct Solution"
    solution_preview.allow_tags = True


# Register models with custom admin classes to enhance the admin interface
admin.site.register(SudokuPuzzle, SudokuPuzzleAdmin)
admin.site.register(PuzzleResult, PuzzleResultAdmin)
