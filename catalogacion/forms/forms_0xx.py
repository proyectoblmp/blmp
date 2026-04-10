"""
Formularios para bloque 0XX - Campos de control e identificación
"""
from django import forms
from catalogacion.models import (
    IncipitMusical,
    IncipitURL,
    CodigoLengua,
    IdiomaObra,
    CodigoPaisEntidad,
)
from .widgets import TextAreaAutosize

CLAVES_PAE = [
    ("G-2", "Clave de Sol (G-2)"),
    ("C-3", "Clave de Do en 3ª (C-3)"),
    ("F-4", "Clave de Fa en 4ª (F-4)"),

]

ARMADURAS_PAE = [
    ("", "Sin armadura"),
    ("xF", "1#"),
    ("xFC", "2#"),
    ("xFCG", "3#"),
    ("xFCGD", "4#"),
    ("xFCGDA", "5#"),
    ("xFCGDAE", "6#"),
    ("xFCGDAEB", "7#"),
    ("bB", "1b"),
    ("bBE", "2b"),
    ("bBEA", "3b"),
    ("bBEAD", "4b"),
    ("bBEADG", "5b"),
    ("bBEADGC", "6b"),
    ("bBEADGCF", "7b"),
]

TIEMPOS_MUSICALES = [
    ("4/4", "4/4"),
    ("3/4", "3/4"),
    ("2/4", "2/4"),
    ("2/2", "2/2"),
    ("3/2", "3/2"),
    ("3/8", "3/8"),
    ("6/8", "6/8"),
    ("9/8", "9/8"),
    ("12/8", "12/8"),
]



class IncipitMusicalForm(forms.ModelForm):
    """Formulario para campo 031 - Íncipit musical"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El modelo tiene blank=True en tiempo → Django lo haría required=False.
        # Forzamos required para que el SELECT no se guarde vacío.
        self.fields["tiempo"].required = True

    def clean(self):
        cleaned_data = super().clean()
        notacion_musical = cleaned_data.get("notacion_musical", "").strip()
        tiempo = cleaned_data.get("tiempo", "").strip()

        # Si hay notación musical, el tiempo es obligatorio
        if notacion_musical and not tiempo:
            self.add_error("tiempo", "El tiempo es obligatorio cuando hay notación musical.")

        return cleaned_data

    class Meta:
        model = IncipitMusical
        fields = [
            "numero_obra",
            "numero_movimiento",
            "numero_pasaje",
            "titulo_encabezamiento",
            "personaje",
            "clave",
            "voz_instrumento",
            "armadura",
            "tiempo",
            "notacion_musical",
            "numero_obra",
            "numero_movimiento",
            "numero_pasaje",
            "titulo_encabezamiento",
            "personaje",
            "clave",
            "voz_instrumento",
            "armadura",
            "tiempo",
            "notacion_musical",
        ]
        widgets = {
            "numero_obra": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                }
            ),
            "numero_movimiento": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                }
            ),
            "numero_pasaje": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                }
            ),
            "titulo_encabezamiento": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "allegro",
                }
            ),
            "personaje": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "031 $e - Personaje",
                }
            ),
            "clave": forms.Select(
                choices=CLAVES_PAE,
                attrs={"class": "form-select"},

            ),
            "voz_instrumento": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "031 $m - Voz/instrumento",
                }
            ),
            "armadura": forms.Select(
                choices=ARMADURAS_PAE,
                attrs={"class": "form-select"},
            ),
            "tiempo": forms.Select(
                choices=TIEMPOS_MUSICALES,
                attrs={"class": "form-select"},
            ),
            "notacion_musical": TextAreaAutosize(
                attrs={
                    "placeholder": "031 $p - Notación musical codificada",
                    "rows": 4,
                }
            ),
            "numero_obra": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                }
            ),
            "numero_movimiento": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                }
            ),
            "numero_pasaje": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                }
            ),
            "titulo_encabezamiento": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "allegro",
                }
            ),
            "personaje": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "031 $e - Personaje",
                }
            ),
            "clave": forms.Select(
                choices=CLAVES_PAE,
                attrs={"class": "form-select"},
            ),
            "voz_instrumento": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "031 $m - Voz/instrumento",
                }
            ),
            "armadura": forms.Select(
                choices=ARMADURAS_PAE,
                attrs={"class": "form-select"},
            ),
            "tiempo": forms.Select(
                choices=TIEMPOS_MUSICALES,
                attrs={"class": "form-select"},
            ),
            "notacion_musical": TextAreaAutosize(
                attrs={
                    "placeholder": "031 $p - Notación musical codificada",
                    "rows": 4,
                }
            ),
        }


class IncipitURLForm(forms.ModelForm):
    """Formulario para campo 031 $u - URL de íncipit"""


    class Meta:
        model = IncipitURL
        fields = ['url']
        widgets = {
            'url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': '031 $u - URL del íncipit',
            }),
        }


class CodigoLenguaForm(forms.ModelForm):
    """Formulario para campo 041 - Código de lengua"""


    class Meta:
        model = CodigoLengua
        fields = [
            'indicacion_traduccion',
            'fuente_codigo',
        ]
        widgets = {
            'indicacion_traduccion': forms.Select(attrs={
                'class': 'form-select',
            }),
            'fuente_codigo': forms.Select(attrs={
                'class': 'form-select',
            }),
        }


class IdiomaObraForm(forms.ModelForm):
    """Formulario para campo 041 $a - Idioma"""


    class Meta:
        model = IdiomaObra
        fields = ['codigo_idioma']
        widgets = {
            'codigo_idioma': forms.Select(attrs={
                'class': 'form-select',
            }),
        }
        labels = {
            'codigo_idioma': '041 $a - Código de idioma',
        }


class CodigoPaisEntidadForm(forms.ModelForm):
    """Formulario para campo 044 $a - País de entidad"""

    class Meta:
        model = CodigoPaisEntidad
        fields = ['codigo_pais']
        widgets = {
            'codigo_pais': forms.Select(attrs={
                'class': 'form-select',
            }),
        }
        labels = {
            'codigo_pais': '044 $a - País',
        }
