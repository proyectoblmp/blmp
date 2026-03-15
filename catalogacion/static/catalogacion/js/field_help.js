/**
 * field_help.js
 * Sistema de ayuda dinámica para campos MARC21
 * Los textos de ayuda se cargan desde field_help_texts.json
 */

(function () {
    "use strict";

    // Cache de textos de ayuda
    let helpTexts = null;

    /**
     * Carga los textos de ayuda desde el archivo JSON
     */
    async function loadHelpTexts() {
        if (helpTexts) return helpTexts;

        try {
            const basePath =
                document.querySelector('script[src*="field_help.js"]')?.src ||
                "";
            const jsonPath = basePath.replace(
                "field_help.js",
                "field_help_texts.json"
            );

            const response = await fetch(jsonPath);
            if (!response.ok)
                throw new Error("No se pudo cargar el archivo de ayuda");

            helpTexts = await response.json();
            return helpTexts;
        } catch (error) {
            console.warn("Error cargando textos de ayuda:", error);
            return { campos: {} };
        }
    }

    /**
     * Obtiene el texto de ayuda para un campo específico
     */
    function getHelpText(fieldCode) {
        if (!helpTexts || !helpTexts.campos || !helpTexts.campos[fieldCode]) {
            return "";
        }
        return helpTexts.campos[fieldCode].ayuda || "";
    }

    /**
     * Inicializa los tooltips de ayuda
     */
    async function initHelpTooltips() {
        await loadHelpTexts();

        const helpButtons = document.querySelectorAll(".campo-help-btn");

        helpButtons.forEach((btn) => {
            const fieldCode = btn.getAttribute("data-field-code");
            if (!fieldCode) return;

            // Click: abrir modal dinámico con el contenido del JSON o formulario si data-help-mode="form"
            btn.addEventListener('click', async function (e) {
                e.stopPropagation();
                const code = btn.getAttribute('data-field-code');
                const subfield = btn.getAttribute('data-subfield');
                const helpMode = btn.getAttribute('data-help-mode');
                await loadHelpTexts();

                if (helpMode === 'form') {
                    openHelpFormModal(code);
                } else {
                    openHelpModal(code, subfield);
                }
            });
        });
    }

    /**
     * Abre el modal de ayuda existente (#helpModal) y rellena contenido dinámico
     */
    function openHelpModal(fieldCode, subfield) {
        if (!helpTexts || !helpTexts.campos) return;
        const entry = helpTexts.campos[fieldCode] || null;

        const modal = document.getElementById('helpModal');
        if (!modal) return;

        const titleEl = modal.querySelector('#helpModalLabel');
        const bodyEl = modal.querySelector('.modal-body');

        const title = (entry && entry.titulo) ? entry.titulo : ('Campo ' + fieldCode);
        titleEl.textContent = title;

        let html = '';
        if (entry) {
            if (subfield && entry.subfields && entry.subfields[subfield]) {
                html += '<div class="mb-2"><strong>Subcampo $' + subfield + '</strong></div>';
                html += '<div class="small">' + entry.subfields[subfield].replace(/\n/g, '<br>') + '</div>';
            } else {
                if (entry.ayuda) html += '<div class="small mb-2">' + entry.ayuda.replace(/\n/g, '<br>') + '</div>';
                if (entry.subfields) {
                    html += '<h6>Subcampos</h6><ul class="small">';
                    for (const k in entry.subfields) {
                        html += '<li><strong>$' + k + '</strong>: ' + entry.subfields[k] + '</li>';
                    }
                    html += '</ul>';
                }
            }
        } else {
            html = '<div class="small text-muted">Información de ayuda no disponible para el campo ' + fieldCode + '.</div>';
        }

        bodyEl.innerHTML = html;

        try {
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
        } catch (err) {
            console.warn('Bootstrap modal no disponible o error al abrir modal:', err);
        }
    }

    /**
     * Abre el modal con un formulario vacío (sin insertar subcampos en el formset).
     * Útil para mostrar un área de notas/ejemplo cuando el usuario pulsa el botón de ayuda en cabecera.
     */
    function openHelpFormModal(fieldCode) {
        const modal = document.getElementById('helpModal');
        if (!modal) return;

        const titleEl = modal.querySelector('#helpModalLabel');
        const bodyEl = modal.querySelector('.modal-body');

        const entry = (helpTexts && helpTexts.campos && helpTexts.campos[fieldCode]) ? helpTexts.campos[fieldCode] : null;
        const title = entry && entry.titulo ? entry.titulo : ('Campo ' + fieldCode);
        titleEl.textContent = title;

        // generar placeholder a partir del texto de ayuda si está disponible
        let placeholderText = 'Escriba aquí una nota o descripción...';
        if (entry) {
            if (entry.ayuda && entry.ayuda.trim()) {
                placeholderText = entry.ayuda.replace(/\n+/g, ' ').trim();
            } else if (entry.subfields && entry.subfields.a) {
                placeholderText = entry.subfields.a.replace(/\n+/g, ' ').trim();
            }
            // acortar si es demasiado largo
            if (placeholderText.length > 800) placeholderText = placeholderText.slice(0, 800) + '...';
        }

        bodyEl.innerHTML = `
            <form id="helpForm_${fieldCode}">
                <div class="mb-3">
                    <label class="form-label">Nota rápida</label>
                    <textarea id="helpFormTextarea_${fieldCode}" class="form-control" rows="12" placeholder="${placeholderText}"></textarea>
                </div>
               
            </form>
        `;

        // Prefill the textarea with the help text (prefer subfields.a if available)
        try {
            const ta = bodyEl.querySelector(`#helpFormTextarea_${fieldCode}`);
            if (ta) {
                let prefill = '';
                if (entry) {
                    if (entry.subfields && entry.subfields.a) prefill = entry.subfields.a;
                    else if (entry.ayuda) prefill = entry.ayuda;
                }
                // If still empty, leave as placeholder only
                if (prefill && prefill.length) ta.value = prefill;
            }
        } catch (err) {
            console.warn('Error prellenando textarea de ayuda:', err);
        }

        try {
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
        } catch (err) {
            console.warn('Bootstrap modal no disponible o error al abrir modal:', err);
        }
    }

    /**
     * Actualiza los textos de ayuda (útil si se cargan dinámicamente nuevos campos)
     */
    function refreshHelpTooltips() {
        initHelpTooltips();
    }

    // Inicializar cuando el DOM esté listo
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initHelpTooltips);
    } else {
        initHelpTooltips();
    }

    // Exponer función para refrescar tooltips
    window.refreshFieldHelp = refreshHelpTooltips;

    // Observador para detectar cambios dinámicos en el DOM
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            if (mutation.addedNodes.length) {
                const hasNewHelpBtns = Array.from(mutation.addedNodes).some(
                    (node) =>
                        node.nodeType === 1 &&
                        (node.classList?.contains("campo-help-btn") ||
                            node.querySelector?.(".campo-help-btn"))
                );
                if (hasNewHelpBtns) {
                    initHelpTooltips();
                    break;
                }
            }
        }
    });

    // Observar cambios en el contenido principal
    document.addEventListener("DOMContentLoaded", () => {
        const mainContent = document.querySelector("main") || document.body;
        observer.observe(mainContent, { childList: true, subtree: true });
    });

    // Listener delegado: garantizar que clicks en botones de ayuda abran el modal
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.campo-help-btn');
        if (!btn) return;

        e.stopPropagation();
        const code = btn.getAttribute('data-field-code');
        const subfield = btn.getAttribute('data-subfield');
        const helpMode = btn.getAttribute('data-help-mode');

        loadHelpTexts().then(() => {
            if (helpMode === 'form') {
                openHelpFormModal(code);
            } else {
                openHelpModal(code, subfield);
            }
        }).catch(err => {
            console.warn('Error cargando textos de ayuda (delegado):', err);
            // intentar abrir modal aunque no haya textos
            if (helpMode === 'form') openHelpFormModal(code);
            else openHelpModal(code, subfield);
        });
    });
})();
