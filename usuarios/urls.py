from django.urls import path
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from .views import (
    CustomLoginView,
    AdminDashboardView,
    CatalogadorDashboardView,
    RevisorDashboardView,
    # Gestión de usuarios (admin)
    ListaUsuariosView,
    CrearUsuarioView,
    EditarUsuarioView,
    EliminarUsuarioView,
    ToggleActivoUsuarioView,
    ResetPasswordUsuarioView,
    # Perfil propio
    PerfilView,
    CambiarPasswordView,
)

app_name = 'usuarios'

urlpatterns = [
    # ---- Autenticación ----
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # ---- Perfil propio (cualquier usuario autenticado) ----
    path('perfil/', PerfilView.as_view(), name='perfil'),
    path('perfil/cambiar-password/', CambiarPasswordView.as_view(), name='cambiar_password'),

    # ---- Dashboards ----
    path('admin/dashboard/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('catalogador/dashboard/', CatalogadorDashboardView.as_view(), name='catalogador_dashboard'),
    path('revisor/dashboard/', RevisorDashboardView.as_view(), name='revisor_dashboard'),

    # ---- Gestión de usuarios (solo admin) ----
    path('admin/usuarios/', ListaUsuariosView.as_view(), name='lista_usuarios'),
    path('admin/usuarios/crear/', CrearUsuarioView.as_view(), name='crear_usuario'),
    path('admin/usuarios/<int:pk>/editar/', EditarUsuarioView.as_view(), name='editar_usuario'),
    path('admin/usuarios/<int:pk>/eliminar/', EliminarUsuarioView.as_view(), name='eliminar_usuario'),
    path('admin/usuarios/<int:pk>/toggle-activo/', ToggleActivoUsuarioView.as_view(), name='toggle_activo_usuario'),
    path('admin/usuarios/<int:pk>/reset-password/', ResetPasswordUsuarioView.as_view(), name='reset_password_usuario'),

    # ---- Compatibilidad: rutas antiguas de catalogadores ----
    path('admin/catalogadores/', lambda req: redirect(reverse_lazy('usuarios:lista_usuarios')), name='lista_catalogadores'),
    path('admin/catalogadores/crear/', lambda req: redirect(reverse_lazy('usuarios:crear_usuario')), name='crear_catalogador'),
]
