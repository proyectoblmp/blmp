from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm, PasswordChangeForm

from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    """Formulario para crear usuarios (usado en admin Django)"""

    class Meta:
        model = CustomUser
        fields = ("email", "nombre_completo", "tipo_catalogador", "activo")
        widgets = {
            "email": forms.EmailInput(
                attrs={"class": "admin-form-input", "placeholder": "correo@ejemplo.com"}
            ),
            "nombre_completo": forms.TextInput(
                attrs={
                    "class": "admin-form-input",
                    "placeholder": "Nombre completo del usuario",
                }
            ),
            "tipo_catalogador": forms.Select(attrs={"class": "admin-form-select"}),
            "activo": forms.CheckboxInput(attrs={"class": "admin-form-checkbox"}),
        }
        error_messages = {
            "email": {
                "required": "Este campo es obligatorio.",
                "invalid": "Ingrese un correo electrónico válido.",
                "unique": "Ya existe un usuario con este correo.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update(
            {"class": "admin-form-input", "placeholder": "Mínimo 8 caracteres"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": "admin-form-input", "placeholder": "Repite la contraseña"}
        )
        self.fields["password1"].error_messages = {"required": "Este campo es obligatorio."}
        self.fields["password2"].error_messages = {"required": "Este campo es obligatorio."}
        self.fields["tipo_catalogador"].empty_label = None
        if not self.instance.pk:
            self.fields["activo"].initial = True


class CustomUserChangeForm(UserChangeForm):
    """Formulario para editar usuarios (usado en Django Admin)"""

    class Meta:
        model = CustomUser
        fields = ("email", "nombre_completo", "tipo_catalogador", "rol", "activo", "debe_cambiar_password")


# ---------------------------------------------------------------------------
# Formularios de gestión de usuarios (panel admin de la app)
# ---------------------------------------------------------------------------

class AdminCrearUsuarioForm(UserCreationForm):
    """Crear cualquier tipo de usuario desde el panel de administración"""

    class Meta:
        model = CustomUser
        fields = (
            "email",
            "nombre_completo",
            "rol",
            "tipo_catalogador",
            "activo",
            "debe_cambiar_password",
        )
        widgets = {
            "email": forms.EmailInput(
                attrs={"class": "admin-form-input", "placeholder": "correo@ejemplo.com"}
            ),
            "nombre_completo": forms.TextInput(
                attrs={"class": "admin-form-input", "placeholder": "Nombre completo"}
            ),
            "rol": forms.Select(attrs={"class": "admin-form-select"}),
            "tipo_catalogador": forms.Select(attrs={"class": "admin-form-select"}),
            "activo": forms.CheckboxInput(attrs={"class": "admin-form-checkbox"}),
            "debe_cambiar_password": forms.CheckboxInput(attrs={"class": "admin-form-checkbox"}),
        }
        error_messages = {
            "email": {
                "required": "Este campo es obligatorio.",
                "invalid": "Ingrese un correo electrónico válido.",
                "unique": "Ya existe un usuario con este correo.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update(
            {"class": "admin-form-input", "placeholder": "Contraseña temporal (mínimo 8 caracteres)"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": "admin-form-input", "placeholder": "Repite la contraseña"}
        )
        self.fields["password1"].error_messages = {"required": "Este campo es obligatorio."}
        self.fields["password2"].error_messages = {"required": "Este campo es obligatorio."}
        self.fields["tipo_catalogador"].empty_label = "— No aplica —"
        self.fields["tipo_catalogador"].required = False
        if not self.instance.pk:
            self.fields["activo"].initial = True
            self.fields["debe_cambiar_password"].initial = True

    def clean(self):
        cleaned_data = super().clean()
        rol = cleaned_data.get("rol")
        tipo_catalogador = cleaned_data.get("tipo_catalogador")
        # tipo_catalogador solo es obligatorio para catalogadores
        if rol == CustomUser.ROL_CATALOGADOR and not tipo_catalogador:
            cleaned_data["tipo_catalogador"] = CustomUser.TIPO_OTROS
        return cleaned_data


class AdminEditarUsuarioForm(forms.ModelForm):
    """Editar cualquier usuario desde el panel de administración (sin contraseña)"""

    class Meta:
        model = CustomUser
        fields = (
            "email",
            "nombre_completo",
            "rol",
            "tipo_catalogador",
            "activo",
            "debe_cambiar_password",
        )
        widgets = {
            "email": forms.EmailInput(
                attrs={"class": "admin-form-input", "placeholder": "correo@ejemplo.com"}
            ),
            "nombre_completo": forms.TextInput(
                attrs={"class": "admin-form-input", "placeholder": "Nombre completo"}
            ),
            "rol": forms.Select(attrs={"class": "admin-form-select"}),
            "tipo_catalogador": forms.Select(attrs={"class": "admin-form-select"}),
            "activo": forms.CheckboxInput(attrs={"class": "admin-form-checkbox"}),
            "debe_cambiar_password": forms.CheckboxInput(attrs={"class": "admin-form-checkbox"}),
        }
        error_messages = {
            "email": {
                "required": "Este campo es obligatorio.",
                "invalid": "Ingrese un correo electrónico válido.",
                "unique": "Ya existe un usuario con este correo.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo_catalogador"].empty_label = "— No aplica —"
        self.fields["tipo_catalogador"].required = False


class AdminResetPasswordForm(forms.Form):
    """Formulario para que el admin resetee la contraseña de otro usuario"""

    nueva_password = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(
            attrs={"class": "admin-form-input", "placeholder": "Nueva contraseña (mínimo 8 caracteres)"}
        ),
        min_length=8,
        error_messages={"required": "Este campo es obligatorio."},
    )
    confirmar_password = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(
            attrs={"class": "admin-form-input", "placeholder": "Repite la nueva contraseña"}
        ),
        error_messages={"required": "Este campo es obligatorio."},
    )
    forzar_cambio = forms.BooleanField(
        label="Forzar cambio de contraseña en el próximo inicio de sesión",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "admin-form-checkbox"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("nueva_password")
        p2 = cleaned_data.get("confirmar_password")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned_data


# ---------------------------------------------------------------------------
# Formularios de perfil propio
# ---------------------------------------------------------------------------

class PerfilUsuarioForm(forms.ModelForm):
    """El usuario edita su propio perfil (solo nombre)"""

    class Meta:
        model = CustomUser
        fields = ("nombre_completo",)
        widgets = {
            "nombre_completo": forms.TextInput(
                attrs={"class": "admin-form-input", "placeholder": "Tu nombre completo"}
            ),
        }


class CambiarPasswordPropioForm(PasswordChangeForm):
    """Cambio de contraseña self-service (requiere contraseña actual)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].widget.attrs.update(
            {"class": "admin-form-input", "placeholder": "Tu contraseña actual"}
        )
        self.fields["old_password"].label = "Contraseña actual"
        self.fields["new_password1"].widget.attrs.update(
            {"class": "admin-form-input", "placeholder": "Nueva contraseña (mínimo 8 caracteres)"}
        )
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].widget.attrs.update(
            {"class": "admin-form-input", "placeholder": "Repite la nueva contraseña"}
        )
        self.fields["new_password2"].label = "Confirmar nueva contraseña"


# ---------------------------------------------------------------------------
# Formulario de login (referencia)
# ---------------------------------------------------------------------------

class LoginForm(forms.Form):
    """Formulario de login personalizado"""

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Correo electrónico",
                "autofocus": True,
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Contraseña"}
        )
    )
