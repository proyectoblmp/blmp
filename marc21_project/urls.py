"""
URLs principales del proyecto Django
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin de Django
    path("admin/", admin.site.urls),
    # Interfaz Pública (home principal)
    path("", include("catalogo_publico.urls")),
    # Aplicación de catalogación (para catalogadores autenticados)
    path("catalogacion/", include("catalogacion.urls")),
    # Autoridades y APIs de autocomplete
    path(
        "catalogacion/",
        include(
            ("catalogacion.urls_autoridades", "autoridades"), namespace="autoridades"
        ),
    ),
    # Sistema de usuarios (login, gestión de catalogadores, dashboards)
    path("usuarios/", include("usuarios.urls")),
    # Aplicación de digitalización
    path("digitalizacion/", include("digitalizacion.urls")),
]

# Servir archivos estáticos y media
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Producción: Django sirve media directamente (app interna, sin alto tráfico)
    from django.views.static import serve
    from django.urls import re_path
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
