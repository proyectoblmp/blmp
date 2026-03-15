from django import forms

from catalogacion.models import (
    AutoridadPersona,
    AutoridadEntidad,
    AutoridadFormaMusical,
    AutoridadMateria,
    AutoridadTituloUniforme,
)


class AutoridadPersonaForm(forms.ModelForm):
    class Meta:
        model = AutoridadPersona
        fields = ["apellidos_nombres", "coordenadas_biograficas", "nota_biografica", "uri_nota_biografica"]
        widgets = {
            "apellidos_nombres": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Apellidos, Nombres (ej: Bach, Johann Sebastian)",
                }
            ),
            "coordenadas_biograficas": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Años de vida o actividad (ej: 1685-1750)",
                }
            ),
            "nota_biografica": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Ej.: Compositor latinoamericano nacido en...",
                }
            ),
            "uri_nota_biografica": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://es.wikipedia.org/wiki/...",
                }
            ),
        }
        labels = {
            "apellidos_nombres": "Apellidos, Nombres",
            "coordenadas_biograficas": "Coordenadas biográficas",
            "nota_biografica": "545 $a – Nota biográfica",
            "uri_nota_biografica": "545 $u – URL de referencia",
        }


class AutoridadEntidadForm(forms.ModelForm):
    class Meta:
        model = AutoridadEntidad
        fields = ["nombre", "pais", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre oficial de la entidad",
                }
            ),
            "pais": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "País (opcional)",
                }
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Descripción o notas (opcional)",
                }
            ),
        }
        labels = {
            "nombre": "Nombre",
            "pais": "País",
            "descripcion": "Descripción",
        }


class AutoridadFormaMusicalForm(forms.ModelForm):
    class Meta:
        model = AutoridadFormaMusical
        fields = ["forma"]
        widgets = {
            "forma": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej: Pasillo, Sinfonía, Vals",
                }
            ),
        }
        labels = {"forma": "Forma musical"}


class AutoridadMateriaForm(forms.ModelForm):
    class Meta:
        model = AutoridadMateria
        fields = ["termino"]
        widgets = {
            "termino": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Término de materia (ej: Música coral)",
                }
            ),
        }
        labels = {"termino": "Término de materia"}


class AutoridadTituloUniformeForm(forms.ModelForm):
    class Meta:
        model = AutoridadTituloUniforme
        fields = ["titulo"]
        widgets = {
            "titulo": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Título uniforme",
                }
            ),
        }
        labels = {"titulo": "Título uniforme"}
