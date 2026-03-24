/**
 * formset-manager.js
 * Gestor centralizado para todos los formsets de Django
 * Maneja agregar/eliminar formularios de manera unificada
 */

(function () {
    "use strict";

    /**
     * Inicializa todos los formsets en la pagina
     */
    function initAllFormsets() {
        console.log('FormsetManager: Inicializando todos los formsets...');

        // Buscar todos los botones de agregar campo y conectarlos
        document
            .querySelectorAll('.campo-add-btn[data-formset-target]')
            .forEach((button) => {
                // Remover TODOS los listeners existentes clonando el boton
                const newButton = button.cloneNode(true);
                button.parentNode.replaceChild(newButton, button);

                const prefix = newButton.dataset.formsetTarget;
                console.log(`FormsetManager: Inicializando boton para prefix "${prefix}"`);

                const container = document.querySelector(
                    `[data-formset-prefix="${prefix}"]`
                );

                if (!container) {
                    console.warn(
                        `FormsetManager: No se encontro contenedor para prefix "${prefix}"`
                    );
                    return;
                }

                const clickHandler = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log(`FormsetManager: Click detectado para prefix "${prefix}"`);
                    addNewForm(prefix);
                };

                newButton.addEventListener('click', clickHandler);
                newButton.dataset.formsetManagerInitialized = 'true';
                console.log(`FormsetManager: Boton inicializado para prefix "${prefix}"`);
            });

        if (!document.body.dataset.formsetDeleteInitialized) {
            document.body.addEventListener('click', handleDeleteClick);
            document.body.dataset.formsetDeleteInitialized = 'true';
        }

        document
            .querySelectorAll('.formset-container[data-formset-prefix]')
            .forEach((container) => refreshInlineAddButton(container));
    }

    /**
     * Agrega un nuevo formulario al formset
     */
    function addNewForm(prefix) {
        console.log(`FormsetManager: Agregando nuevo formulario para prefix "${prefix}"`);

        if (window._formsetAdding && window._formsetAdding[prefix]) {
            console.log(`FormsetManager: Ya se esta agregando para ${prefix}, ignorando...`);
            return;
        }

        if (!window._formsetAdding) window._formsetAdding = {};
        window._formsetAdding[prefix] = true;

        const container = document.querySelector(
            `[data-formset-prefix="${prefix}"]`
        );
        if (!container) {
            window._formsetAdding[prefix] = false;
            return;
        }

        const totalFormsInput = container.querySelector(
            `#id_${prefix}-TOTAL_FORMS`
        );
        const formsContainer = container.querySelector('.formset-forms');
        const emptyFormTemplate = formsContainer?.querySelector('.empty-form');

        if (!totalFormsInput || !formsContainer || !emptyFormTemplate) {
            console.error(
                `FormsetManager: Faltan elementos para prefix "${prefix}"`
            );
            window._formsetAdding[prefix] = false;
            return;
        }

        const totalForms = parseInt(totalFormsInput.value, 10) || 0;
        console.log(`FormsetManager: Formularios actuales: ${totalForms}`);

        const newForm = emptyFormTemplate.cloneNode(true);
        console.log('FormsetManager: Template clonado');

        newForm.innerHTML = newForm.innerHTML.replace(/__prefix__/g, totalForms);
        newForm.classList.remove('empty-form', 'd-none');
        newForm.style.display = '';

        formsContainer.insertBefore(newForm, emptyFormTemplate);

        totalFormsInput.value = totalForms + 1;
        console.log(`FormsetManager: Nuevo total de formularios: ${totalForms + 1}`);

        refreshInlineAddButton(container);

        setTimeout(() => {
            window._formsetAdding[prefix] = false;
        }, 100);

        try {
            const ev = new CustomEvent('formset:added', {
                bubbles: true,
                detail: {
                    prefix,
                    newForm: newForm,
                    totalForms: totalForms + 1,
                },
            });
            container.dispatchEvent(ev);
            console.log(`FormsetManager: Evento formset:added emitido para ${prefix}`, {
                prefix,
                newForm,
                totalForms: totalForms + 1,
            });
        } catch (err) {
            console.warn('FormsetManager: Error al emitir evento formset:added', err);
        }

        focusFirstField(newForm);
    }

    /**
     * Reindexar todos los formularios nuevos (no existentes) de un formset
     * para que los indices sean secuenciales (0, 1, 2...) sin huecos.
     */
    function reindexForms(container, prefix) {
        const formsContainer = container.querySelector('.formset-forms');
        if (!formsContainer) return;

        const allRows = formsContainer.querySelectorAll(
            '.formset-row:not(.empty-form)'
        );

        allRows.forEach((row, index) => {
            const elements = row.querySelectorAll(
                `[name^="${prefix}-"], [id^="id_${prefix}-"]`
            );
            elements.forEach((el) => {
                if (el.name) {
                    el.name = el.name.replace(
                        new RegExp(`${prefix}-\\d+`),
                        `${prefix}-${index}`
                    );
                }
                if (el.id) {
                    el.id = el.id.replace(
                        new RegExp(`id_${prefix}-\\d+`),
                        `id_${prefix}-${index}`
                    );
                }
            });

            const labels = row.querySelectorAll(`[for^="id_${prefix}-"]`);
            labels.forEach((label) => {
                label.setAttribute(
                    'for',
                    label.getAttribute('for').replace(
                        new RegExp(`id_${prefix}-\\d+`),
                        `id_${prefix}-${index}`
                    )
                );
            });

            const dynamicSelectors = [
                'lugar_produccion_264_',
                'entidad_produccion_264_',
                'fecha_produccion_264_',
                'medio_interpretacion_382_',
                'funcion_institucional_710_',
                'url_disponible_856_',
                'texto_disponible_856_',
                'subdivision_materia_650_',
                'subdivision_cronologica_650_',
                'subdivision_genero_655_',
                'volumen_mencion_490_',
                'estanteria_ubicacion_852_',
            ];
            const dynamicSelector = dynamicSelectors
                .map((s) => `[name^="${s}"]`)
                .join(', ');
            const dynamicInputs = row.querySelectorAll(dynamicSelector);
            const funcion700Inputs = row.querySelectorAll('[name^="funcion700-"]');

            dynamicInputs.forEach((el) => {
                el.name = el.name.replace(
                    /^([a-zA-Z_]+\d*_)(\d+)/,
                    `$1${index}`
                );
            });
            funcion700Inputs.forEach((el) => {
                el.name = el.name.replace(
                    /^(funcion700-[^-]*-)(\d+)/,
                    `$1${index}`
                );
            });
        });

        const totalFormsInput = container.querySelector(
            `#id_${prefix}-TOTAL_FORMS`
        );
        if (totalFormsInput) {
            totalFormsInput.value = allRows.length;
        }

        refreshInlineAddButton(container);

        console.log(
            `FormsetManager: Reindexado ${prefix}, total: ${allRows.length}`
        );
    }

    function focusFirstField(row) {
        if (!row) return;

        const firstField = row.querySelector(
            'input:not([type="hidden"]):not([readonly]), select, textarea'
        );

        if (firstField && typeof firstField.focus === 'function') {
            firstField.focus();
        }

        if (typeof row.scrollIntoView === 'function') {
            row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    function isRowMarkedForDelete(row) {
        const deleteCheckbox = row.querySelector('input[name*="DELETE"]');
        return !!(deleteCheckbox && deleteCheckbox.checked);
    }

    function getVisibleRows(container) {
        return Array.from(
            container.querySelectorAll('.formset-row:not(.empty-form)')
        ).filter((row) => !isRowMarkedForDelete(row));
    }

    function createInlineAddButton(prefix) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'inline-add-row-btn';
        button.title = 'Agregar otro registro';
        button.setAttribute('aria-label', 'Agregar otro registro');
        button.innerHTML = '<i class="bi bi-plus-lg"></i>';
        button.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            addNewForm(prefix);
        });
        return button;
    }

    function refreshInlineAddButton(container) {
        if (!container) return;

        const prefix = container.dataset.formsetPrefix;
        const rows = getVisibleRows(container);

        container
            .querySelectorAll('.inline-add-row-btn')
            .forEach((button) => button.remove());

        const lastRow = rows[rows.length - 1];
        if (!lastRow || !prefix) return;

        lastRow.appendChild(createInlineAddButton(prefix));
    }

    /**
     * Maneja clicks en botones de eliminar
     */
    function handleDeleteClick(e) {
        const deleteBtn = e.target.closest('.delete-row-btn');
        if (!deleteBtn) return;

        const row = deleteBtn.closest('.formset-row');
        if (!row || row.classList.contains('empty-form')) return;

        const container = row.closest('.formset-container');
        if (!container) return;

        const prefix = container.dataset.formsetPrefix;
        const deleteCheckbox = row.querySelector('input[name*="DELETE"]');

        if (row.classList.contains('existing-form')) {
            if (deleteCheckbox && deleteCheckbox.checked) {
                deleteCheckbox.checked = false;
                row.style.opacity = '1';
                row.dataset.markedDelete = 'false';
                deleteBtn.classList.remove('btn-warning');
                deleteBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
                deleteBtn.title = 'Eliminar';
            } else if (deleteCheckbox) {
                deleteCheckbox.checked = true;
                row.style.opacity = '0.5';
                row.dataset.markedDelete = 'true';
                deleteBtn.classList.add('btn-warning');
                deleteBtn.innerHTML =
                    '<i class="bi bi-arrow-counterclockwise"></i>';
                deleteBtn.title = 'Cancelar eliminacion';
            }
            refreshInlineAddButton(container);
        } else {
            row.remove();
            reindexForms(container, prefix);
        }
    }

    /**
     * Actualiza la visibilidad de botones de eliminar en subcampos
     */
    function updateSubcampoDeleteVisibility(container) {
        const rows = container.querySelectorAll('.subcampo-row');
        rows.forEach((row) => {
            const deleteBtn = row.querySelector('.subcampo-delete-btn');
            if (deleteBtn) {
                const hasAddButton = row.querySelector('.subcampo-add-btn');
                if (hasAddButton) {
                    deleteBtn.style.visibility = 'hidden';
                } else {
                    deleteBtn.style.visibility = 'visible';
                }
            }
        });
    }

    window.FormsetManager = {
        init: initAllFormsets,
        addNewForm: addNewForm,
        updateSubcampoDeleteVisibility: updateSubcampoDeleteVisibility,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAllFormsets);
    } else {
        initAllFormsets();
    }

    document.addEventListener('htmx:afterSwap', initAllFormsets);
})();
