from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models import Q
from catalogacion.models import ObraGeneral
import json

@require_GET
def buscar_obras(request):
    obra_id = (request.GET.get("id") or "").strip()
    if obra_id:
        try:
            o = (
                ObraGeneral.objects
                .select_related("compositor", "titulo_uniforme")
                .get(id=obra_id)
            )
        except (ObraGeneral.DoesNotExist, ValueError):
            return JsonResponse({"results": []})

        return JsonResponse(
            {
                "results": [
                    {
                        "id": o.id,
                        "num_control": o.num_control,
                        "titulo": o.titulo_principal or "",
                        "compositor": (
                            o.compositor.apellidos_nombres
                            if o.compositor else ""
                        ),
                        "tipo": o.get_nivel_bibliografico_display(),
                    }
                ]
            }
        )

    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    # Búsqueda ampliada: num_control, título, compositor, signatura
    qs = (
        ObraGeneral.objects
        .select_related("compositor", "titulo_uniforme")
        .prefetch_related("ubicaciones_852")
        .filter(
            Q(num_control__icontains=q) |
            Q(titulo_principal__icontains=q) |
            Q(compositor__apellidos_nombres__icontains=q) |
            Q(ubicaciones_852__signatura_original__icontains=q)
        )
        .distinct()
        .order_by("num_control")[:20]
    )

    results = []
    for o in qs:
        # Obtener signatura si existe
        signatura = ""
        ubicacion = o.ubicaciones_852.first()
        if ubicacion and ubicacion.signatura_original:
            signatura = ubicacion.signatura_original

        results.append({
            "id": o.id,
            "num_control": o.num_control,
            "titulo": o.titulo_principal or "",
            "compositor": (
                o.compositor.apellidos_nombres
                if o.compositor else ""
            ),
            "compositor_id": (o.compositor.id if o.compositor else None),
            "titulo_id": (o.titulo_uniforme.id if getattr(o, 'titulo_uniforme', None) else None),
            "tipo": o.get_nivel_bibliografico_display(),
            "nivel_bibliografico": o.nivel_bibliografico,
            "signatura": signatura,
        })

    return JsonResponse({"results": results})


@method_decorator(csrf_exempt, name='dispatch')
class Autocompletado773View(View):
    """
    API para obtener campos heredables de una obra padre via 773 $w
    """
    
    def get(self, request):
        """
        Busca obras para selección en campo 773 $w
        """
        q = (request.GET.get("q") or "").strip()
        if len(q) < 2:
            return JsonResponse({"results": []})
        
        # Buscar obras que puedan ser padre (colecciones u obras independientes)
        qs = (
            ObraGeneral.objects
            .select_related("compositor", "titulo_uniforme")
            .filter(
                num_control__icontains=q
            )
            .filter(
                nivel_bibliografico__in=['c', 'm']  # Solo colecciones o obras independientes
            )
            .order_by("num_control")[:20]
        )
        
        results = []
        for o in qs:
            results.append({
                "id": o.id,
                "num_control": o.num_control,
                "titulo": o.titulo_principal or "",
                "compositor": (
                    o.compositor.apellidos_nombres
                    if o.compositor else ""
                ),
                "tipo_registro": o.get_tipo_registro_display(),
                "nivel_bibliografico": o.get_nivel_bibliografico_display(),
            })
        
        return JsonResponse({"results": results})
    
    def post(self, request):
        """
        Obtiene campos heredables de una obra específica
        """
        try:
            data = json.loads(request.body)
            obra_id = data.get("obra_id")
            
            if not obra_id:
                return JsonResponse({
                    "error": "Se requiere obra_id"
                }, status=400)
            
            # Obtener la obra padre con todos los campos relacionados
            obra = (
                ObraGeneral.objects
                .select_related(
                    "compositor", 
                    "titulo_uniforme"
                )
                .prefetch_related(
                    "producciones_publicaciones__lugares",
                    "producciones_publicaciones__entidades", 
                    "producciones_publicaciones__fechas",
                    "medios_interpretacion_382__medios",
                    "ubicaciones_852__estanterias",
                    "disponibles_856__urls_856",
                    "disponibles_856__textos_enlace_856"
                )
                .get(id=obra_id)
            )
            
            # Obtener campos heredables usando el método del modelo
            campos_heredables = obra.obtener_campos_para_heredar_773()
            
            return JsonResponse({
                "success": True,
                "obra": {
                    "id": obra.id,
                    "num_control": obra.num_control,
                    "titulo": obra.titulo_principal,
                    "compositor": str(obra.compositor) if obra.compositor else None,
                },
                "campos_heredables": campos_heredables
            })
            
        except ObraGeneral.DoesNotExist:
            return JsonResponse({
                "error": "Obra no encontrada"
            }, status=404)
            
        except json.JSONDecodeError:
            return JsonResponse({
                "error": "JSON inválido"
            }, status=400)
            
        except Exception as e:
            return JsonResponse({
                "error": f"Error del servidor: {str(e)}"
            }, status=500)


@require_GET
def obtener_obras_774(request):
    """
    Retorna las obras del campo 774 de una colección.
    Se usa para que el usuario seleccione cuál obra del 774 va a catalogar.
    """
    obra_id = request.GET.get("obra_id")

    if not obra_id:
        return JsonResponse({"error": "obra_id requerido"}, status=400)

    try:
        obra = ObraGeneral.objects.get(id=obra_id)

        if obra.nivel_bibliografico != 'c':
            return JsonResponse({
                "success": False,
                "error": "La obra seleccionada no es una colección"
            }, status=400)

        entries = []
        for enlace in obra.enlaces_unidades_774.select_related(
            'encabezamiento_principal', 'titulo'
        ).all():
            entries.append({
                "id": enlace.id,
                "compositor_id": enlace.encabezamiento_principal.id if enlace.encabezamiento_principal else None,
                "compositor_texto": str(enlace.encabezamiento_principal) if enlace.encabezamiento_principal else "",
                "titulo_id": enlace.titulo.id if enlace.titulo else None,
                "titulo_texto": str(enlace.titulo) if enlace.titulo else "",
                "has_linked_work": enlace.numeros_control.filter(
                    obra_relacionada__activo=True,
                    obra_relacionada__num_control__isnull=False,
                ).exists(),
            })

        return JsonResponse({
            "success": True,
            "coleccion": {
                "id": obra.id,
                "num_control": obra.num_control,
                "titulo": obra.titulo_principal,
                "compositor": str(obra.compositor) if obra.compositor else "",
            },
            "obras_774": entries
        })

    except ObraGeneral.DoesNotExist:
        return JsonResponse({"error": "Obra no encontrada"}, status=404)


@require_GET
def obtener_bio_compositor(request):
    """
    Retorna datos biográficos (545) de otras obras del compositor dado.
    Se usa para auto-llenar 545 al seleccionar compositor en 100 $a.
    """
    from catalogacion.models import DatosBiograficos545
    compositor_id = request.GET.get('compositor_id', '').strip()
    if not compositor_id or not compositor_id.isdigit():
        return JsonResponse({'success': False, 'datos': None})

    bio = (
        DatosBiograficos545.objects
        .filter(obra__compositor_id=int(compositor_id))
        .exclude(texto_biografico__isnull=True)
        .exclude(texto_biografico='')
        .select_related('obra')
        .order_by('-obra__id')
        .first()
    )

    if not bio:
        return JsonResponse({'success': False, 'datos': None})

    return JsonResponse({
        'success': True,
        'datos': {
            'texto_biografico': bio.texto_biografico,
            'uri': bio.uri or '',
        }
    })
