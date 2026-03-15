"""
URLs principales de catalogación
"""

from django.urls import include, path

from catalogacion.views import (
    CrearObraView,
    DetalleObraView,
    DespublicarObraView,
    EditarObraView,
    EliminarObraView,  # COMENTADO: Funcionalidad de borrado desactivada temporalmente
    IndexView,
    ListaObrasView,
    PapeleraObrasView,
    PublicarObraView,
    PurgarObraView,
    PurgarTodoView,
    RestaurarObraView,
    SeleccionarTipoObraView,
)
from catalogacion.views import borradores as borradores_views
from catalogacion.views.api_views import (
    Autocompletado773View,
    buscar_obras,
    obtener_bio_compositor,
    obtener_obras_774,
)

app_name = "catalogacion"

urlpatterns = [
    # Redirección inteligente según rol
    path("", IndexView.as_view(), name="index"),
    # Obras (protegidas - requieren ser catalogador)
    path(
        "obras/",
        include(
            [
                path("", ListaObrasView.as_view(), name="lista_obras"),
                path(
                    "seleccionar-tipo/",
                    SeleccionarTipoObraView.as_view(),
                    name="seleccionar_tipo",
                ),
                path("crear/<str:tipo>/", CrearObraView.as_view(), name="crear_obra"),
                path("<int:pk>/", DetalleObraView.as_view(), name="detalle_obra"),
                path("<int:pk>/editar/", EditarObraView.as_view(), name="editar_obra"),
                path(
                    "<int:pk>/eliminar/",
                    EliminarObraView.as_view(),
                    name="eliminar_obra",
                ),
                path(
                    "<int:pk>/publicar/",
                    PublicarObraView.as_view(),
                    name="publicar_obra",
                ),
                path(
                    "<int:pk>/despublicar/",
                    DespublicarObraView.as_view(),
                    name="despublicar_obra",
                ),
            ]
        ),
    ),
    # Papelera de obras eliminadas
    path(
        "papelera/",
        PapeleraObrasView.as_view(),
        name="papelera_obras",
    ),
    path(
        "papelera/<int:pk>/restaurar/",
        RestaurarObraView.as_view(),
        name="restaurar_obra",
    ),
    path(
        "papelera/<int:pk>/purgar/",
        PurgarObraView.as_view(),
        name="purgar_obra",
    ),
    path(
        "papelera/purgar-todo/",
        PurgarTodoView.as_view(),
        name="purgar_todo",
    ),
    # Interfaz de borradores
    path(
        "borradores/",
        borradores_views.ListaBorradoresView.as_view(),
        name="lista_borradores",
    ),
    path(
        "borradores/<int:pk>/recuperar/",
        borradores_views.recuperar_borrador_view,
        name="recuperar_borrador",
    ),
    path(
        "borradores/<int:pk>/descartar/",
        borradores_views.DescartarBorradorView.as_view(),
        name="descartar_borrador",
    ),
    # API de borradores (usado por borrador-system.js)
    path(
        "api/borradores/guardar/",
        borradores_views.guardar_borrador_ajax,
        name="api_guardar_borrador",
    ),
    path(
        "borradores/<int:pk>/editar/",
        borradores_views.recuperar_borrador_view,
        name="editar_borrador",
    ),
    path(
        "borradores/<int:pk>/preview/",
        borradores_views.VistaPreviaBorradorView.as_view(),
        name="preview_borrador",
    ),
    path(
        "api/borradores/autoguardar/",
        borradores_views.autoguardar_borrador_ajax,
        name="api_autoguardar_borrador",
    ),
    path(
        "api/borradores/<int:borrador_id>/",
        borradores_views.obtener_borrador_ajax,
        name="api_obtener_borrador",
    ),
    path(
        "api/borradores/obra/<int:obra_id>/ultimo/",
        borradores_views.obtener_ultimo_borrador_obra_ajax,
        name="api_ultimo_borrador_obra",
    ),
    path(
        "api/borradores/<int:borrador_id>/eliminar/",
        borradores_views.eliminar_borrador_ajax,
        name="api_eliminar_borrador",
    ),
    path(
        "api/borradores/verificar/",
        borradores_views.verificar_borrador_ajax,
        name="api_verificar_borrador",
    ),
    path(
        "api/borradores/listar/",
        borradores_views.listar_borradores_ajax,
        name="api_listar_borradores",
    ),
    path(
        "api/borradores/limpiar-sesion/",
        borradores_views.limpiar_sesion_borrador_ajax,
        name="api_limpiar_sesion_borrador",
    ),
    path(
        "api/borradores/activo/",
        borradores_views.obtener_borrador_activo_ajax,
        name="api_borrador_activo",
    ),
    path(
        "api/borradores/limpiar-tipo/",
        borradores_views.limpiar_borrador_tipo_ajax,
        name="api_limpiar_borrador_tipo",
    ),
    # API de autocompletado 773
    path(
        "api/obras/buscar/",
        buscar_obras,
        name="api_buscar_obras",
    ),
    path(
        "api/obras/autocomplete/773/",
        Autocompletado773View.as_view(),
        name="api_autocompletado_773",
    ),
    path(
        "api/obras/774-entries/",
        obtener_obras_774,
        name="api_obtener_obras_774",
    ),
    path(
        "api/compositor/bio-545/",
        obtener_bio_compositor,
        name="api_compositor_bio_545",
    ),
]
