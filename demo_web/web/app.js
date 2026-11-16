/* LESCO-Agent · visor local. Todo el contenido de las trazas se inserta como texto (nunca como HTML). */
"use strict";

const URL_DICCIONARIO = /^https:\/\/lesco\.cenarec\.go\.cr\/DiccLESCO\.php\?idw=\d+$/;
const POR_DEFECTO = { configuracion: "B", repeticion: "1", caso: "c015" };

const estado = {
  modo: "real",
  datos: null,        // respuesta de /api/corrida o /api/simulacion
  eventos: [],
  cursor: -1,
  detalles: false,
  corridas: [],
  sondeo: null,
  simIniciada: false,
  seguir: true,       // modo voz: el cursor sigue al último evento mientras llegan
  motorVoz: "reglas", // modo voz: "reglas" (motor local) o "ia" (IA real por la API, fase 2)
};

// Modos que ejecutan algo en el servidor (y su ruta de API).
const API_EJECUCION = { sim: "/api/simulacion", voz: "/api/voz" };
const esVozIA = () => estado.modo === "voz" && estado.motorVoz === "ia";
const rutaEjecucion = (modo) => (modo === "voz" && estado.motorVoz === "ia" ? "/api/voz-ia" : API_EJECUCION[modo]);
const esPruebaIA = () => esVozIA() && !!(estado.datos && estado.datos.modo_prueba);

const $ = (id) => document.getElementById(id);

function el(tag, attrs, ...hijos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else n.setAttribute(k, v === true ? "" : String(v));
  }
  for (const h of hijos.flat()) {
    if (h === null || h === undefined || h === false) continue;
    n.append(h instanceof Node ? h : document.createTextNode(String(h)));
  }
  return n;
}

function enlaceDiccionario(url, texto) {
  if (typeof url === "string" && URL_DICCIONARIO.test(url)) {
    return el("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, texto);
  }
  return document.createTextNode(texto);
}

function json(texto) {
  if (typeof texto !== "string") return null;
  try { return JSON.parse(texto); } catch { return null; }
}

function corta(nombre) { return String(nombre || "").split("__").pop(); }

async function pedir(url, opciones) {
  const r = await fetch(url, Object.assign({ cache: "no-store" }, opciones || {}));
  const cuerpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(cuerpo.error || `HTTP ${r.status}`);
  return cuerpo;
}

const postJSON = (url, cuerpo) =>
  pedir(url, { method: "POST", headers: { "Content-Type": "application/json", "X-Lesco-Demo": "1" },
               body: JSON.stringify(cuerpo || {}) });

// ===================================================================== clasificación de eventos
function categoria(e) {
  if (e.tipo === "inicio") return "c-sistema";
  if (e.tipo === "fin") return "c-resumen";
  if (e.tipo === "respuesta_modelo" && esVozIA()) return "c-ia-vivo";
  if (e.tipo === "respuesta_modelo" && estado.modo === "voz") return "c-reglas";
  if (e.tipo === "respuesta_modelo") return estado.modo === "real" ? "c-modelo-real" : "c-guion";
  if (e.tipo === "herramienta") {
    if (e.decision === "denegar") return "c-denegada";
    if (e.es_error) return "c-error";
    if (corta(e.nombre) === "guardar_resultado") return "c-guardado";
    return "c-mcp";
  }
  return "c-sistema";
}

function tipoLegible(e) {
  const c = categoria(e);
  return {
    "c-sistema": "Host · inicio",
    "c-resumen": "Host · fin de la ejecución",
    "c-modelo-real": "Modelo real (traza histórica)",
    "c-guion": "Agente simulado · guion fijo",
    "c-reglas": "Motor local de reglas · no es un LLM",
    "c-ia-vivo": esPruebaIA() ? "API de PRUEBA local · no es Claude" : "IA real en vivo · claude-sonnet-5-5 (API)",
    "c-mcp": "Llamada MCP · permitida",
    "c-guardado": "Guardado real",
    "c-denegada": "Denegada por la política",
    "c-error": "Llamada MCP · error del servidor",
  }[c];
}

function resumenArgs(e) {
  const a = e.argumentos || {};
  switch (corta(e.nombre)) {
    case "obtener_transcripcion": return `caso ${a.caso_id}`;
    case "buscar_sena": return `«${a.texto}»`;
    case "validar_secuencia": return `${(a.secuencia || []).length} elementos`;
    case "guardar_resultado": return `caso ${a.caso_id}, ${(a.secuencia || []).length} elementos`;
    default: return "";
  }
}

function tituloEvento(e) {
  if (e.tipo === "inicio") return `Inicio · configuración ${e.configuracion} · caso ${e.caso_id}`;
  if (e.tipo === "fin" && esVozIA()) return `Fin · ${e.motivo}`;
  if (e.tipo === "fin" && estado.modo === "voz") return `Fin · motor de reglas terminado (el host registra: ${e.motivo})`;
  if (e.tipo === "fin") return estado.modo === "sim" ? `Fin · guion completado (el host registra: ${e.motivo})` : `Fin · ${e.motivo}`;
  if (e.tipo === "respuesta_modelo") {
    const n = (e.herramientas || []).length;
    const pide = n ? `solicita ${n} herramienta${n > 1 ? "s" : ""}` : "da su respuesta final";
    if (estado.modo === "sim") return `Turno ${e.paso} del guion: ${e.texto || pide}`;
    if (esVozIA()) return `Paso ${e.paso}: el modelo ${pide}`;
    if (estado.modo === "voz") return `Paso ${e.paso} · ${e.texto || pide}`;
    return `Paso ${e.paso}: el modelo ${pide}`;
  }
  if (e.tipo === "herramienta") return `${corta(e.nombre)}(${resumenArgs(e)})`;
  return e.tipo;
}

// ===================================================================== estado derivado
function derivado(hasta) {
  const d = { texto: null, inicio: null, elementos: null, guardado: false, guardadoArgs: null, validada: false };
  for (let i = 0; i <= hasta && i < estado.eventos.length; i++) {
    const e = estado.eventos[i];
    if (e.tipo === "inicio") d.inicio = e;
    if (e.tipo !== "herramienta" || e.decision !== "permitir" || e.es_error) continue;
    const s = json(e.salida);
    if (!s) continue;
    const h = corta(e.nombre);
    if (h === "obtener_transcripcion" && s.transcripcion) d.texto = s.transcripcion;
    if (h === "validar_secuencia" && Array.isArray(s.elementos)) { d.elementos = s.elementos; d.validada = !!s.valida; }
    if (h === "guardar_resultado" && s.guardado === true) { d.guardado = true; d.guardadoArgs = e.argumentos; }
  }
  return d;
}

// ===================================================================== pintado
function pintar() {
  const total = estado.eventos.length;
  if (estado.cursor >= total) estado.cursor = total - 1;
  const d = derivado(estado.cursor);

  // insignia
  const ins = $("insignia-modo");
  if (estado.modo === "real") {
    const c = estado.datos && estado.datos.corrida;
    ins.textContent = c
      ? `TRAZA REAL · ejecución histórica del ${String(c.fecha).slice(0, 10)} · no es una llamada API en vivo`
      : "TRAZA REAL · ejecución histórica · no es una llamada API en vivo";
  } else if (esPruebaIA()) {
    ins.textContent = "VOZ · API DE PRUEBA LOCAL — NO ES CLAUDE (solo pruebas) · servidor MCP real";
  } else if (esVozIA()) {
    ins.textContent = "VOZ · IA REAL: claude-sonnet-5-5 + Skill (B) · API con costo · servidor MCP real";
  } else if (estado.modo === "voz") {
    ins.textContent = "VOZ · MOTOR LOCAL DE REGLAS — NO ES UN LLM · servidor MCP real · sin API";
  } else {
    ins.textContent = "DEMO SIMULADA · guion fijo, no es inferencia de un LLM · servidor MCP real · sin API";
  }

  // texto original
  const t = $("texto-original");
  t.textContent = d.texto ? `«${d.texto}»` : "—";
  t.classList.toggle("vacio", !d.texto);

  // configuración
  const dl = $("configuracion");
  dl.replaceChildren();
  const filas = [];
  if (d.inicio) {
    const conf = d.inicio.configuracion;
    const descr = conf === "A" ? "A · instrucciones genéricas" : conf === "B" ? "B · genéricas + Skill"
      : conf === "demo" ? "demo · genéricas + Skill + aprobación"
        : conf === "voz" ? "voz · motor de reglas, sin Skill"
          : conf === "voz-ia" ? "voz-ia · genéricas + Skill (B) + aprobación" : conf;
    filas.push(["Config.", descr], ["Caso", d.inicio.caso_id],
      ["Modelo", esPruebaIA() ? "API de PRUEBA local (no es Claude)"
        : esVozIA() ? `${d.inicio.modelo} (API, en vivo)`
        : estado.modo === "voz" ? "motor local de reglas, no es un LLM (la traza registra «simulado»)"
        : d.inicio.modelo === "simulado" ? "simulado (guion fijo)" : d.inicio.modelo],
      ["Política", String(d.inicio.politica || "").split("/").pop()]);
    if (estado.modo === "real" && estado.datos) filas.push(["Repetición", estado.datos.corrida.repeticion]);
  } else {
    filas.push(["Estado", "sin iniciar"]);
  }
  for (const [k, v] of filas) dl.append(el("dt", {}, k), el("dd", {}, v));

  // secuencia
  const ol = $("secuencia");
  ol.replaceChildren();
  ol.classList.toggle("guardada", d.guardado);
  const est = $("estado-secuencia");
  if (d.elementos) {
    for (const x of d.elementos) {
      if (x.tipo === "sena") {
        ol.append(el("li", {}, el("span", { class: "glosa" }, x.glosa),
          el("span", { class: "id" }, enlaceDiccionario(x.url, x.id))));
      } else {
        ol.append(el("li", { class: "sin-cobertura" }, el("span", { class: "glosa" }, "SIN_COBERTURA"),
          el("span", { class: "id" }, `«${x.texto || ""}» no está en el índice`)));
      }
    }
    est.textContent = d.guardado
      ? "Guardada por el servidor MCP (resultado real de esta ejecución)."
      : d.validada ? "Validada por el servidor MCP contra el índice CENAREC · aún sin guardar."
        : "El servidor MCP rechazó la secuencia (ver detalle).";
    est.className = "estado-secuencia" + (d.guardado ? " guardada" : "");
  } else {
    est.textContent = "Aún no hay secuencia validada.";
    est.className = "estado-secuencia vacio";
  }

  // línea de tiempo (solo eventos ya revelados)
  const lt = $("linea-tiempo");
  lt.replaceChildren();
  for (let i = 0; i <= estado.cursor; i++) {
    const e = estado.eventos[i];
    const li = el("li", { class: `${categoria(e)}${i === estado.cursor ? " actual" : ""}`, "data-i": i },
      el("span", { class: "tipo" }, `${i + 1}. ${tipoLegible(e)}`), tituloEvento(e));
    li.addEventListener("click", () => { estado.cursor = i; pintar(); });
    lt.append(li);
  }
  const actual = lt.querySelector(".actual");
  if (actual) actual.scrollIntoView({ block: "nearest" });
  const quedan = total - estado.cursor - 1;
  $("pendientes").textContent = total === 0 ? "" : quedan > 0 ? `${quedan} evento(s) por mostrar.` : "";

  // contador y botones
  $("contador").textContent = `${Math.max(estado.cursor + 1, 0)} / ${total}`;
  $("btn-anterior").disabled = estado.cursor <= 0;
  const ejecuta = estado.modo in API_EJECUCION;
  const esperando = ejecuta && estado.datos && estado.datos.estado === "esperando_aprobacion";
  const enCurso = ejecuta && estado.datos && ["en_curso", "esperando_aprobacion"].includes(estado.datos.estado);
  $("btn-siguiente").disabled = estado.cursor >= total - 1;
  $("btn-reiniciar").disabled = total === 0;
  $("btn-iniciar").disabled = enCurso;
  $("btn-detalles").setAttribute("aria-pressed", String(estado.detalles));
  $("btn-detalles").textContent = estado.detalles ? "Ocultar detalles de la herramienta" : "Mostrar detalles de la herramienta";

  // detalle del evento actual
  pintarDetalle(estado.eventos[estado.cursor], d);

  // aprobación humana (solo en la simulación, cuando ya se vio el último evento)
  const ap = $("aprobacion");
  ap.hidden = !(esperando && estado.cursor === total - 1 && estado.datos.pendiente);
  if (!ap.hidden) {
    const p = estado.datos.pendiente;
    const a = p.argumentos || {};
    $("aprobacion-args").textContent = `${p.nombre}\ncaso_id: ${a.caso_id}\ntexto_fuente: «${a.texto_fuente}»\n` +
      `secuencia: ${(a.secuencia || []).join(", ")}`;
    ap.parentElement.scrollTop = 0;
  }

  // estado de la simulación y contingencia
  if (estado.modo === "sim") {
    const s = estado.datos ? estado.datos.estado : "inactiva";
    $("estado-sim").textContent = {
      inactiva: "Simulación sin iniciar.",
      en_curso: "Simulación en curso…",
      esperando_aprobacion: "El host espera la aprobación humana del guardado.",
      terminada: `Simulación terminada · ${estado.datos && estado.datos.resultado ? estado.datos.resultado.motivo : ""}`,
      error: "La simulación falló.",
    }[s] || s;
  }
  const falla = estado.modo === "sim" && estado.datos && estado.datos.estado === "error";
  $("contingencia").hidden = !falla;
  if (falla) $("contingencia-texto").textContent =
    `La simulación no pudo completarse (${estado.datos.error}). Plan B: mostrar una ejecución histórica real.`;
  if (typeof pintarVoz === "function") pintarVoz(d);   // monitor del modo de voz (voz.js)
  if (typeof pintarVisor === "function") pintarVisor(d);   // visor de señas CENAREC (visor_cenarec.js)
}

function bloque(rotulo, ...contenido) {
  return el("div", { class: "bloque" }, el("div", { class: "rotulo" }, rotulo), ...contenido);
}

function pintarDetalle(e, d) {
  const cont = $("detalle");
  cont.replaceChildren();
  if (!e) {
    $("detalle-titulo").textContent = "Evento";
    cont.append(el("p", { class: "vacio" }, estado.modo === "voz"
      ? "Dicte o escriba una oración, corríjala si hace falta y pulse «Confirmar texto y procesar»."
      : estado.modo === "sim"
      ? "Pulse «Iniciar demostración» para ejecutar el agente simulado."
      : "Elija una corrida y pulse «Iniciar demostración»."));
    return;
  }
  const cat = categoria(e);
  $("detalle-titulo").textContent = `Evento ${estado.cursor + 1} de ${estado.eventos.length}`;
  cont.append(el("span", { class: `etiqueta ${cat}` }, tipoLegible(e)));
  if (e.t) cont.append(el("span", { class: "etiqueta c-politica" }, e.t.replace("T", " ")));
  cont.append(el("h3", {}, tituloEvento(e)));

  if (e.tipo === "inicio") detalleInicio(cont, e);
  else if (e.tipo === "respuesta_modelo") detalleModelo(cont, e);
  else if (e.tipo === "herramienta") detalleHerramienta(cont, e);
  else if (e.tipo === "fin") detalleFin(cont, e);

  if (estado.detalles) {
    const copia = Object.assign({}, e);
    if (typeof copia.salida === "string" && json(copia.salida)) copia.salida = json(copia.salida);
    cont.append(bloque("Evento completo de la traza (JSON)", el("pre", { class: "crudo" }, JSON.stringify(copia, null, 2))));
  }
}

function detalleInicio(cont, e) {
  cont.append(bloque("Objetivo entregado al agente", el("div", { class: "cita" }, e.objetivo)));
  cont.append(bloque("Catálogo MCP visible para el modelo",
    el("ul", {}, (e.herramientas || []).map((h) => el("li", {}, el("code", {}, h))))));
  if ((e.ocultas || []).length) cont.append(bloque("Ocultas por la política", e.ocultas.join(", ")));
  cont.append(bloque("Instrucciones cargadas", (e.instrucciones || []).join(" + ")));
  cont.append(bloque("Límites del host",
    `máx. ${e.limites.max_pasos} pasos · presupuesto ${e.limites.presupuesto_tokens} tokens`));
  cont.append(bloque("Servidor MCP", (e.servidores || []).map((s) =>
    `${s.nombre} v${s.version} · vinculado al caso ${s.caso_vinculado}`).join("; ")));
}

function detalleModelo(cont, e) {
  if (esVozIA()) {
    if (e.texto) cont.append(bloque(esPruebaIA() ? "Texto de la API de PRUEBA local (no es Claude)"
      : "Texto devuelto por el modelo real (en vivo)", el("div", { class: "cita" }, e.texto)));
    const hs = e.herramientas || [];
    if (hs.length) {
      cont.append(bloque("Herramientas que pidió el modelo",
        el("ol", {}, hs.map((h) => el("li", {}, el("code", {}, corta(h.name)), " ", JSON.stringify(h.input))))));
    }
    const u = e.uso || {};
    cont.append(bloque("Tokens del paso", `${u.input_tokens} entrada · ${u.output_tokens} salida · stop_reason=${e.stop_reason}`));
    return;
  }
  if (estado.modo === "voz") {
    cont.append(bloque("Decisión del motor local de reglas (no es razonamiento de un LLM)",
      el("div", { class: "cita reglas" }, e.texto || "—")));
    const hs = e.herramientas || [];
    if (hs.length) {
      cont.append(bloque("Herramientas que pide el motor de reglas",
        el("ol", {}, hs.map((h) => el("li", {}, el("code", {}, corta(h.name)), " ", JSON.stringify(h.input))))));
    }
    cont.append(bloque("Tokens del paso", "0: no hay modelo de lenguaje"));
    return;
  }
  if (estado.modo === "sim") {
    cont.append(bloque("Texto del guion fijo (no es razonamiento de un modelo)",
      el("div", { class: "cita guion" }, e.texto || "—")));
  } else if (e.texto) {
    cont.append(bloque("Texto devuelto por el modelo real (histórico)", el("div", { class: "cita" }, e.texto)));
  }
  const hs = e.herramientas || [];
  if (hs.length) {
    cont.append(bloque(estado.modo === "sim" ? "Herramientas que pide el guion" : "Herramientas que pidió el modelo",
      el("ol", {}, hs.map((h) => el("li", {}, el("code", {}, corta(h.name)), " ", JSON.stringify(h.input))))));
  }
  const u = e.uso || {};
  cont.append(bloque("Tokens del paso", estado.modo === "sim"
    ? `estimados por el simulador (no facturados): ${u.input_tokens} entrada · ${u.output_tokens} salida`
    : `${u.input_tokens} entrada · ${u.output_tokens} salida · stop_reason=${e.stop_reason}`));
}

function cajaPolitica(e) {
  const confirmada = /persona|interfaz web local/.test(e.razon || "");
  const txt = confirmada
    ? `Política del host: CONFIRMAR → ${e.decision === "permitir" ? "APROBADA" : "RECHAZADA"} · ${e.razon}`
    : `Política del host: ${String(e.decision).toUpperCase()} · ${e.razon}`;
  return el("div", { class: `politica ${e.decision === "denegar" ? "denegar" : ""}` }, txt);
}

function detalleHerramienta(cont, e) {
  cont.append(cajaPolitica(e));
  if (e.decision === "denegar") {
    cont.append(el("div", { class: "denegada-caja" },
      "Acción no ejecutada: el host la bloqueó y el servidor MCP no recibió la llamada. ", e.salida));
    return;
  }
  const s = json(e.salida);
  if (e.es_error || !s) {
    cont.append(bloque("Respuesta del servidor MCP (error)", el("div", { class: "cita" }, e.salida)));
    return;
  }
  const h = corta(e.nombre);
  if (h === "obtener_transcripcion") {
    cont.append(bloque("Transcripción entregada por el servidor", el("div", { class: "cita" }, `«${s.transcripcion}»`)));
  } else if (h === "buscar_sena") {
    const res = s.resultados || [];
    cont.append(bloque(`Búsqueda «${s.consulta}» en el índice CENAREC · ${s.total_coincidencias} coincidencia(s)`,
      res.length ? el("table", {}, el("tr", {}, el("th", {}, "Glosa"), el("th", {}, "ID"), el("th", {}, "Coincidencia")),
        res.map((r) => el("tr", {}, el("td", {}, el("strong", {}, r.glosa)),
          el("td", {}, enlaceDiccionario(r.url, r.id)), el("td", {}, r.coincidencia))))
        : el("div", { class: "cita" }, "Sin coincidencias: candidata a SIN_COBERTURA.")));
  } else if (h === "validar_secuencia") {
    cont.append(bloque("Validación del servidor contra el diccionario",
      el("div", { class: "cita" }, s.valida ? "Secuencia válida" : "Secuencia NO válida")));
    cont.append(el("table", {}, el("tr", {}, el("th", {}, "#"), el("th", {}, "Elemento"), el("th", {}, "ID")),
      (s.elementos || []).map((x) => el("tr", {}, el("td", {}, x.posicion + 1),
        el("td", {}, x.tipo === "sena" ? x.glosa : `SIN_COBERTURA («${x.texto || ""}»)`),
        el("td", {}, x.tipo === "sena" ? enlaceDiccionario(x.url, x.id) : "—")))));
    if ((s.errores || []).length) cont.append(bloque("Errores", JSON.stringify(s.errores)));
  } else if (h === "guardar_resultado") {
    const lugar = estado.modo !== "real"
      ? "en la carpeta temporal aislada de la demo (se elimina al cerrar)"
      : `en ${estado.datos.ruta_guardado} (archivo histórico, solo lectura)`;
    const caja = el("div", { class: "guardado-real" },
      el("strong", {}, "Resultado realmente guardado por el servidor MCP "), lugar, ".",
      el("br"), `Archivo ${s.archivo} · ${s.elementos} elementos · ${s.sin_cobertura} SIN_COBERTURA`);
    cont.append(caja);
    const g = estado.datos && estado.datos.guardado;
    if (g && Array.isArray(g.glosas)) cont.append(bloque("Glosas registradas en el archivo", g.glosas.join(" · ")));
  } else {
    cont.append(bloque("Respuesta", el("div", { class: "cita" }, e.salida)));
  }
}

function detalleFin(cont, e) {
  const hs = estado.eventos.filter((x) => x.tipo === "herramienta");
  const por = {};
  for (const x of hs) por[corta(x.nombre)] = (por[corta(x.nombre)] || 0) + 1;
  const escrituras = hs.filter((x) => corta(x.nombre) === "guardar_resultado" && x.decision === "permitir" && !x.es_error).length;
  const filas = [
    ["Motivo de parada", e.motivo],
    ["Pasos del bucle", e.pasos],
    ["Llamadas a herramientas", `${hs.length} (${Object.entries(por).map(([k, v]) => `${k} ×${v}`).join(", ")})`],
    ["Denegadas por la política", hs.filter((x) => x.decision === "denegar").length],
    ["Errores del servidor", hs.filter((x) => x.es_error && x.decision === "permitir").length],
    ["Escrituras realizadas", escrituras],
    ["Tokens", esVozIA() ? `${e.tokens_entrada} entrada + ${e.tokens_salida} salida · costo estimado ` +
      `US$ ${estado.datos && estado.datos.costo_estimado_usd != null ? estado.datos.costo_estimado_usd.toFixed(4) : "?"} (estimación desde tokens)`
      : estado.modo === "voz" ? "0 (motor de reglas: no hay modelo de lenguaje)" : estado.modo === "sim" ? `${e.tokens_entrada} + ${e.tokens_salida} (estimados por el simulador, sin costo)`
      : `${e.tokens_entrada} entrada + ${e.tokens_salida} salida`],
    ["Duración", `${e.duracion_s} s`],
  ];
  if (estado.modo === "real") {
    filas.push(["Corrida", estado.datos.corrida.id], ["SHA-256 de la traza", estado.datos.sha256_traza]);
  }
  cont.append(el("table", { class: "resumen-tabla" }, filas.map(([k, v]) => el("tr", {}, el("td", {}, k), el("td", {}, v)))));
  if (e.respuesta_final) {
    const rotuloFinal = esVozIA() ? "Respuesta final del modelo (en vivo)" : estado.modo === "voz" ? "Mensaje final del motor de reglas (construido con las respuestas del servidor)"
      : estado.modo === "sim" ? "Mensaje final del guion (texto fijo)" : "Respuesta final del modelo (histórica)";
    const claseFinal = esVozIA() ? "" : estado.modo === "voz" ? "reglas" : estado.modo === "sim" ? "guion" : "";
    cont.append(bloque(rotuloFinal, el("div", { class: `cita ${claseFinal}` }, e.respuesta_final)));
    if (estado.modo === "sim" && escrituras === 0) {
      cont.append(el("div", { class: "denegada-caja" },
        "Atención: el guion fijo no se adapta a lo ocurrido. En esta ejecución no hubo ninguna escritura; " +
        "lo que vale es la traza, no el mensaje del guion."));
    }
  }
}

// ===================================================================== modo traza real
function opciones(select, valores, elegido, rotulo) {
  select.replaceChildren(...valores.map((v) => el("option", { value: v, selected: v === elegido }, rotulo ? rotulo(v) : v)));
}

function textoDeCaso(caso) {
  const c = estado.corridas.find((x) => x.caso_id === caso);
  return c ? c.texto : "";
}

function actualizarSelectores(preferido) {
  const conf = $("sel-config").value || preferido.configuracion;
  const reps = [...new Set(estado.corridas.filter((c) => c.configuracion === conf).map((c) => String(c.repeticion)))].sort();
  opciones($("sel-rep"), reps, reps.includes($("sel-rep").value) ? $("sel-rep").value : preferido.repeticion);
  const rep = $("sel-rep").value;
  const casos = estado.corridas.filter((c) => c.configuracion === conf && String(c.repeticion) === rep).map((c) => c.caso_id).sort();
  const actual = casos.includes($("sel-caso").value) ? $("sel-caso").value : (casos.includes(preferido.caso) ? preferido.caso : casos[0]);
  opciones($("sel-caso"), casos, actual, (c) => `${c} · ${textoDeCaso(c)}`);
  const n = estado.corridas.length;
  $("origen-real").textContent = `${n} corridas formales del experimento A/B (modelo real, 14-nov-2026). ` +
    "Se leen las trazas guardadas sin modificarlas; no se llama al modelo.";
}

async function cargarCorridas() {
  const r = await pedir("/api/corridas");
  estado.corridas = r.corridas;
  const confs = [...new Set(estado.corridas.map((c) => c.configuracion))].sort();
  opciones($("sel-config"), confs, confs.includes(POR_DEFECTO.configuracion) ? POR_DEFECTO.configuracion : confs[0],
    (c) => (c === "A" ? "A · sin Skill" : c === "B" ? "B · con Skill" : c));
  actualizarSelectores(POR_DEFECTO);
}

function idSeleccionado() {
  return `experimento/${$("sel-config").value}/rep${$("sel-rep").value}/${$("sel-caso").value}`;
}

async function iniciarReal() {
  const datos = await pedir(`/api/corrida?id=${encodeURIComponent(idSeleccionado())}`);
  estado.datos = datos;
  estado.eventos = datos.eventos;
  estado.cursor = 0;
  pintar();
}

// ===================================================================== modo simulación
async function iniciarSim() {
  await postJSON("/api/simulacion/iniciar", {});
  estado.simIniciada = true;
  estado.eventos = [];
  estado.cursor = -1;
  estado.datos = { estado: "en_curso" };
  pintar();
  sondear();
}

function sondear() {
  clearTimeout(estado.sondeo);
  estado.sondeo = setTimeout(async () => {
    const modo = estado.modo;
    if (!(modo in API_EJECUCION)) return;
    try {
      const datos = await pedir(rutaEjecucion(modo));
      if (estado.modo !== modo) return;
      estado.datos = datos;
      estado.eventos = datos.eventos;
      if (estado.cursor < 0 && estado.eventos.length) estado.cursor = 0;
      pintar();
      if (["en_curso", "esperando_aprobacion"].includes(datos.estado)) sondear();
    } catch (err) {
      estado.datos = { estado: "error", error: err.message };
      pintar();
    }
  }, 350);
}

async function responderAprobacion(aprobar) {
  $("btn-aprobar").disabled = $("btn-rechazar").disabled = true;
  try {
    await postJSON(`${rutaEjecucion(estado.modo)}/aprobacion`, { aprobar });
  } finally {
    $("btn-aprobar").disabled = $("btn-rechazar").disabled = false;
  }
  sondear();
}

// ===================================================================== modos y controles
async function cambiarModo(modo) {
  if (estado.modo === modo) return;
  estado.modo = modo;
  document.body.dataset.modo = modo;
  $("btn-modo-real").setAttribute("aria-pressed", String(modo === "real"));
  $("btn-modo-sim").setAttribute("aria-pressed", String(modo === "sim"));
  $("btn-modo-voz").setAttribute("aria-pressed", String(modo === "voz"));
  $("panel-real").hidden = modo !== "real";
  $("panel-sim").hidden = modo !== "sim";
  $("panel-voz").hidden = modo !== "voz";
  if (modo !== "voz" && typeof detenerMicrofono === "function") detenerMicrofono();
  clearTimeout(estado.sondeo);
  estado.datos = null;
  estado.eventos = [];
  estado.cursor = -1;
  if (modo === "sim") {
    // Si ya hay una simulación de esta sesión del servidor, se recupera su estado.
    try {
      const datos = await pedir("/api/simulacion");
      if (datos.estado !== "inactiva") {
        estado.datos = datos;
        estado.eventos = datos.eventos;
        estado.cursor = estado.eventos.length ? 0 : -1;
        if (["en_curso", "esperando_aprobacion"].includes(datos.estado)) sondear();
      }
    } catch { /* se mostrará al iniciar */ }
  }
  if (modo === "voz") {
    estado.seguir = true;
    try {
      const datos = await pedir(rutaEjecucion("voz"));
      if (datos.estado !== "inactiva") {
        estado.datos = datos;
        estado.eventos = datos.eventos;
        estado.cursor = estado.eventos.length - 1;
        if (["en_curso", "esperando_aprobacion"].includes(datos.estado)) sondear();
      }
    } catch { /* se mostrará al confirmar */ }
  }
  pintar();
}

function avisarError(err) {
  $("detalle").replaceChildren(el("p", { class: "denegada-caja" }, `No se pudo completar la acción: ${err.message}`));
}

async function iniciar() {
  try {
    if (estado.modo === "real") await iniciarReal();
    else if (estado.modo === "voz") await iniciarVoz();
    else await iniciarSim();
  } catch (err) { avisarError(err); }
}

function siguiente() { if (estado.cursor < estado.eventos.length - 1) { estado.cursor++; pintar(); } }
function anterior() {
  if (estado.modo === "voz") estado.seguir = false;   // navegar hacia atrás pausa el autoseguimiento
  if (estado.cursor > 0) { estado.cursor--; pintar(); }
}
function reiniciar() { estado.cursor = estado.eventos.length ? 0 : -1; pintar(); }
function alternarDetalles() { estado.detalles = !estado.detalles; pintar(); }

function pantallaCompleta() {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen().catch(() => {});
}

function conectar() {
  $("btn-modo-real").addEventListener("click", () => cambiarModo("real"));
  $("btn-modo-sim").addEventListener("click", () => cambiarModo("sim"));
  $("btn-modo-voz").addEventListener("click", () => cambiarModo("voz"));
  $("btn-pantalla").addEventListener("click", pantallaCompleta);
  $("btn-iniciar").addEventListener("click", iniciar);
  $("btn-siguiente").addEventListener("click", siguiente);
  $("btn-anterior").addEventListener("click", anterior);
  $("btn-reiniciar").addEventListener("click", reiniciar);
  $("btn-detalles").addEventListener("click", alternarDetalles);
  $("btn-aprobar").addEventListener("click", () => responderAprobacion(true).catch(avisarError));
  $("btn-rechazar").addEventListener("click", () => responderAprobacion(false).catch(avisarError));
  $("btn-plan-b").addEventListener("click", async () => { await cambiarModo("real"); iniciar(); });
  $("sel-config").addEventListener("change", () => actualizarSelectores(POR_DEFECTO));
  $("sel-rep").addEventListener("change", () => actualizarSelectores(POR_DEFECTO));
  document.addEventListener("fullscreenchange", () => {
    $("btn-pantalla").textContent = document.fullscreenElement ? "Salir de pantalla completa" : "Pantalla completa";
  });
  document.addEventListener("keydown", (ev) => {
    if (document.body.classList.contains("visor-abierto")) return;   // el visor CENAREC maneja sus teclas
    if (ev.target instanceof HTMLSelectElement || ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.target instanceof HTMLInputElement || ev.target instanceof HTMLTextAreaElement) return;   // se está escribiendo
    const k = ev.key;
    if (k === " " && ev.target instanceof HTMLButtonElement) return;   // el botón enfocado ya actúa
    if (k === "ArrowRight" || k === "PageDown" || k === " ") { ev.preventDefault(); siguiente(); }
    else if (k === "ArrowLeft" || k === "PageUp") { ev.preventDefault(); anterior(); }
    else if (k === "Home") { ev.preventDefault(); reiniciar(); }
    else if (k === "d" || k === "D") alternarDetalles();
    else if (k === "f" || k === "F") pantallaCompleta();
  });
}

conectar();
pintar();
cargarCorridas().catch(avisarError);
