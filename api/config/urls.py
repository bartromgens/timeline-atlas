"""
URL configuration for timeline-atlas API.
"""

from django.contrib import admin
from django.urls import include, path

from api.config.views import auth_me

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/me/", auth_me),
    path("api/", include("api.events.urls")),
]
