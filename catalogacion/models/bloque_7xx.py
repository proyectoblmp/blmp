from django.db import models

# =====================================================
# ⚙️ Choices (listas controladas)
# =====================================================

FUNCIONES_PERSONA = [
    ("arreglista", "Arreglista"),
    ("coeditor", "Coeditor"),
    ("compilador", "Compilador"),
    ("compositor", "Compositor"),
    ("copista", "Copista"),
    ("dedicatario", "Dedicatario"),
    ("editor", "Editor"),
    ("prologuista", "Prologuista"),
]

AUTORIAS_CHOICES = [
    ("atribuida", "Atribuida"),
    ("certificada", "Certificada"),
    ("erronea", "Errónea"),
]

FUNCIONES_ENTIDAD = [
    ("coeditor", "Coeditor"),
    ("dedicatario", "Dedicatario"),
    ("editor", "Editor"),
    ("lugar_ejecucion", "Lugar de ejecución"),
    ("lugar_estreno", "Lugar de estreno"),
    ("patrocinante", "Patrocinante"),
]


# =====================================================
# 🧑 700 1# Punto de acceso adicional – Nombre de persona (R)
# =====================================================


class NombreRelacionado700(models.Model):
    """
    700 1# – Nombre relacionado (Persona)
      $a persona (AutoridadPersona)
      $d coordenadas biográficas
      $i relación
      $j autoría
      $t título de la obra
    """

    obra = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.CASCADE,
        related_name="nombres_relacionados_700",
    )

    persona = models.ForeignKey(
        "AutoridadPersona",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text="700 $a – Apellidos, Nombres (NR, autoridad)",
    )

    coordenadas_biograficas = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="700 $d – Coordenadas biográficas (NR)",
    )

    relacion = models.CharField(
        max_length=200, blank=True, null=True, help_text="700 $i – Relación (NR)"
    )

    autoria = models.CharField(
        max_length=20,
        choices=AUTORIAS_CHOICES,
        blank=True,
        null=True,
        help_text="700 $j – Autoría (NR)",
    )

    titulo_obra = models.CharField(
        max_length=250,
        blank=True,
        null=True,
        help_text="700 $t – Título de la obra (NR)",
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "700 – Nombre relacionado"
        verbose_name_plural = "700 – Nombres relacionados (R)"

    def __str__(self):
        """
        IMPORTANTÍSIMO: aquí NUNCA usamos relaciones reverse
        (terminos_asociados, funciones, etc.), solo campos directos.
        Eso evita problemas con instancias sin pk en el admin/formsets.
        """
        partes = []
        if getattr(self, "persona", None):
            partes.append(str(self.persona))
        if self.titulo_obra:
            partes.append(f"«{self.titulo_obra}»")
        if self.relacion:
            partes.append(f"({self.relacion})")

        if partes:
            return " - ".join(partes)

        # fallback seguro
        return f"Nombre relacionado 700 (id={self.pk or 'nuevo'})"


class TerminoAsociado700(models.Model):
    """
    700 $c – Término asociado (R)
    Ej: Dr., Lic., etc.
    """

    nombre_700 = models.ForeignKey(
        NombreRelacionado700,
        on_delete=models.CASCADE,
        related_name="terminos_asociados",
    )
    termino = models.CharField(
        max_length=100, help_text="700 $c – Término asociado (R)"
    )

    class Meta:
        verbose_name = "700 $c – Término asociado"
        verbose_name_plural = "700 $c – Términos asociados (R)"

    def __str__(self):
        return self.termino or f"Término asociado 700 (id={self.pk or 'nuevo'})"


class Funcion700(models.Model):
    """
    700 $e – Función (R)
    """

    nombre_700 = models.ForeignKey(
        NombreRelacionado700,
        on_delete=models.CASCADE,
        related_name="funciones",
    )
    funcion = models.CharField(
        max_length=30, choices=FUNCIONES_PERSONA, help_text="700 $e – Función (R)"
    )

    class Meta:
        verbose_name = "700 $e – Función"
        verbose_name_plural = "700 $e – Funciones (R)"

    def __str__(self):
        # devuelve la etiqueta legible si existe
        return dict(FUNCIONES_PERSONA).get(self.funcion, self.funcion)


# =====================================================
# 🏛️ 710 2# Entidad relacionada (R)
# =====================================================


class EntidadRelacionada710(models.Model):
    """
    710 2# – Entidad relacionada (R)
      $a entidad (AutoridadEntidad)
      $e función institucional
    """

    obra = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.CASCADE,
        related_name="entidades_relacionadas_710",
        blank=True,
        null=True,
        help_text="710 $a – Entidad relacionada (NR)",
    )

    entidad = models.ForeignKey(
        "AutoridadEntidad",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text="710 $a – Entidad relacionada (NR)",
    )

    class Meta:
        verbose_name = "710 – Entidad relacionada"
        verbose_name_plural = "710 – Entidades relacionadas (R)"

    def __str__(self):
        if getattr(self, "entidad", None):
            funciones = self.funciones_institucionales.all() if self.pk else []
            if funciones:
                funcs_str = ", ".join(str(f) for f in funciones)
                return f"{self.entidad} ({funcs_str})"
            return str(self.entidad)
        return f"Entidad relacionada 710 (id={self.pk or 'nuevo'})"


class FuncionInstitucional710(models.Model):
    """
    710 $e – Función institucional (R)
    """

    entidad_710 = models.ForeignKey(
        EntidadRelacionada710,
        on_delete=models.CASCADE,
        related_name="funciones_institucionales",
    )
    funcion = models.CharField(
        max_length=50,
        choices=FUNCIONES_ENTIDAD,
        help_text="710 $e – Función institucional",
    )

    class Meta:
        verbose_name = "710 $e – Función institucional"
        verbose_name_plural = "710 $e – Funciones institucionales"

    def __str__(self):
        return dict(FUNCIONES_ENTIDAD).get(self.funcion, self.funcion)


# =====================================================
# 📘 773 – Enlace a documento fuente (R)
# =====================================================


class EnlaceDocumentoFuente773(models.Model):
    """
    773 1# – Enlace a documento fuente (R)
      $a Encabezamiento principal (persona)
      $t Título (AutoridadTituloUniforme)
    """

    obra = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.CASCADE,
        related_name="enlaces_documento_fuente_773",
    )

    encabezamiento_principal = models.ForeignKey(
        "AutoridadPersona",
        on_delete=models.PROTECT,
        help_text="773 $a – Encabezamiento principal (NR)",
    )

    titulo = models.ForeignKey(
        "AutoridadTituloUniforme",
        on_delete=models.PROTECT,
        help_text="773 $t – Título (NR)",
    )

    class Meta:
        verbose_name = "773 – Enlace a documento fuente"
        verbose_name_plural = "773 – Enlaces a documentos fuente (R)"

    def __str__(self):
        if getattr(self, "titulo", None):
            return f"En: {self.titulo}"
        return f"Enlace 773 (id={self.pk or 'nuevo'})"


class NumeroControl773(models.Model):
    """
    773 $w – Número de control del registro relacionado (R)
    Apunta a otra ObraGeneral cuyo 001 (num_control) se mostrará.
    """

    enlace_773 = models.ForeignKey(
        EnlaceDocumentoFuente773,
        on_delete=models.CASCADE,
        related_name="numeros_control",
    )

    obra_relacionada = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.PROTECT,
        help_text="Referencia al registro cuyo 001 se usará en $w",
    )

    enlace_774 = models.ForeignKey(
        "EnlaceUnidadConstituyente774",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="numeros_control_773",
        help_text="Slot 774 en la colección al que corresponde esta obra hija (referencia explícita)",
    )

    class Meta:
        verbose_name = "773 $w – Número de control"
        verbose_name_plural = "773 $w – Números de control (R)"

    def __str__(self):
        # evitamos romper si la obra_relacionada no tiene num_control aún
        if getattr(self, "obra_relacionada", None) and getattr(
            self.obra_relacionada, "num_control", None
        ):
            return self.obra_relacionada.num_control
        return f"Número de control 773 (id={self.pk or 'nuevo'})"


# =====================================================
# 📗 774 – Unidad constituyente (R)
# =====================================================


class EnlaceUnidadConstituyente774(models.Model):
    """
    774 – Unidad constituyente (R)
      $a Encabezamiento principal (persona)
      $t Título (AutoridadTituloUniforme)
    """

    obra = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.CASCADE,
        related_name="enlaces_unidades_774",
    )

    encabezamiento_principal = models.ForeignKey(
        "AutoridadPersona",
        on_delete=models.PROTECT,
        help_text="774 $a – Encabezamiento principal (NR)",
    )

    titulo = models.ForeignKey(
        "AutoridadTituloUniforme",
        on_delete=models.PROTECT,
        help_text="774 $t – Título (NR)",
    )

    class Meta:
        verbose_name = "774 – Unidad constituyente"
        verbose_name_plural = "774 – Unidades constituyentes (R)"

    def __str__(self):
        if getattr(self, "titulo", None):
            return f"Contiene: {self.titulo}"
        return f"Unidad constituyente 774 (id={self.pk or 'nuevo'})"


class NumeroControl774(models.Model):
    """774 $w – Número de control (R)"""

    enlace_774 = models.ForeignKey(
        EnlaceUnidadConstituyente774,
        on_delete=models.CASCADE,
        related_name="numeros_control",
    )

    obra_relacionada = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.PROTECT,
        help_text="Obra cuyo 001 aparecerá en $w",
    )

    class Meta:
        verbose_name = "774 $w – Número de control"
        verbose_name_plural = "774 $w – Números de control (R)"

    def __str__(self):
        if getattr(self, "obra_relacionada", None) and getattr(
            self.obra_relacionada, "num_control", None
        ):
            return self.obra_relacionada.num_control
        return f"Número de control 774 (id={self.pk or 'nuevo'})"


# =====================================================
# 🔗 787 – Otras relaciones (R)
# =====================================================


class OtrasRelaciones787(models.Model):
    """
    787 – Otras relaciones (R)
      $a Encabezamiento principal (persona)
      $t Título libre
    """

    obra = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.CASCADE,
        related_name="otras_relaciones_787",
    )

    encabezamiento_principal = models.ForeignKey(
        "AutoridadPersona",
        on_delete=models.PROTECT,
        help_text="787 $a – Encabezamiento principal (NR)",
    )

    titulo = models.CharField(max_length=250, help_text="787 $t – Título (NR)")

    class Meta:
        verbose_name = "787 – Otra relación"
        verbose_name_plural = "787 – Otras relaciones (R)"

    def __str__(self):
        if self.titulo:
            return f"Documento relacionado: {self.titulo}"
        return f"Otra relación 787 (id={self.pk or 'nuevo'})"


class NumeroControl787(models.Model):
    """787 $w – Número de control del registro relacionado (R)"""

    enlace_787 = models.ForeignKey(
        OtrasRelaciones787,
        on_delete=models.CASCADE,
        related_name="numeros_control",
    )

    obra_relacionada = models.ForeignKey(
        "ObraGeneral",
        on_delete=models.PROTECT,
        help_text="Obra cuyo 001 aparecerá en $w",
    )

    class Meta:
        verbose_name = "787 $w – Número de control"
        verbose_name_plural = "787 $w – Números de control (R)"

    def __str__(self):
        if getattr(self, "obra_relacionada", None) and getattr(
            self.obra_relacionada, "num_control", None
        ):
            return self.obra_relacionada.num_control
        return f"Número de control 787 (id={self.pk or 'nuevo'})"
