"""
Señales automáticas para:
- Actualización de signatura por cambios en campo 044
- Bidireccionalidad 773 $w ↔ 774 $w
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .bloque_0xx import CodigoPaisEntidad
from .bloque_7xx import (
    NumeroControl773,
    EnlaceUnidadConstituyente774,
    NumeroControl774,
)


@receiver(post_save, sender=CodigoPaisEntidad)
@receiver(post_delete, sender=CodigoPaisEntidad)
def actualizar_signatura_por_cambio_pais(sender, instance, raw=False, **kwargs):
    if raw:
        return
    """
    Actualiza automáticamente la signatura de la obra cuando se cambia un código de país.
    
    Esta señal se dispara cuando:
    - Se crea un nuevo código de país (post_save)
    - Se modifica un código de país existente (post_save)  
    - Se elimina un código de país (post_delete)
    
    Args:
        sender: Modelo CodigoPaisEntidad
        instance: Instancia del código de país modificado
        **kwargs: Argumentos adicionales de la señal
    """
    print(f"🚀 SEÑAL DISPARADA: {sender.__name__} - País: {instance.codigo_pais} - Obra: {instance.obra.num_control if instance.obra else 'None'}")
    
    try:
        obra = instance.obra
        
        # Verificar que la obra tenga los campos necesarios para generar signatura
        if obra.centro_catalogador and obra.num_control:
            # Importamos aquí para evitar importación circular
            from .utils import generar_signatura_completa, obtener_pais_principal
            
            # Generar nueva signatura con el país actualizado
            nueva_signatura = generar_signatura_completa(obra)
            pais_actual = obtener_pais_principal(obra)
            
            print(f"🔍 DEBUG: País actual = {pais_actual}")
            print(f"🔍 DEBUG: Nueva signatura = {nueva_signatura}")
            print(f"🔍 DEBUG: signatura_publica_display = {obra.signatura_publica_display}")
            
            # Forzar la recalculación de properties relacionadas con el país
            # Esto asegura que las views y templates obtengan el valor actualizado
            
            # Invalidar caché de properties si existe
            if hasattr(obra, '_signatura_completa_cache'):
                delattr(obra, '_signatura_completa_cache')
            if hasattr(obra, '_signatura_publica_display_cache'):
                delattr(obra, '_signatura_publica_display_cache')
            
            # Log para debugging
            import logging
            logger = logging.getLogger('marc21')
            logger.info(
                f"✅ Signatura actualizada automáticamente por cambio de país: "
                f"Obra {obra.num_control} - Nueva signatura: {nueva_signatura}"
            )
            
        else:
            print(f"❌ Obra sin campos necesarios: centro={obra.centro_catalogador}, num_control={obra.num_control}")

    except Exception as e:
        # Log del error pero sin interrumpir la operación
        print(f"❌ ERROR en señal: {str(e)}")
        import logging
        logger = logging.getLogger('marc21')
        logger.error(
            f"❌ Error al actualizar signatura por cambio de país: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Bidireccionalidad 773 $w ↔ 774 $w
# ─────────────────────────────────────────────────────────────────────────────

def _titulos_autoridad_posibles(obra):
    """Retorna los FK de título uniforme que mejor representan a la obra hija."""
    posibles = []
    if getattr(obra, "titulo_240_id", None):
        posibles.append(obra.titulo_240_id)
    if getattr(obra, "titulo_uniforme_id", None) and obra.titulo_uniforme_id not in posibles:
        posibles.append(obra.titulo_uniforme_id)
    return posibles


def _asignar_w_774(enlace_774, obra_hijo):
    """
    Asigna $w de obra_hijo al slot enlace_774.
    Limpia cualquier $w duplicado de la misma obra en otros slots de la colección.
    """
    # Borrar este $w de cualquier otro slot donde esté mal colocado
    NumeroControl774.objects.filter(
        enlace_774__obra=enlace_774.obra,
        obra_relacionada=obra_hijo,
    ).exclude(enlace_774=enlace_774).delete()

    NumeroControl774.objects.get_or_create(
        enlace_774=enlace_774,
        obra_relacionada=obra_hijo,
    )


@receiver(post_save, sender=NumeroControl773)
def sincronizar_774_al_guardar_773(sender, instance, created, raw=False, **kwargs):
    """
    Al guardar un 773 $w (obra hija → colección padre), asigna el $w al slot 774
    correcto de la colección.

    Prioridad:
    1. FK explícito instance.enlace_774 (guardado desde el modal de selección).
    2. ¿Ya hay un $w correcto para esta obra en la colección? → no tocar.
    3. Búsqueda por FK exacto compositor+título (sin fuzzy text).
    NUNCA crea nuevas filas 774 automáticamente.
    """
    if raw:
        return
    try:
        import logging
        logger = logging.getLogger('marc21')

        obra_hijo  = instance.enlace_773.obra
        obra_padre = instance.obra_relacionada
        persona_hijo = obra_hijo.compositor

        # PRIORIDAD 1: FK explícito guardado desde el modal de selección
        if instance.enlace_774_id:
            enlace_774 = instance.enlace_774
            if enlace_774 and enlace_774.obra_id == obra_padre.id:
                _asignar_w_774(enlace_774, obra_hijo)
                return
            else:
                logger.warning(
                    f"[773 sync] enlace_774_id={instance.enlace_774_id} no pertenece "
                    f"a la colección {obra_padre.num_control} — ignorado"
                )

        # PRIORIDAD 2: ¿ya hay un $w válido para esta obra en la colección?
        enlace_actual = EnlaceUnidadConstituyente774.objects.filter(
            obra=obra_padre,
            numeros_control__obra_relacionada=obra_hijo,
        ).order_by("pk").first()
        if enlace_actual:
            return  # ya vinculado, no modificar

        # PRIORIDAD 3: buscar por FK exacto (compositor + título uniforme)
        if not persona_hijo:
            return

        titulo_ids = _titulos_autoridad_posibles(obra_hijo)
        if not titulo_ids:
            logger.warning(
                f"[773 sync] Sin slot 774 exacto para {obra_hijo.num_control} "
                f"en {obra_padre.num_control}: obra hija sin título uniforme (240/130). "
                f"Edita la obra y selecciona el slot correcto en el modal."
            )
            return

        enlace_774 = (
            obra_padre.enlaces_unidades_774
            .filter(encabezamiento_principal=persona_hijo, titulo_id__in=titulo_ids)
            .order_by("pk")
            .first()
        )

        if not enlace_774:
            logger.warning(
                f"[773 sync] Sin slot 774 exacto para {obra_hijo.num_control} "
                f"en {obra_padre.num_control}. "
                f"Edita la obra y selecciona el slot correcto en el modal."
            )
            return

        _asignar_w_774(enlace_774, obra_hijo)

    except Exception as e:
        import logging
        logging.getLogger('marc21').error(
            f"Error en sincronizar_774_al_guardar_773: {e}"
        )


@receiver(post_delete, sender=NumeroControl773)
def limpiar_774_al_borrar_773(sender, instance, **kwargs):
    """
    Al borrar un 773 $w, borra el 774 $w correspondiente en la colección padre.
    Si el 774 queda sin $w y fue creado automáticamente, lo elimina también.
    """
    try:
        obra_hijo  = instance.enlace_773.obra
        obra_padre = instance.obra_relacionada

        enlace_774 = (
            obra_padre.enlaces_unidades_774.filter(
                numeros_control__obra_relacionada=obra_hijo
            )
            .order_by("pk")
            .first()
        )

        if not enlace_774 and getattr(instance, 'enlace_774_id', None):
            enlace_774 = EnlaceUnidadConstituyente774.objects.filter(
                pk=instance.enlace_774_id,
                obra=obra_padre,
            ).first()

        if not enlace_774:
            titulo_ids = _titulos_autoridad_posibles(obra_hijo)
            if titulo_ids and obra_hijo.compositor:
                enlace_774 = (
                    obra_padre.enlaces_unidades_774
                    .filter(
                        encabezamiento_principal=obra_hijo.compositor,
                        titulo_id__in=titulo_ids,
                    )
                    .order_by("pk")
                    .first()
                )

        if enlace_774:
            # Solo borra el $w (NC774), nunca el slot 774 en sí.
            # Los slots son creados manualmente por el catalogador y no deben eliminarse automáticamente.
            enlace_774.numeros_control.filter(obra_relacionada=obra_hijo).delete()

    except Exception:
        pass  # La obra o el enlace ya pueden haber sido eliminados en cascada
