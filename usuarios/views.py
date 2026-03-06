from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, FormView
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash

from .models import CustomUser
from .forms import (
    AdminCrearUsuarioForm,
    AdminEditarUsuarioForm,
    AdminResetPasswordForm,
    PerfilUsuarioForm,
    CambiarPasswordPropioForm,
)


# ============================================================================
# MIXINS DE PERMISOS (inline, también están en mixins.py para otras apps)
# ============================================================================

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin que verifica que el usuario sea administrador"""

    def test_func(self):
        return self.request.user.es_admin

    def handle_no_permission(self):
        messages.error(self.request, 'No tienes permisos para acceder a esta sección.')
        return redirect('usuarios:login')


class CatalogadorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin que verifica que el usuario pueda catalogar"""

    def test_func(self):
        return self.request.user.puede_catalogar

    def handle_no_permission(self):
        messages.error(self.request, 'No tienes permisos para acceder a esta sección.')
        return redirect('usuarios:login')


class RevisorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin que verifica que el usuario pueda revisar"""

    def test_func(self):
        return self.request.user.puede_revisar

    def handle_no_permission(self):
        messages.error(self.request, 'No tienes permisos para acceder a esta sección.')
        return redirect('usuarios:login')


# ============================================================================
# AUTENTICACIÓN
# ============================================================================

class CustomLoginView(LoginView):
    """Vista personalizada de login"""
    template_name = 'registration/inicio_sesion.html'
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Iniciar Sesión'
        return context

    def form_valid(self, form):
        """Verificar si el usuario está activo antes de permitir login"""
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')

        try:
            user = CustomUser.objects.get(email=username)
            if user.check_password(password):
                if not user.activo:
                    return self.render_to_response(
                        self.get_context_data(
                            form=form,
                            cuenta_desactivada=True,
                            usuario_nombre=user.nombre_completo or user.email
                        )
                    )
        except CustomUser.DoesNotExist:
            pass

        return super().form_valid(form)

    def get_success_url(self):
        """Redirige según el rol del usuario; fuerza cambio de contraseña si es necesario"""
        user = self.request.user
        if user.debe_cambiar_password:
            messages.warning(
                self.request,
                'Tu contraseña debe ser cambiada antes de continuar.'
            )
            return reverse_lazy('usuarios:cambiar_password')
        if user.es_admin:
            return reverse_lazy('usuarios:admin_dashboard')
        if user.es_revisor:
            return reverse_lazy('usuarios:revisor_dashboard')
        return reverse_lazy('usuarios:catalogador_dashboard')


# ============================================================================
# DASHBOARDS
# ============================================================================

class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """Dashboard principal para administradores"""
    template_name = 'usuarios/admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Panel de Administración'
        context['total_catalogadores'] = CustomUser.objects.filter(rol=CustomUser.ROL_CATALOGADOR).count()
        context['catalogadores_activos'] = CustomUser.objects.filter(rol=CustomUser.ROL_CATALOGADOR, activo=True).count()
        context['total_revisores'] = CustomUser.objects.filter(rol=CustomUser.ROL_REVISOR).count()
        context['revisores_activos'] = CustomUser.objects.filter(rol=CustomUser.ROL_REVISOR, activo=True).count()
        context['total_usuarios'] = CustomUser.objects.exclude(rol=CustomUser.ROL_ADMIN).count()
        return context


class CatalogadorDashboardView(CatalogadorRequiredMixin, TemplateView):
    """Dashboard principal para catalogadores"""
    template_name = 'usuarios/catalogador/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Panel del Catalogador'
        return context


class RevisorDashboardView(RevisorRequiredMixin, TemplateView):
    """Dashboard principal para revisores"""
    template_name = 'usuarios/revisor/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Panel del Revisor'
        return context


# ============================================================================
# GESTIÓN DE USUARIOS (SOLO ADMIN) — rutas /admin/usuarios/
# ============================================================================

class ListaUsuariosView(AdminRequiredMixin, ListView):
    """Lista de todos los usuarios con filtro por rol"""
    model = CustomUser
    template_name = 'usuarios/admin/lista_usuarios.html'
    context_object_name = 'usuarios'
    paginate_by = 20

    def get_queryset(self):
        rol_filtro = self.request.GET.get('rol', '')
        qs = CustomUser.objects.all()
        if rol_filtro in [CustomUser.ROL_CATALOGADOR, CustomUser.ROL_REVISOR, CustomUser.ROL_ADMIN]:
            qs = qs.filter(rol=rol_filtro)
        return qs.order_by('-fecha_creacion')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Gestión de Usuarios'
        context['rol_filtro'] = self.request.GET.get('rol', '')
        context['ROL_CATALOGADOR'] = CustomUser.ROL_CATALOGADOR
        context['ROL_REVISOR'] = CustomUser.ROL_REVISOR
        context['ROL_ADMIN'] = CustomUser.ROL_ADMIN
        context['total_catalogadores'] = CustomUser.objects.filter(rol=CustomUser.ROL_CATALOGADOR).count()
        context['total_revisores'] = CustomUser.objects.filter(rol=CustomUser.ROL_REVISOR).count()
        context['total_admins'] = CustomUser.objects.filter(rol=CustomUser.ROL_ADMIN).count()
        return context


class CrearUsuarioView(AdminRequiredMixin, CreateView):
    """Crear nuevo usuario de cualquier rol"""
    model = CustomUser
    form_class = AdminCrearUsuarioForm
    template_name = 'usuarios/admin/form_usuario.html'
    success_url = reverse_lazy('usuarios:lista_usuarios')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Usuario'
        context['accion'] = 'Crear'
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Usuario "{form.instance.nombre_completo or form.instance.email}" creado exitosamente.')
        return super().form_valid(form)


class EditarUsuarioView(AdminRequiredMixin, UpdateView):
    """Editar usuario existente"""
    model = CustomUser
    form_class = AdminEditarUsuarioForm
    template_name = 'usuarios/admin/form_usuario.html'
    success_url = reverse_lazy('usuarios:lista_usuarios')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar Usuario: {self.object.nombre_completo or self.object.email}'
        context['accion'] = 'Guardar cambios'
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Usuario "{self.object.nombre_completo or self.object.email}" actualizado exitosamente.')
        return super().form_valid(form)


class EliminarUsuarioView(AdminRequiredMixin, DeleteView):
    """Eliminar usuario"""
    model = CustomUser
    template_name = 'usuarios/admin/confirmar_eliminar_usuario.html'
    success_url = reverse_lazy('usuarios:lista_usuarios')

    def form_valid(self, form):
        nombre = self.object.nombre_completo or self.object.email
        messages.success(self.request, f'Usuario "{nombre}" eliminado exitosamente.')
        return super().form_valid(form)


class ToggleActivoUsuarioView(AdminRequiredMixin, UpdateView):
    """Activar/desactivar cualquier usuario"""
    model = CustomUser
    fields = []
    success_url = reverse_lazy('usuarios:lista_usuarios')

    def form_valid(self, form):
        self.object.activo = not self.object.activo
        self.object.save()
        estado = 'activado' if self.object.activo else 'desactivado'
        nombre = self.object.nombre_completo or self.object.email
        messages.success(self.request, f'Usuario "{nombre}" {estado} exitosamente.')
        return redirect(self.success_url)


class ResetPasswordUsuarioView(AdminRequiredMixin, FormView):
    """El admin resetea la contraseña de otro usuario"""
    template_name = 'usuarios/admin/reset_password.html'
    form_class = AdminResetPasswordForm

    def get_usuario(self):
        return get_object_or_404(CustomUser, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.get_usuario()
        context['titulo'] = f'Resetear contraseña: {usuario.nombre_completo or usuario.email}'
        context['usuario_destino'] = usuario
        return context

    def form_valid(self, form):
        usuario = self.get_usuario()
        nueva_password = form.cleaned_data['nueva_password']
        forzar_cambio = form.cleaned_data.get('forzar_cambio', True)
        usuario.set_password(nueva_password)
        usuario.debe_cambiar_password = forzar_cambio
        usuario.save()
        nombre = usuario.nombre_completo or usuario.email
        messages.success(self.request, f'Contraseña de "{nombre}" actualizada exitosamente.')
        return redirect(reverse_lazy('usuarios:lista_usuarios'))


# ============================================================================
# PERFIL PROPIO Y CAMBIO DE CONTRASEÑA (cualquier usuario autenticado)
# ============================================================================

def _base_template_para_rol(user):
    """Retorna el template base según el rol del usuario"""
    if user.es_admin:
        return 'usuarios/admin/base_admin.html'
    if user.es_revisor:
        return 'usuarios/revisor/base_revisor.html'
    return 'usuarios/catalogador/base_catalogador.html'


class PerfilView(LoginRequiredMixin, UpdateView):
    """El usuario ve y edita su propio perfil"""
    model = CustomUser
    form_class = PerfilUsuarioForm
    template_name = 'usuarios/perfil/perfil.html'
    success_url = reverse_lazy('usuarios:perfil')

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Mi Perfil'
        context['base_template'] = _base_template_para_rol(self.request.user)
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Perfil actualizado exitosamente.')
        return super().form_valid(form)


class CambiarPasswordView(LoginRequiredMixin, PasswordChangeView):
    """El usuario cambia su propia contraseña"""
    form_class = CambiarPasswordPropioForm
    template_name = 'usuarios/perfil/cambiar_password.html'
    success_url = reverse_lazy('usuarios:perfil')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Cambiar Contraseña'
        context['forzado'] = self.request.user.debe_cambiar_password
        context['base_template'] = _base_template_para_rol(self.request.user)
        return context

    def form_valid(self, form):
        # Desmarcar el flag de cambio forzado
        user = form.save()
        user.debe_cambiar_password = False
        user.save(update_fields=['debe_cambiar_password'])
        # Mantener la sesión activa tras el cambio
        update_session_auth_hash(self.request, user)
        messages.success(self.request, 'Contraseña actualizada exitosamente.')
        return redirect(self.get_success_url())


# ============================================================================
# COMPATIBILIDAD: rutas antiguas /admin/catalogadores/ → redirigen a /admin/usuarios/
# ============================================================================

class _RedirectToListaUsuarios(AdminRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        return redirect(reverse_lazy('usuarios:lista_usuarios'))


# Aliases para las vistas antiguas que aún puedan estar enlazadas en templates
ListaCatalogadoresView = ListaUsuariosView
CrearCatalogadorView = CrearUsuarioView
EditarCatalogadorView = EditarUsuarioView
EliminarCatalogadorView = EliminarUsuarioView
ToggleActivoCatalogadorView = ToggleActivoUsuarioView
