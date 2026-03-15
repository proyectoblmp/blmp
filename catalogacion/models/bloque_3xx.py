"""
Campos de descripción física y características técnicas:
- Campo 382: Medio de interpretación
"""

from django.db import models

# ================================================
#? 📌 CAMPO 382: MEDIO DE INTERPRETACIÓN (R)
# ================================================

class MedioInterpretacion382(models.Model):
    """
    Campo 382 (R) - Medio de interpretación
    
    Instancia de 382 que agrupa subcampos $a, $b, $n que describen
    los instrumentos/voces y solistas de una obra.
    """
    
    obra = models.ForeignKey(
        'ObraGeneral',
        on_delete=models.CASCADE,
        related_name='medios_interpretacion_382',
        help_text="Obra a la que pertenece"
    )
    
    # Subcampo $b (NR) - Solista
    solista = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        default='---------',
        help_text="382 $b — Solista (predeterminado: ---------)"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Medio de Interpretación (382)"
        verbose_name_plural = "Medios de Interpretación (382 - R)"
        ordering = ['obra', 'id']
    
    def __str__(self):
        partes = []
        medios = ", ".join([m.get_medio_display() for m in self.medios.all()])
        if medios:
            partes.append(f"Medios: {medios}")
        if self.solista:
            partes.append(f"Solista: {self.solista}")
        return " | ".join(partes) if partes else "382 (sin datos)"


class MedioInterpretacion382_a(models.Model):
    """
    Subcampo $a de 382 (R)
    Medio de interpretación - instrumento, voz o conjunto
    """
    
    MEDIOS = [
        ('piano', 'Piano'),
        ('dos pianos', 'Dos pianos'),
        ('piano a cuatro manos', 'Piano a cuatro manos'),
        ('piano con acompañamiento', 'Piano con acompañamiento'),
    ]
    
    medio_interpretacion = models.ForeignKey(
        MedioInterpretacion382,
        on_delete=models.CASCADE,
        related_name='medios',
        help_text="Medio de interpretación al que pertenece"
    )
    
    # Subcampo $a
    medio = models.CharField(
        max_length=50,
        choices=MEDIOS,
        default='piano',
        help_text="382 $a – Medio de interpretación (predeterminado: piano)"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Medio (382 $a)"
        verbose_name_plural = "Medios (382 $a - R)"
        ordering = ['medio_interpretacion', 'id']
    
    def __str__(self):
        return self.get_medio_display()
