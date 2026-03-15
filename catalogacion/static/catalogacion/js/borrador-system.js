/**
 * Sistema de Borradores para Obras MARC21
 * VERSION REFACTORIZADA - Arquitectura limpia y mantenible
 *
 * ARQUITECTURA:
 * - Serialización: Captura TODOS los inputs del formulario tal cual están
 * - Restauración: Crea las filas necesarias y llena los valores en orden
 *
 * FORMATOS DE CAMPOS:
 * 1. Campos simples: name="campo" -> valor directo
 * 2. Formsets Django: name="prefix-N-campo" -> por fila
 * 3. Subcampos repetibles: name="tipo_subtipo_parentIndex_timestamp" -> dinámicos
 */

(function () {
  "use strict";

  // ========================================
  // CONFIGURACIÓN
  // ========================================
  const CONFIG = {
    AUTOSAVE_INTERVAL: 60000, // 60 segundos
    MIN_CHANGE_DELAY: 3000, // 3 segundos después del último cambio
    ROW_ADD_DELAY: 100, // Delay entre agregar filas
    SUBCAMPO_ADD_DELAY: 50, // Delay entre agregar subcampos
  };

  const API_URLS = {
    guardar: "/catalogacion/api/borradores/guardar/",
    autoguardar: "/catalogacion/api/borradores/autoguardar/",
    obtener: (id) => `/catalogacion/api/borradores/${id}/`,
    obtenerUltimoPorObra: (obraId) =>
      `/catalogacion/api/borradores/obra/${obraId}/ultimo/`,
    eliminar: (id) => `/catalogacion/api/borradores/${id}/eliminar/`,
    limpiarSesion: "/catalogacion/api/borradores/limpiar-sesion/",
    buscarObras: "/catalogacion/api/buscar-obras/",
  };

  // ========================================
  // ESTADO
  // ========================================
  let state = {
    borradorId: null,
    autoSaveTimer: null,
    changeTimer: null,
    hasUnsavedChanges: false,
    allowNativeReload: false,
    allowUnloadOnce: false,
    isPublishing: false,
  };

  const form = document.getElementById("obra-form");

  // Si no hay formulario, no inicializar
  if (!form) return;

  // ========================================
  // UTILIDADES
  // ========================================

  function getCsrfToken() {
    // Leer de la cookie (siempre actualizada) con fallback al input hidden
    const cookieMatch = document.cookie.match(/csrftoken=([^;]+)/);
    if (cookieMatch) return cookieMatch[1];
    const token = document.querySelector('[name="csrfmiddlewaretoken"]');
    return token ? token.value : "";
  }

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function getTipoObra() {
    const tipoRegistro = document.getElementById("id_tipo_registro")?.value;
    const nivelBibliografico = document.getElementById(
      "id_nivel_bibliografico",
    )?.value;

    if (!tipoRegistro || !nivelBibliografico) return null;

    const mapa = {
      d_c: "coleccion_manuscrita",
      d_a: "obra_en_coleccion_manuscrita",
      d_m: "obra_manuscrita_individual",
      c_c: "coleccion_impresa",
      c_a: "obra_en_coleccion_impresa",
      c_m: "obra_impresa_individual",
    };

    return mapa[`${tipoRegistro}_${nivelBibliografico}`] || "desconocido";
  }

  function getObraObjetivoId() {
    const match = window.location.pathname.match(/\/obras\/(\d+)\/editar\/?$/);
    return match ? parseInt(match[1], 10) : null;
  }

  // ========================================
  // SERIALIZACIÓN (Guardar)
  // ========================================

  /**
   * Serializa el formulario en un formato estructurado:
   * {
   *   campos: { "name": "value" | ["value1", "value2"] },
   *   formsets: { "prefix": { count: N, rows: [ {campo: valor, ...}, ... ] } },
   *   subcampos: { "groupKey_parentIndex": [ {value, name}, ... ] }
   * }
   */
  function serializarFormulario() {
    const formData = new FormData(form);
    const result = {
      campos: {},
      formsets: {},
      subcampos: {},
    };

    // Patterns para identificar tipos de campos
    const formsetPattern = /^([a-z_]+)-(\d+)-(.+)$/;
    const subcampoPattern4 = /^(\w+)_(\w+)_(\d+)_(\d+)$/; // tipo_subtipo_parent_ts
    const subcampoPattern5 = /^(\w+)_(\w+)_(\d+)_(\d+)_(\d+)$/; // tipo_subtipo_campo_parent_ts

    for (const [name, value] of formData.entries()) {
      if (!name || name.includes("NaN")) continue;

      const strValue = String(value).trim();

      // 1) Intentar subcampo de 5 partes
      let match = name.match(subcampoPattern5);
      if (match) {
        const [, tipo, subtipo, campo, parentIndex] = match;
        const groupKey = `${tipo}_${subtipo}_${campo}_${parentIndex}`;
        if (strValue) {
          // Solo guardar si tiene valor
          if (!result.subcampos[groupKey]) result.subcampos[groupKey] = [];
          result.subcampos[groupKey].push({ value: strValue, name });
        }
        continue;
      }

      // 2) Intentar subcampo de 4 partes
      match = name.match(subcampoPattern4);
      if (match) {
        const [, tipo, subtipo, parentIndex] = match;
        const groupKey = `${tipo}_${subtipo}_${parentIndex}`;
        if (strValue) {
          // Solo guardar si tiene valor
          if (!result.subcampos[groupKey]) result.subcampos[groupKey] = [];
          result.subcampos[groupKey].push({ value: strValue, name });
        }
        continue;
      }

      // 3) Intentar formset Django
      match = name.match(formsetPattern);
      if (match) {
        const [, prefix, indexStr, field] = match;
        const index = parseInt(indexStr, 10);

        if (!result.formsets[prefix]) {
          result.formsets[prefix] = { count: 0, rows: [] };
        }

        // Asegurar que existe la fila
        while (result.formsets[prefix].rows.length <= index) {
          result.formsets[prefix].rows.push({});
        }

        result.formsets[prefix].rows[index][field] = value;
        result.formsets[prefix].count = Math.max(
          result.formsets[prefix].count,
          index + 1,
        );
        continue;
      }

      // 4) Campo simple
      if (result.campos.hasOwnProperty(name)) {
        // Convertir a array si hay múltiples valores
        if (!Array.isArray(result.campos[name])) {
          result.campos[name] = [result.campos[name]];
        }
        result.campos[name].push(value);
      } else {
        result.campos[name] = value;
      }
    }

    // Incluir checkboxes no marcados
    form.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      if (!cb.checked && !result.campos.hasOwnProperty(cb.name)) {
        result.campos[cb.name] = "";
      }
    });

    // Limpiar filas vacías de formsets (DELETE=on o sin datos reales)
    for (const prefix of Object.keys(result.formsets)) {
      const fs = result.formsets[prefix];
      fs.rows = fs.rows.filter((row, idx) => {
        // Si está marcado para eliminar, excluir
        if (row.DELETE === "on") return false;

        // Si solo tiene campos de management, excluir
        const realFields = Object.keys(row).filter(
          (k) => !["id", "DELETE", "ORDER"].includes(k),
        );
        const hasRealData = realFields.some((k) => {
          const v = row[k];
          return v && String(v).trim() !== "";
        });

        return hasRealData;
      });
      fs.count = fs.rows.length;
    }

    return result;
  }

  // ========================================
  // RESTAURACIÓN (Cargar)
  // ========================================

  /**
   * Restaura el formulario desde los datos guardados
   */
  async function restaurarFormulario(datos) {
    if (!datos) return;

    // Compatibilidad: convertir formato antiguo si es necesario
    const normalized = normalizarDatos(datos);

    // 1. Restaurar campos simples
    restaurarCamposSimples(normalized.campos);

    // 2. Restaurar formsets (crear filas y llenar)
    await restaurarFormsets(normalized.formsets);

    // 3. Restaurar subcampos repetibles
    await restaurarSubcampos(normalized.subcampos);

    // 4. Rehidratar campos derivados (ej: enlaces 773/774/787)
    await rehidratarEnlacesObras();
  }

  /**
   * Convierte formato antiguo (_campos_simples, _formsets, _subcampos_dinamicos)
   * al nuevo formato (campos, formsets, subcampos)
   */
  function normalizarDatos(datos) {
    // Si ya tiene el nuevo formato
    if (datos.campos && datos.formsets && datos.subcampos) {
      return datos;
    }

    // Convertir desde formato antiguo
    const result = {
      campos: {},
      formsets: {},
      subcampos: {},
    };

    // Campos simples
    const camposAntiguos = datos._campos_simples || datos.campos || {};
    for (const [name, value] of Object.entries(camposAntiguos)) {
      result.campos[name] = value;
    }

    // Formsets: convertir de { prefix: { "0": {campo: valor}, "1": {...} } }
    // a { prefix: { count: N, rows: [{campo: valor}, ...] } }
    const formsetsAntiguos = datos._formsets || {};
    for (const prefix of Object.keys(formsetsAntiguos)) {
      const oldFormat = formsetsAntiguos[prefix];
      const indices = Object.keys(oldFormat)
        .filter((k) => k !== "_total" && !isNaN(parseInt(k, 10)))
        .map((k) => parseInt(k, 10))
        .sort((a, b) => a - b);

      result.formsets[prefix] = {
        count: indices.length,
        rows: indices.map((i) => oldFormat[String(i)] || {}),
      };
    }

    // Subcampos dinámicos: convertir de { key: [{value, tipo, subtipo, parentIndex}, ...] }
    // a { groupKey: [{value, name}, ...] }
    const subcamposAntiguos = datos._subcampos_dinamicos || {};
    for (const key of Object.keys(subcamposAntiguos)) {
      const items = subcamposAntiguos[key];
      if (!items || !items.length) continue;

      // Extraer groupKey del key o del primer item
      const first = items[0];
      let groupKey;
      if (first.campo) {
        groupKey = `${first.tipo}_${first.subtipo}_${first.campo}_${first.parentIndex}`;
      } else {
        groupKey = `${first.tipo}_${first.subtipo}_${first.parentIndex}`;
      }

      result.subcampos[groupKey] = items
        .filter((it) => it.value && String(it.value).trim())
        .map((it) => ({ value: it.value, name: null }));
    }

    return result;
  }

  /**
   * Restaura campos simples (no formsets, no subcampos)
   */
  function restaurarCamposSimples(campos) {
    for (const [name, value] of Object.entries(campos)) {
      // Ignorar management forms de formsets
      if (name.includes("-TOTAL_FORMS") || name.includes("-INITIAL_FORMS")) {
        continue;
      }

      // Ignorar campos que parecen de formset
      if (/^[a-z_]+-\d+-/.test(name)) continue;

      const inputs = form.querySelectorAll(`[name="${name}"]`);
      if (!inputs.length) continue;

      if (Array.isArray(value)) {
        inputs.forEach((input, i) => {
          if (i < value.length) setInputValue(input, value[i]);
        });
      } else {
        inputs.forEach((input) => setInputValue(input, value));
      }
    }
  }

  /**
   * Restaura formsets: crea las filas necesarias y llena los valores
   */
  async function restaurarFormsets(formsets) {
    for (const [prefix, data] of Object.entries(formsets)) {
      const container = document.querySelector(
        `[data-formset-prefix="${prefix}"]`,
      );
      if (!container) continue;

      const { rows } = data;
      if (!rows || !rows.length) continue;

      // Contar filas actuales (excluyendo empty-form)
      const currentRows = container.querySelectorAll(
        ".formset-row:not(.empty-form)",
      );
      let currentCount = currentRows.length;

      // Crear filas adicionales si es necesario
      while (currentCount < rows.length) {
        const added = await agregarFilaFormset(prefix, container);
        if (!added) break;
        currentCount++;
        await delay(CONFIG.ROW_ADD_DELAY);
      }

      // Llenar cada fila con sus datos
      for (let i = 0; i < rows.length; i++) {
        const rowData = rows[i];
        for (const [field, value] of Object.entries(rowData)) {
          if (["id", "DELETE", "ORDER"].includes(field)) continue;

          const inputName = `${prefix}-${i}-${field}`;
          const input = form.querySelector(`[name="${inputName}"]`);
          if (input) {
            setInputValue(input, value);
          }
        }
      }
    }
  }

  /**
   * Agrega una fila a un formset usando el mecanismo del proyecto
   */
  async function agregarFilaFormset(prefix, container) {
    // Opción 1: FormsetManager (mecanismo oficial)
    if (window.FormsetManager?.addNewForm) {
      window.FormsetManager.addNewForm(prefix);
      return true;
    }

    // Opción 2: Botón en el header
    const headerBtn = document.querySelector(
      `.campo-add-btn[data-formset-target="${prefix}"]`,
    );
    if (headerBtn) {
      headerBtn.click();
      return true;
    }

    // Opción 3: Botón dentro del contenedor
    const localBtn = container?.querySelector(".add-form-row");
    if (localBtn) {
      localBtn.click();
      return true;
    }

    console.warn(`No se pudo agregar fila para formset "${prefix}"`);
    return false;
  }

  /**
   * Restaura subcampos repetibles usando el contrato data-borrador-*
   */
  async function restaurarSubcampos(subcampos) {
    // Agrupar por groupKey base (sin el parentIndex al final)
    // para poder aplicar el remapeo de índices
    const grouped = new Map();

    for (const [fullKey, items] of Object.entries(subcampos)) {
      if (!items || !items.length) continue;

      // Extraer groupKey base y parentIndex del fullKey
      // fullKey puede ser: "tipo_subtipo_parentIndex" o "tipo_subtipo_campo_parentIndex"
      const parts = fullKey.split("_");
      const parentIndex = parseInt(parts.pop(), 10);
      const groupKey = parts.join("_");

      if (isNaN(parentIndex)) continue;

      if (!grouped.has(groupKey)) {
        grouped.set(groupKey, new Map());
      }
      grouped.get(groupKey).set(parentIndex, items);
    }

    // Para cada grupo, aplicar los valores
    for (const [groupKey, parentMap] of grouped.entries()) {
      // Obtener índices ordenados y crear remapeo
      const oldIndices = Array.from(parentMap.keys()).sort((a, b) => a - b);
      const indexRemap = new Map();
      oldIndices.forEach((oldIdx, newIdx) => indexRemap.set(oldIdx, newIdx));

      // Restaurar cada parentIndex
      for (const [oldParentIndex, items] of parentMap.entries()) {
        const newParentIndex = indexRemap.get(oldParentIndex);

        // Buscar contenedor y botón usando data-borrador-*
        const container = document.querySelector(
          `[data-borrador-container="${groupKey}"][data-borrador-parent="${newParentIndex}"]`,
        );
        const addButton = document.querySelector(
          `[data-borrador-add="${groupKey}"][data-borrador-parent="${newParentIndex}"]`,
        );

        if (!container || !addButton) {
          console.warn(
            `No se encontró contenedor para ${groupKey} parent=${newParentIndex}`,
          );
          continue;
        }

        // Obtener filas existentes
        let rows = getSubcampoRows(container);

        // Llenar filas existentes primero, crear nuevas si faltan
        for (let i = 0; i < items.length; i++) {
          const item = items[i];

          if (i < rows.length) {
            // Usar fila existente
            setSubcampoRowValue(rows[i], item.value);
          } else {
            // Crear nueva fila
            addButton.click();
            await delay(CONFIG.SUBCAMPO_ADD_DELAY);
            rows = getSubcampoRows(container);
            const newRow = rows[rows.length - 1];
            if (newRow) {
              setSubcampoRowValue(newRow, item.value);
            }
          }
        }
      }
    }
  }

  /**
   * Obtiene las filas de subcampos visibles de un contenedor
   */
  function getSubcampoRows(container) {
    return Array.from(container.querySelectorAll(".subcampo-row:not(.d-none)"));
  }

  /**
   * Establece el valor de una fila de subcampo
   */
  function setSubcampoRowValue(row, value) {
    const input = row.querySelector("input, select, textarea");
    if (input) {
      setInputValue(input, value);
    }
  }

  /**
   * Establece el valor de cualquier tipo de input
   */
  function setInputValue(input, value) {
    if (input.type === "checkbox") {
      input.checked = value === "on" || value === true || value === "true";
    } else if (input.type === "radio") {
      input.checked = input.value === value;
    } else if (input.tagName === "SELECT") {
      input.value = value || "";
      // Trigger Select2 si existe
      if (window.$ && $(input).data("select2")) {
        $(input).val(value).trigger("change");
      }
    } else {
      input.value = value || "";
    }

    // Disparar eventos para validadores y otros listeners
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  /**
   * Rehidrata los campos de enlaces a obras relacionadas (773/774/787)
   * El hidden tiene el ID de la obra, el visible debe mostrar el num_control
   */
  async function rehidratarEnlacesObras() {
    const hiddenInputs = form.querySelectorAll(
      'input.obra-relacionada-id-input[name^="w_"]',
    );
    if (!hiddenInputs.length) return;

    const cache = new Map();

    async function resolverNumControl(id) {
      if (!id) return null;
      if (cache.has(id)) return cache.get(id);

      try {
        const resp = await fetch(
          `${API_URLS.buscarObras}?id=${encodeURIComponent(id)}`,
        );
        const data = await resp.json();
        const num = data?.results?.[0]?.num_control || null;
        cache.set(id, num);
        return num;
      } catch {
        cache.set(id, null);
        return null;
      }
    }

    for (const hidden of hiddenInputs) {
      const obraId = hidden.value?.trim();
      if (!obraId) continue;

      const group = hidden.closest(".input-group");
      const visible = group?.querySelector(".numero-w-input");
      if (!visible) continue;

      const num = await resolverNumControl(obraId);
      if (num) {
        visible.value = num;
        visible.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }
  }

  // ========================================
  // API DE BORRADORES
  // ========================================

  async function guardarBorrador(esAutoguardado = false) {
    try {
      const datos = serializarFormulario();
      const tipoObra = getTipoObra();
      const obraObjetivoId = getObraObjetivoId();

      // Validar que podemos guardar
      if (!obraObjetivoId && (!tipoObra || tipoObra === "desconocido")) {
        if (!esAutoguardado) {
          console.warn("No se puede guardar: tipo de obra no determinado");
        }
        return { success: false, error: "Tipo de obra no determinado" };
      }

      const pestanaActual =
        typeof currentTabIndex !== "undefined" ? currentTabIndex : 0;

      const payload = {
        tipo_obra: tipoObra,
        datos_formulario: datos,
        pestana_actual: pestanaActual,
      };

      if (obraObjetivoId) payload.obra_objetivo_id = obraObjetivoId;
      if (state.borradorId) payload.borrador_id = state.borradorId;

      const url = esAutoguardado ? API_URLS.autoguardar : API_URLS.guardar;

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(payload),
      });

      const result = await response.json();

      if (result.success) {
        const esPrimerGuardado = !state.borradorId;
        state.borradorId = result.borrador_id;
        state.hasUnsavedChanges = false;
        mostrarNotificacion(
          esAutoguardado ? "Autoguardado" : result.message,
          "success",
          esAutoguardado ? 2000 : 3000,
        );
        actualizarIndicadorGuardado();

        // Agregar estado al historial para detectar botón atrás (solo la primera vez)
        if (esPrimerGuardado) {
          window.history.pushState(
            { borrador: true },
            "",
            window.location.href,
          );
        }

        return { success: true, borradorId: state.borradorId };
      } else {
        console.error("Error guardando:", result.error);
        if (!esAutoguardado) {
          mostrarNotificacion("Error al guardar", "error");
        }
        // Actualizar indicador del sidebar con error
        if (window.updateAutosaveIndicator) {
          window.updateAutosaveIndicator("error", "Error al guardar");
        }
        return { success: false, error: result.error };
      }
    } catch (error) {
      console.error("Error en guardarBorrador:", error);
      if (!esAutoguardado) {
        mostrarNotificacion("Error de conexión", "error");
      }
      // Actualizar indicador del sidebar con error de conexión
      if (window.updateAutosaveIndicator) {
        window.updateAutosaveIndicator("error", "Error de conexión");
      }
      return { success: false, error: error.message };
    }
  }

  async function cargarBorrador(id) {
    try {
      mostrarNotificacion("Cargando borrador...", "info", 2000);

      const response = await fetch(API_URLS.obtener(id));
      const result = await response.json();

      if (!result.success) {
        mostrarNotificacion("Error al cargar borrador", "error");
        return;
      }

      const borrador = result.borrador;
      const obraObjetivoId = getObraObjetivoId();
      const tipoObraActual = getTipoObra();

      // Validar tipo de obra en modo creación
      if (
        !obraObjetivoId &&
        (!tipoObraActual || tipoObraActual === "desconocido")
      ) {
        console.warn("Tipo de obra aún no determinado, reintentando...");
        setTimeout(() => cargarBorrador(id), 500);
        return;
      }

      if (!obraObjetivoId && borrador.tipo_obra !== tipoObraActual) {
        mostrarNotificacion(
          "Error: Este borrador es de otro tipo de obra.",
          "error",
          5000,
        );
        return;
      }

      state.borradorId = borrador.id;

      // Restaurar formulario
      await restaurarFormulario(borrador.datos_formulario);

      // Navegar a la pestaña guardada
      if (typeof switchTab === "function" && borrador.pestana_actual) {
        setTimeout(() => switchTab(borrador.pestana_actual), 500);
      }

      mostrarNotificacion("Borrador recuperado exitosamente", "success");
      actualizarIndicadorGuardado();

      // Limpiar variable de sesión
      if (typeof BORRADOR_A_RECUPERAR !== "undefined") {
        fetch(API_URLS.limpiarSesion, {
          method: "POST",
          headers: { "X-CSRFToken": getCsrfToken() },
        }).catch(() => {});
      }
    } catch (error) {
      console.error("Error cargando borrador:", error);
      mostrarNotificacion("Error al cargar borrador", "error");
    }
  }

  async function eliminarBorrador(id) {
    try {
      const response = await fetch(API_URLS.eliminar(id), {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken() },
      });

      const result = await response.json();
      if (result.success && id === state.borradorId) {
        state.borradorId = null;
      }
    } catch (error) {
      console.error("Error eliminando:", error);
    }
  }

  // ========================================
  // UI
  // ========================================

  function mostrarNotificacion(mensaje, tipo = "info", duracion = 3000) {
    const notif = document.createElement("div");
    notif.textContent = mensaje;
    notif.style.cssText = `
            position: fixed; bottom: 20px; right: 20px;
            padding: 12px 20px; border-radius: 4px;
            color: white; font-size: 14px; font-weight: 500;
            z-index: 10000; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;

    const colores = {
      success: "#27AE60",
      error: "#E74C3C",
      info: "#3498DB",
    };
    notif.style.backgroundColor = colores[tipo] || colores.info;

    document.body.appendChild(notif);
    setTimeout(() => notif.remove(), duracion);
  }

  function actualizarIndicadorGuardado() {
    let indicador = document.getElementById("save-indicator");

    if (!indicador) {
      indicador = document.createElement("div");
      indicador.id = "save-indicator";
      indicador.style.cssText = `
                position: fixed; bottom: 20px; left: calc(var(--sidebar-width, 250px) + 20px);
                padding: 8px 16px; border-radius: 20px;
                font-size: 12px; font-weight: 500; z-index: 9999;
                display: flex; align-items: center; gap: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            `;
      document.body.appendChild(indicador);
    }

    if (state.hasUnsavedChanges) {
      indicador.style.backgroundColor = "#F39C12";
      indicador.style.color = "white";
      indicador.innerHTML = "<span>●</span> Cambios sin guardar";
      // Actualizar indicador del sidebar si existe
      if (window.updateAutosaveIndicator) {
        window.updateAutosaveIndicator("saving", "Guardando...");
      }
    } else if (state.borradorId) {
      indicador.style.backgroundColor = "#27AE60";
      indicador.style.color = "white";
      indicador.innerHTML = "<span>✓</span> Guardado";
      // Actualizar indicador del sidebar si existe
      if (window.updateAutosaveIndicator) {
        window.updateAutosaveIndicator("saved", "Guardado");
      }
    }
  }

  // ========================================
  // EVENTOS Y AUTOGUARDADO
  // ========================================

  function onFormChange() {
    state.hasUnsavedChanges = true;
    actualizarIndicadorGuardado();

    if (state.changeTimer) clearTimeout(state.changeTimer);
    state.changeTimer = setTimeout(
      () => guardarBorrador(true),
      CONFIG.MIN_CHANGE_DELAY,
    );
  }

  function iniciarAutoguardado() {
    if (state.autoSaveTimer) clearInterval(state.autoSaveTimer);

    state.autoSaveTimer = setInterval(() => {
      if (state.borradorId && state.hasUnsavedChanges) {
        guardarBorrador(true);
      }
    }, CONFIG.AUTOSAVE_INTERVAL);
  }

  // ========================================
  // ALERTAS DE SALIDA
  // ========================================

  /**
   * Muestra un diálogo informativo cuando el usuario intenta salir
   */
  async function mostrarDialogoSalida(accion, onContinue) {
    // Usar SweetAlert2 si está disponible
    if (typeof Swal !== "undefined") {
      const result = await Swal.fire({
        icon: "info",
        title: "Borrador guardado",
        html: `
          <div class="text-start">
            <p>Tu avance está guardado como <strong>borrador</strong>.</p>
            <ul>
              <li>Para continuar luego, ve a <strong>Borradores</strong> desde el menú.</li>
              <li>Si ${accion}, podrás recuperar este borrador más tarde.</li>
            </ul>
            <hr>
            <p class="text-muted small mb-0">
              <i class="bi bi-trash"></i> También puedes descartar el borrador si no lo necesitas.
            </p>
          </div>
        `,
        showCancelButton: true,
        showDenyButton: true,
        confirmButtonText:
          '<i class="bi bi-file-earmark-text"></i> Ir a Borradores',
        denyButtonText:
          '<i class="bi bi-box-arrow-right"></i> Salir (mantener borrador)',
        cancelButtonText: "Cancelar",
        footer:
          '<div class="text-center w-100 pt-2 border-top"><button type="button" class="btn btn-outline-danger btn-sm" id="btn-descartar-salir"><i class="bi bi-trash"></i> Descartar borrador y salir</button></div>',
        focusCancel: true,
        customClass: {
          confirmButton: "btn btn-primary",
          denyButton: "btn btn-secondary",
          cancelButton: "btn btn-outline-secondary",
          footer: "swal2-footer-visible",
        },
        didOpen: () => {
          const btnDescartar = document.getElementById("btn-descartar-salir");
          if (btnDescartar) {
            btnDescartar.addEventListener("click", async () => {
              // Eliminar el borrador
              if (state.borradorId) {
                await eliminarBorrador(state.borradorId);
              }
              state.allowUnloadOnce = true;
              Swal.close();
              onContinue();
            });
          }
        },
      });

      if (result.isConfirmed) {
        state.allowUnloadOnce = true;
        window.location.href = "/catalogacion/borradores/";
      } else if (result.isDenied) {
        onContinue();
      }
    } else {
      // Fallback a confirm nativo
      if (
        confirm(
          "Tu avance está guardado como borrador.\n\n¿Salir de todos modos?",
        )
      ) {
        onContinue();
      }
    }
  }

  /**
   * Instala interceptores para alertar al usuario antes de salir
   */
  function instalarAlertasSalida() {
    // 1. Evento beforeunload (navegador nativo - para cerrar pestaña/ventana)
    window.addEventListener("beforeunload", (e) => {
      if (state.allowUnloadOnce) {
        state.allowUnloadOnce = false;
        return;
      }
      // Solo mostrar si hay borrador activo o cambios sin guardar
      if (state.hasUnsavedChanges || state.borradorId) {
        e.preventDefault();
        e.returnValue = "";
      }
    });

    // 2. Interceptar F5 / Ctrl+R
    window.addEventListener(
      "keydown",
      async (e) => {
        const isReload =
          e.key === "F5" ||
          ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "r");
        if (!isReload || !state.borradorId) return;

        e.preventDefault();
        e.stopPropagation();
        await mostrarDialogoSalida("recargas la página", () => {
          state.allowUnloadOnce = true;
          window.location.reload();
        });
      },
      true,
    );

    // 3. Interceptar clicks en enlaces internos
    document.addEventListener(
      "click",
      async (e) => {
        const link = e.target.closest("a[href]");
        if (!link || !state.borradorId) return;

        const href = link.getAttribute("href");
        if (!href || href.startsWith("#") || href.startsWith("javascript:"))
          return;
        if (
          link.getAttribute("target") &&
          link.getAttribute("target") !== "_self"
        )
          return;
        if (link.hasAttribute("download")) return;

        // Verificar si es navegación a otra página
        try {
          const dest = new URL(href, window.location.href);
          // Si es la misma URL (solo cambia el hash), permitir
          if (dest.href.split("#")[0] === window.location.href.split("#")[0]) {
            return;
          }
        } catch {
          return;
        }

        e.preventDefault();
        e.stopPropagation();

        await mostrarDialogoSalida("sales de la página", () => {
          state.allowUnloadOnce = true;
          window.location.href = href;
        });
      },
      true,
    );

    // 4. Interceptar botón atrás del navegador
    window.addEventListener("popstate", async (e) => {
      // Solo interceptar si hay un borrador guardado
      if (!state.borradorId) return;

      // Volver a agregar el estado actual al historial para poder interceptar de nuevo
      window.history.pushState({ borrador: true }, "", window.location.href);

      await mostrarDialogoSalida("vuelves atrás", () => {
        state.allowUnloadOnce = true;
        // Navegar a la página de borradores en vez de ir atrás (más predecible)
        window.location.href = "/catalogacion/borradores/";
      });
    });
  }

  // ========================================
  // INICIALIZACIÓN
  // ========================================

  function init() {
    const esperarFormularioListo = () => {
      const tipoRegistro = document.getElementById("id_tipo_registro");
      const nivelBibliografico = document.getElementById(
        "id_nivel_bibliografico",
      );
      const obraObjetivoId = getObraObjetivoId();

      // En creación, esperar a poder determinar tipo de obra
      if (!obraObjetivoId) {
        const tipoObra = getTipoObra();
        if (!tipoObra || tipoObra === "desconocido") {
          setTimeout(esperarFormularioListo, 100);
          return;
        }
      }

      // En creación, esperar a los campos
      if (!obraObjetivoId && (!tipoRegistro || !nivelBibliografico)) {
        setTimeout(esperarFormularioListo, 100);
        return;
      }

      // Cargar borrador si viene desde lista de borradores
      if (
        typeof BORRADOR_A_RECUPERAR !== "undefined" &&
        BORRADOR_A_RECUPERAR !== null &&
        BORRADOR_A_RECUPERAR !== "null" &&
        BORRADOR_A_RECUPERAR !== "" &&
        !isNaN(parseInt(BORRADOR_A_RECUPERAR, 10))
      ) {
        setTimeout(
          () => cargarBorrador(parseInt(BORRADOR_A_RECUPERAR, 10)),
          300,
        );
      }

      // En edición: cargar borrador activo de la obra
      if (obraObjetivoId) {
        const params = new URLSearchParams(window.location.search);
        const borradorQuery = params.get("borrador");

        if (borradorQuery && !isNaN(parseInt(borradorQuery, 10))) {
          setTimeout(() => cargarBorrador(parseInt(borradorQuery, 10)), 300);
        } else {
          fetch(API_URLS.obtenerUltimoPorObra(obraObjetivoId))
            .then((r) => r.json())
            .then((res) => {
              if (res?.success && res.tiene_borrador && res.borrador?.id) {
                setTimeout(() => cargarBorrador(res.borrador.id), 300);
              }
            })
            .catch(() => {});
        }
      }

      iniciarAutoguardado();
      instalarAlertasSalida();

      form.addEventListener("input", onFormChange);
      form.addEventListener("change", onFormChange);
    };

    esperarFormularioListo();
  }

  // Eliminar borrador al publicar
  form.addEventListener("submit", (e) => {
    if (state.borradorId) {
      eliminarBorrador(state.borradorId);
    }
  });

  // Iniciar
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Función para permitir publicación (llamada desde el modal de confirmación)
  function permitirPublicacion() {
    state.allowUnloadOnce = true;
    state.isPublishing = true;
    state.hasUnsavedChanges = false;
    state.borradorId = null;
  }

  // API pública
  window.BorradorSystem = {
    guardar: () => guardarBorrador(false),
    cargar: cargarBorrador,
    eliminar: eliminarBorrador,
    getState: () => state,
    getBorradorId: () => state.borradorId,
    permitirPublicacion: permitirPublicacion,
  };
})();
