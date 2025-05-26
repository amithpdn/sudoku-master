"""
URL configuration for sudoku_game project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include

# =============================================================================
# MAIN URL PATTERNS
# =============================================================================

urlpatterns = [
    # Django Admin Interface
    # Access at: /admin/
    # Provides administrative interface for managing users, sessions, and app data
    # Requires superuser credentials (create with: python manage.py createsuperuser)
    path("admin/", admin.site.urls),
    
    # Sudoku Game Application
    # Access at: /sudoku/
    # All game-related URLs are handled by the sudoku app's URL configuration
    # See sudoku/urls.py for detailed routing within the application
    path("sudoku/", include("sudoku.urls")),
    
    # Note: Root URL (/) is not used here
]
