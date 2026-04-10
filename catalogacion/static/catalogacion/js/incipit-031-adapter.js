// Adapter minimo entre el formulario Django (031) y el motor legacy incipitManager.js.
// Usa el objeto global CanvasIncipit que crea incipitManager.js.

(function () {
  if (typeof window.CanvasIncipit === "undefined") {
    console.warn("incipit-031-adapter: CanvasIncipit no esta disponible");
    return;
  }

  function parsePaeCode(paeCode) {
    if (!paeCode || typeof paeCode !== "string") {
      return { clef: "", armadura: "", tiempo: "", cuerpo: "" };
    }

    const dollarIndex = paeCode.indexOf("$");
    const atIndex = paeCode.indexOf("@");

    let clef = "";
    const endForPercent =
      dollarIndex !== -1 && (atIndex === -1 || dollarIndex < atIndex)
        ? dollarIndex
        : atIndex !== -1
        ? atIndex
        : paeCode.length;
    const percentPart = paeCode.slice(0, endForPercent).trim();
    if (percentPart.startsWith("%")) {
      const match = percentPart.match(/%([GCF](?:-[1-5])?)/);
      if (match) clef = match[1];
    }

    let armadura = "";
    if (dollarIndex !== -1) {
      const endForDollar =
        atIndex !== -1 && atIndex > dollarIndex ? atIndex : paeCode.length;
      const dollarPart = paeCode.slice(dollarIndex, endForDollar).trim();
      armadura = dollarPart.replace(/^\$/, "").trim();
    }

    let tiempo = "";
    let cuerpo = "";
    if (atIndex !== -1) {
      const atPart = paeCode.slice(atIndex).trim();
      const atRest = atPart.replace(/^@/, "");
      const timeMatch = atRest.match(/^(\d+\/\d+)/);
      if (timeMatch) {
        tiempo = timeMatch[1];
        cuerpo = atRest.slice(timeMatch[0].length).trim();
      } else {
        cuerpo = atRest.trim();
      }
    }

    console.log("[parsePaeCode] tiempo:", tiempo, "| cuerpo extraido:", cuerpo);
    return { clef, armadura, tiempo, cuerpo };
  }

  function dispatchSyncEvents(element) {
    if (!element) return;
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function fillFieldsFromPaeCode(paeCode) {
    const parsed = parsePaeCode(paeCode);
    const root = document.querySelector(".formset-incipit") || document;

    const clefInput = root.querySelector(
      'select[name^="incipits-"][name$="-clave"]'
    );
    if (clefInput) {
      clefInput.value = parsed.clef || "";
      dispatchSyncEvents(clefInput);
    } else {
      console.warn("[fillFieldsFromPaeCode] No se encontro select clave");
    }

    const armaduraInput = root.querySelector(
      'select[name^="incipits-"][name$="-armadura"]'
    );
    if (armaduraInput) {
      armaduraInput.value = parsed.armadura || "";
      dispatchSyncEvents(armaduraInput);
    } else {
      console.warn("[fillFieldsFromPaeCode] No se encontro select armadura");
    }

    const tiempoInput = root.querySelector(
      'select[name^="incipits-"][name$="-tiempo"]'
    );
    if (tiempoInput) {
      tiempoInput.value = parsed.tiempo || "";
      dispatchSyncEvents(tiempoInput);
    } else {
      console.warn("[fillFieldsFromPaeCode] No se encontro select tiempo");
    }

    const cuerpoTextarea = root.querySelector(
      'textarea[name^="incipits-"][name$="-notacion_musical"]'
    );
    if (cuerpoTextarea) {
      cuerpoTextarea.value = parsed.cuerpo || "";
      dispatchSyncEvents(cuerpoTextarea);
    } else {
      console.warn("[fillFieldsFromPaeCode] No se encontro textarea notacion_musical");
    }

    const displayFull = document.getElementById("incipit_paec_display_0");
    if (displayFull) {
      displayFull.value = (paeCode || "").trim();
    }

    return parsed;
  }

  function syncFromCanvas() {
    const paecInput = document.getElementById("incipitPaec");
    const paeCode = paecInput ? paecInput.value || "" : "";
    console.log("[syncFromCanvas] Sincronizando desde #incipitPaec:", paeCode);
    return fillFieldsFromPaeCode(paeCode);
  }

  function updateCanvasHeaderFromInputs() {
    console.log("[updateCanvasHeaderFromInputs] Iniciando.");

    const root = document.querySelector(".formset-incipit") || document;
    const clefInput = root.querySelector(
      'select[name^="incipits-"][name$="-clave"]'
    );
    const armaduraInput = root.querySelector(
      'select[name^="incipits-"][name$="-armadura"]'
    );
    const tiempoInput = root.querySelector(
      'select[name^="incipits-"][name$="-tiempo"]'
    );

    const clefValue = clefInput ? clefInput.value.trim() : "";
    const armaduraValue = armaduraInput ? armaduraInput.value.trim() : "";
    const tiempoValue = tiempoInput ? tiempoInput.value.trim() : "";

    if (!clefValue) {
      alert("Por favor ingresa al menos la clave (031$g) antes de aplicar.");
      return false;
    }

    const clefMap = {
      "G-2": "treble",
      "C-3": "alto",
      "F-4": "bass",
    };

    const clefName = clefMap[clefValue];
    if (!clefName) {
      alert(`Clave \"${clefValue}\" no reconocida. Use: G-2, C-3 o F-4`);
      return false;
    }

    let qtyAlteration = 0;
    let alterationName = "becuadro";
    if (armaduraValue) {
      if (armaduraValue.startsWith("x")) {
        alterationName = "sostenido";
        qtyAlteration = armaduraValue.length - 1;
      } else if (armaduraValue.startsWith("b")) {
        alterationName = "bemol";
        qtyAlteration = armaduraValue.length - 1;
      }
    }

    const timeMap = {
      "4/4": "tiempo1",
      "2/2": "tiempo2",
      "2/4": "tiempo3",
      "3/4": "tiempo4",
      "3/8": "tiempo5",
      "6/8": "tiempo6",
      "9/8": "tiempo7",
      "12/8": "tiempo8",
      "3/2": "tiempo9",
    };

    const timeName = timeMap[tiempoValue] || null;
    const hasTime = !!timeName;

    if (CanvasIncipit.drawIncipitElements.length === 0) {
      const canvasEl = document.getElementById("incipit_canvas_0");
      if (canvasEl) {
        CanvasIncipit.initializeCanvas("incipit_canvas_0", "add", "");
      }
      if (CanvasIncipit.drawIncipitElements.length === 0) {
        console.error("[updateCanvasHeaderFromInputs] No se pudo inicializar el canvas.");
        return false;
      }
    }

    const clefElement = CanvasIncipit.drawIncipitElements[0];
    const clefNote = CanvasIncipit.incipit.getNoteByName(clefName);

    clefElement.noteName = clefName;
    clefElement.yPosition = clefNote.yPosition;
    clefElement.qtyAlteration = qtyAlteration;
    clefElement.alterationName = alterationName;
    clefElement.hasTime = hasTime;
    clefElement.timeName = timeName;

    CanvasIncipit.setDefaultClefAlt(
      CanvasIncipit,
      clefName,
      qtyAlteration,
      alterationName
    );

    CanvasIncipit.gDrawingContext.clearRect(
      0,
      0,
      CanvasIncipit.gCanvasElement.width,
      CanvasIncipit.gCanvasElement.height
    );
    CanvasIncipit.drawPentagram(CanvasIncipit);

    const paecHeader =
      `%${clefValue}` +
      (armaduraValue ? ` $${armaduraValue}` : "") +
      (tiempoValue ? ` @${tiempoValue}` : "");

    const hiddenPaec = document.getElementById("incipitPaec");
    if (hiddenPaec) {
      hiddenPaec.value = paecHeader;
      syncFromCanvas();
    }

    console.log("[updateCanvasHeaderFromInputs] Cabecera aplicada:", paecHeader);
    showFeedback("Cabecera aplicada correctamente");
    return true;
  }

  function showFeedback(message) {
    const parseBtn = document.getElementById("parse-inc-p0");
    if (!parseBtn) return;

    const originalText = parseBtn.textContent;
    parseBtn.textContent = message;
    parseBtn.style.backgroundColor = "#4CAF50";
    parseBtn.style.color = "white";

    setTimeout(() => {
      parseBtn.textContent = originalText;
      parseBtn.style.backgroundColor = "";
      parseBtn.style.color = "";
    }, 2000);
  }

  const originalTransform = CanvasIncipit.TransformIncipitToPAEC
    ? CanvasIncipit.TransformIncipitToPAEC.bind(CanvasIncipit)
    : null;

  if (!originalTransform) {
    console.warn(
      "incipit-031-adapter: CanvasIncipit.TransformIncipitToPAEC no esta definido"
    );
  } else {
    CanvasIncipit.TransformIncipitToPAEC = function (context) {
      originalTransform(context);
      const paecInput = document.getElementById("incipitPaec");
      const paeCode = paecInput ? paecInput.value || "" : "";
      console.log("[TransformIncipitToPAEC] PAE generado:", paeCode);
      fillFieldsFromPaeCode(paeCode);
      return paeCode;
    };
  }

  document.addEventListener("DOMContentLoaded", function () {
    const canvasEl = document.getElementById("incipit_canvas_0");
    if (!canvasEl) {
      console.warn("incipit-031-adapter: no se encontro #incipit_canvas_0");
      return;
    }

    let hiddenPaec = document.getElementById("incipitPaec");
    if (!hiddenPaec) {
      hiddenPaec = document.createElement("input");
      hiddenPaec.type = "hidden";
      hiddenPaec.id = "incipitPaec";
      hiddenPaec.name = "incipit_paec_0";
      canvasEl.parentNode.appendChild(hiddenPaec);
    }

    let hiddenTransp = document.getElementById("incipitTransposition");
    if (!hiddenTransp) {
      hiddenTransp = document.createElement("input");
      hiddenTransp.type = "hidden";
      hiddenTransp.id = "incipitTransposition";
      hiddenTransp.name = "incipit_transp_0";
      canvasEl.parentNode.appendChild(hiddenTransp);
    }

    hiddenPaec.addEventListener("input", syncFromCanvas);
    hiddenPaec.addEventListener("change", syncFromCanvas);

    // Si hay un íncipit guardado en BD, cargarlo en el canvas para edición.
    const existingPaecEl = document.getElementById("incipit_existing_paec");
    const existingPaec = existingPaecEl ? existingPaecEl.textContent.trim() : "";

    if (existingPaec) {
      console.log("[incipit-031-adapter] Cargando íncipit existente:", existingPaec.substring(0, 60));
      // IMPORTANTE: asignar a #incipitPaec ANTES de initializeCanvas("edit"),
      // porque el motor lee ese input directamente e ignora el parámetro paec.
      hiddenPaec.value = existingPaec;
      CanvasIncipit.initializeCanvas("incipit_canvas_0", "edit", existingPaec);
      fillFieldsFromPaeCode(existingPaec);
    } else {
      CanvasIncipit.initializeCanvas("incipit_canvas_0", "add", "");
      syncFromCanvas();
    }

    const parseBtn = document.getElementById("parse-inc-p0");
    if (parseBtn) {
      parseBtn.addEventListener("click", function (e) {
        e.preventDefault();
        console.log("[Parse Button] Click detectado");

        if (updateCanvasHeaderFromInputs() === false) {
          return;
        }

        if (
          typeof CanvasIncipit !== "undefined" &&
          typeof CanvasIncipit.TransformIncipitToPAEC === "function"
        ) {
          CanvasIncipit.TransformIncipitToPAEC(CanvasIncipit);
          syncFromCanvas();
        } else {
          console.warn(
            "[Parse Button] CanvasIncipit.TransformIncipitToPAEC no disponible"
          );
        }
      });
    } else {
      console.warn("[DOMContentLoaded] No se encontro boton Parse (#parse-inc-p0)");
    }

    const form = canvasEl.closest("form");
    if (form) {
      form.addEventListener("submit", function () {
        if (
          typeof CanvasIncipit !== "undefined" &&
          typeof CanvasIncipit.TransformIncipitToPAEC === "function"
        ) {
          CanvasIncipit.TransformIncipitToPAEC(CanvasIncipit);
        }
        syncFromCanvas();
      });
    }
  });

  window.fillFieldsFromPaeCode = fillFieldsFromPaeCode;
  window.parsePaeCode = parsePaeCode;
  window.syncIncipit031FromCanvas = syncFromCanvas;
  window.updateCanvasHeaderFromInputs = updateCanvasHeaderFromInputs;
})();
