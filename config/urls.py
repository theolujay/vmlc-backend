"""
URL configuration for the Verboheit Math League project.

Includes:
- Admin interface
- API routes with versioning
- Interactive API docs via Swagger and ReDoc (powered by drf-yasg)
- Debug toolbar URLs
"""

import os

from django.contrib import admin
from django.http import FileResponse
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.views.static import serve

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes

from drf_yasg.views import get_schema_view
from drf_yasg import openapi


@api_view(["GET"])
@permission_classes([AllowAny])
def get_favicon(request):
    """Allow browsers retrieve favicon for tab icon"""
    favicon_path = os.path.join(settings.BASE_DIR, "favicon.ico")
    try:
        return FileResponse(open(favicon_path, "rb"), content_type="image/x-icon")
    except FileNotFoundError:
        return Response(status=status.HTTP_404_NOT_FOUND)

schema_view = get_schema_view(
    openapi.Info(
        title="Verboheit MLC API",
        default_version="v1",
        description="Interactive API doc for the Verboheit MLC Portal.",
        contact=openapi.Contact(
            name="API Support",
            email=settings.CONTACT_EMAIL,
            url=settings.CONTACT_URL,
        ),
    ),
    public=True,
    permission_classes=[AllowAny],
    authentication_classes=[],
    url=settings.BASE_URL if not settings.DEBUG else None,
)

vmlc_urlpatterns = [
    path("v1/", include("vmlc.urls", namespace="vmlc")),
]

comms_urlpatterns = [
    path("v1/", include("comms.urls", namespace="comms")),
]

docs_urlpatterns = [
    path(
        "schema.json",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    path(
        "schema.yaml",
        schema_view.without_ui(cache_timeout=0),
        name="schema-yaml",
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
    path(
        "spec/",
        serve,
        {"document_root": settings.BASE_DIR / "docs/views", "path": "index.html"},
    ),
    re_path(
        r"^spec/(?P<path>.*)$",
        serve,
        {"document_root": settings.BASE_DIR / "docs/views"},
    ),
]

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    # === VMLC ===
    path("", include(vmlc_urlpatterns)),
    path("", include(comms_urlpatterns)),
    # === Docs ===
    path("docs/", include(docs_urlpatterns)),
    path("favicon.ico", get_favicon, name="favicon"),
    path("", RedirectView.as_view(url="/docs/swagger/", permanent=False)),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
