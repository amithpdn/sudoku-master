from django.apps import AppConfig


class SudokuConfig(AppConfig):
    """
    Django application configuration for the Sudoku app.

    Defines the app name and default auto field type for models.
    """

    # Use BigAutoField as the primary key type for models
    default_auto_field = "django.db.models.BigAutoField"
    # Application name used by Django
    name = "sudoku"
