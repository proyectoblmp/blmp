"""
Modelos de Autoridades para catalogación MARC21
Centraliza nombres, títulos y términos controlados
"""
from django.db import models


class AutoridadPersona(models.Model):
    """
    Autoridad para nombres de personas.
    Usado en: 100, 600, 700, 773, 774, 787
    """
    apellidos_nombres = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        help_text="Formato: Apellidos, Nombres (normalizado)"
    )
    coordenadas_biograficas = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Coordenadas biográficas: año nacimiento - año muerte"
    )
    nota_biografica = models.TextField(
        blank=True,
        default='',
        help_text="Nota biográfica del compositor (MARC 545 $a)"
    )
    uri_nota_biografica = models.URLField(
        blank=True,
        default='',
        help_text="URL de referencia biográfica (MARC 545 $u)"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Autoridad - Persona"
        verbose_name_plural = "Autoridades - Personas"
        ordering = ['apellidos_nombres']
        indexes = [
            models.Index(fields=['apellidos_nombres']),
        ]

    def __str__(self):
        if self.coordenadas_biograficas:
            return f"{self.apellidos_nombres} ({self.coordenadas_biograficas})"
        return self.apellidos_nombres


class AutoridadTituloUniforme(models.Model):
    """
    Autoridad para títulos uniformes.
    Usado en: 130, 240
    """
    titulo = models.CharField(
        max_length=300,
        unique=True,
        db_index=True,
        help_text="Título uniforme normalizado"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Autoridad - Título Uniforme"
        verbose_name_plural = "Autoridades - Títulos Uniformes"
        ordering = ['titulo']
        indexes = [
            models.Index(fields=['titulo']),
        ]

    def __str__(self):
        return self.titulo


class AutoridadFormaMusical(models.Model):
    """
    Autoridad para formas musicales.
    Usado en: 130 $k, 240 $k, 655
    """
    forma = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Forma o género musical (ej: Pasillo, Sinfonía, Vals)"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Autoridad - Forma Musical"
        verbose_name_plural = "Autoridades - Formas Musicales"
        ordering = ['forma']
        indexes = [
            models.Index(fields=['forma']),
        ]

    def __str__(self):
        return self.forma


class AutoridadMateria(models.Model):
    """
    Autoridad para términos de materia.
    Usado en: 650
    """
    termino = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        help_text="Término de materia normalizado"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Autoridad - Materia"
        verbose_name_plural = "Autoridades - Materias"
        ordering = ['termino']
        indexes = [
            models.Index(fields=['termino']),
        ]

    def __str__(self):
        return self.termino


class AutoridadEntidad(models.Model):
    """
    Autoridad para entidades o instituciones.
    Usado en: 710, 852
    """
    nombre = models.CharField(
        max_length=300,
        unique=True,
        db_index=True
    )
    pais = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    descripcion = models.TextField(
        blank=True,
        null=True
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Autoridad - Entidad"
        verbose_name_plural = "Autoridades - Entidades"
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['nombre']),
        ]

    def __str__(self):
        return self.nombre