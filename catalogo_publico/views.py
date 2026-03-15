from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from catalogacion.models import ObraGeneral
from digitalizacion.models import DigitalPage, DigitalSet, WorkSegment


class HomePublicoView(TemplateView):
    """Página de inicio pública del catálogo"""

    template_name = "catalogo_publico/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Catálogo Musical MARC21"
        # Solo contar obras publicadas
        context["total_obras"] = ObraGeneral.objects.filter(publicada=True, activo=True).count()
        # Últimas obras PUBLICADAS (no solo registradas)
        context["ultimas_obras"] = ObraGeneral.objects.filter(publicada=True, activo=True).order_by(
            "-fecha_creacion_sistema"
        )[:6]
        return context


class ListaObrasPublicaView(ListView):
    """Lista pública de obras catalogadas"""

    model = ObraGeneral
    template_name = "catalogo_publico/lista_obras.html"
    context_object_name = "obras"
    paginate_by = 12

    def get_queryset(self):
        queryset = (
            ObraGeneral.objects.filter(publicada=True, activo=True)  # Solo obras publicadas y activas
            .select_related(
                "compositor",
                "titulo_uniforme",
                "titulo_240",
                "forma_130",
                "forma_240",
                "digital_set",
            )
            .prefetch_related(
                "medios_interpretacion_382__medios",
                "materias_650__subdivisiones",
                "materias_650__subdivisiones_geograficas",
                "materias_655__subdivisiones",
                "producciones_publicaciones__lugares",
                "producciones_publicaciones__entidades",
                "producciones_publicaciones__fechas",
                "enlaces_documento_fuente_773__titulo",
                "enlaces_documento_fuente_773__encabezamiento_principal",
                "enlaces_documento_fuente_773__numeros_control__obra_relacionada",
                "incipits_musicales",
                # 🆕 NUEVO para mostrar 852 y 856
                "ubicaciones_852",
                "ubicaciones_852__estanterias",
                "disponibles_856",
                "disponibles_856__urls_856",
                "disponibles_856__textos_enlace_856",
            )
            .order_by("-fecha_creacion_sistema")
        )

        # Búsqueda por texto
        busqueda = self.request.GET.get("q", "")
        if busqueda:
            queryset = queryset.filter(
                Q(titulo_principal__icontains=busqueda)
                | Q(compositor__apellidos_nombres__icontains=busqueda)
                | Q(
                    centro_catalogador__icontains=busqueda
                )  # Búsqueda por signatura (parte 1)
                | Q(num_control__icontains=busqueda)  # Búsqueda por signatura (parte 2)
            )

        # Filtro por tipo de obra
        tipo = self.request.GET.get("tipo", "")
        if tipo:
            queryset = queryset.filter(tipo_registro=tipo)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Catálogo de Obras"
        context["busqueda"] = self.request.GET.get("q", "")
        context["tipo_seleccionado"] = self.request.GET.get("tipo", "")
        context["tipos_obra"] = [
            ("d", "Manuscritos"),
            ("c", "Impresos"),
        ]

        obras = context.get("obras")
        obras_list = list(obras) if obras is not None else []
        obra_ids = [o.id for o in obras_list]
        if not obra_ids:
            return context

        # 1) Primer segmento por obra (si existe)
        segments = (
            WorkSegment.objects.filter(obra_id__in=obra_ids)
            .select_related("digital_set")
            .order_by("obra_id", "start_page")
        )
        first_segment_by_obra = {}
        for seg in segments:
            if seg.obra_id not in first_segment_by_obra:
                first_segment_by_obra[seg.obra_id] = seg

        # 2) Decide ds + página + visor_url por obra
        # PRIORIDAD: DigitalSet propio > Segmento en colección
        wanted_pairs = []
        wanted_meta = {}  # obra_id -> {ds_id, page, visor_url, pdf_path}
        for o in obras_list:
            # PRIORIDAD 1: DigitalSet propio de la obra
            ds_propio = getattr(o, "digital_set", None)
            if ds_propio:
                ds = ds_propio
                page_n = 1
                visor_url = reverse(
                    "digitalizacion:visor_obra", kwargs={"obra_id": o.id}
                )
                pdf_path = getattr(ds, "pdf_path", "") if ds else ""
            else:
                # PRIORIDAD 2: Segmento en colección
                seg = first_segment_by_obra.get(o.id)
                if seg:
                    ds = seg.digital_set
                    page_n = seg.start_page
                    visor_url = reverse(
                        "digitalizacion:visor_obra", kwargs={"obra_id": o.id}
                    )
                    pdf_path = getattr(ds, "pdf_path", "") if ds else ""
                else:
                    ds = None
                    page_n = 1
                    visor_url = reverse(
                        "digitalizacion:visor_digital", kwargs={"pk": o.id}
                    )
                    pdf_path = ""

            ds_id = ds.id if ds else None
            if ds_id:
                wanted_pairs.append((ds_id, page_n))

            wanted_meta[o.id] = {
                "ds_id": ds_id,
                "page": page_n,
                "visor_url": visor_url,  # dejamos link aunque no haya cover; el template decide
                "pdf_path": pdf_path,
            }

        # 3) Buscar derivative JPG para esas páginas
        from django.db.models import Q

        q = Q()
        for ds_id, page_n in wanted_pairs:
            q |= Q(digital_set_id=ds_id, page_number=page_n)

        dp_map = {}
        if q:
            pages = DigitalPage.objects.filter(q).only(
                "digital_set_id", "page_number", "derivative_path"
            )
            for dp in pages:
                if dp.derivative_path:
                    dp_map[(dp.digital_set_id, dp.page_number)] = dp.derivative_path

        # 4) Inyectar cover_url + visor_url en cada obra
        from digitalizacion.services.thumbnail_service import (
            get_pdf_thumbnail_for_digital_set,
            get_pdf_thumbnail_for_segment,
        )

        for o in obras_list:
            meta = wanted_meta.get(o.id, {})
            ds_id = meta.get("ds_id")
            page_n = meta.get("page", 1)

            derivative_path = dp_map.get((ds_id, page_n)) if ds_id else None

            cover_url = None
            cover_kind = None  # "jpg" | "pdf"

            if derivative_path:
                cover_url = default_storage.url(derivative_path)
                cover_kind = "jpg"
            else:
                pdf_path = meta.get("pdf_path") or ""
                if pdf_path and ds_id:
                    # Intentar generar thumbnail del PDF
                    thumb_path = None
                    ds_propio = getattr(o, "digital_set", None)
                    if ds_propio and ds_propio.id == ds_id:
                        # Es DigitalSet propio - generar thumbnail de página 1
                        thumb_path = get_pdf_thumbnail_for_digital_set(ds_propio)
                    else:
                        # Es segmento de colección - usar primera página del segmento
                        seg = first_segment_by_obra.get(o.id)
                        if seg:
                            thumb_path = get_pdf_thumbnail_for_segment(seg)

                    if thumb_path:
                        cover_url = default_storage.url(thumb_path)
                        cover_kind = "jpg"  # El thumbnail es JPG
                    else:
                        # Fallback: mostrar placeholder PDF
                        cover_url = default_storage.url(pdf_path)
                        cover_kind = "pdf"

            o.cover_url = cover_url
            o.cover_kind = cover_kind
            o.visor_url = meta.get("visor_url")

        return context


class DetalleObraPublicaView(DetailView):
    """Vista pública de detalle de una obra"""

    model = ObraGeneral
    template_name = "catalogo_publico/resumen_obra.html"
    context_object_name = "obra"

    def get_queryset(self):
        return (
            ObraGeneral.objects.filter(publicada=True, activo=True)  # Solo obras publicadas y activas
            .select_related(
                "compositor",
                "titulo_uniforme",
                "titulo_240",
                "forma_130",
                "forma_240",
                "digital_set",
            )
            .prefetch_related(
                "medios_interpretacion_382__medios",
                "materias_650__subdivisiones",
                "materias_650__subdivisiones_geograficas",
                "materias_655__subdivisiones",
                "producciones_publicaciones__lugares",
                "producciones_publicaciones__entidades",
                "producciones_publicaciones__fechas",
                "enlaces_documento_fuente_773__titulo",
                "enlaces_documento_fuente_773__encabezamiento_principal",
                "enlaces_documento_fuente_773__numeros_control__obra_relacionada",
                "incipits_musicales",
                "notas_generales_500",
                # 🆕 NUEVO para mostrar 852 y 856
                "ubicaciones_852",
                "ubicaciones_852__estanterias",
                "disponibles_856",
                "disponibles_856__urls_856",
                "disponibles_856__textos_enlace_856",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = f"Detalle: {self.object}"

        # Determinar si hay PDF disponible para descarga
        obra = self.object
        has_pdf = False

        # Prioridad 1: DigitalSet propio
        ds_propio = getattr(obra, "digital_set", None)
        if ds_propio and getattr(ds_propio, "pdf_path", ""):
            has_pdf = True
        else:
            # Prioridad 2: Segmento en colección
            seg = (
                WorkSegment.objects.filter(obra=obra)
                .select_related("digital_set")
                .first()
            )
            if seg and seg.digital_set:
                # Hay PDF si hay imágenes (genera PDF) o si hay PDF de colección
                from digitalizacion.models import DigitalPage

                has_images = (
                    DigitalPage.objects.filter(
                        digital_set=seg.digital_set,
                        page_number__gte=seg.start_page,
                        page_number__lte=seg.end_page,
                    )
                    .exclude(derivative_path="")
                    .exists()
                )
                has_pdf = has_images or bool(getattr(seg.digital_set, "pdf_path", ""))

        context["has_pdf"] = has_pdf
        return context


class VistaDetalladaObraView(DetailView):
    """Vista pública detallada completa de una obra"""

    model = ObraGeneral
    template_name = "catalogo_publico/detalle_obra.html"
    context_object_name = "obra"

    def get_queryset(self):
        return (
            ObraGeneral.objects.filter(publicada=True, activo=True)  # Solo obras publicadas y activas
            .select_related(
                "compositor",
                "titulo_uniforme",
                "titulo_240",
                "forma_130",
                "forma_240",
                "digital_set",
            )
            .prefetch_related(
                "medios_interpretacion_382__medios",
                "materias_650__subdivisiones",
                "materias_650__subdivisiones_geograficas",
                "materias_655__subdivisiones",
                "producciones_publicaciones__lugares",
                "producciones_publicaciones__entidades",
                "producciones_publicaciones__fechas",
                "enlaces_documento_fuente_773__titulo",
                "enlaces_documento_fuente_773__encabezamiento_principal",
                "enlaces_documento_fuente_773__numeros_control__obra_relacionada",
                "incipits_musicales",
                "notas_generales_500",
                "titulos_alternativos",
                "ediciones",
                "nombres_relacionados_700__persona",
                "nombres_relacionados_700__funciones",
                "nombres_relacionados_700__terminos_asociados",
                "entidades_relacionadas_710__entidad",
                "entidades_relacionadas_710__funciones_institucionales",
                "menciones_serie__titulos",
                "menciones_serie__volumenes",
                "enlaces_unidades_774__encabezamiento_principal",
                "enlaces_unidades_774__titulo",
                "otras_relaciones_787__encabezamiento_principal",
                "contenidos_505",
                "sumarios_520",
                "ubicaciones_852",
                "ubicaciones_852__estanterias",
                "disponibles_856",
                "disponibles_856__urls_856",
                "disponibles_856__textos_enlace_856",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obra = self.object
        context["titulo"] = f"Vista detallada: {obra}"

        # Resolver PDF y start_page:
        # PRIORIDAD 1: DigitalSet propio de la obra (si existe)
        ds_propio = getattr(obra, "digital_set", None)
        if ds_propio and getattr(ds_propio, "pdf_path", ""):
            # La obra tiene su propio PDF - usarlo
            pdf_url = default_storage.url(ds_propio.pdf_path)
            context["pdf_url"] = pdf_url
            context["pdf_start_page"] = 1
            context["has_pdf"] = True
            return context

        # PRIORIDAD 2: Buscar segmento en colección
        seg = (
            WorkSegment.objects.filter(obra=obra)
            .select_related("digital_set")
            .order_by("start_page")
            .first()
        )

        if seg and seg.digital_set:
            # Usar PDF segmentado (prioridad: imágenes > PDF colección)
            from digitalizacion.services.pdf_service import get_segment_pdf

            segment_pdf_path = get_segment_pdf(seg)
            if segment_pdf_path:
                pdf_url = default_storage.url(segment_pdf_path)
                context["pdf_url"] = pdf_url
                context["pdf_start_page"] = 1  # Ya es PDF segmentado
                context["has_pdf"] = True
                return context

            # Fallback: PDF de colección completo
            ds = seg.digital_set
            if getattr(ds, "pdf_path", ""):
                pdf_url = default_storage.url(ds.pdf_path)
                context["pdf_url"] = pdf_url
                context["pdf_start_page"] = seg.start_page or 1
                context["has_pdf"] = True
                return context

        context["pdf_url"] = None
        context["pdf_start_page"] = 1
        context["has_pdf"] = False

        return context


class FormatoMARC21View(DetailView):
    """Vista pública del formato MARC21 de una obra"""

    model = ObraGeneral
    template_name = "catalogo_publico/formato_marc21.html"
    context_object_name = "obra"

    def get_queryset(self):
        return (
            ObraGeneral.objects.filter(publicada=True, activo=True)  # Solo obras publicadas y activas
            .select_related(
                "compositor",
                "titulo_uniforme",
                "titulo_240",
                "forma_130",
                "forma_240",
            )
            .prefetch_related(
                # Bloque 0XX
                "incipits_musicales__urls",  # 031 con subcampo $u
                "codigos_lengua__idiomas",  # 041 con subcampo $a
                "codigos_pais_entidad",  # 044
                # Bloque 1XX
                "funciones_compositor",  # 100 $e
                # Bloque 2XX
                "titulos_alternativos",  # 246
                "ediciones",  # 250
                "producciones_publicaciones__lugares",  # 264 $a
                "producciones_publicaciones__entidades",  # 264 $b
                "producciones_publicaciones__fechas",  # 264 $c
                # Bloque 3XX
                "medios_interpretacion_382__medios",  # 382 $a
                # Bloque 4XX
                "menciones_serie__titulos",  # 490 $a
                "menciones_serie__volumenes",  # 490 $v
                # Bloque 5XX
                "notas_generales_500",  # 500
                "contenidos_505",  # 505
                "sumarios_520",  # 520
                # Bloque 6XX
                "materias_650__subdivisiones",  # 650 $y (cronológica)
                "materias_650__subdivisiones_geograficas",  # 650 $z (geográfica)
                "materias_655__subdivisiones",  # 655 $x
                # Bloque 7XX
                "nombres_relacionados_700__persona",
                "nombres_relacionados_700__funciones",
                "nombres_relacionados_700__terminos_asociados",
                "entidades_relacionadas_710__entidad",
                "entidades_relacionadas_710__funciones_institucionales",  # 710 $e
                "enlaces_documento_fuente_773__titulo",
                "enlaces_documento_fuente_773__encabezamiento_principal",
                "enlaces_documento_fuente_773__numeros_control",
                "enlaces_unidades_774__encabezamiento_principal",
                "enlaces_unidades_774__titulo",
                "enlaces_unidades_774__numeros_control",
                "otras_relaciones_787__encabezamiento_principal",
                "otras_relaciones_787__numeros_control",
                # Bloque 8XX
                "ubicaciones_852__estanterias",  # 852 con $c
                "disponibles_856__urls_856",  # 856 $u
                "disponibles_856__textos_enlace_856",  # 856 $y
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = f"Formato MARC21: {self.object}"

        # Intentar obtener datos biográficos (OneToOne puede no existir)
        try:
            context["datos_biograficos"] = self.object.datos_biograficos_545
        except:
            context["datos_biograficos"] = None

        return context


class DescargarPDFObraView(View):
    """Vista para descargar el PDF de una obra (segmentado si corresponde)"""

    def get(self, request, pk):
        obra = get_object_or_404(ObraGeneral.objects.filter(publicada=True, activo=True), pk=pk)

        # Prioridad 1: DigitalSet propio de la obra
        ds = DigitalSet.objects.filter(obra=obra).first()
        if ds and ds.pdf_path:
            return self._serve_pdf(ds.pdf_path, obra)

        # Prioridad 2: Segmento en colección (genera PDF segmentado)
        from digitalizacion.services.pdf_service import get_segment_pdf

        segment = WorkSegment.objects.filter(obra=obra).first()
        if segment:
            segment_pdf = get_segment_pdf(segment)
            if segment_pdf:
                return self._serve_pdf(segment_pdf, obra)

        raise Http404("No hay PDF disponible para esta obra")

    def _serve_pdf(self, rel_path, obra):
        """Sirve un archivo PDF para descarga"""
        pdf_path = Path(settings.MEDIA_ROOT) / rel_path
        if not pdf_path.exists():
            raise Http404("PDF no encontrado")

        # Nombre seguro para descarga basado en la signatura
        sig = obra.signatura_publica_display or f"obra_{obra.id}"
        # Reemplazar caracteres problemáticos
        filename = sig.replace(" ", "_").replace(".", "-").replace("/", "-") + ".pdf"

        response = FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class VistaMARCCrudoView(DetailView):
    """Vista técnica MARC crudo para catalogadores"""

    model = ObraGeneral
    template_name = "catalogo_publico/vista_marc_crudo.html"
    context_object_name = "obra"

    def get_queryset(self):
        return ObraGeneral.objects.filter(publicada=True, activo=True)  # Solo obras publicadas y activas

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = f"Vista MARC Crudo: {self.object}"

        # Generar ambos formatos
        marc_mnemonic_content = self._generar_marc_mnemonic(self.object)
        marc_hexadecimal_content = self._generar_marc_hexadecimal(self.object)

        context["marc_mnemonic_content"] = marc_mnemonic_content
        context["marc_hexadecimal_content"] = marc_hexadecimal_content
        context["marc_raw_content"] = marc_mnemonic_content  # Por defecto mnemónico

        return context

    def _generar_marc_mnemonic(self, obra):
        """Genera contenido MARC en formato crudo/mnemónico usando los mismos campos que formato_marc21.html"""
        lines = []

        # Líder (igual que en formato_marc21.html)
        leader = f"00000n{obra.tipo_registro}{obra.nivel_bibliografico} a2200000 i 4500"
        lines.append(leader)

        # 001 - Número de control
        if hasattr(obra, "num_control") and obra.num_control:
            lines.append(f"=001  {obra.num_control}")

        # 005 - Fecha/hora última transacción
        if (
            hasattr(obra, "fecha_hora_ultima_transaccion")
            and obra.fecha_hora_ultima_transaccion
        ):
            lines.append(f"=005  {obra.fecha_hora_ultima_transaccion}")

        # 008 - Código de información
        if hasattr(obra, "codigo_informacion") and obra.codigo_informacion:
            lines.append(f"=008  {obra.codigo_informacion}")

        # 020 - ISBN
        if hasattr(obra, "isbn") and obra.isbn:
            lines.append(f"=020 ##${obra.isbn}")

        # 024 - ISMN
        if hasattr(obra, "ismn") and obra.ismn:
            lines.append(f"=024 2#${obra.ismn}")

        # 028 - Número de editor
        if hasattr(obra, "numero_editor") and obra.numero_editor:
            tipo = getattr(obra, "tipo_numero_028", "2")
            control = getattr(obra, "control_nota_028", "0")
            lines.append(f"=028 {tipo}{control}${obra.numero_editor}")

        # 031 - Íncipits musicales
        if hasattr(obra, "incipits_musicales") and obra.incipits_musicales.exists():
            for incipit in obra.incipits_musicales.all():
                parts_031 = ["=031 ##"]
                if incipit.numero_obra:
                    parts_031.append(f"${incipit.numero_obra}")
                if incipit.numero_movimiento:
                    parts_031.append(f"${incipit.numero_movimiento}")
                if incipit.numero_pasaje:
                    parts_031.append(f"${incipit.numero_pasaje}")
                if incipit.titulo_encabezamiento:
                    parts_031.append(f"${incipit.titulo_encabezamiento}")
                if incipit.personaje:
                    parts_031.append(f"${incipit.personaje}")

                if len(parts_031) > 1:
                    lines.append("".join(parts_031))

        # 040 - Centro catalogador
        if hasattr(obra, "centro_catalogador") and obra.centro_catalogador:
            lines.append(
                f"=040 ##${obra.centro_catalogador}$bspa$c{obra.centro_catalogador}"
            )

        # 041 - Códigos de lengua
        if hasattr(obra, "codigos_lengua") and obra.codigos_lengua.exists():
            for codigo in obra.codigos_lengua.all():
                indicadores = f"{codigo.indicacion_traduccion}{codigo.fuente_codigo}"
                if hasattr(codigo, "idiomas") and codigo.idiomas.exists():
                    for idioma in codigo.idiomas.all():
                        lines.append(f"=041 {indicadores}${idioma.codigo_idioma}")

        # 044 - Códigos de país
        if hasattr(obra, "codigos_pais_entidad") and obra.codigos_pais_entidad.exists():
            parts_044 = ["=044 ##"]
            for pais in obra.codigos_pais_entidad.all():
                parts_044.append(f"${pais.codigo_pais}")
            if len(parts_044) > 1:
                lines.append("".join(parts_044))

        # 100 - Compositor
        if hasattr(obra, "compositor") and obra.compositor:
            parts_100 = [f"=100 1#${obra.compositor.apellidos_nombres}"]
            if obra.compositor.coordenadas_biograficas:
                parts_100.append(f"${obra.compositor.coordenadas_biograficas}")
            if hasattr(obra, "termino_asociado") and obra.termino_asociado:
                parts_100.append(f"${obra.termino_asociado}")
            if (
                hasattr(obra, "funciones_compositor")
                and obra.funciones_compositor.exists()
            ):
                for funcion in obra.funciones_compositor.all():
                    parts_100.append(f"${funcion.get_funcion_display()}")
            if hasattr(obra, "autoria") and obra.autoria:
                parts_100.append(f"${obra.get_autoria_display()}")

            lines.append("".join(parts_100))

        # 130 - Título uniforme (sin compositor)
        if (
            hasattr(obra, "titulo_uniforme")
            and obra.titulo_uniforme
            and not obra.compositor
        ):
            parts_130 = [f"=130 0#${obra.titulo_uniforme}"]
            if hasattr(obra, "forma_130") and obra.forma_130:
                parts_130.append(f"${obra.forma_130}")
            if hasattr(obra, "numero_parte_130") and obra.numero_parte_130:
                parts_130.append(f"${obra.numero_parte_130}")
            if hasattr(obra, "nombre_parte_130") and obra.nombre_parte_130:
                parts_130.append(f"${obra.nombre_parte_130}")

            lines.append("".join(parts_130))

        # 240 - Título uniforme (con compositor)
        if hasattr(obra, "titulo_240") and obra.titulo_240 and obra.compositor:
            parts_240 = [f"=240 10${obra.titulo_240}"]
            if hasattr(obra, "forma_240") and obra.forma_240:
                parts_240.append(f"${obra.forma_240}")
            if hasattr(obra, "numero_parte_240") and obra.numero_parte_240:
                parts_240.append(f"${obra.numero_parte_240}")
            if hasattr(obra, "nombre_parte_240") and obra.nombre_parte_240:
                parts_240.append(f"${obra.nombre_parte_240}")
            if hasattr(obra, "tonalidad_240") and obra.tonalidad_240:
                parts_240.append(f"${obra.get_tonalidad_240_display()}")

            lines.append("".join(parts_240))

        # 245 - Título
        if hasattr(obra, "titulo_245_display") and obra.titulo_245_display:
            lines.append(f"=245 10${obra.titulo_245_display}")

        # 260/264 - Producción/Publicación
        if (
            hasattr(obra, "producciones_publicaciones")
            and obra.producciones_publicaciones.exists()
        ):
            for pub in obra.producciones_publicaciones.all():
                parts_264 = [f"=264 #{pub.funcion}"]
                if hasattr(pub, "lugares") and pub.lugares.exists():
                    for lugar in pub.lugares.all():
                        parts_264.append(f"${lugar.lugar}")
                if hasattr(pub, "entidades") and pub.entidades.exists():
                    for entidad in pub.entidades.all():
                        parts_264.append(f"${entidad.nombre}")
                if hasattr(pub, "fechas") and pub.fechas.exists():
                    for fecha in pub.fechas.all():
                        parts_264.append(f"${fecha.fecha}")

                if len(parts_264) > 1:
                    lines.append("".join(parts_264))

        # 300 - Descripción física (igual que formato_marc21.html)
        if (
            (hasattr(obra, "extension") and obra.extension)
            or (hasattr(obra, "otras_caracteristicas") and obra.otras_caracteristicas)
            or (hasattr(obra, "dimension") and obra.dimension)
            or (hasattr(obra, "material_acompanante") and obra.material_acompanante)
        ):
            parts_300 = ["=300 ##"]
            if hasattr(obra, "extension") and obra.extension:
                parts_300.append(f"${obra.extension}")
            if hasattr(obra, "otras_caracteristicas") and obra.otras_caracteristicas:
                parts_300.append(f"${obra.otras_caracteristicas}")
            if hasattr(obra, "dimension") and obra.dimension:
                parts_300.append(f"${obra.dimension}")
            if hasattr(obra, "material_acompanante") and obra.material_acompanante:
                parts_300.append(f"${obra.material_acompanante}")

            lines.append("".join(parts_300))

        # 382 - Medio de interpretación
        if (
            hasattr(obra, "medios_interpretacion_382")
            and obra.medios_interpretacion_382.exists()
        ):
            for medio382 in obra.medios_interpretacion_382.all():
                parts_382 = ["=382 ##"]
                if hasattr(medio382, "medios") and medio382.medios.exists():
                    for medio in medio382.medios.all():
                        parts_382.append(f"${medio.get_medio_display()}")
                if medio382.solista:
                    parts_382.append(f"${medio382.solista}")

                if len(parts_382) > 1:
                    lines.append("".join(parts_382))

        # 500 - Notas generales
        if hasattr(obra, "notas_generales_500") and obra.notas_generales_500.exists():
            for nota in obra.notas_generales_500.all():
                if nota.nota_general:
                    lines.append(f"=500 ##${nota.nota_general}")

        # 505 - Contenidos
        if hasattr(obra, "contenidos_505") and obra.contenidos_505.exists():
            for contenido in obra.contenidos_505.all():
                if contenido.contenido:
                    lines.append(f"=505 00${contenido.contenido}")

        # 520 - Sumarios
        if hasattr(obra, "sumarios_520") and obra.sumarios_520.exists():
            for sumario in obra.sumarios_520.all():
                if hasattr(sumario, "sumario") and sumario.sumario:
                    lines.append(f"=520 ##${sumario.sumario}")

        # 650 - Materias temáticas
        if hasattr(obra, "materias_650") and obra.materias_650.exists():
            for materia in obra.materias_650.all():
                if materia.materia:
                    parts_650 = [f"=650 04${materia.materia}"]
                    if (
                        hasattr(materia, "subdivisiones")
                        and materia.subdivisiones.exists()
                    ):
                        for subdiv in materia.subdivisiones.all():
                            if subdiv.subdivision:
                                parts_650.append(f"${subdiv.subdivision}")
                    lines.append("".join(parts_650))

        # 655 - Materias género/forma
        if hasattr(obra, "materias_655") and obra.materias_655.exists():
            for materia in obra.materias_655.all():
                if materia.materia:
                    parts_655 = [f"=655 #4${materia.materia}"]
                    if (
                        hasattr(materia, "subdivisiones")
                        and materia.subdivisiones.exists()
                    ):
                        for subdiv in materia.subdivisiones.all():
                            if subdiv.subdivision:
                                parts_655.append(f"${subdiv.subdivision}")
                    lines.append("".join(parts_655))

        # 700 - Nombres relacionados
        if (
            hasattr(obra, "nombres_relacionados_700")
            and obra.nombres_relacionados_700.exists()
        ):
            for nombre in obra.nombres_relacionados_700.all():
                if hasattr(nombre, "persona") and nombre.persona:
                    parts_700 = [f"=700 1#${nombre.persona.apellidos_nombres}"]
                    if hasattr(nombre, "funciones") and nombre.funciones.exists():
                        for funcion in nombre.funciones.all():
                            parts_700.append(f"${funcion.get_funcion_display()}")
                    lines.append("".join(parts_700))

        # 710 - Entidades relacionadas
        if (
            hasattr(obra, "entidades_relacionadas_710")
            and obra.entidades_relacionadas_710.exists()
        ):
            for entidad in obra.entidades_relacionadas_710.all():
                if hasattr(entidad, "entidad") and entidad.entidad:
                    lines.append(f"=710 2#${entidad.entidad}")

        # 856 - Recursos electrónicos
        if hasattr(obra, "disponibles_856") and obra.disponibles_856.exists():
            for enlace in obra.disponibles_856.all():
                if hasattr(enlace, "urls_856") and enlace.urls_856.exists():
                    for url in enlace.urls_856.all():
                        if url.url:
                            lines.append(f"=856 40${url.url}")
                if (
                    hasattr(enlace, "textos_enlace_856")
                    and enlace.textos_enlace_856.exists()
                ):
                    for texto in enlace.textos_enlace_856.all():
                        if texto.texto_enlace:
                            lines.append(f"=856 40$y{texto.texto_enlace}")

        # 852 - Ubicación
        if hasattr(obra, "ubicaciones_852") and obra.ubicaciones_852.exists():
            for ubicacion in obra.ubicaciones_852.all():
                parts_852 = ["=852 0#"]
                if ubicacion.signatura_original:
                    parts_852.append(f"${ubicacion.signatura_original}")
                if hasattr(ubicacion, "estanterias") and ubicacion.estanterias.exists():
                    for estanteria in ubicacion.estanterias.all():
                        if estanteria.estanteria:
                            parts_852.append(f"${estanteria.estanteria}")

                if len(parts_852) > 1:
                    lines.append("".join(parts_852))

        return (
            "\n".join(lines)
            if lines
            else "No hay datos MARC disponibles para esta obra."
        )

    def _generar_marc_hexadecimal(self, obra):
        """Genera contenido MARC en formato hexadecimal (estilo Biblioteca Nacional)"""
        lines = []

        # Líder en formato hexadecimal (posición por posición)
        posiciones_hex = {
            0: "0",
            1: "0",
            2: "0",
            3: "0",
            4: "0",  # 00000
            5: "n",  # Estado del registro
            6: obra.tipo_registro or "d",  # Tipo de registro
            7: obra.nivel_bibliografico or "m",  # Nivel bibliográfico
            8: "a",
            9: "2",  # Tipo de bibliográfica
            10: "2",
            11: "0",
            12: "0",
            13: "0",
            14: "0",
            15: "0",
            16: "0",  # Base de datos
            17: "7",  # Nivel de codificación
            18: "a",  # Forma de catalogación descriptiva
            19: "2",  # Nivel de recurso
            20: "2",  # Tipo de control
            21: "0",
            22: "0",
            23: " ",  # Resto
        }

        # Agregar cada posición del líder
        for pos, valor in posiciones_hex.items():
            lines.append(f"=h-{pos:03d} {valor}")

        # 001 - Número de control
        if hasattr(obra, "num_control") and obra.num_control:
            lines.append(f"=h-001 {obra.num_control}")

        # 005 - Fecha/hora última transacción
        if (
            hasattr(obra, "fecha_hora_ultima_transaccion")
            and obra.fecha_hora_ultima_transaccion
        ):
            lines.append(f"=h-005 {obra.fecha_hora_ultima_transaccion}")

        # 008 - Código de información
        if hasattr(obra, "codigo_informacion") and obra.codigo_informacion:
            lines.append(f"=h-008 {obra.codigo_informacion}")

        # 100 - Compositor
        if hasattr(obra, "compositor") and obra.compositor:
            parts_100 = [f"=h-100 1#{obra.compositor.apellidos_nombres}"]
            if obra.compositor.coordenadas_biograficas:
                parts_100.append(f"${obra.compositor.coordenadas_biograficas}")
            lines.append("".join(parts_100))

        # 245 - Título
        if hasattr(obra, "titulo_245_display") and obra.titulo_245_display:
            lines.append(f"=h-245 10${obra.titulo_245_display}")

        # 264 - Producción/Publicación
        if (
            hasattr(obra, "producciones_publicaciones")
            and obra.producciones_publicaciones.exists()
        ):
            for pub in obra.producciones_publicaciones.all():
                parts_264 = [f"=h-264 #{pub.funcion}"]
                if hasattr(pub, "lugares") and pub.lugares.exists():
                    for lugar in pub.lugares.all():
                        parts_264.append(f"${lugar.lugar}")
                if hasattr(pub, "entidades") and pub.entidades.exists():
                    for entidad in pub.entidades.all():
                        parts_264.append(f"${entidad.nombre}")
                if hasattr(pub, "fechas") and pub.fechas.exists():
                    for fecha in pub.fechas.all():
                        parts_264.append(f"${fecha.fecha}")

                if len(parts_264) > 1:
                    lines.append("".join(parts_264))

        # 300 - Descripción física
        if (
            (hasattr(obra, "extension") and obra.extension)
            or (hasattr(obra, "otras_caracteristicas") and obra.otras_caracteristicas)
            or (hasattr(obra, "dimension") and obra.dimension)
            or (hasattr(obra, "material_acompanante") and obra.material_acompanante)
        ):
            parts_300 = ["=h-300 ##"]
            if hasattr(obra, "extension") and obra.extension:
                parts_300.append(f"${obra.extension}")
            if hasattr(obra, "otras_caracteristicas") and obra.otras_caracteristicas:
                parts_300.append(f"${obra.otras_caracteristicas}")
            if hasattr(obra, "dimension") and obra.dimension:
                parts_300.append(f"${obra.dimension}")
            if hasattr(obra, "material_acompanante") and obra.material_acompanante:
                parts_300.append(f"${obra.material_acompanante}")

            lines.append("".join(parts_300))

        # 650 - Materias temáticas
        if hasattr(obra, "materias_650") and obra.materias_650.exists():
            for materia in obra.materias_650.all():
                if materia.materia:
                    parts_650 = [f"=h-650 04${materia.materia}"]
                    if (
                        hasattr(materia, "subdivisiones")
                        and materia.subdivisiones.exists()
                    ):
                        for subdiv in materia.subdivisiones.all():
                            if subdiv.subdivision:
                                parts_650.append(f"${subdiv.subdivision}")
                    lines.append("".join(parts_650))

        # 856 - Recursos electrónicos
        if hasattr(obra, "disponibles_856") and obra.disponibles_856.exists():
            for enlace in obra.disponibles_856.all():
                if hasattr(enlace, "urls_856") and enlace.urls_856.exists():
                    for url in enlace.urls_856.all():
                        if url.url:
                            lines.append(f"=h-856 40${url.url}")

        return (
            "\n".join(lines)
            if lines
            else "No hay datos MARC disponibles para esta obra."
        )
