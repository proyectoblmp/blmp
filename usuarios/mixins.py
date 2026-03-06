"""
Mixins de permisos para proteger las vistas.
Uso en vistas de catalogación y otras apps.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages


class CatalogadorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin que verifica que el usuario esté autenticado y pueda catalogar.
    Puede ser admin o catalogador.
    """
    
    def test_func(self):
        return self.request.user.puede_catalogar
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('usuarios:login')
        messages.error(self.request, 'No tienes permisos para acceder a esta sección.')
        return redirect('catalogo_publico:home')


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin que verifica que el usuario sea administrador.
    """

    def test_func(self):
        return self.request.user.es_admin

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('usuarios:login')
        messages.error(self.request, 'No tienes permisos para acceder a esta sección.')
        return redirect('catalogo_publico:home')


class RevisorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin que verifica que el usuario pueda revisar (revisor o admin).
    """

    def test_func(self):
        return self.request.user.puede_revisar

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('usuarios:login')
        messages.error(self.request, 'No tienes permisos para acceder a esta sección.')
        return redirect('catalogo_publico:home')
