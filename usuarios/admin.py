from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm


class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    ordering = ['email']
    list_display = ['email', 'nombre_completo', 'rol', 'tipo_catalogador', 'activo', 'debe_cambiar_password', 'is_staff', 'fecha_creacion']
    list_filter = ['rol', 'activo', 'debe_cambiar_password', 'is_staff', 'is_superuser']
    search_fields = ['email', 'nombre_completo']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Información Personal', {'fields': ('nombre_completo',)}),
        ('Rol y Estado', {'fields': ('rol', 'tipo_catalogador', 'activo', 'debe_cambiar_password')}),
        ('Permisos Django', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre_completo', 'rol', 'tipo_catalogador', 'debe_cambiar_password', 'password1', 'password2'),
        }),
    )


admin.site.register(CustomUser, CustomUserAdmin)
