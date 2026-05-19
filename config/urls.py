"""
URL configuration for the Verboheit Math League project.
"""

import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse
from django.urls import include, path
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.views import health_check

admin.site.site_header = "Verboheit MLC Developer Admin"
admin.site.index_title = "Verboheit MLC"
admin.site.site_title = "Dev Portal"


@api_view(["GET"])
@permission_classes([AllowAny])
def get_favicon(request):
    """Allow browsers retrieve favicon for tab icon"""
    favicon_path = os.path.join(settings.BASE_DIR, "docs/assets/favicon.ico")
    try:
        return FileResponse(open(favicon_path, "rb"), content_type="image/x-icon")
    except FileNotFoundError:
        return Response(status=status.HTTP_404_NOT_FOUND)


vmlc_urlpatterns = [
    path("v1/", include("vmlc.urls", namespace="vmlc")),
]

identity_urlpatterns = [path("v1/", include("identity.urls", namespace="identity"))]

comms_urlpatterns = [
    path("v1/", include("comms.urls", namespace="comms")),
]

competition_urlpatterns = [
    path("v1/competition/", include("competition.urls", namespace="competition")),
]

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("v1/health/", health_check, name="health-check"),
    path("", include(vmlc_urlpatterns)),
    path("", include(comms_urlpatterns)),
    path("", include(competition_urlpatterns)),
    path("", include(identity_urlpatterns)),
    path("favicon.ico", get_favicon, name="favicon"),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
