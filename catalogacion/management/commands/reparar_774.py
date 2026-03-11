"""
Comando de reparación de integridad para relaciones 774 $w.

Diagnostica y corrige registros NumeroControl774 cuya obra_relacionada no
corresponde a la obra hija real (la que tiene el 773 $w apuntando a la colección).

Causas habituales del problema:
- Entrada manual incorrecta en el autocomplete del campo 774 $w
- La señal sincronizar_774_al_guardar_773 no limpiaba links previos erróneos

Uso:
    python manage.py reparar_774 [--dry-run] [--coleccion=M000138]

Opciones:
    --dry-run          Muestra qué se corregiría sin modificar la BD
    --coleccion        Limita la reparación a una colección por num_control
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from catalogacion.models import ObraGeneral
from catalogacion.models.bloque_7xx import (
    EnlaceUnidadConstituyente774,
    NumeroControl774,
)


class Command(BaseCommand):
    help = "Repara relaciones 774 $w cuya obra_relacionada no coincide con la obra hija real"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra qué se corregiría, sin modificar la BD",
        )
        parser.add_argument(
            "--coleccion",
            type=str,
            default=None,
            help="Limitar a una colección específica (num_control, ej: M000138)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        coleccion_filtro = options["coleccion"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== MODO DRY-RUN: no se modificará la BD ===\n"))

        # Obtener todos los EnlaceUnidadConstituyente774
        qs = EnlaceUnidadConstituyente774.objects.select_related(
            "obra", "titulo"
        ).prefetch_related("numeros_control__obra_relacionada")

        if coleccion_filtro:
            qs = qs.filter(obra__num_control=coleccion_filtro)
            self.stdout.write(f"Filtrando solo colección: {coleccion_filtro}\n")

        total = qs.count()
        self.stdout.write(f"Total de entradas 774 a analizar: {total}\n")

        corregidos = 0
        huerfanos = 0
        sin_problema = 0

        for e774 in qs:
            titulo_esperado = e774.titulo
            coleccion = e774.obra

            # Buscar la obra hija correcta:
            # debe tener un 773 $w apuntando a esta colección Y su título debe coincidir
            obra_correcta = ObraGeneral.objects.filter(
                activo=True,
                enlaces_documento_fuente_773__numeros_control__obra_relacionada=coleccion,
            ).filter(
                Q(titulo_240=titulo_esperado)
                | Q(titulo_uniforme=titulo_esperado)
                | Q(titulo_principal__iexact=titulo_esperado.titulo)
            ).first()

            # Obtener los numeros_control actuales
            ncs_actuales = list(e774.numeros_control.select_related("obra_relacionada").all())
            tiene_link = len(ncs_actuales) > 0

            if obra_correcta is None:
                if tiene_link:
                    # Tiene link pero no encontramos la obra correcta → huérfano
                    obras_linked = [nc.obra_relacionada.num_control for nc in ncs_actuales]
                    self.stdout.write(
                        self.style.ERROR(
                            f"  HUERFANO | Colección {coleccion.num_control} | "
                            f"774 $t='{titulo_esperado.titulo}' | "
                            f"$w actual={obras_linked} | "
                            f"No se encontró obra hija con 773 coincidente"
                        )
                    )
                    huerfanos += 1
                else:
                    # Sin link y sin obra → entrada 774 sin $w (normal si la obra no está catalogada)
                    sin_problema += 1
                continue

            # Hay obra correcta: verificar si los numeros_control ya apuntan a ella
            ya_correcto = (
                len(ncs_actuales) == 1
                and ncs_actuales[0].obra_relacionada_id == obra_correcta.pk
            )

            if ya_correcto:
                sin_problema += 1
                continue

            # Hay discrepancia
            obras_actuales_str = (
                [nc.obra_relacionada.num_control for nc in ncs_actuales]
                if ncs_actuales else ["(ninguno)"]
            )
            self.stdout.write(
                self.style.WARNING(
                    f"  DISCREPANCIA | Colección {coleccion.num_control} | "
                    f"774 $t='{titulo_esperado.titulo}' | "
                    f"$w actual={obras_actuales_str} | "
                    f"Correcto={obra_correcta.num_control}"
                )
            )

            if not dry_run:
                # Eliminar los links incorrectos
                e774.numeros_control.exclude(obra_relacionada=obra_correcta).delete()
                # Crear el link correcto si no existe
                NumeroControl774.objects.get_or_create(
                    enlace_774=e774,
                    obra_relacionada=obra_correcta,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"    → Corregido: {coleccion.num_control} / "
                        f"'{titulo_esperado.titulo}' → {obra_correcta.num_control}"
                    )
                )

            corregidos += 1

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(f"Sin problema : {sin_problema}")
        self.stdout.write(
            self.style.WARNING(f"Huérfanos    : {huerfanos}  (revisar manualmente)")
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Corregibles  : {corregidos}  (ejecutar sin --dry-run para aplicar)")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Corregidos   : {corregidos}")
            )
