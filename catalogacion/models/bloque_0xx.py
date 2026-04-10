"""
Modelos MARC21 - Bloque 0XX
Campos de control, números de identificación y códigos
"""
import re

from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .constantes import CODIGOS_LENGUAJE, CODIGOS_PAIS



class IncipitMusical(models.Model):
    """
    Campo 031 (R) - Información del íncipit musical
    Permite múltiples íncipits para una obra
    """
    obra = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.CASCADE,
        related_name="incipits_musicales",
        help_text="Obra a la que pertenece este íncipit",
    )

    # Subcampo $a - Número de la obra (NR)
    numero_obra = models.PositiveIntegerField(
        default=1, help_text="031 $a – Número de la obra (predeterminado: 1)"
    )

    # Subcampo $b - Número del movimiento (NR)
    numero_movimiento = models.PositiveIntegerField(
        default=1, help_text="031 $b – Número del movimiento (predeterminado: 1)"
    )

    # Subcampo $c - Número de pasaje/sistema (NR)
    numero_pasaje = models.PositiveIntegerField(
        default=1, help_text="031 $c – Número de pasaje o sistema (predeterminado: 1)"
    )

    # Subcampo $d - Tempo (NR)
    titulo_encabezamiento = models.CharField(
        max_length=200,
        blank=True,
        help_text="031 $d – Tempo",
    )
    #  Subcampo $e – Personaje
    personaje = models.CharField(
        max_length=200, blank=True, null=True, help_text="031 $e – Personaje"
    )

    # Subcampo $g – Clave musical (ej. G-2, F-4)
    clave = models.CharField(
        max_length=20,
        blank=True,
        help_text="031 $g – Clave musical (ej.: G-2, F-4)",
    )

    # Subcampo $m - Voz/instrumento (NR)
    voz_instrumento = models.CharField(
        max_length=100,
        blank=True,
        default="piano",
        help_text="031 $m – Voz/instrumento",
    )

    # Subcampo $n – Armadura (ej. bBE)
    armadura = models.CharField(
        max_length=20, blank=True, help_text="031 $n – Armadura"
    )

    # Subcampo $o – Compás (ej. 4/4)
    tiempo = models.CharField(
        max_length=20, blank=True, help_text="031 $o – Compás"
    )

    # Subcampo $p - Notación musical (Cuerpo PAE)
    notacion_musical = models.TextField(
        blank=True,
        null=True,
        help_text="031 $p – Íncipit musical codificado en PAE (Plaine & Easie)",
    )
    # PAEC completo (CABECERA + Cuerpo PAE)
    paec_full = models.TextField(
        blank=True,
        null=True,
        help_text="PAEC completo para render en modo vista. Ej: %G-2 $xFCGD @2/2 '2G4B/B''2E8EDC/'B''C'BABA/",
    )

    # Transposición (la usa en búsquedas)
    transposicion = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text="Transposición asociada al íncipit (si aplica).",
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Íncipit Musical (031)"
        verbose_name_plural = "Íncipits Musicales (031)"
        ordering = ['obra', 'numero_obra', 'numero_movimiento', 'numero_pasaje']
        unique_together = [
            ['obra', 'numero_obra', 'numero_movimiento', 'numero_pasaje']
        ]
        indexes = [
            models.Index(fields=['obra', 'numero_obra']),
        ]

    def __str__(self):
        partes = [
            f"Obra {self.numero_obra}",
            f"Mov. {self.numero_movimiento}",
            f"Pas. {self.numero_pasaje}"
        ]
        if self.titulo_encabezamiento:
            partes.append(f"- {self.titulo_encabezamiento}")
        return " ".join(partes)

    @property
    def identificador_completo(self):
        """Retorna el identificador completo del íncipit"""
        return f"{self.numero_obra}.{self.numero_movimiento}.{self.numero_pasaje}"

    def get_marc_format(self):
        """Retorna el campo completo en formato MARC"""
        marc = f"031 ## $a{self.numero_obra} $b{self.numero_movimiento} $c{self.numero_pasaje}"

        if self.titulo_encabezamiento:
            marc += f" $d{self.titulo_encabezamiento}"

        if self.voz_instrumento:
            marc += f" $m{self.voz_instrumento}"

        if self.notacion_musical:
            notacion_preview = (
                self.notacion_musical[:50] + "..."
                if len(self.notacion_musical) > 50
                else self.notacion_musical
            )
            marc += f" $p{notacion_preview}"

        return marc

    @property
    def build_paec_full(self) -> str:
        """
        Construye PAEC completo para el legacy.
        Mantiene apóstrofes del body (son parte del PAEC).
        Formato recomendado (compatible con tu adapter):
          %<clave> $<armadura> @<tiempo> <body>
        """
        body = (self.notacion_musical or "").strip()
        if not body:
            return ""

        parts = []

        # clave: "G-2", "C-3", "F-4"
        if self.clave:
            parts.append(f"%{self.clave}")

        # armadura: "xFCGD" / "bBEADG" / etc
        if self.armadura:
            parts.append(f"${self.armadura}")

        # tiempo: "2/2", "4/4", "6/8", etc
        if self.tiempo:
            parts.append(f"@{self.tiempo}")

        header = " ".join(parts).strip()
        # IMPORTANTE: un espacio entre cabecera y body
        return f"{header} {body}".strip()

    def save(self, *args, **kwargs):
        # Si el catalogador pegó el PAEC completo en notacion_musical (con cabecera),
        # extraemos clave, armadura y tiempo antes de continuar.
        txt = (self.notacion_musical or "").strip()
        if txt:
            if not self.clave:
                m = re.match(r'%([GCFgcf][A-Za-z0-9\-]*)', txt)
                if m:
                    self.clave = m.group(1)
            if not self.armadura:
                m = re.search(r'\$([A-Za-z0-9]+)', txt)
                if m:
                    self.armadura = m.group(1)
            if not self.tiempo:
                m = re.search(r'@(\d+/\d+)', txt)
                if m:
                    self.tiempo = m.group(1)

        # Autogenera paec_full si hay body
        # `build_paec_full` es una `@property` que retorna un `str`,
        # por eso debe usarse sin paréntesis.
        self.paec_full = self.build_paec_full or None
        super().save(*args, **kwargs)


class IncipitURL(models.Model):
    """
    Campo 031 - Subcampo $u (R)
    URLs asociadas a un íncipit musical
    """
    incipit = models.ForeignKey(
        IncipitMusical,
        on_delete=models.CASCADE,
        related_name='urls',
        help_text="Íncipit al que pertenece esta URL"
    )

    url = models.URLField(
        max_length=500,
        help_text="031 $u — URL del íncipit codificado"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "URL de Íncipit (031 $u)"
        verbose_name_plural = "URLs de Íncipit (031 $u)"
        ordering = ['incipit', 'id']

    def __str__(self):
        return self.url


class CodigoLengua(models.Model):
    """
    Campo 041 (R) - Código de lengua
    Permite múltiples registros de idioma para una obra
    """
    INDICACION_TRADUCCION = [
        ('#', 'No se proporciona información'),
        ('0', 'El documento no es ni incluye una traducción'),
        ('1', 'El documento es o incluye una traducción'),
    ]

    FUENTE_CODIGO = [
        ('#', 'Código MARC de lengua'),
        ('7', 'Fuente especificada en el subcampo $2'),
    ]

    obra = models.ForeignKey(
        'ObraGeneral',
        on_delete=models.CASCADE,
        related_name='codigos_lengua',
        help_text="Obra a la que pertenece este código de lengua"
    )

    indicacion_traduccion = models.CharField(
        max_length=1,
        choices=INDICACION_TRADUCCION,
        default='0',
        help_text="Primer indicador: ¿Es traducción?"
    )

    fuente_codigo = models.CharField(
        max_length=1,
        choices=FUENTE_CODIGO,
        default='#',
        help_text="Segundo indicador: Fuente del código"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Código de Lengua (041)"
        verbose_name_plural = "Códigos de Lengua (041)"
        ordering = ['obra', 'id']
        indexes = [
            models.Index(fields=['obra']),
        ]

    def __str__(self):
        indicadores = f"{self.indicacion_traduccion}{self.fuente_codigo}"
        idiomas = ", ".join([idioma.get_codigo_display() for idioma in self.idiomas.all()])
        return f"041 {indicadores} - {idiomas if idiomas else 'Sin idiomas'}"

    @property
    def indicadores(self):
        """Retorna los indicadores en formato MARC"""
        return f"{self.indicacion_traduccion}{self.fuente_codigo}"

    @property
    def es_traduccion(self):
        """Verifica si el documento es o incluye traducción"""
        return self.indicacion_traduccion == '1'

    @property
    def codigo_lengua_texto(self):
        """Retorna el primer código de idioma para compatibilidad con tests"""
        primer_idioma = self.idiomas.first()
        return primer_idioma.codigo_idioma if primer_idioma else ''


class IdiomaObra(models.Model):
    """
    Campo 041 - Subcampo $a (R)
    Códigos de idioma asociados a un registro 041
    """
    codigo_lengua = models.ForeignKey(
        CodigoLengua,
        on_delete=models.CASCADE,
        related_name='idiomas',
        help_text="Registro 041 al que pertenece este idioma"
    )

    codigo_idioma = models.CharField(
        max_length=3,
        choices=CODIGOS_LENGUAJE,
        default='spa',
        help_text="041 $a — Código ISO 639-2/B del idioma"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Idioma (041 $a)"
        verbose_name_plural = "Idiomas (041 $a)"
        ordering = ['codigo_lengua', 'id']

    def __str__(self):
        return self.get_codigo_idioma_display()

    @property
    def nombre_completo(self):
        """Retorna el nombre completo del idioma"""
        return self.get_codigo_idioma_display()


class CodigoPaisEntidad(models.Model):
    """
    Campo 044 - Subcampo $a (R)
    Códigos de países asociados a la entidad editora/productora
    """
    obra = models.ForeignKey(
        'ObraGeneral',
        on_delete=models.CASCADE,
        related_name='codigos_pais_entidad',
        help_text="Obra a la que pertenece este código de país"
    )

    codigo_pais = models.CharField(
        max_length=5,
        choices=CODIGOS_PAIS,
        default='ec',
        help_text="044 $a — Código MARC21 del país"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "País Editor/Productor (044 $a)"
        verbose_name_plural = "Países Editor/Productor (044 $a)"
        ordering = ['obra', 'id']
        unique_together = [['obra', 'codigo_pais']]
        indexes = [
            models.Index(fields=['obra']),
        ]

    def __str__(self):
        return self.get_codigo_pais_display()

    @property
    def nombre_completo(self):
        """Retorna el nombre completo del país"""
        return self.get_codigo_pais_display()

    def get_marc_format(self):
        """Retorna el subcampo en formato MARC"""
        return f"$a{self.codigo_pais}"


