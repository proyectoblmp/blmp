"""
Formularios para bloque 3XX - Descripción física y técnica
"""
from django import forms
from catalogacion.models import (
    MedioInterpretacion382,
    MedioInterpretacion382_a,
)


class MedioInterpretacion382Form(forms.ModelForm):
    """Formulario para campo 382 - Medio de interpretación (contenedor)"""
    
    class Meta:
        model = MedioInterpretacion382
        fields = ['solista']  # Subcampo $b (NR)
        widgets = {
            'solista': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej.: piano, piano y orquesta…',
            }),
        }
        labels = {
            'solista': '382 $b - Solista',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prellenar $b con '---------' para nuevas instancias (sin pk guardado)
        if not self.instance.pk:
            self.fields['solista'].initial = '---------'


class MedioInterpretacion382_aForm(forms.ModelForm):
    """Formulario para campo 382 $a - Medio de interpretación"""
    
    class Meta:
        model = MedioInterpretacion382_a
        fields = ['medio']
        widgets = {
            'medio': forms.Select(attrs={
                'class': 'form-select',
            }),
        }
        labels = {
            'medio': '382 $a - Medio de interpretación',
        }