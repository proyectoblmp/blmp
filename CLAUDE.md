# BLMP — Biblioteca Latinoamericana de Música para Piano

Sistema de catalogación de obras musicales basado en estándar MARC21.

## Stack tecnológico

- **Backend**: Django 5.2, PostgreSQL
- **Frontend**: Bootstrap 5.3.2 + Bootstrap Icons 1.11.1 + Select2 + HTMX
- **Auth**: Email-based login, `AUTH_USER_MODEL = "usuarios.CustomUser"`
- **Zona horaria**: `America/Bogota`
- **Servidor de desarrollo**: `cd blmp && python manage.py runserver`

## Estructura del proyecto

```
blmp/                          ← Raíz Django (BASE_DIR)
├── marc21_project/            ← Configuración del proyecto
│   ├── settings.py
│   └── urls.py                ← URLs raíz
├── templates/                 ← Templates globales (base.html, errors/)
├── usuarios/                  ← Auth, roles, perfiles
├── catalogacion/              ← Catalogación MARC21 (núcleo)
├── catalogo_publico/          ← Interfaz pública (sin login)
└── digitalizacion/            ← Gestión de archivos digitales
```

## Apps y sus responsabilidades

### `usuarios` — Autenticación y roles

**Roles**: `catalogador`, `revisor`, `admin`

**Modelo**: `CustomUser`
- Campos: `email`, `nombre_completo`, `rol`, `tipo_catalogador`, `activo`, `debe_cambiar_password`
- Propiedades: `es_admin`, `es_catalogador`, `es_revisor`, `puede_catalogar`, `puede_revisar`

**Flujo de login**: Login → si `debe_cambiar_password=True` → redirige a `cambiar_password` obligatoriamente.
Tras login: admin→`admin_dashboard`, revisor→`revisor_dashboard`, catalogador→`catalogador_dashboard`.

**Mixins de permisos** (`usuarios/mixins.py`):
- `AdminRequiredMixin`, `CatalogadorRequiredMixin`, `RevisorRequiredMixin`

**URLs** (`/usuarios/`):
```
login/                     → inicio de sesión
logout/
perfil/                    → perfil del usuario autenticado
perfil/cambiar-password/
admin/dashboard/
admin/usuarios/            → CRUD de usuarios (crear, editar, eliminar, toggle-activo, reset-password)
catalogador/dashboard/
revisor/dashboard/
```

**Templates** (cada rol tiene su propio base):
- Admin: `usuarios/admin/base_admin.html` — sidebar oscuro
- Catalogador: `usuarios/catalogador/base_catalogador.html`
- Revisor: `usuarios/revisor/base_revisor.html` — acento verde
- Perfil y cambiar_password usan `{% extends base_template %}` (dinámico por rol)

---

### `catalogacion` — Núcleo MARC21

**Modelo principal**: `ObraGeneral` en `catalogacion/models/obra_general.py`
- Campos MARC21 directos: `tipo_registro` (c=impreso, d=manuscrito), `nivel_bibliografico` (a/c/m), `num_control` (M000001 o I000001), `compositor` (FK a `AutoridadPersona`), `titulo_propio`, `tonalidad`, `forma_musical`, etc.
- Usa `SoftDeleteMixin` — borrado lógico, tiene papelera.
- `NumeroControlSecuencia` — generación atómica de `num_control`.

**Modelos relacionados** (relaciones FK a `ObraGeneral`):
| Archivo | Modelos / Campo MARC21 |
|---|---|
| `bloque_0xx.py` | `IncipitMusical` (031), `IdiomaObra` (041), `CodigoPaisEntidad` |
| `bloque_1xx.py` | `FuncionCompositor` (100) |
| `bloque_2xx.py` | `TituloAlternativo` (246), `ProduccionPublicacion` (264), `Edicion` (250) |
| `bloque_3xx.py` | `MedioInterpretacion382` |
| `bloque_4xx.py` | `MencionSerie490` |
| `bloque_5xx.py` | `NotaGeneral500`, `Contenido505`, `Sumario520`, `DatosBiograficos545` |
| `bloque_6xx.py` | `Materia650`, `MateriaGenero655` y sus subdivisiones |
| `bloque_7xx.py` | `NombreRelacionado700`, `EntidadRelacionada710`, `OtrasRelaciones787`, enlaces 773/774 |
| `bloque_8xx.py` | `Estanteria852`, `URL856` |

**Autoridades** (`catalogacion/models/autoridades.py`):
- `AutoridadPersona`, `AutoridadTituloUniforme`, `AutoridadFormaMusical`, `AutoridadEntidad`, `AutoridadMateria`

**Tipos de obra** (6 tipos en `catalogacion/views/obra_config.py`):
```
coleccion_manuscrita         → tipo_registro=d, nivel_bibliografico=c
obra_en_coleccion_manuscrita → tipo_registro=d, nivel_bibliografico=a
obra_manuscrita_individual   → tipo_registro=d, nivel_bibliografico=m
coleccion_impresa            → tipo_registro=c, nivel_bibliografico=c
obra_en_coleccion_impresa    → tipo_registro=c, nivel_bibliografico=a
obra_impresa_individual      → tipo_registro=c, nivel_bibliografico=m
```

**Borradores**: `BorradorObra` en `catalogacion/models/borradores.py`. Sistema de autoguardado vía AJAX.

**URLs** (`/catalogacion/`):
```
obras/                           → lista_obras
obras/seleccionar-tipo/          → seleccionar_tipo
obras/crear/<tipo>/              → crear_obra
obras/<pk>/                      → detalle_obra
obras/<pk>/editar/               → editar_obra
obras/<pk>/publicar/             → publicar_obra
obras/<pk>/despublicar/          → despublicar_obra
papelera/                        → papelera_obras
borradores/                      → lista_borradores
api/borradores/guardar/          → api_guardar_borrador  (AJAX)
api/borradores/autoguardar/      → api_autoguardar_borrador  (AJAX)
api/obras/buscar/                → api_buscar_obras
api/obras/autocomplete/773/      → api_autocompletado_773
api/compositor/bio-545/          → api_compositor_bio_545
```

**URLs de autoridades** (`/catalogacion/`, namespace `autoridades`):
```
autoridades/personas/            → lista_personas
autoridades/entidades/           → lista_entidades
autoridades/materias/            → lista_materias
autoridades/formas-musicales/    → lista_formas_musicales
autoridades/titulos-uniformes/   → lista_titulos_uniformes
```

**Templates** (`catalogacion/templates/catalogacion/`):
- `base_catalogacion.html` — base de la sección
- `lista_obras.html`, `detalle_obra.html`, `editar_obra.html`, `seleccionar_tipo_obra.html`
- `secciones/` — fragmentos del formulario de edición (una por bloque MARC21)
- `bloques/` — formularios por bloque (bloque_0xx.html … bloque_8xx.html)
- `includes/` — formsets reutilizables (formset_264_template.html, etc.)

**CSS** (`catalogacion/static/catalogacion/css/`):
- `crear-obra.css`, `detalle-obra.css`, `tipo-obra.css`, `styles.css`

**JS** (`catalogacion/static/catalogacion/js/`):
- `borrador-system.js` — sistema de borradores (autoguardado)
- `formset-manager.js` — gestión dinámica de formsets Django
- `compositor-autocomplete.js`, `materias-autocomplete.js`, `titulos-formas-autocomplete.js` — Select2
- `form-validator.js`, `subcampo-validators.js`, `required-fields-tracker.js`
- `incipitManager.js`, `incipitInit.js`, `incipit-031-adapter.js` — editor de íncipit musical

---

### `catalogo_publico` — Interfaz pública

Accesible sin autenticación. Muestra obras con `publicada=True`.

**URLs** (`/`):
```
/                          → home
obras/                     → lista_obras
obras/<pk>/                → detalle (resumen)
obras/<pk>/detalle/        → detalle_obra (vista completa)
obras/<pk>/marc21/         → formato_marc21
obras/<pk>/descargar-pdf/  → descargar_pdf
obras/<pk>/marc-crudo/     → vista_marc_crudo
```

**Templates** (`catalogo_publico/templates/catalogo_publico/`):
- `base_publico.html` — navbar pública (Bootstrap dark navbar)
- `home.html`, `lista_obras.html`, `detalle_obra.html`, `resumen_obra.html`
- `formato_marc21.html`, `vista_marc_crudo.html`

**CSS** (`catalogo_publico/static/catalogo_publico/css/`):
- `publico.css` — estilos principales del catálogo público
- `detalle_obra.css`, `lista-obras.css`, `resumen_obra.css`

---

### `digitalizacion` — Gestión de archivos

**Modelos**:
- `DigitalSet` — OneToOne con `ObraGeneral`. Estados: NUEVO / IMPORTADO / SEGMENTADO. Tipos: COLECCION / OBRA_SUELTA.
- `DigitalPage` — páginas individuales (rutas: source, master, derivative)
- `WorkSegment` — segmentos de una colección (tipos: OBRA / NOTAS / ANEXO / EXCLUIDO)

**URLs** (`/digitalizacion/`):
```
/                          → dashboard
obra/<pk>/                 → obra_home
obra/<pk>/importar/        → importar (TIFF)
obra/<pk>/segmentar/       → segmentar (solo colecciones)
obra/<pk>/visor/           → visor_digital
obra/<pk>/subir-pdf/       → subir_pdf
obra/<pk>/eliminar-pdf/    → eliminar_pdf
obra/<pk>/eliminar-digitalset/ → eliminar_digitalset
```

**Servicios** (`digitalizacion/services/`):
- `pdf_service.py` — manejo de PDFs
- `thumbnail_service.py` — generación de miniaturas

**JS** (`digitalizacion/static/digitalizacion/js/`):
- `segmentar.js` — UI de segmentación por arrastre

---

## Convenciones de templates

### Herencia
Cada sección usa su propio template base:
```django
{# Catálogo público #}
{% extends 'catalogo_publico/base_publico.html' %}

{# Catalogación #}
{% extends 'catalogacion/base_catalogacion.html' %}

{# Panel admin #}
{% extends 'usuarios/admin/base_admin.html' %}

{# Panel catalogador #}
{% extends 'usuarios/catalogador/base_catalogador.html' %}

{# Panel revisor #}
{% extends 'usuarios/revisor/base_revisor.html' %}
```

### Bloques estándar
```django
{% block title %}...{% endblock %}
{% block page_title %}...{% endblock %}
{% block content %}...{% endblock %}
{% block extra_css %}...{% endblock %}
{% block extra_js %}...{% endblock %}
```

### Mensajes Django
Incluir en templates con:
```django
{% include 'includes/messages.html' %}
```

---

## Librerías frontend (CDN)

| Librería | Versión | Uso |
|---|---|---|
| Bootstrap | 5.3.2 | Layout, componentes |
| Bootstrap Icons | 1.11.1 | Iconografía (`bi bi-...`) |
| Select2 | — | Selects con búsqueda y autocomplete |
| HTMX | — | Interactividad sin JS complejo |

Cargar JS de Bootstrap al final del body. Select2 requiere jQuery o su versión standalone.

---

## Archivos estáticos

```
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
```

En desarrollo, los archivos media y static se sirven automáticamente (DEBUG=True).
Cada app tiene su carpeta `static/<app_name>/css/` y `static/<app_name>/js/`.

Usar siempre `{% load static %}` y `{% static 'ruta/archivo.css' %}`.

---

## Base de datos

- **Motor**: PostgreSQL
- **Nombre**: `blmp` (configurable por env var `DB_NAME`)
- **Credenciales**: via variables de entorno en `.env` en la raíz del repo (un nivel arriba de `blmp/`)

Variables de entorno: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`

---

## Comandos útiles

```bash
cd blmp

# Servidor de desarrollo
python manage.py runserver

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Shell interactivo
python manage.py shell

# Limpiar borradores huérfanos
python manage.py limpiar_borradores

# Purgar papelera
python manage.py purgar_papelera

# Generar miniaturas PDF
python manage.py generate_pdf_thumbs
```

---

## Patrones de código frecuentes

### Vista protegida por rol
```python
from usuarios.mixins import CatalogadorRequiredMixin

class MiVista(CatalogadorRequiredMixin, View):
    ...
```

### URL con namespace
```django
{% url 'catalogacion:crear_obra' tipo %}
{% url 'autoridades:lista_personas' %}
{% url 'catalogo_publico:detalle' pk %}
{% url 'digitalizacion:obra_home' pk %}
{% url 'usuarios:catalogador_dashboard' %}
```

### Acceso condicional en template por rol
```django
{% if user.is_authenticated and user.puede_catalogar %}
{% if user.es_admin %}
```

### Formset Django con template dinámico
Los formsets usan plantillas en `catalogacion/templates/catalogacion/includes/formset_XXX_template.html`.
El JS en `formset-manager.js` maneja añadir/eliminar filas dinámicamente clonando el template.

### Autocompletado Select2
Los autocompletes llaman a endpoints en `/catalogacion/autoridades/` que devuelven JSON.
Ver `compositor-autocomplete.js` como referencia del patrón.

---

## Notas importantes para el frontend

- El **catálogo público** es la interfaz más visible: debe ser responsiva, rápida y accesible.
- La **interfaz de catalogación** es densa (formularios MARC21 complejos): priorizar usabilidad sobre estética.
- Los **borradores** se autoguardan cada X segundos vía `borrador-system.js` (AJAX POST).
- El visor de digitalización (`visor_digital`) usa páginas JPG derivadas, no el TIFF original.
- Los **íncipit musicales** (campo 031) tienen su propio editor canvas (`incipitManager.js`).
- Evitar añadir dependencias JS/CSS nuevas sin consenso — ya hay 4 librerías cargadas globalmente.
