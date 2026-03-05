"""
Handlers para procesamiento de formsets con subcampos dinámicos en MARC21.
Cada subcampo repetible que llega vía JavaScript se agrupa por índice de
formset y se guarda de forma encadenada en la base de datos.
"""

import logging

logger = logging.getLogger("obra_views")


class FormsetSubcampoHandler:
    """Procesa los subcampos repetibles enviados desde inputs dinámicos."""

    def __init__(self, request_post):
        self.request_post = request_post

    def _agrupar_subcampos_por_indice(self, prefijo_input, indice_posicion=3):
        """Agrupa los valores por índice de formset (0, 1, 2, ...).

        El prefijo_input tiene formato como 'lugar_produccion_264_'
        y las keys del POST son como 'lugar_produccion_264_0_0'
        donde el primer número después del prefijo es el índice del formset.
        """
        agrupados = {}

        for key, value in self.request_post.items():
            if key.startswith(prefijo_input) and value.strip():
                try:
                    # Extraer la parte después del prefijo
                    # Ej: key='lugar_produccion_264_0_0', prefijo='lugar_produccion_264_'
                    # sufijo = '0_0' → primer número es el índice del formset
                    sufijo = key[len(prefijo_input) :]
                    partes_sufijo = sufijo.split("_")

                    # Ignorar __prefix__ (template vacío)
                    if partes_sufijo[0] == "_" or "_prefix_" in sufijo:
                        continue

                    indice_formset = int(partes_sufijo[0])
                    agrupados.setdefault(indice_formset, []).append(value.strip())
                except (ValueError, IndexError):
                    continue

        return agrupados

    def procesar_subcampo_simple(
        self,
        formset,
        prefijo_input,
        modelo_subcampo,
        campo_fk,
        campo_valor,
        indice_posicion=3,
    ):
        """Reemplaza los subcampos asociados a cada formulario guardado."""

        valores = self._agrupar_subcampos_por_indice(prefijo_input, indice_posicion)
        logger.debug(
            f"procesar_subcampo_simple: prefijo={prefijo_input}, "
            f"valores={valores}, formset.instance={formset.instance}, "
            f"total_forms={len(list(formset))}"
        )

        for index, form in enumerate(formset):
            # Saltar forms marcados para eliminación
            if getattr(form, "cleaned_data", None) and form.cleaned_data.get(
                "DELETE", False
            ):
                logger.debug(f"  index={index}: marcado para DELETE, saltar")
                continue

            # Sin datos de subcampos para este índice → saltar
            # (evita crear padres vacíos para forms sin datos)
            if index not in valores:
                logger.debug(f"  index={index}: sin datos de subcampos, saltar")
                continue

            # Asegurar que el form padre exista
            if not form.instance.pk:
                logger.debug(
                    f"  index={index}: padre sin PK, creando... "
                    f"cleaned_data={getattr(form, 'cleaned_data', 'NO EXISTE')}"
                )
                parent = form.save(commit=False)
                obra = formset.instance
                parent.obra = obra
                parent.save()
                logger.debug(f"  index={index}: padre creado con pk={parent.pk}")

            relacionado = getattr(
                form.instance,
                modelo_subcampo._meta.get_field(campo_fk).related_query_name(),
            )
            relacionado.all().delete()

            for valor in valores[index]:
                modelo_subcampo.objects.create(
                    **{
                        campo_fk: form.instance,
                        campo_valor: valor,
                    }
                )
                logger.debug(
                    f"  index={index}: subcampo creado {campo_valor}={valor}"
                )


# ================================================================
# HANDLERS ESPECÍFICOS
# ================================================================


def save_subdivisiones_650(request_post, formset):
    from catalogacion.models import SubdivisionMateria650

    handler = FormsetSubcampoHandler(request_post)
    handler.procesar_subcampo_simple(
        formset=formset,
        prefijo_input="subdivision_materia_650_",
        modelo_subcampo=SubdivisionMateria650,
        campo_fk="materia650",
        campo_valor="subdivision",
    )


def save_subdivisiones_geograficas_650(request_post, formset):
    """Guarda subdivisiones geográficas (650 $z)"""
    from catalogacion.models import SubdivisionCronologica650

    handler = FormsetSubcampoHandler(request_post)
    handler.procesar_subcampo_simple(
        formset=formset,
        prefijo_input="subdivision_cronologica_650_",
        modelo_subcampo=SubdivisionCronologica650,
        campo_fk="materia650",
        campo_valor="subdivision",
    )


def save_subdivisiones_655(request_post, formset):
    from catalogacion.models import SubdivisionGeneral655

    handler = FormsetSubcampoHandler(request_post)
    handler.procesar_subcampo_simple(
        formset=formset,
        prefijo_input="subdivision_genero_655_",
        modelo_subcampo=SubdivisionGeneral655,
        campo_fk="materia655",
        campo_valor="subdivision",
    )


def save_estanterias_852(request_post, formset):
    from catalogacion.models import Estanteria852

    handler = FormsetSubcampoHandler(request_post)
    handler.procesar_subcampo_simple(
        formset,
        "estanteria_ubicacion_852_",
        Estanteria852,
        "ubicacion",
        "estanteria",
    )


def _save_urls_856(request_post, disponibles):
    from catalogacion.models import URL856

    # 🔥 Recorremos POST en orden, no por índice
    for key, value in request_post.items():
        if not key.startswith("url_disponible_856_"):
            continue

        if not value.strip():
            continue

        try:
            _, _, _, orden = key.split("_", 3)
        except ValueError:
            continue

        # 🔐 USAR EL ORDEN REAL, NO EL ÍNDICE DEL NAME
        try:
            disponible = disponibles.pop(0)
        except IndexError:
            break  # no hay más padres

        URL856.objects.create(disponible=disponible, url=value.strip())


def _save_textos_enlace_856(request_post, disponibles):
    from catalogacion.models import TextoEnlace856

    for key, value in request_post.items():
        if not key.startswith("texto_disponible_856_"):
            continue

        if not value.strip():
            continue

        try:
            disponible = disponibles.pop(0)
        except IndexError:
            break

        TextoEnlace856.objects.create(disponible=disponible, texto_enlace=value.strip())


def save_lugares_264(request_post, formset, obra=None):
    """
    Handler especial para guardar lugares del 264
    """
    from catalogacion.models import Lugar264

    handler = FormsetSubcampoHandler(request_post)
    valores = handler._agrupar_subcampos_por_indice("lugar_produccion_264_", 2)
    logger.info(f"[264] Lugares recibidos: {valores}")

    for index, form in enumerate(formset):
        if not form.instance.pk:
            parent = form.save(commit=False)
            parent.obra = obra
            parent.save()

        form.instance.lugares.all().delete()

        if index in valores:
            for valor in valores[index]:
                if valor.strip():
                    Lugar264.objects.create(
                        produccion_publicacion=form.instance, lugar=valor.strip()
                    )


def save_entidades_264(request_post, formset, obra=None):
    """
    Handler especial para guardar entidades del 264
    """
    from catalogacion.models import NombreEntidad264

    handler = FormsetSubcampoHandler(request_post)
    valores = handler._agrupar_subcampos_por_indice("entidad_produccion_264_", 2)
    logger.info(f"[264] Entidades recibidas: {valores}")

    for index, form in enumerate(formset):
        if not form.instance.pk:
            parent = form.save(commit=False)
            parent.obra = obra
            parent.save()

        form.instance.entidades.all().delete()

        if index in valores:
            for valor in valores[index]:
                if valor.strip():
                    NombreEntidad264.objects.create(
                        produccion_publicacion=form.instance, nombre=valor.strip()
                    )


def save_fechas_264(request_post, formset, obra=None):
    """
    Handler especial para guardar fechas del 264
    """
    from catalogacion.models import Fecha264

    handler = FormsetSubcampoHandler(request_post)
    valores = handler._agrupar_subcampos_por_indice("fecha_produccion_264_", 2)
    logger.info(f"[264] Fechas recibidas: {valores}")

    for index, form in enumerate(formset):
        if not form.instance.pk:
            parent = form.save(commit=False)
            parent.obra = obra
            parent.save()

        form.instance.fechas.all().delete()

        if index in valores:
            for valor in valores[index]:
                if valor.strip():
                    Fecha264.objects.create(
                        produccion_publicacion=form.instance, fecha=valor.strip()
                    )


def save_medios_382(request_post, formset):
    from catalogacion.models import MedioInterpretacion382_a

    handler = FormsetSubcampoHandler(request_post)
    handler.procesar_subcampo_simple(
        formset,
        "medio_interpretacion_382_",
        MedioInterpretacion382_a,
        "medio_interpretacion",
        "medio",
    )


def save_titulos_490(request_post, formset):
    from catalogacion.models import TituloSerie490

    handler = FormsetSubcampoHandler(request_post)
    handler.procesar_subcampo_simple(
        formset,
        "titulo_mencion_490_",
        TituloSerie490,
        "mencion_serie",
        "titulo_serie",
    )


def save_volumenes_490(request_post, formset):
    from catalogacion.models import VolumenSerie490

    handler = FormsetSubcampoHandler(request_post)
    handler.procesar_subcampo_simple(
        formset,
        "volumen_mencion_490_",
        VolumenSerie490,
        "mencion_serie",
        "volumen",
    )


# ================================================================
# HANDLERS 700 – Términos asociados ($c) y Funciones ($e)
# ================================================================


def save_terminos_asociados_700(request_post, formset):
    """Guarda los términos asociados (700 $c) desde inputs dinámicos POST."""
    from catalogacion.models import TerminoAsociado700

    handler = FormsetSubcampoHandler(request_post)
    valores = handler._agrupar_subcampos_por_indice("termino_asociado_700_")

    for index, form in enumerate(formset):
        if not form.instance.pk:
            continue  # solo procesar padres ya guardados

        form.instance.terminos_asociados.all().delete()

        if index in valores:
            for valor in valores[index]:
                if val := valor.strip():
                    TerminoAsociado700.objects.create(
                        nombre_700=form.instance, termino=val
                    )

    logger.info(f"[700 $c] Términos asociados recibidos: {valores}")


def save_funciones_700(request_post, formset):
    """Guarda funciones (700 $e) parseando directamente del POST.

    Los selects tienen name como:
    - Existentes: funcion700-nombres_700-0-0-funcion, funcion700-nombres_700-0-1-funcion
    - Nuevos (empty form): funcion700-0-0-funcion, funcion700-1-0-funcion

    Estrategia: buscar ambos patrones de prefix para cada form.
    """
    from catalogacion.models import Funcion700

    for index, form in enumerate(formset):
        if not form.instance.pk:
            continue

        # Saltar forms marcados para eliminación
        if getattr(form, "cleaned_data", None) and form.cleaned_data.get(
            "DELETE", False
        ):
            continue

        # Recopilar funciones desde el POST para este form
        # El prefix con nombre completo (forms existentes renderizados por Django)
        prefix_full = f"funcion700-{form.prefix}-"
        # El prefix corto (forms nuevos creados desde empty form)
        prefix_short = f"funcion700-{index}-"

        funciones = []
        for key, value in request_post.items():
            if (
                key.startswith(prefix_full) or key.startswith(prefix_short)
            ) and key.endswith("-funcion"):
                if value.strip():
                    funciones.append(value.strip())

        # Limpiar funciones anteriores y guardar las nuevas
        form.instance.funciones.all().delete()

        for funcion_val in funciones:
            Funcion700.objects.create(
                nombre_700=form.instance,
                funcion=funcion_val,
            )

        if funciones:
            logger.info(f"[700 $e] Funciones guardadas para #{index}: {funciones}")


def save_funciones_institucionales_710(request_post, formset):
    """Guarda funciones institucionales (710 $e) parseando directamente del POST.

    Los selects tienen name como: funcion_institucional_710_X_Y
    donde X = índice de la entidad, Y = índice de la función.
    """
    from catalogacion.models import FuncionInstitucional710

    for index, form in enumerate(formset):
        if not form.instance.pk:
            continue

        # Saltar forms marcados para eliminación
        if getattr(form, "cleaned_data", None) and form.cleaned_data.get(
            "DELETE", False
        ):
            continue

        # Recopilar funciones desde el POST para este form
        prefix = f"funcion_institucional_710_{index}_"

        funciones = []
        for key, value in request_post.items():
            if key.startswith(prefix) and value.strip():
                funciones.append(value.strip())

        # Limpiar funciones anteriores y guardar las nuevas
        form.instance.funciones_institucionales.all().delete()

        for funcion_val in funciones:
            FuncionInstitucional710.objects.create(
                entidad_710=form.instance,
                funcion=funcion_val,
            )

        if funciones:
            logger.info(
                f"[710 $e] Funciones institucionales guardadas para #{index}: {funciones}"
            )


# ================================================================
# MAPEO DE HANDLERS REGISTRADOS
# ================================================================

SUBCAMPO_HANDLERS = {
    "_save_subdivisiones_650": save_subdivisiones_650,
    "_save_subdivisiones_geograficas_650": save_subdivisiones_geograficas_650,
    "_save_subdivisiones_655": save_subdivisiones_655,
    "_save_estanterias_852": save_estanterias_852,
    "_save_urls_856": _save_urls_856,
    "_save_textos_enlace_856": _save_textos_enlace_856,
    "_save_lugares_264": save_lugares_264,
    "_save_entidades_264": save_entidades_264,
    "_save_fechas_264": save_fechas_264,
    "_save_medios_382": save_medios_382,
    "_save_titulos_490": save_titulos_490,
    "_save_volumenes_490": save_volumenes_490,
    "_save_terminos_asociados_700": save_terminos_asociados_700,
    "_save_funciones_700": save_funciones_700,
    "_save_funciones_institucionales_710": save_funciones_institucionales_710,
}
