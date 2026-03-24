"""
Prueba de la bidireccionalidad 773 $w ↔ 774 $w.

Escenarios cubiertos:
  1. Al guardar un 773 $w se crea/vincula el 774 $w en la colección padre.
  2. Si la colección ya tenía un 774 con el mismo $t, no se duplica.
  3. Al borrar el 773 $w se limpia el 774 $w en la colección.
  4. Si el 774 queda sin $w tras el borrado, se elimina el registro completo.

Uso:
    python manage.py probar_774_bidireccional
    python manage.py probar_774_bidireccional --keep   # no borra datos al final
"""
from django.core.management.base import BaseCommand

from catalogacion.models import ObraGeneral, AutoridadPersona, AutoridadTituloUniforme
from catalogacion.models.bloque_7xx import (
    EnlaceDocumentoFuente773,
    NumeroControl773,
    EnlaceUnidadConstituyente774,
    NumeroControl774,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de salida
# ─────────────────────────────────────────────────────────────────────────────

class R:
    OK  = "✅"
    ERR = "❌"
    INF = "ℹ️ "
    SEP = "─" * 60


def _obras_minimas():
    """Crea las autoridades y obras mínimas para los tests."""
    compositor, _ = AutoridadPersona.objects.get_or_create(
        apellidos_nombres="TEST_774, Compositor",
        defaults={"coordenadas_biograficas": "1900-1980"},
    )
    titulo_hijo, _ = AutoridadTituloUniforme.objects.get_or_create(
        titulo="TEST_774 Sonata nº1",
    )

    coleccion, _ = ObraGeneral.objects.get_or_create(
        titulo_principal="TEST_774 Colección",
        defaults={
            "tipo_registro": "d",
            "nivel_bibliografico": "c",
            "compositor": compositor,
        },
    )
    hijo, _ = ObraGeneral.objects.get_or_create(
        titulo_principal="TEST_774 Sonata nº1",
        defaults={
            "tipo_registro": "d",
            "nivel_bibliografico": "a",
            "compositor": compositor,
            "titulo_240": titulo_hijo,
        },
    )
    return coleccion, hijo, compositor, titulo_hijo


def _limpiar(coleccion, hijo):
    """Elimina registros de prueba creados por este comando."""
    hijo.delete()
    coleccion.delete()
    AutoridadTituloUniforme.objects.filter(titulo="TEST_774 Sonata nº1").delete()
    AutoridadPersona.objects.filter(apellidos_nombres="TEST_774, Compositor").delete()


# ─────────────────────────────────────────────────────────────────────────────
# Escenarios
# ─────────────────────────────────────────────────────────────────────────────

def escenario_1(coleccion, hijo, compositor, titulo_hijo, out):
    """Al guardar 773 $w en la obra hijo → se crea/vincula el 774 $w en la colección."""
    out(R.SEP)
    out("Escenario 1: guardar 773 $w dispara 774 $w en la colección")

    # Limpiar estado previo de este escenario
    EnlaceUnidadConstituyente774.objects.filter(obra=coleccion).delete()
    EnlaceDocumentoFuente773.objects.filter(obra=hijo).delete()

    # Crear el enlace 773 en la obra hijo
    enlace_773 = EnlaceDocumentoFuente773.objects.create(obra=hijo)
    NumeroControl773.objects.create(
        enlace_773=enlace_773,
        obra_relacionada=coleccion,
    )
    # La señal sincronizar_774_al_guardar_773 debería haberse disparado

    enlace_774 = EnlaceUnidadConstituyente774.objects.filter(
        obra=coleccion, titulo=titulo_hijo
    ).first()

    if enlace_774 is None:
        out(f"{R.ERR} El 774 NO se creó en la colección")
        return False

    nc_774 = enlace_774.numeros_control.filter(obra_relacionada=hijo).first()
    if nc_774 is None:
        out(f"{R.ERR} El 774 $w NO apunta a la obra hijo")
        return False

    if enlace_774.encabezamiento_principal != compositor:
        out(f"{R.ERR} El 774 $a no coincide con el compositor del hijo")
        return False

    out(f"{R.OK} 774 creado: $a={enlace_774.encabezamiento_principal} / "
        f"$t={enlace_774.titulo} / $w={nc_774.obra_relacionada.num_control}")
    return True


def escenario_2(coleccion, hijo, compositor, titulo_hijo, out):
    """Si ya existe un 774 con el mismo $t, la señal lo reutiliza (no duplica)."""
    out(R.SEP)
    out("Escenario 2: 774 preexistente con el mismo $t → no se duplica")

    # El estado de escenario 1 debe estar activo (773 ya existe)
    count_antes = EnlaceUnidadConstituyente774.objects.filter(obra=coleccion).count()

    # Forzar re-guardado del NumeroControl773 para disparar la señal de nuevo
    nc773 = NumeroControl773.objects.filter(
        enlace_773__obra=hijo,
        obra_relacionada=coleccion,
    ).first()
    if nc773:
        nc773.save()  # dispara la señal otra vez

    count_despues = EnlaceUnidadConstituyente774.objects.filter(obra=coleccion).count()

    if count_despues != count_antes:
        out(f"{R.ERR} Se duplicó el 774: había {count_antes}, ahora hay {count_despues}")
        return False

    out(f"{R.OK} Sin duplicados: sigue habiendo {count_despues} entrada(s) 774")
    return True


def escenario_3(coleccion, hijo, titulo_hijo, out):
    """Al borrar el 773 $w → se limpia el 774 $w en la colección."""
    out(R.SEP)
    out("Escenario 3: borrar 773 $w → limpia el 774 $w")

    nc773 = NumeroControl773.objects.filter(
        enlace_773__obra=hijo,
        obra_relacionada=coleccion,
    ).first()
    if not nc773:
        out(f"{R.ERR} No se encontró el NumeroControl773 para borrar")
        return False

    nc773.delete()  # dispara limpiar_774_al_borrar_773

    nc774 = NumeroControl774.objects.filter(
        enlace_774__obra=coleccion,
        obra_relacionada=hijo,
    ).first()

    if nc774 is not None:
        out(f"{R.ERR} El 774 $w sigue existiendo tras borrar el 773")
        return False

    out(f"{R.OK} 774 $w eliminado correctamente de la colección")
    return True


def escenario_4(coleccion, titulo_hijo, out):
    """Si el 774 queda sin $w, se elimina el registro EnlaceUnidadConstituyente774."""
    out(R.SEP)
    out("Escenario 4: 774 sin $w tras el borrado → se elimina el registro completo")

    enlace_774 = EnlaceUnidadConstituyente774.objects.filter(
        obra=coleccion, titulo=titulo_hijo
    ).first()

    if enlace_774 is not None:
        tiene_ncs = enlace_774.numeros_control.exists()
        if tiene_ncs:
            out(f"{R.ERR} El EnlaceUnidadConstituyente774 tiene $w y debería estar vacío")
            return False
        else:
            out(f"{R.ERR} El registro 774 existe pero sin $w (debería haberse eliminado)")
            return False

    out(f"{R.OK} Registro EnlaceUnidadConstituyente774 eliminado correctamente")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Command
# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Prueba la bidireccionalidad 773 $w ↔ 774 $w con datos de prueba temporales"

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep",
            action="store_true",
            help="No eliminar los datos de prueba al finalizar",
        )

    def handle(self, *args, **options):
        out = self.stdout.write
        keep = options["keep"]

        out("\n" + "=" * 60)
        out("PRUEBA: Bidireccionalidad 773 $w ↔ 774 $w")
        out("=" * 60 + "\n")

        coleccion, hijo, compositor, titulo_hijo = _obras_minimas()
        out(f"{R.INF} Colección : {coleccion.num_control} ({coleccion.titulo_principal})")
        out(f"{R.INF} Obra hijo : {hijo.num_control} ({hijo.titulo_principal})\n")

        resultados = []
        try:
            resultados.append(escenario_1(coleccion, hijo, compositor, titulo_hijo, out))
            resultados.append(escenario_2(coleccion, hijo, compositor, titulo_hijo, out))
            resultados.append(escenario_3(coleccion, hijo, titulo_hijo, out))
            resultados.append(escenario_4(coleccion, titulo_hijo, out))
        finally:
            if not keep:
                _limpiar(coleccion, hijo)
                out(f"\n{R.INF} Datos de prueba eliminados (usa --keep para conservarlos)")

        out("\n" + "=" * 60)
        aprobados = sum(1 for r in resultados if r)
        total = len(resultados)
        if aprobados == total:
            out(self.style.SUCCESS(f"Resultado: {aprobados}/{total} escenarios OK"))
        else:
            out(self.style.ERROR(f"Resultado: {aprobados}/{total} escenarios OK"))
        out("=" * 60 + "\n")
