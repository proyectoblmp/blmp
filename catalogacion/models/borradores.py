"""
Modelo para gestión de borradores de obras MARC21
Permite guardar el progreso de catalogación y recuperarlo posteriormente
"""

import json
import re

from django.db import models
from django.utils import timezone


class BorradorObra(models.Model):
    """
    Modelo para guardar borradores de obras MARC21 en progreso.
    Asociado al usuario catalogador que lo creó.
    """

    usuario = models.ForeignKey(
        "usuarios.CustomUser",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="borradores",
        help_text="Usuario que creó este borrador",
    )

    tipo_obra = models.CharField(
        max_length=50,
        help_text="Tipo de obra MARC21: manuscrito, impreso, coleccion, etc.",
    )

    obra_objetivo = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="borradores_edicion",
        help_text=(
            "Si se está editando una obra existente, referencia la obra objetivo. "
            "Si es un borrador de creación, queda vacío."
        ),
    )

    datos_formulario = models.JSONField(
        help_text="Datos del formulario serializados en JSON"
    )

    pestana_actual = models.IntegerField(
        default=0, help_text="Índice de la pestaña actual (0-8)"
    )

    titulo_temporal = models.CharField(
        max_length=500,
        blank=True,
        help_text="Título extraído del campo 245$a para mostrar en la lista",
    )

    num_control_temporal = models.CharField(
        max_length=50, blank=True, help_text="Número de control temporal si existe"
    )

    tipo_registro = models.CharField(
        max_length=1, blank=True, help_text="c=impreso, d=manuscrito"
    )

    nivel_bibliografico = models.CharField(
        max_length=1, blank=True, help_text="a=parte, c=colección, m=monografía"
    )

    estado = models.CharField(
        max_length=20,
        choices=[
            ("activo", "Activo"),
            ("convertido", "Convertido a Obra"),
            ("descartado", "Descartado"),
        ],
        default="activo",
        help_text="Estado del borrador: activo (en progreso), convertido (publicado como obra), descartado (eliminado por usuario)",
    )

    obra_creada = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="borrador_origen",
        help_text="Obra final creada a partir de este borrador",
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalogacion_borrador_obra"
        verbose_name = "Borrador de Obra MARC21"
        verbose_name_plural = "Borradores de Obras MARC21"
        ordering = ["-fecha_modificacion"]
        indexes = [
            models.Index(fields=["-fecha_modificacion"]),
            models.Index(fields=["tipo_obra"]),
            models.Index(fields=["tipo_registro"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["obra_objetivo"]),
        ]

    def __str__(self):
        titulo = self.titulo_temporal or "Sin título"
        fecha = self.fecha_modificacion.strftime("%d/%m/%Y %H:%M")
        return f"{titulo} ({fecha})"

    def extraer_metadatos(self):
        """Extrae título, tipo de registro y nivel bibliográfico del formulario"""
        try:
            datos = self.datos_formulario
            if isinstance(datos, str):
                datos = json.loads(datos)

            # Soportar múltiples formatos:
            # v1: { _campos_simples: {...}, _formsets: {...}, _subcampos_dinamicos: {...} }
            # v2: { version: 2, campos: {...}, formsets: {...}, meta: {...} }
            if isinstance(datos, dict):
                if "_campos_simples" in datos:
                    # Formato v1
                    campos = datos.get("_campos_simples", {})
                elif "version" in datos and datos.get("version") == 2:
                    # Formato v2
                    campos = datos.get("campos", {})
                else:
                    # Formato legacy o directo
                    campos = datos
            else:
                campos = {}

            # Extraer título del campo 245$a (titulo_principal)
            titulo = campos.get("titulo_principal", "")
            if isinstance(titulo, list):
                titulo = titulo[0] if titulo else ""
            self.titulo_temporal = (titulo or "Sin título")[:500]

            # Extraer tipo de registro y nivel bibliográfico del formulario
            # Si no existen, usar la configuración del tipo_obra
            from catalogacion.views.obra_config import TIPO_OBRA_CONFIG
            
            config = TIPO_OBRA_CONFIG.get(self.tipo_obra, {})
            self.tipo_registro = campos.get("tipo_registro") or config.get("tipo_registro", "")
            self.nivel_bibliografico = campos.get("nivel_bibliografico") or config.get("nivel_bibliografico", "")

            # Extraer número de control si existe
            self.num_control_temporal = (
                campos.get("num_control") or campos.get("numero_control") or ""
            )

        except Exception as e:
            self.titulo_temporal = "Sin título"
            print(f"Error extrayendo metadatos: {e}")

    def save(self, *args, **kwargs):
        """Override save para extraer metadatos automáticamente"""
        self.extraer_metadatos()
        super().save(*args, **kwargs)

    @property
    def dias_desde_modificacion(self):
        """Retorna días desde última modificación"""
        diferencia = timezone.now() - self.fecha_modificacion
        return diferencia.days

    def get_descripcion_tipo(self):
        """Retorna descripción legible del tipo de obra"""
        tipos = {
            "manuscrito_independiente": "Manuscrito Independiente",
            "manuscrito_coleccion": "Manuscrito Colección",
            "impreso_independiente": "Impreso Independiente",
            "impreso_coleccion": "Impreso Colección",
        }
        return tipos.get(self.tipo_obra, self.tipo_obra)

    @property
    def titulo_identificable(self):
        """Mejor tÃ­tulo disponible para reconocer el borrador en listados."""
        if self.titulo_temporal and self.titulo_temporal.strip():
            return self.titulo_temporal.strip()
        if self.obra_objetivo and self.obra_objetivo.titulo_principal:
            return self.obra_objetivo.titulo_principal.strip()
        return "Sin tÃ­tulo"

    @property
    def numero_identificable(self):
        """Mejor nÃºmero de control disponible para reconocer el borrador."""
        if self.num_control_temporal and self.num_control_temporal.strip():
            return self.num_control_temporal.strip()
        if self.obra_objetivo and self.obra_objetivo.num_control:
            return self.obra_objetivo.num_control.strip()
        return ""

    @property
    def usuario_identificable(self):
        """Texto breve para identificar al dueÃ±o del borrador."""
        if not self.usuario:
            return "Sin usuario"
        if self.usuario.nombre_completo and self.usuario.nombre_completo.strip():
            return self.usuario.nombre_completo.strip()
        return self.usuario.email

    @property
    def clave_similitud(self):
        """
        Clave para agrupar borradores aparentemente del mismo trabajo.
        Sirve para marcar duplicados similares en la lista.
        """
        if self.obra_objetivo_id:
            return f"edicion:{self.usuario_id}:{self.obra_objetivo_id}"

        numero = (self.numero_identificable or "").strip().lower()
        titulo = re.sub(r"\s+", " ", self.titulo_identificable.strip().lower())
        return f"creacion:{self.usuario_id}:{self.tipo_obra}:{numero}:{titulo}"
