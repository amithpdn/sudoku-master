from django.urls import path
from . import views

urlpatterns = [
    # Index/Home page
    path("", views.index, name="index"),
    # Existing URLs
    path("new/", views.new_puzzle, name="new_puzzle"),
    path("check/", views.check_puzzle, name="check_puzzle"),
    path("view/", views.view_puzzle, name="view_puzzle"),
    # Health check endpoint
    path("health/", views.health_check, name="health_check"),
]
