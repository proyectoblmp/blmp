"""
Signals para auditoría automática de cambios en ObraGeneral
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .obra_general import ObraGeneral
from .auxiliares import HistorialCambio


def obtener_usuario_actual():
    """
    Obtiene el usuario actual del contexto de la petición.
    En el futuro se puede implementar con middleware.
    """
    # TODO: Implementar con middleware para obtener el usuario de la request
    return "sistema"


def obtener_ip_actual():
    """
    Obtiene la IP actual del contexto de la petición.
    """
    # TODO: Implementar con middleware
    return None


@receiver(post_save, sender=ObraGeneral)
def registrar_cambio_obra(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    """
    Registra automáticamente los cambios en ObraGeneral
    """
    content_type = ContentType.objects.get_for_model(instance)
    
    if created:
        # Registro de creación
        HistorialCambio.objects.create(
            content_type=content_type,
            object_id=instance.pk,
            accion='create',
            usuario=obtener_usuario_actual(),
            ip_address=obtener_ip_actual(),
            valores_completos={
                'num_control': instance.num_control,
                'tipo_registro': instance.tipo_registro,
                'nivel_bibliografico': instance.nivel_bibliografico,
                'titulo_principal': instance.titulo_principal,
                'compositor': str(instance.compositor) if instance.compositor else None,
                'titulo_uniforme': str(instance.titulo_uniforme) if instance.titulo_uniforme else None,
            },
            notas=f"Creación de obra {instance.num_control}"
        )
    else:
        # Registro de modificación
        # En una implementación completa, aquí se compararían los valores anteriores
        # con los nuevos para registrar solo los campos modificados
        HistorialCambio.objects.create(
            content_type=content_type,
            object_id=instance.pk,
            accion='update',
            usuario=obtener_usuario_actual(),
            ip_address=obtener_ip_actual(),
            valores_completos={
                'num_control': instance.num_control,
                'titulo_principal': instance.titulo_principal,
                'fecha_modificacion': str(instance.fecha_modificacion_sistema),
            },
            notas=f"Modificación de obra {instance.num_control}"
        )


@receiver(pre_delete, sender=ObraGeneral)
def registrar_eliminacion_obra(sender, instance, **kwargs):
    """
    Registra cuando se elimina una obra (física o lógicamente)
    """
    content_type = ContentType.objects.get_for_model(instance)
    
    accion = 'delete' if instance.activo else 'restore'
    
    HistorialCambio.objects.create(
        content_type=content_type,
        object_id=instance.pk,
        accion=accion,
        usuario=obtener_usuario_actual(),
        ip_address=obtener_ip_actual(),
        valores_completos={
            'num_control': instance.num_control,
            'titulo_principal': instance.titulo_principal,
            'activo': instance.activo,
        },
        notas=f"Eliminación {'lógica' if not instance.activo else 'física'} de obra {instance.num_control}"
    )
