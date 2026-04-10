"""
Definición de todos los formsets para campos repetibles
"""

from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from catalogacion.models import (
    CodigoLengua,
    CodigoPaisEntidad,
    Contenido505,
    DatosBiograficos545,
    Disponible856,
    Edicion,
    EnlaceDocumentoFuente773,
    EnlaceUnidadConstituyente774,
    EntidadRelacionada710,
    Estanteria852,
    Fecha264,
    Funcion700,
    # Bloque 1XX
    FuncionCompositor,
    IdiomaObra,
    # Bloque 0XX
    IncipitMusical,
    IncipitURL,
    Lugar264,
    # Bloque 6XX
    Materia650,
    MateriaGenero655,
    # Bloque 3XX
    MedioInterpretacion382,
    MedioInterpretacion382_a,
    # Bloque 4XX
    MencionSerie490,
    NombreEntidad264,
    # Bloque 7XX
    NombreRelacionado700,
    # Bloque 5XX
    NotaGeneral500,
    NumeroControl773,
    NumeroControl774,
    NumeroControl787,
    ObraGeneral,
    OtrasRelaciones787,
    ProduccionPublicacion,
    Sumario520,
    TerminoAsociado700,
    # Bloque 2XX
    TituloAlternativo,
    # Bloque 8XX
    Ubicacion852,
)

# IMPORTAR FORMULARIOS
from .forms_0xx import (
    CodigoLenguaForm,
    CodigoPaisEntidadForm,
    IdiomaObraForm,
    IncipitMusicalForm,
    IncipitURLForm,
)
from .forms_1xx import FuncionCompositorForm
from .forms_2xx import (
    EdicionForm,
    Fecha264Form,
    Lugar264Form,
    NombreEntidad264Form,
    ProduccionPublicacionForm,
    TituloAlternativoForm,
)
from .forms_3xx import (
    MedioInterpretacion382_aForm,
    MedioInterpretacion382Form,
)
from .forms_4xx import MencionSerie490Form
from .forms_5xx import (
    Contenido505Form,
    DatosBiograficos545Form,
    NotaGeneral500Form,
    Sumario520Form,
)
from .forms_6xx import (
    Materia650Form,
    MateriaGenero655Form,
)
from .forms_7xx import (
    EnlaceDocumentoFuente773Form,
    EnlaceUnidadConstituyente774Form,
    EntidadRelacionada710Form,
    Funcion700Form,
    NombreRelacionado700Form,
    NumeroControl773Form,
    NumeroControl774Form,
    NumeroControl787Form,
    OtrasRelaciones787Form,
    TerminoAsociado700Form,
)
from .forms_8xx import (
    Disponible856Form,
    Estanteria852Form,
    Ubicacion852Form,
)

# =====================================================
# FORMSETS PERSONALIZADOS
# =====================================================


class BaseDynamicExtraFormSet(BaseInlineFormSet):
    """
    Clase base para formsets que controlan dinámicamente el atributo 'extra'.
    - Al crear: muestra 1 formulario vacío
    - Al editar: si ya hay registros existentes, no agrega extras (el usuario usa botón "+")

    Funciona modificando self.extra después de __init__ pero ANTES de que
    se acceda a la propiedad forms (que es lazy/cached).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Calcular y establecer extra dinámicamente
        # IMPORTANTE: esto debe hacerse DESPUÉS de super().__init__() que configura
        # self.instance y self.queryset, pero ANTES de que se acceda a self.forms
        if self.instance and self.instance.pk:
            # Estamos editando una instancia existente
            queryset = getattr(self, "queryset", None)
            if queryset is not None:
                try:
                    has_existing = queryset.exists()
                except Exception:
                    has_existing = bool(queryset)
                # Si ya hay registros, no agregar extra (usuario usa botón "+")
                self.extra = 0 if has_existing else 1
            else:
                self.extra = 1
        else:
            # Para nuevas instancias, mostrar 1 formulario vacío
            self.extra = 1


class IncipitMusicalFormSet(BaseDynamicExtraFormSet):
    """
    Formset para íncipits musicales.
    - Evita íncipits duplicados (misma numeración obra.mov.pasaje)
    - Hereda control dinámico de extra de BaseDynamicExtraFormSet
    """

    def clean(self):
        if any(self.errors):
            return

        combinaciones = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE"):
                tup = (
                    form.cleaned_data.get("numero_obra"),
                    form.cleaned_data.get("numero_movimiento"),
                    form.cleaned_data.get("numero_pasaje"),
                )
                if tup in combinaciones:
                    raise ValidationError("Íncipit duplicado.")
                combinaciones.append(tup)


class Materia650FormSet(BaseDynamicExtraFormSet):
    """Evita materias duplicadas - hereda control dinámico de extra"""

    def clean(self):
        if any(self.errors):
            return

        materias = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE"):
                materia = form.cleaned_data.get("materia")
                if materia:
                    # Solo verificar duplicados para materias NUEVAS (sin pk)
                    # Las materias existentes ya están validadas en la BD
                    form_instance = getattr(form, "instance", None)
                    is_new = not (form_instance and form_instance.pk)

                    if is_new and materia in materias:
                        raise ValidationError(f"La materia '{materia}' está duplicada.")
                    materias.append(materia)


# =====================================================
# BLOQUE 0XX
# =====================================================

IncipitMusicalFormSet = inlineformset_factory(
    ObraGeneral,
    IncipitMusical,
    form=IncipitMusicalForm,
    formset=IncipitMusicalFormSet,
    extra=0,  # No agregar formularios extra automáticamente (usuario agrega con botón "+")
    max_num=1,  # Máximo 1 íncipit por obra (canvas soporta solo 1)
    validate_max=True,
    can_delete=True,
)

IncipitURLFormSet = inlineformset_factory(
    IncipitMusical,
    IncipitURL,
    form=IncipitURLForm,
    extra=1,
    can_delete=True,
)

CodigoLenguaFormSet = inlineformset_factory(
    ObraGeneral,
    CodigoLengua,
    form=CodigoLenguaForm,
    extra=1,
    can_delete=True,
)

IdiomaObraFormSet = inlineformset_factory(
    CodigoLengua,
    IdiomaObra,
    form=IdiomaObraForm,
    extra=1,
    can_delete=True,
)

CodigoPaisEntidadFormSet = inlineformset_factory(
    ObraGeneral,
    CodigoPaisEntidad,
    form=CodigoPaisEntidadForm,
    extra=1,
    can_delete=True,
)

# =====================================================
# BLOQUE 1XX
# =====================================================

FuncionCompositorFormSet = inlineformset_factory(
    ObraGeneral,
    FuncionCompositor,
    form=FuncionCompositorForm,
    extra=1,
    can_delete=True,
)

# =====================================================
# BLOQUE 2XX
# =====================================================

TituloAlternativoFormSet = inlineformset_factory(
    ObraGeneral,
    TituloAlternativo,
    form=TituloAlternativoForm,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

EdicionFormSet = inlineformset_factory(
    ObraGeneral,
    Edicion,
    form=EdicionForm,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

ProduccionPublicacionFormSet = inlineformset_factory(
    ObraGeneral,
    ProduccionPublicacion,
    form=ProduccionPublicacionForm,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

Lugar264FormSet = inlineformset_factory(
    ProduccionPublicacion,
    Lugar264,
    form=Lugar264Form,
    extra=1,
    can_delete=True,
)

NombreEntidad264FormSet = inlineformset_factory(
    ProduccionPublicacion,
    NombreEntidad264,
    form=NombreEntidad264Form,
    extra=1,
    can_delete=True,
)

Fecha264FormSet = inlineformset_factory(
    ProduccionPublicacion,
    Fecha264,
    form=Fecha264Form,
    extra=1,
    can_delete=True,
)

# =====================================================
# BLOQUE 3XX
# =====================================================

MedioInterpretacion382FormSet = inlineformset_factory(
    ObraGeneral,
    MedioInterpretacion382,
    form=MedioInterpretacion382Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

MedioInterpretacion382_aFormSet = inlineformset_factory(
    MedioInterpretacion382,
    MedioInterpretacion382_a,
    form=MedioInterpretacion382_aForm,
    extra=1,
    can_delete=True,
)

# =====================================================
# BLOQUE 4XX
# =====================================================

MencionSerie490FormSet = inlineformset_factory(
    ObraGeneral,
    MencionSerie490,
    form=MencionSerie490Form,
    extra=1,
    can_delete=True,
)

# =====================================================
# BLOQUE 5XX
# =====================================================

NotaGeneral500FormSet = inlineformset_factory(
    ObraGeneral,
    NotaGeneral500,
    form=NotaGeneral500Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

Contenido505FormSet = inlineformset_factory(
    ObraGeneral,
    Contenido505,
    form=Contenido505Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

Sumario520FormSet = inlineformset_factory(
    ObraGeneral,
    Sumario520,
    form=Sumario520Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)


class DatosBiograficos545BaseFormSet(BaseInlineFormSet):
    """
    Formset especial para DatosBiograficos545 (OneToOneField).
    - Solo permite 1 registro por obra
    - Al editar: si ya existe, no muestra formulario extra
    - Al crear: muestra 1 formulario vacío

    IMPORTANTE: Para OneToOneField, hay que manejar el caso donde el usuario
    quiere sobrescribir datos existentes. Este formset usa validación relajada
    porque el guardado se maneja manualmente con update_or_create en la vista.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si la obra ya tiene datos biográficos, no agregar extra
        if self.instance and self.instance.pk:
            # Verificar si ya existe un registro para esta obra
            has_existing = DatosBiograficos545.objects.filter(
                obra=self.instance
            ).exists()
            self.extra = 0 if has_existing else 1
        else:
            self.extra = 1

    def is_valid(self):
        """
        Validación relajada para OneToOneField.

        Ignoramos errores de 'id' y 'obra' porque el guardado se maneja
        manualmente con update_or_create en _guardar_formsets.
        """
        # Ejecutar validación base
        result = super().is_valid()

        # Si hay errores, filtrar los relacionados con id y obra
        # que son causados por el manejo especial de OneToOneField
        if not result:
            for form in self.forms:
                errors_to_remove = []
                for field in ["id", "obra"]:
                    if field in form.errors:
                        errors_to_remove.append(field)
                for field in errors_to_remove:
                    del form.errors[field]

            # Verificar si quedan errores reales
            has_real_errors = (
                any(form.errors or form.non_field_errors() for form in self.forms)
                or self.non_form_errors()
            )

            return not has_real_errors

        return result

    def clean(self):
        """
        Validación personalizada que permite sobrescribir registros existentes.
        """
        # No llamar a super().clean() para evitar validaciones de unicidad
        # La unicidad se maneja en _guardar_formsets con update_or_create
        pass


DatosBiograficos545FormSet = inlineformset_factory(
    ObraGeneral,
    DatosBiograficos545,
    form=DatosBiograficos545Form,
    formset=DatosBiograficos545BaseFormSet,
    extra=1,
    max_num=1,
    validate_max=True,
    can_delete=True,
)

# =====================================================
# BLOQUE 6XX
# =====================================================

Materia650FormSet = inlineformset_factory(
    ObraGeneral,
    Materia650,
    form=Materia650Form,
    formset=Materia650FormSet,
    extra=1,
    can_delete=True,
)

MateriaGenero655FormSet = inlineformset_factory(
    ObraGeneral,
    MateriaGenero655,
    form=MateriaGenero655Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

# =====================================================
# BLOQUE 7XX
# =====================================================

NombreRelacionado700FormSet = inlineformset_factory(
    ObraGeneral,
    NombreRelacionado700,
    form=NombreRelacionado700Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

TerminoAsociado700FormSet = inlineformset_factory(
    NombreRelacionado700,
    TerminoAsociado700,
    form=TerminoAsociado700Form,
    extra=1,
    can_delete=True,
)

Funcion700FormSet = inlineformset_factory(
    NombreRelacionado700,
    Funcion700,
    form=Funcion700Form,
    extra=1,
    can_delete=True,
)

EntidadRelacionada710FormSet = inlineformset_factory(
    ObraGeneral,
    EntidadRelacionada710,
    form=EntidadRelacionada710Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

EnlaceDocumentoFuente773FormSet = inlineformset_factory(
    ObraGeneral,
    EnlaceDocumentoFuente773,
    form=EnlaceDocumentoFuente773Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

NumeroControl773FormSet = inlineformset_factory(
    EnlaceDocumentoFuente773,
    NumeroControl773,
    form=NumeroControl773Form,
    extra=1,
    can_delete=True,
)

EnlaceUnidadConstituyente774FormSet = inlineformset_factory(
    ObraGeneral,
    EnlaceUnidadConstituyente774,
    form=EnlaceUnidadConstituyente774Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

NumeroControl774FormSet = inlineformset_factory(
    EnlaceUnidadConstituyente774,
    NumeroControl774,
    form=NumeroControl774Form,
    extra=1,
    can_delete=True,
)

OtrasRelaciones787FormSet = inlineformset_factory(
    ObraGeneral,
    OtrasRelaciones787,
    form=OtrasRelaciones787Form,
    extra=0,
    can_delete=True,
)

NumeroControl787FormSet = inlineformset_factory(
    OtrasRelaciones787,
    NumeroControl787,
    form=NumeroControl787Form,
    extra=1,
    can_delete=True,
)

# =====================================================
# BLOQUE 8XX
# =====================================================

Ubicacion852FormSet = inlineformset_factory(
    ObraGeneral,
    Ubicacion852,
    form=Ubicacion852Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)

Estanteria852FormSet = inlineformset_factory(
    Ubicacion852,
    Estanteria852,
    form=Estanteria852Form,
    extra=1,
    can_delete=True,
)

Disponible856FormSet = inlineformset_factory(
    ObraGeneral,
    Disponible856,
    form=Disponible856Form,
    formset=BaseDynamicExtraFormSet,
    extra=1,
    can_delete=True,
)
