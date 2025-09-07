"""
URL configuration for the Verboheit Math League project.

Includes:
- Admin interface
- API routes with versioning
- Interactive API docs via Swagger and ReDoc (powered by drf-yasg)
- Debug toolbar URLs
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# === Swagger Schema Configuration ===
schema_view = get_schema_view(
    openapi.Info(
        title="Verboheit Math League Competition API",
        default_version="v1",
        description="API documentation for the Verboheit Math League Competition Web Platform",
        # terms_of_service=settings.TOS_URL,
        contact=openapi.Contact(
            name="API Support",
            email=settings.CONTACT_EMAIL,
            url=settings.CONTACT_URL,
        ),
        # license=openapi.License(
        #     name="Proprietary License",
        #     url=settings.LICENSE_URL,
        # ),
        x_logo={
            "url": settings.LOGO_URL,
            "backgroundColor": "#FFFFFF",
            "altText": "Verboheit Logo",
        },
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[],
    url=settings.BASE_URL if not settings.DEBUG else None,
)

api_urlpatterns = [
    path("v1/", include("vmlc.urls", namespace="v1")),
]

docs_urlpatterns = [
    re_path(
        r"^schema(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema",
    ),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path(
        "redoc/",
        schema_view.with_ui("redoc", cache_timeout=0),
        name="schema-redoc",
    ),
]

urlpatterns = [
    # === Admin Panel ===
    path(settings.ADMIN_URL, admin.site.urls),
    # === API ===
    path("", include(api_urlpatterns)),
    # === API Docs ===
    path("docs/", include(docs_urlpatterns)),
    # === Root Redirects ===
    path("", RedirectView.as_view(url="/docs/swagger/", permanent=False)),
]

# === Development-only URLs ===
if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
    # Serve static and media files from development server
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
