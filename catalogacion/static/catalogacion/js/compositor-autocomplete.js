/**
 * Autocomplete editable para campo Compositor (100 $a)
 * Basado en helper general CatalogacionAutocomplete
 */

(function () {
    "use strict";

    const compositorInput = document.getElementById("id_compositor_texto");
    const coordenadasInput = document.getElementById(
        "id_compositor_coordenadas"
    );
    const compositorIdInput = document.getElementById("id_compositor");
    const suggestionsContainer = document.getElementById(
        "compositor-suggestions"
    );

    if (
        !compositorInput ||
        !suggestionsContainer ||
        !window.CatalogacionAutocomplete
    ) {
        console.warn("Compositor autocomplete: dependencias no disponibles");
        return;
    }

    if (compositorIdInput && compositorIdInput.value) {
        prefillCompositor(compositorIdInput.value);
    }

    CatalogacionAutocomplete.setup({
        input: compositorInput,
        hiddenInput: compositorIdInput,
        suggestionsContainer,
        endpoint: "/catalogacion/api/autocompletar/persona/",
        transformResults: (data) =>
            (data?.results || []).map((item) => ({
                id: item.id,
                label: item.apellidos_nombres,
                sublabel: item.coordenadas_biograficas,
                raw: item,
            })),
        renderItem: (item) => {
            const sub = item.sublabel
                ? `<small class="text-muted">${escapeHtml(
                      item.sublabel
                  )}</small>`
                : "";
            return `<strong>${escapeHtml(item.label)}</strong>${sub}`;
        },
        renderCreateItem: (query) =>
            `<strong>Crear nuevo:</strong> “${escapeHtml(query)}”`,
        onSelect: (item, elements) => {
            elements.input.value = item.label;
            if (elements.hiddenInput) {
                elements.hiddenInput.value = item.id || "";
            }
            if (coordenadasInput) {
                coordenadasInput.value =
                    item.raw?.coordenadas_biograficas || "";
            }
            // Limpiar 545 al cambiar de compositor para que siempre se intente
            // auto-llenar con los datos del nuevo compositor seleccionado
            const bio545prev = document.querySelector(
                '[data-formset-prefix="biograficos_545"] textarea[name*="texto_biografico"]'
            );
            const uri545prev = document.querySelector(
                '[data-formset-prefix="biograficos_545"] input[name*="uri"]'
            );
            if (bio545prev) bio545prev.value = "";
            if (uri545prev) uri545prev.value = "";
            if (item.id) llenarBio545(item.id);
        },
        onCreate: (query, elements) => {
            elements.input.value = query;
            if (elements.hiddenInput) {
                elements.hiddenInput.value = "";
            }
            if (coordenadasInput) {
                coordenadasInput.value = "";
            }
        },
        onClear: (elements) => {
            if (elements.hiddenInput) {
                elements.hiddenInput.value = "";
            }
            if (coordenadasInput) {
                coordenadasInput.value = "";
            }
        },
    });

    function prefillCompositor(id) {
        fetch(`/catalogacion/api/autocompletar/persona/?id=${id}`)
            .then((response) => response.json())
            .then((data) => {
                const compositor = data?.results?.[0];
                if (!compositor) {
                    return;
                }
                compositorInput.value = compositor.apellidos_nombres;
                if (coordenadasInput) {
                    coordenadasInput.value =
                        compositor.coordenadas_biograficas || "";
                }
                // Notificar al tracker de campos obligatorios
                // Solo dispatch "change" (no "input" para no disparar búsqueda de autocomplete)
                compositorInput.dispatchEvent(new Event("change", { bubbles: true }));
                if (window.RequiredFieldsTracker) {
                    window.RequiredFieldsTracker.updateProgress();
                }
            })
            .catch((error) =>
                console.error("Error al precargar compositor", error)
            );
    }

    function llenarBio545(compositorId) {
        const bio545 = document.querySelector(
            '[data-formset-prefix="biograficos_545"] textarea[name*="texto_biografico"]'
        );
        const uri545 = document.querySelector(
            '[data-formset-prefix="biograficos_545"] input[name*="uri"]'
        );
        if (!bio545) return;

        fetch(`/catalogacion/api/compositor/bio-545/?compositor_id=${compositorId}`)
            .then(r => r.json())
            .then(data => {
                if (!data.success || !data.datos) return;
                bio545.value = data.datos.texto_biografico || '';
                if (uri545 && data.datos.uri) uri545.value = data.datos.uri;
            })
            .catch(err => console.warn('[545 auto-fill]', err));
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text || "";
        return div.innerHTML;
    }
})();
