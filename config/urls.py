"""
URL configuration for the Verboheit Math League project.

Includes:
- Admin interface
- API routes with versioning
- Interactive API docs via Swagger and ReDoc (powered by drf-yasg)
- Debug toolbar URLs
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from rest_framework.permissions import AllowAny
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Verboheit MLC API",
        default_version="v1",
        description="Interactive API doc for the Verboheit MLC Portal.",
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
]

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    # === VMLC ===
    path("", include(vmlc_urlpatterns)),
    path("", include(comms_urlpatterns)),
    # === Docs ===
    path("docs/", include(docs_urlpatterns)),
    path("v1/docs/spec/", RedirectView.as_view(url="https://vmlc-api.readthedocs.io/latest", permanent=False), name="api-spec-redirect"),
    path("", RedirectView.as_view(url="/docs/swagger/", permanent=False)),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
