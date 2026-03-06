from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class CustomUserManager(BaseUserManager):
    """Manager personalizado porque el de defecto espera un username"""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("rol", CustomUser.ROL_ADMIN)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    """Modelo de usuario personalizado con roles"""

    # Tipos de roles
    ROL_CATALOGADOR = "catalogador"
    ROL_REVISOR = "revisor"
    ROL_ADMIN = "admin"

    ROL_CHOICES = [
        (ROL_CATALOGADOR, "Catalogador"),
        (ROL_REVISOR, "Revisor"),
        (ROL_ADMIN, "Administrador"),
    ]

    # Tipos de catalogador
    TIPO_INVESTIGADOR_UNL = "investigador_unl"
    TIPO_INVESTIGADOR_EXTERNO = "investigador_externo"
    TIPO_COLABORADOR = "colaborador"
    TIPO_PASANTE = "pasante"
    TIPO_OTROS = "otros"

    TIPO_CATALOGADOR_CHOICES = [
        (TIPO_INVESTIGADOR_UNL, "Investigador UNL"),
        (TIPO_INVESTIGADOR_EXTERNO, "Investigador Externo"),
        (TIPO_COLABORADOR, "Colaborador"),
        (TIPO_PASANTE, "Pasante"),
        (TIPO_OTROS, "Otros"),
    ]

    username = None  # Eliminamos el campo username
    email = models.EmailField("email address", unique=True)

    # Nuevo campo para el rol
    rol = models.CharField(
        "Rol",
        max_length=20,
        choices=ROL_CHOICES,
        default=ROL_CATALOGADOR,
        help_text="Define los permisos del usuario en el sistema",
    )

    # Tipo de catalogador
    tipo_catalogador = models.CharField(
        "Tipo de Catalogador",
        max_length=30,
        choices=TIPO_CATALOGADOR_CHOICES,
        default=TIPO_OTROS,
        help_text="Clasificación del catalogador según su rol en la institución",
    )

    # Campos adicionales útiles
    nombre_completo = models.CharField(
        "Nombre completo",
        max_length=200,
        blank=True,
        help_text="Nombre completo del usuario",
    )
    activo = models.BooleanField(
        "Activo",
        default=True,
        help_text="Indica si el usuario puede acceder al sistema",
    )
    debe_cambiar_password = models.BooleanField(
        "Debe cambiar contraseña",
        default=False,
        help_text="Si está marcado, el usuario deberá cambiar su contraseña al iniciar sesión",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return self.nombre_completo or self.email

    @property
    def es_admin(self):
        """Verifica si el usuario es administrador"""
        return self.rol == self.ROL_ADMIN or self.is_superuser

    @property
    def es_catalogador(self):
        """Verifica si el usuario es catalogador"""
        return self.rol == self.ROL_CATALOGADOR

    @property
    def es_revisor(self):
        """Verifica si el usuario es revisor"""
        return self.rol == self.ROL_REVISOR

    @property
    def puede_catalogar(self):
        """Verifica si el usuario puede catalogar (solo admin o catalogador, NO revisor)"""
        return self.es_admin or self.es_catalogador

    @property
    def puede_revisar(self):
        """Verifica si el usuario puede revisar registros (admin o revisor)"""
        return self.es_admin or self.es_revisor
