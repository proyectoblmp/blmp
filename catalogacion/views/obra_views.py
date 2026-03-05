"""
Views principales para gestión de obras MARC21.
Este módulo contiene las vistas CRUD para obras musicales siguiendo el estándar MARC21.
"""

import logging
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from catalogacion.forms import ObraGeneralForm
from catalogacion.forms.formsets import Funcion700FormSet
from catalogacion.models import (
    NombreRelacionado700,
    NumeroControl773,
    NumeroControl774,
    NumeroControl787,
    ObraGeneral,
)
from catalogacion.views.obra_config import (
    TIPO_OBRA_CONFIG,
    get_campos_visibles,
)
from catalogacion.views.obra_mixins import ObraFormsetMixin
from usuarios.mixins import CatalogadorRequiredMixin

# Configurar logger
logger = logging.getLogger("catalogacion")


def limpiar_archivos_obra(obra):
    """
    Elimina todos los archivos media asociados a una obra.
    Debe llamarse ANTES de eliminar la obra de la base de datos.

    Limpia:
    - Carpeta de digitalización (media/digitalizacion/{nombre_carpeta}/)
    - Archivos de DigitalSet (PDF, thumbnails)
    - Archivos de WorkSegment (PDFs cacheados)
    """
    from digitalizacion.models import DigitalSet

    archivos_eliminados = 0
    carpetas_eliminadas = 0

    try:
        # Obtener el DigitalSet si existe
        digital_set = getattr(obra, "digital_set", None)
        if not digital_set:
            try:
                digital_set = DigitalSet.objects.get(obra=obra)
            except DigitalSet.DoesNotExist:
                digital_set = None

        if digital_set:
            # Calcular la carpeta del repositorio
            from digitalizacion.views import nombre_carpeta_obra

            nombre_carpeta = nombre_carpeta_obra(obra)
            repo_dir = Path(settings.MEDIA_ROOT) / "digitalizacion" / nombre_carpeta

            # Eliminar carpeta completa del repositorio
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
                carpetas_eliminadas += 1
                logger.info(f"Carpeta eliminada: {repo_dir}")

            # Eliminar archivos individuales que puedan estar fuera de la carpeta
            # (por si hay rutas absolutas o archivos en otras ubicaciones)
            for path_attr in ["pdf_path", "pdf_thumb_path"]:
                rel_path = getattr(digital_set, path_attr, "")
                if rel_path:
                    abs_path = Path(settings.MEDIA_ROOT) / rel_path
                    if abs_path.exists() and abs_path.is_file():
                        abs_path.unlink()
                        archivos_eliminados += 1

            # Limpiar archivos de WorkSegments
            for segment in digital_set.segments.all():
                for path_attr in ["cached_pdf_path", "cached_thumb_path"]:
                    rel_path = getattr(segment, path_attr, "")
                    if rel_path:
                        abs_path = Path(settings.MEDIA_ROOT) / rel_path
                        if abs_path.exists() and abs_path.is_file():
                            abs_path.unlink()
                            archivos_eliminados += 1

        logger.info(
            f"Limpieza de archivos para obra {obra.pk}: "
            f"{carpetas_eliminadas} carpetas, {archivos_eliminados} archivos"
        )
        return True

    except Exception as e:
        logger.error(f"Error limpiando archivos de obra {obra.pk}: {e}")
        return False


def eliminar_obra_permanentemente(obra):
    """
    Elimina una obra permanentemente de la base de datos.
    Maneja manualmente las relaciones SET_NULL para evitar problemas con db_table.

    Args:
        obra: Instancia de ObraGeneral a eliminar

    Returns:
        bool: True si se eliminó correctamente
    """
    from catalogacion.models.borradores import BorradorObra

    try:
        # 1. Limpiar archivos media
        limpiar_archivos_obra(obra)

        # 2. Manejar manualmente las relaciones SET_NULL
        # (evita que Django use el nombre de tabla incorrecto)
        BorradorObra.objects.filter(obra_objetivo=obra).update(obra_objetivo=None)
        BorradorObra.objects.filter(obra_creada=obra).update(obra_creada=None)

        # 3. Ahora podemos eliminar la obra (CASCADE se encarga del resto)
        obra.delete()

        return True

    except Exception as e:
        logger.error(f"Error eliminando obra {obra.pk}: {e}")
        raise


class SeleccionarTipoObraView(CatalogadorRequiredMixin, TemplateView):
    """
    Vista para seleccionar el tipo de obra a catalogar.
    Presenta las opciones disponibles según la configuración MARC21.
    """

    template_name = "catalogacion/seleccionar_tipo_obra.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tipos_obra"] = TIPO_OBRA_CONFIG
        return context

    def post(self, request, *args, **kwargs):
        """Redirigir a la vista de creación con el tipo seleccionado"""
        tipo_obra = request.POST.get("tipo_obra")
        if tipo_obra in TIPO_OBRA_CONFIG:
            return redirect("catalogacion:crear_obra", tipo=tipo_obra)

        messages.error(request, "Debe seleccionar un tipo de obra válido.")
        return self.get(request, *args, **kwargs)


def validar_autores_principales_y_secundarios(form_principal, formset_700):
    autor_100 = form_principal.cleaned_data.get("compositor")

    if not autor_100:
        return []  # No hay autor principal, no validar nada

    if not formset_700:
        return []

    errores = []

    for f in formset_700:
        if f.cleaned_data and not f.cleaned_data.get("DELETE", False):
            autor_700 = f.cleaned_data.get("nombre_relacionado")

            if autor_700 and autor_700 == autor_100:
                errores.append(
                    "El autor del campo 700 no puede ser igual al autor del 100."
                )

    return errores


class CrearObraView(CatalogadorRequiredMixin, ObraFormsetMixin, CreateView):
    """
    Vista para crear una nueva obra MARC21.
    Guarda correctamente formulario principal + formsets + formsets anidados.
    """

    model = ObraGeneral
    form_class = ObraGeneralForm
    template_name = "catalogacion/crear_obra.html"

    # =====================================================
    # POST (solo logging / debug)
    # =====================================================
    def post(self, request, *args, **kwargs):
        logger.info("=" * 70)
        logger.info(f"📨 POST RECIBIDO: {len(request.POST)} campos")
        logger.info(f"tipo_obra: {kwargs.get('tipo')}")
        logger.info("=" * 70)
        return super().post(request, *args, **kwargs)

    # =====================================================
    # DISPATCH
    # =====================================================
    def dispatch(self, request, *args, **kwargs):
        self.tipo_obra = kwargs.get("tipo")

        if self.tipo_obra not in TIPO_OBRA_CONFIG:
            messages.error(request, "Tipo de obra inválido.")
            return redirect("catalogacion:seleccionar_tipo")

        self.config_obra = TIPO_OBRA_CONFIG[self.tipo_obra]
        return super().dispatch(request, *args, **kwargs)

    # =====================================================
    # FORM KWARGS
    # =====================================================
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        if self.request.method == "GET":
            kwargs["initial"] = {
                "tipo_registro": self.config_obra["tipo_registro"],
                "nivel_bibliografico": self.config_obra["nivel_bibliografico"],
            }
        return kwargs

    # =====================================================
    # CONTEXT
    # =====================================================
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["tipo_obra"] = self.tipo_obra
        context["tipo_obra_titulo"] = self.config_obra["titulo"]
        context["tipo_obra_descripcion"] = self.config_obra["descripcion"]

        # Borradores: si se viene de "recuperar borrador", se guarda en sesión
        context["borrador_id_recuperar"] = self.request.session.get("borrador_id")

        campos_config = get_campos_visibles(self.tipo_obra)
        context["campos_visibles"] = campos_config["campos_simples"]
        context["formsets_visibles"] = campos_config["formsets_visibles"]

        with_post = self.request.method == "POST"
        formsets = self._get_formsets(instance=None, with_post=with_post)

        for key, fs in formsets.items():
            context[key] = fs
        # =====================================================
        # 🔥 INLINE FORMSET 700 $e – Función
        # =====================================================
        formset_700 = formsets.get("nombres_relacionados_700") or formsets.get("700")

        if formset_700:
            for form in formset_700:
                fs = Funcion700FormSet(
                    instance=form.instance,
                    prefix=f"funcion700-{form.prefix}",
                )
                # extra=0 si ya tiene funciones guardadas para no agregar fila vacía
                if form.instance.pk and form.instance.funciones.exists():
                    fs.extra = 0
                form.funcion700_formset = fs
            # Attach a Funcion700FormSet for the empty_form template so
            # the client-side can clone a proper nested inline formset.
            try:
                empty = formset_700.empty_form
                empty_prefix = empty.prefix
                empty.funcion700_formset = Funcion700FormSet(
                    instance=None,
                    prefix=f"funcion700-{empty_prefix}",
                )
            except Exception:
                # Safety: if empty_form is not available, ignore
                pass

            # 🔥 Empty formset para nuevas filas (clonado en frontend)
            context["funcion700_empty_formset"] = Funcion700FormSet(
                instance=NombreRelacionado700(),
                prefix="funcion700-__prefix__",
            )

        # 382 → nested
        medios_formset = context.get("medios_interpretacion")
        if medios_formset:
            parent_instances = (
                [f.instance for f in medios_formset if f.instance.pk]
                if with_post
                else []
            )
            nested = self._get_nested_formsets(
                parent_instances=parent_instances, with_post=with_post
            )
            context.update(nested)

        return context

    # =====================================================
    # FORM VALID
    # =====================================================
    @transaction.atomic
    def form_valid(self, form):
        logger.info("🚀 INICIANDO form_valid()")

        context = self.get_context_data()
        formsets_validos, formsets = self._validar_formsets(context)

        if not formsets_validos:
            # Extraer errores específicos de cada formset
            errores_detallados = []
            for key, formset in formsets.items():
                # Saltar 856 que usa validación custom (no Django is_valid)
                if key == "disponibles_856":
                    continue
                if not formset.is_valid():
                    for i, frm in enumerate(formset.forms):
                        if frm.errors:
                            for field, errs in frm.errors.items():
                                for err in errs:
                                    # Traducir campo __all__ y mensajes técnicos
                                    if field == "__all__":
                                        if "already exists" in str(err):
                                            # Error de unicidad - explicar mejor según el formset
                                            if "incipit" in key.lower():
                                                err = "Numeración duplicada (la combinación obra.movimiento.pasaje debe ser única para cada íncipit)"
                                            else:
                                                err = "Registro duplicado - verifique que no haya entradas repetidas con los mismos datos"
                                        errores_detallados.append(
                                            f"{key} #{i + 1}: {err}"
                                        )
                                    else:
                                        errores_detallados.append(
                                            f"{key} #{i + 1}, campo '{field}': {err}"
                                        )
                    if formset.non_form_errors():
                        for err in formset.non_form_errors():
                            errores_detallados.append(f"{key}: {err}")

            if errores_detallados:
                messages.error(
                    self.request,
                    f"Errores encontrados: {'; '.join(errores_detallados[:5])}",
                )
            else:
                messages.error(self.request, "Hay errores en los formsets.")
            return self.form_invalid(form)

        errores_autores = validar_autores_principales_y_secundarios(
            form,
            formsets.get("nombres_relacionados_700"),
        )

        if errores_autores:
            for error in errores_autores:
                form.add_error(None, error)
            return self.form_invalid(form)

        # =====================================================
        # GUARDAR OBRA PRINCIPAL (UNA SOLA VEZ)
        # =====================================================
        self.object = form.save(commit=False)

        # Asignar el catalogador (usuario que crea la obra)
        if self.request.user.is_authenticated:
            self.object.catalogador = self.request.user

        self.object.save()

        # =====================================================
        # 🔥 GUARDAR TODOS LOS FORMSETS (856 INCLUIDO)
        # IMPORTANTE: Esto debe hacerse ANTES de procesar w_773_/w_774_/w_787_
        # porque esos procesos necesitan que los enlace ya existan en BD
        # =====================================================
        self._guardar_formsets(formsets, self.object)

        # =====================================================
        # 773 / 774 / 787 $w (DESPUÉS DE GUARDAR FORMSETS)
        # =====================================================
        # Construir mapa de POSTs tipo w_773_{suffix} -> lista de ids
        w_773_map = {}
        for k, vals in self.request.POST.lists():
            if k.startswith("w_773_"):
                try:
                    suffix = int(k.split("w_773_")[1])
                except Exception:
                    continue
                w_773_map[suffix] = vals
        logger.debug(f"POST w_773_map: {w_773_map}")

        for idx, enlace in enumerate(self.object.enlaces_documento_fuente_773.all()):
            obra_ids = w_773_map.get(enlace.pk) or w_773_map.get(idx) or []
            logger.debug(
                f"  w_773 processing: idx={idx}, enlace.pk={enlace.pk}, obra_ids={obra_ids}"
            )
            for obra_id in obra_ids:
                logger.debug(
                    f"    obra_id={obra_id}, int(obra_id)={int(obra_id)}, self.object.pk={self.object.pk}"
                )
                if obra_id and int(obra_id) != self.object.pk:
                    NumeroControl773.objects.create(
                        enlace_773=enlace, obra_relacionada_id=obra_id
                    )
                    logger.debug("    ✅ NC773 creado")
                else:
                    logger.debug("    ❌ SKIP: igual a self.object")

        w_774_map = {}
        for k, vals in self.request.POST.lists():
            if k.startswith("w_774_"):
                try:
                    suffix = int(k.split("w_774_")[1])
                except Exception:
                    continue
                w_774_map[suffix] = vals

        for idx, enlace in enumerate(self.object.enlaces_unidades_774.all()):
            obra_ids = w_774_map.get(enlace.pk) or w_774_map.get(idx) or []
            for obra_id in obra_ids:
                if obra_id and int(obra_id) != self.object.pk:
                    NumeroControl774.objects.create(
                        enlace_774=enlace, obra_relacionada_id=obra_id
                    )

        w_787_map = {}
        for k, vals in self.request.POST.lists():
            if k.startswith("w_787_"):
                try:
                    suffix = int(k.split("w_787_")[1])
                except Exception:
                    continue
                w_787_map[suffix] = vals

        for idx, enlace in enumerate(self.object.otras_relaciones_787.all()):
            obra_ids = w_787_map.get(enlace.pk) or w_787_map.get(idx) or []
            for obra_id in obra_ids:
                if obra_id and int(obra_id) != self.object.pk:
                    NumeroControl787.objects.create(
                        enlace_787=enlace, obra_relacionada_id=obra_id
                    )

        # Verificar si se solicitó publicar
        publicar = self.request.POST.get("accion") == "publicar"
        if publicar:
            self.object.publicar(usuario=self.request.user)
            messages.success(self.request, "Obra registrada y publicada exitosamente.")
        else:
            messages.success(self.request, "Obra registrada exitosamente.")
        return redirect(self.get_success_url())


class EditarObraView(CatalogadorRequiredMixin, ObraFormsetMixin, UpdateView):
    """
    Vista para editar una obra MARC21 existente.
    Maneja el formulario principal y todos los formsets anidados.
    """

    model = ObraGeneral
    form_class = ObraGeneralForm
    template_name = "catalogacion/editar_obra.html"

    def dispatch(self, request, *args, **kwargs):
        """Obtener configuración según tipo de obra"""
        # Obtener la obra ANTES de llamar a super().dispatch()
        # para que self.object esté disponible en get_context_data()
        self.object = self.get_object()

        # Determinar tipo de obra basado en sus características
        self.tipo_obra = self._determinar_tipo_obra(self.object)
        self.config_obra = TIPO_OBRA_CONFIG.get(self.tipo_obra, {})

        # Ahora sí llamar a super().dispatch()
        return super().dispatch(request, *args, **kwargs)

    def _determinar_tipo_obra(self, obra):
        """
        Determinar el tipo de obra basado en sus características MARC21.

        Args:
            obra: Instancia de ObraGeneral

        Returns:
            str: Clave del tipo de obra en TIPO_OBRA_CONFIG
        """
        tipo_reg = obra.tipo_registro
        nivel_bib = obra.nivel_bibliografico

        # Manuscritos (tipo_registro = 'd')
        if tipo_reg == "d":
            if nivel_bib == "c":
                return "coleccion_manuscrita"
            elif nivel_bib == "a":
                return "obra_en_coleccion_manuscrita"
            elif nivel_bib == "m":
                return "obra_manuscrita_individual"

        # Impresos (tipo_registro = 'c')
        elif tipo_reg == "c":
            if nivel_bib == "c":
                return "coleccion_impresa"
            elif nivel_bib == "a":
                return "obra_en_coleccion_impresa"
            elif nivel_bib == "m":
                return "obra_impresa_individual"

        # Default
        return "obra_impresa_individual"

    def get_context_data(self, **kwargs):
        logger.info(f"🔧 get_context_data() EDITAR (method={self.request.method})")

        context = super().get_context_data(**kwargs)

        # Información del tipo de obra
        context["tipo_obra"] = self.tipo_obra
        context["tipo_obra_titulo"] = self.config_obra.get("titulo", "Obra")
        context["tipo_obra_descripcion"] = self.config_obra.get("descripcion", "")

        # Configuración de campos visibles
        campos_config = get_campos_visibles(self.tipo_obra)
        context["campos_visibles"] = campos_config["campos_simples"]

        # 🚨 IMPORTANTE: declarar formsets_visibles ANTES de generarlos
        context["formsets_visibles"] = campos_config["formsets_visibles"]

        with_post = self.request.method == "POST"

        # 🚀 Crear todos los formsets
        formsets = self._get_formsets(instance=self.object, with_post=with_post)

        # Añadir cada formset explícitamente al contexto
        for key, fs in formsets.items():
            context[key] = fs

        # =====================================================
        # 🔥 INLINE FORMSET 700 $e – Función
        # =====================================================
        formset_700 = formsets.get("nombres_relacionados_700") or formsets.get("700")

        if formset_700:
            for form in formset_700:
                fs = Funcion700FormSet(
                    instance=form.instance,
                    prefix=f"funcion700-{form.prefix}",
                )
                # extra=0 si ya tiene funciones guardadas para no agregar fila vacía
                if form.instance.pk and form.instance.funciones.exists():
                    fs.extra = 0
                form.funcion700_formset = fs

            # 🔥 Empty formset para nuevas filas (clonado en frontend)
            context["funcion700_empty_formset"] = Funcion700FormSet(
                instance=NombreRelacionado700(),
                prefix="funcion700-__prefix__",
            )

        logger.debug(
            f"   Formsets cargados en contexto (editar): {list(formsets.keys())}"
        )

        # Formsets anidados del 382 (382$a)
        medios_formset = context.get("medios_interpretacion")
        if medios_formset:
            if with_post:
                # Instancias con PK
                parent_instances = [
                    form.instance for form in medios_formset if form.instance.pk
                ]
            else:
                # Todas las instancias ya guardadas
                parent_instances = list(self.object.medios_interpretacion_382.all())

            nested = self._get_nested_formsets(
                parent_instances=parent_instances, with_post=with_post
            )
            context.update(nested)

        return context

    @transaction.atomic
    def form_valid(self, form):
        """Actualizar obra y todos los formsets en una transacción atómica"""
        context = self.get_context_data()

        # Validar todos los formsets
        formsets_validos, formsets = self._validar_formsets(context)

        if not formsets_validos:
            # Extraer errores específicos de cada formset
            errores_detallados = []
            for key, formset in formsets.items():
                # Saltar 856 que usa validación custom (no Django is_valid)
                if key == "disponibles_856":
                    continue
                if not formset.is_valid():
                    for i, frm in enumerate(formset.forms):
                        if frm.errors:
                            for field, errs in frm.errors.items():
                                for err in errs:
                                    # Traducir campo __all__ y mensajes técnicos
                                    if field == "__all__":
                                        if "already exists" in str(err):
                                            # Error de unicidad - explicar mejor según el formset
                                            if "incipit" in key.lower():
                                                err = "Numeración duplicada (la combinación obra.movimiento.pasaje debe ser única para cada íncipit)"
                                            else:
                                                err = "Registro duplicado - verifique que no haya entradas repetidas con los mismos datos"
                                        errores_detallados.append(
                                            f"{key} #{i + 1}: {err}"
                                        )
                                    else:
                                        errores_detallados.append(
                                            f"{key} #{i + 1}, campo '{field}': {err}"
                                        )
                    if formset.non_form_errors():
                        for err in formset.non_form_errors():
                            errores_detallados.append(f"{key}: {err}")

            if errores_detallados:
                messages.error(
                    self.request,
                    f"Errores encontrados: {'; '.join(errores_detallados[:5])}",
                )
            else:
                messages.error(
                    self.request, "Por favor corrija los errores en los formularios."
                )
            return self.form_invalid(form)

        errores_autores = validar_autores_principales_y_secundarios(
            form,
            formsets.get("nombres_relacionados_700"),
        )

        if errores_autores:
            for error in errores_autores:
                form.add_error(None, error)
            return self.form_invalid(form)

        # Actualizar la obra principal
        self.object = form.save(commit=False)

        # Registrar quién modificó la obra
        if self.request.user.is_authenticated:
            self.object.modificado_por = self.request.user

        self.object.save()

        # Guardar todos los formsets y sus subcampos
        self._guardar_formsets(formsets, self.object)

        # =====================================================
        # 773 / 774 / 787 $w (DESPUÉS DE GUARDAR FORMSETS)
        # En edición: limpiar existentes y recrear
        # =====================================================

        # Procesar 773 $w
        w_773_map = {}
        for k, vals in self.request.POST.lists():
            if k.startswith("w_773_"):
                try:
                    suffix = int(k.split("w_773_")[1])
                except Exception:
                    continue
                w_773_map[suffix] = vals
        logger.debug(f"EDIT POST w_773_map: {w_773_map}")

        for idx, enlace in enumerate(self.object.enlaces_documento_fuente_773.all()):
            # Limpiar NumeroControl773 existentes para este enlace
            enlace.numeros_control.all().delete()
            # Crear nuevos
            obra_ids = w_773_map.get(enlace.pk) or w_773_map.get(idx) or []
            logger.debug(
                f"  EDIT w_773 processing: idx={idx}, enlace.pk={enlace.pk}, obra_ids={obra_ids}"
            )
            for obra_id in obra_ids:
                if obra_id and int(obra_id) != self.object.pk:
                    NumeroControl773.objects.create(
                        enlace_773=enlace, obra_relacionada_id=obra_id
                    )
                    logger.debug(f"    ✅ NC773 creado para obra_id={obra_id}")

        # Procesar 774 $w
        w_774_map = {}
        for k, vals in self.request.POST.lists():
            if k.startswith("w_774_"):
                try:
                    suffix = int(k.split("w_774_")[1])
                except Exception:
                    continue
                w_774_map[suffix] = vals

        for idx, enlace in enumerate(self.object.enlaces_unidades_774.all()):
            # Limpiar NumeroControl774 existentes para este enlace
            enlace.numeros_control.all().delete()
            # Crear nuevos
            obra_ids = w_774_map.get(enlace.pk) or w_774_map.get(idx) or []
            for obra_id in obra_ids:
                if obra_id and int(obra_id) != self.object.pk:
                    NumeroControl774.objects.create(
                        enlace_774=enlace, obra_relacionada_id=obra_id
                    )

        # Procesar 787 $w
        w_787_map = {}
        for k, vals in self.request.POST.lists():
            if k.startswith("w_787_"):
                try:
                    suffix = int(k.split("w_787_")[1])
                except Exception:
                    continue
                w_787_map[suffix] = vals

        for idx, enlace in enumerate(self.object.otras_relaciones_787.all()):
            # Limpiar NumeroControl787 existentes para este enlace
            enlace.numeros_control.all().delete()
            # Crear nuevos
            obra_ids = w_787_map.get(enlace.pk) or w_787_map.get(idx) or []
            for obra_id in obra_ids:
                if obra_id and int(obra_id) != self.object.pk:
                    NumeroControl787.objects.create(
                        enlace_787=enlace, obra_relacionada_id=obra_id
                    )

        # Verificar si se solicitó publicar/despublicar
        accion = self.request.POST.get("accion")
        if accion == "publicar" and not self.object.publicada:
            self.object.publicar(usuario=self.request.user)
            messages.success(
                self.request,
                f"{self.config_obra['titulo']} actualizada y publicada exitosamente.",
            )
        elif accion == "despublicar" and self.object.publicada:
            self.object.despublicar(usuario=self.request.user)
            messages.success(
                self.request,
                f"{self.config_obra['titulo']} actualizada y retirada del catálogo público.",
            )
        else:
            messages.success(
                self.request, f"{self.config_obra['titulo']} actualizada exitosamente."
            )

        return redirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        form = self.get_form()

        if form.errors:
            logger.error("❌ Errores en formulario de EDICIÓN:")
            for field, errs in form.errors.items():
                logger.error(f"   - {field}: {errs}")

        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        """Redirigir al detalle de la obra"""
        return reverse("catalogacion:detalle_obra", kwargs={"pk": self.object.pk})


class DetalleObraView(CatalogadorRequiredMixin, DetailView):
    """
    Vista de detalle de una obra.
    Muestra toda la información catalogada de una obra MARC21.
    """

    model = ObraGeneral
    template_name = "catalogacion/detalle_obra.html"
    context_object_name = "obra"

    def get_object(self, queryset=None):
        """
        Optimiza la consulta con prefetch_related para evitar N+1 queries
        """
        obj = super().get_object(queryset)

        # Prefetch para campo 650 (subdivisiones cronológicas $y y geográficas $z)
        obj = ObraGeneral.objects.filter(pk=obj.pk).prefetch_related(
            "materias_650__subdivisiones",  # $y cronológica
            "materias_650__subdivisiones_geograficas",  # $z geográfica
        ).first()

        return obj


class ListaObrasView(CatalogadorRequiredMixin, ListView):
    """
    Vista de listado de obras con paginación y búsqueda.
    Permite filtrar obras por título, número de control o compositor.
    """

    model = ObraGeneral
    template_name = "catalogacion/lista_obras.html"
    context_object_name = "obras"
    paginate_by = 20

    def get_queryset(self):
        """Obtener queryset con búsqueda y optimizaciones, filtrado por usuario"""
        queryset = (
            ObraGeneral.objects.activos()
            .select_related("compositor", "titulo_uniforme", "catalogador")
            .order_by("-fecha_creacion_sistema")
        )

        # Filtrar por el usuario autenticado (solo sus obras)
        # Los administradores ven todas las obras
        if self.request.user.is_authenticated:
            if not self.request.user.es_admin:
                queryset = queryset.filter(catalogador=self.request.user)

        # Filtro de búsqueda
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(titulo_principal__icontains=q)
                | Q(num_control__icontains=q)
                | Q(compositor__apellidos_nombres__icontains=q)
            )

        return queryset


class EliminarObraView(CatalogadorRequiredMixin, DeleteView):
    """
    Vista para eliminar (soft delete) una obra.
    No elimina físicamente, solo marca como inactiva.
    Valida relaciones PROTECT antes de eliminar.
    """

    model = ObraGeneral
    template_name = "catalogacion/confirmar_eliminar_obra.html"
    success_url = reverse_lazy("catalogacion:lista_obras")

    def get_context_data(self, **kwargs):
        """Agregar información de relaciones al contexto"""
        context = super().get_context_data(**kwargs)
        obra = self.object

        # Verificar relaciones que bloquean la eliminación
        from catalogacion.models import (
            NumeroControl773,
            NumeroControl774,
            NumeroControl787,
        )

        relaciones_773 = NumeroControl773.objects.filter(
            obra_relacionada=obra
        ).select_related("enlace_773__obra")
        relaciones_774 = NumeroControl774.objects.filter(
            obra_relacionada=obra
        ).select_related("enlace_774__obra")
        relaciones_787 = NumeroControl787.objects.filter(
            obra_relacionada=obra
        ).select_related("enlace_787__obra")

        context["tiene_relaciones_protect"] = (
            relaciones_773.exists()
            or relaciones_774.exists()
            or relaciones_787.exists()
        )
        context["relaciones_773"] = relaciones_773
        context["relaciones_774"] = relaciones_774
        context["relaciones_787"] = relaciones_787

        return context

    def form_valid(self, form):
        """Realizar soft delete de la obra con validación de relaciones.

        Nota: En Django 4.0+ DeleteView usa form_valid() en lugar de delete().
        """
        is_ajax = self.request.headers.get("X-Requested-With") == "XMLHttpRequest"

        # Verificar relaciones PROTECT antes de eliminar
        from catalogacion.models import (
            NumeroControl773,
            NumeroControl774,
            NumeroControl787,
        )

        if (
            NumeroControl773.objects.filter(obra_relacionada=self.object).exists()
            or NumeroControl774.objects.filter(obra_relacionada=self.object).exists()
            or NumeroControl787.objects.filter(obra_relacionada=self.object).exists()
        ):
            msg = (
                f'No se puede eliminar "{self.object.titulo_principal}". '
                "Existen obras que hacen referencia a esta."
            )
            if is_ajax:
                return JsonResponse({"ok": False, "mensaje": msg})
            messages.error(self.request, msg)
            return redirect("catalogacion:lista_obras")

        # Realizar soft delete con usuario (NO llamar a super() que haría delete real)
        self.object.soft_delete(usuario=self.request.user.get_username())
        msg = (
            f'Obra "{self.object.titulo_principal}" movida a la papelera. '
            "Puede restaurarla en los próximos 30 días."
        )
        if is_ajax:
            return JsonResponse({"ok": True, "mensaje": msg})
        messages.success(self.request, msg)
        return redirect(self.success_url)


class PapeleraObrasView(CatalogadorRequiredMixin, ListView):
    """
    Vista para mostrar obras eliminadas (papelera).
    Permite restaurar o purgar permanentemente.
    """

    model = ObraGeneral
    template_name = "catalogacion/papelera_obras.html"
    context_object_name = "obras"
    paginate_by = 20

    def get_queryset(self):
        """Obtener solo obras eliminadas (activo=False)"""
        return (
            ObraGeneral.objects.filter(activo=False)
            .select_related("compositor", "catalogador")
            .order_by("-fecha_eliminacion")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from datetime import timedelta

        from django.utils import timezone

        # Calcular obras que se purgarán pronto (más de 25 días)
        limite_alerta = timezone.now() - timedelta(days=25)
        context["obras_por_purgar"] = (
            self.get_queryset().filter(fecha_eliminacion__lt=limite_alerta).count()
        )
        context["dias_retencion"] = 30
        return context


class RestaurarObraView(CatalogadorRequiredMixin, DetailView):
    """Vista para restaurar una obra desde la papelera"""

    model = ObraGeneral

    def get_queryset(self):
        """Solo permitir restaurar obras eliminadas"""
        return ObraGeneral.objects.filter(activo=False)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.restore()
        messages.success(
            request,
            f'Obra "{self.object.titulo_principal}" restaurada exitosamente.',
        )
        return redirect("catalogacion:papelera_obras")


class PurgarObraView(CatalogadorRequiredMixin, DetailView):
    """Vista para eliminar permanentemente una obra de la papelera"""

    model = ObraGeneral

    def get_queryset(self):
        """Solo permitir purgar obras eliminadas"""
        return ObraGeneral.objects.filter(activo=False)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        titulo = self.object.titulo_principal

        # Verificar relaciones PROTECT antes de eliminar físicamente
        if (
            NumeroControl773.objects.filter(obra_relacionada=self.object).exists()
            or NumeroControl774.objects.filter(obra_relacionada=self.object).exists()
            or NumeroControl787.objects.filter(obra_relacionada=self.object).exists()
        ):
            messages.error(
                request,
                f'No se puede purgar "{titulo}". '
                "Existen obras que hacen referencia a esta.",
            )
            return redirect("catalogacion:papelera_obras")

        # Eliminar obra permanentemente (incluye limpieza de archivos y SET_NULL manual)
        eliminar_obra_permanentemente(self.object)
        messages.success(
            request,
            f'Obra "{titulo}" eliminada permanentemente de la base de datos.',
        )
        return redirect("catalogacion:papelera_obras")


class PublicarObraView(CatalogadorRequiredMixin, DetailView):
    """Vista para publicar una obra en el catálogo público"""

    model = ObraGeneral

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.publicar(usuario=request.user)
        messages.success(
            request,
            f'Obra "{self.object.titulo_principal}" publicada exitosamente en el catálogo público.',
        )
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
        if next_url:
            return redirect(next_url)
        return redirect("catalogacion:detalle_obra", pk=self.object.pk)


class DespublicarObraView(CatalogadorRequiredMixin, DetailView):
    """Vista para retirar una obra del catálogo público"""

    model = ObraGeneral

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.despublicar(usuario=request.user)
        messages.success(
            request,
            f'Obra "{self.object.titulo_principal}" retirada del catálogo público.',
        )
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
        if next_url:
            return redirect(next_url)
        return redirect("catalogacion:detalle_obra", pk=self.object.pk)


class PurgarTodoView(CatalogadorRequiredMixin, TemplateView):
    """Vista para purgar todas las obras antiguas de la papelera"""

    def post(self, request, *args, **kwargs):
        from datetime import timedelta

        from django.utils import timezone

        # Obtener obras eliminadas hace más de 30 días
        limite = timezone.now() - timedelta(days=30)
        obras_a_purgar = ObraGeneral.objects.filter(
            activo=False,
            fecha_eliminacion__lt=limite,
        )

        # Filtrar las que no tienen relaciones PROTECT
        obras_purgadas = 0
        obras_protegidas = 0

        for obra in obras_a_purgar:
            tiene_relaciones = (
                NumeroControl773.objects.filter(obra_relacionada=obra).exists()
                or NumeroControl774.objects.filter(obra_relacionada=obra).exists()
                or NumeroControl787.objects.filter(obra_relacionada=obra).exists()
            )
            if not tiene_relaciones:
                eliminar_obra_permanentemente(obra)
                obras_purgadas += 1
            else:
                obras_protegidas += 1

        if obras_purgadas > 0:
            messages.success(
                request,
                f"Se purgaron {obras_purgadas} obra(s) permanentemente.",
            )
        if obras_protegidas > 0:
            messages.warning(
                request,
                f"{obras_protegidas} obra(s) no se pudieron purgar por tener referencias.",
            )
        if obras_purgadas == 0 and obras_protegidas == 0:
            messages.info(request, "No hay obras antiguas para purgar.")

        return redirect("catalogacion:papelera_obras")
