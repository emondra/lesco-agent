/* LESCO-Agent · modo «Demostración por voz» (fase 1: motor local de reglas, sin API).
   Se carga después de app.js y usa su estado y sus funciones (estado, pintar, sondear, el, $…).
   El audio nunca sale del navegador hacia la demo: solo se envía el texto que una persona confirma.
   La voz no aprueba nada: la aprobación es un clic en «Aprobar guardado». */
"use strict";

const LENGUA_VOZ = "es-ES";
const RITMO_MS = 600;   // autoseguimiento: un evento ya recibido se muestra cada 0,6 s (todos son reales)

const vozCliente = {
  soportado: false,     // el navegador ofrece SpeechRecognition
  local: null,          // lo que informa el navegador sobre reconocimiento en el equipo (null = no informa)
  avisoAceptado: false,
  reconocimiento: null,
  escuchando: false,
  usado: false,         // hubo evento «start» del reconocimiento
  parcial: false,       // hay resultados intermedios
  final: false,         // hubo un resultado final
  corregido: false,     // la persona editó el texto después del dictado
  manual: false,        // se escribió sin dictar
  error: null,          // error real del reconocimiento (p. ej. not-allowed, network, no-speech)
  errorTexto: null,     // rechazo real del servidor al confirmar (400/409)
  mensaje: null,        // aviso local de la interfaz (p. ej. micrófono no disponible)
  iaHabilitada: false,  // el servidor se inició con --permitir-api
  permiso: null,        // permiso de un solo uso devuelto por /api/voz-ia/preparar (fase 2)
};

async function cargarConfigIA() {
  try {
    const info = await pedir("/api/info");
    vozCliente.iaHabilitada = !!(info.ia_real && info.ia_real.habilitada);
  } catch { vozCliente.iaHabilitada = false; }
  pintar();
}

async function elegirMotor(motor) {
  if (motor === estado.motorVoz || (motor === "ia" && !vozCliente.iaHabilitada)) return;
  const datos = estado.datos || {};
  if (["en_curso", "esperando_aprobacion"].includes(datos.estado)) return;   // no se cambia a mitad de una ejecución
  estado.motorVoz = motor;
  cerrarConsentimiento();
  clearTimeout(estado.sondeo);
  estado.datos = null; estado.eventos = []; estado.cursor = -1; estado.seguir = true;
  Object.assign(vozCliente, { errorTexto: null, mensaje: null });
  try {
    const d = await pedir(rutaEjecucion("voz"));
    if (d.estado !== "inactiva") { estado.datos = d; estado.eventos = d.eventos; estado.cursor = d.eventos.length - 1; }
    else if (motor === "ia") estado.datos = d;      // sin eventos: solo cupo y estimación
  } catch { /* se verá al confirmar */ }
  pintar();
}

function constructorVoz() { return window.SpeechRecognition || window.webkitSpeechRecognition || null; }

async function detectarVoz() {
  const SR = constructorVoz();
  vozCliente.soportado = !!SR;
  if (SR && typeof SR.available === "function") {
    try { vozCliente.local = await SR.available({ langs: [LENGUA_VOZ], processLocally: true }); }
    catch { vozCliente.local = null; }
  }
  pintar();
}

function descripcionMotorVoz() {
  if (!vozCliente.soportado) return "Este navegador no ofrece reconocimiento de voz: escriba la oración.";
  if (vozCliente.local === "available") {
    return "Reconocimiento del navegador; el navegador informa que puede hacerlo en el equipo (no verificado por la demo).";
  }
  return "Reconocimiento del navegador: puede usar servicios externos (requiere Internet).";
}

// ---------------------------------------------------------------- micrófono
function pulsarMicrofono() {
  if (vozCliente.escuchando) { detenerMicrofono(); return; }
  if (!vozCliente.soportado) {
    vozCliente.manual = true;
    vozCliente.mensaje = "Este navegador no ofrece reconocimiento de voz: escriba la oración y pulse «Confirmar».";
    pintar();
    $("texto-voz").focus();
    return;
  }
  if (!vozCliente.avisoAceptado) { $("aviso-microfono").hidden = false; return; }
  iniciarEscucha();
}

function iniciarEscucha() {
  const SR = constructorVoz();
  if (!SR) return;
  Object.assign(vozCliente, { error: null, parcial: false, final: false, corregido: false, manual: false, errorTexto: null });
  const r = new SR();
  r.lang = LENGUA_VOZ;
  r.interimResults = true;
  r.continuous = false;
  r.maxAlternatives = 1;
  if (vozCliente.local === "available") { try { r.processLocally = true; } catch { /* no lo admite */ } }
  r.onstart = () => { vozCliente.escuchando = true; vozCliente.usado = true; pintar(); };
  r.onresult = (ev) => {
    let texto = "";
    for (let i = 0; i < ev.results.length; i++) texto += ev.results[i][0].transcript;
    $("texto-voz").value = texto.trim().slice(0, 200);
    vozCliente.parcial = true;
    if (ev.results[ev.results.length - 1].isFinal) vozCliente.final = true;
    pintar();
  };
  r.onerror = (ev) => { vozCliente.error = ev.error || "error desconocido"; pintar(); };
  r.onend = () => { vozCliente.escuchando = false; vozCliente.reconocimiento = null; pintar(); };
  vozCliente.reconocimiento = r;
  try { r.start(); } catch (e) { vozCliente.error = e.message; pintar(); }
}

function detenerMicrofono() {
  if (vozCliente.reconocimiento) { try { vozCliente.reconocimiento.stop(); } catch { /* ya detenido */ } }
}

// ---------------------------------------------------------------- confirmar y procesar
async function iniciarVoz() {
  detenerMicrofono();
  const texto = $("texto-voz").value;
  vozCliente.errorTexto = null;
  vozCliente.mensaje = null;
  if (!vozCliente.usado) vozCliente.manual = true;
  if (estado.motorVoz === "ia") { await prepararIA(texto); return; }
  try {
    await postJSON("/api/voz/iniciar", { texto });
  } catch (err) {
    vozCliente.errorTexto = err.message;   // mensaje real del servidor (texto no válido u otra ejecución en curso)
    pintar();
    return;
  }
  estado.seguir = true;
  estado.eventos = [];
  estado.cursor = -1;
  estado.datos = { estado: "en_curso", origen: "voz" };
  pintar();
  sondear();
}

// ---------------------------------------------------------------- fase 2: consentimiento por clic
async function prepararIA(texto) {
  let p;
  try {
    p = await postJSON("/api/voz-ia/preparar", { texto });   // solo valida y emite un permiso; no llama a la API
  } catch (err) {
    vozCliente.errorTexto = err.message;
    pintar();
    return;
  }
  vozCliente.permiso = p.token;
  const est = p.estimacion || {};
  const filas = [
    ["Oración", `«${p.texto}»`],
    ["Modelo", `${p.modelo} · configuración ${p.configuracion}`],
    ["Costo estimado", est.media_usd != null
      ? `≈ US$ ${est.media_usd.toFixed(2)} por frase (máximo observado US$ ${est.max_observado_usd.toFixed(2)} en ${est.corridas} corridas B). Es una estimación, no un tope garantizado.`
      : "sin estimación disponible"],
    ["Ejecuciones reales", `quedan ${p.restantes} de ${p.maximo} en esta sesión`],
    ["Límites implementados", p.limites ? `${p.limites.max_pasos} pasos · ${p.limites.presupuesto_tokens} tokens `
      + `(comprobado antes de cada solicitud) · ${p.limites.max_tokens_por_respuesta} tokens por respuesta · 0 reintentos` : "—"],
    ["Presupuesto estimado de la sesión", p.presupuesto
      ? `gastado ≈ US$ ${p.presupuesto.gastado_estimado_usd.toFixed(2)} de US$ ${p.presupuesto.limite_usd.toFixed(2)}; `
        + `reserva por ejecución US$ ${p.presupuesto.reserva_por_ejecucion_usd.toFixed(2)} (peor caso teórico). Estimación, no facturación.`
      : "—"],
    ["Gasto facturado", "solo lo informa el proveedor (consola de Anthropic); la demo no lo conoce."],
    ["Condiciones", "sin reintentos automáticos; si falla, se detiene e informa. Guardar seguirá pidiendo «Aprobar guardado»."],
  ];
  $("consentimiento-datos").replaceChildren(...filas.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)]));
  $("consentimiento-ia").hidden = false;
  // Espera mínima tras mostrar el costo (el servidor también la exige): tiempo para leer el diálogo.
  const boton = $("btn-autorizar-ia");
  const listo = Date.now() + Math.ceil((p.espera_minima_s || 0) * 1000) + 150;
  boton.disabled = true;
  const cuenta = () => {
    if (vozCliente.permiso !== p.token) return;
    const falta = listo - Date.now();
    if (falta > 0) { boton.textContent = `Lea el costo… (${Math.ceil(falta / 1000)})`; setTimeout(cuenta, 200); }
    else { boton.disabled = false; boton.textContent = "Autorizar esta ejecución (con costo)"; }
  };
  cuenta();
  pintar();
}

async function autorizarIA() {
  const token = vozCliente.permiso;
  if (!token) return;
  vozCliente.permiso = null;
  $("btn-autorizar-ia").disabled = true;
  $("consentimiento-ia").hidden = true;
  try {
    await postJSON("/api/voz-ia/autorizar", { token });       // el ÚNICO punto que lanza una ejecución real
  } catch (err) {
    vozCliente.errorTexto = err.message;
    pintar();
    return;
  }
  estado.seguir = true;
  estado.eventos = [];
  estado.cursor = -1;
  estado.datos = { estado: "en_curso", origen: "voz_ia" };
  pintar();
  sondear();
}

function cerrarConsentimiento() {
  if (vozCliente.permiso) postJSON("/api/voz-ia/cancelar", {}).catch(() => {});   // el permiso queda inutilizable
  vozCliente.permiso = null;
  $("consentimiento-ia").hidden = true;
}

function seguirEnVivo() {
  estado.seguir = true;     // reanuda el avance automático desde el evento actual
  pintar();
}

function avanzarEnVivo() {
  if (estado.modo !== "voz" || !estado.seguir) return;
  if (estado.cursor < estado.eventos.length - 1) { estado.cursor++; pintar(); }
}

// ---------------------------------------------------------------- monitor de etapas
function etapasVoz() {
  // El monitor refleja lo que ya se mostró en la línea de tiempo (hasta el evento actual).
  const todos = estado.eventos || [];
  const ev = todos.slice(0, estado.cursor + 1);
  const alFinal = estado.cursor >= todos.length - 1;
  const datos = estado.datos || {};
  const herr = ev.filter((e) => e.tipo === "herramienta");
  const de = (n) => herr.filter((e) => corta(e.nombre) === n);
  const inicio = ev.find((e) => e.tipo === "inicio");
  const fin = ev.find((e) => e.tipo === "fin");
  const turnos = ev.filter((e) => e.tipo === "respuesta_modelo");
  const corriendo = ["en_curso", "esperando_aprobacion"].includes(datos.estado) || !alFinal;
  const esperando = datos.estado === "esperando_aprobacion" && alFinal;
  const E = (nombre, est, detalle) => ({ nombre, est, detalle });
  const etapas = [];

  // 1. Micrófono y 2. STT: eventos del navegador
  if (!vozCliente.soportado) etapas.push(E("Micrófono", "no-aplica", "no disponible en este navegador"));
  else if (vozCliente.error === "not-allowed") etapas.push(E("Micrófono", "error", "permiso denegado"));
  else if (vozCliente.escuchando) etapas.push(E("Micrófono", "en-curso", "escuchando…"));
  else if (vozCliente.usado) etapas.push(E("Micrófono", "hecho", "captura terminada (audio no guardado)"));
  else if (vozCliente.manual) etapas.push(E("Micrófono", "omitido", "entrada manual"));
  else etapas.push(E("Micrófono", "pendiente", "inactivo"));

  if (vozCliente.error && vozCliente.error !== "not-allowed") etapas.push(E("STT", "error", `navegador: ${vozCliente.error}`));
  else if (vozCliente.final) etapas.push(E("STT", "hecho", vozCliente.corregido ? "transcrito y corregido a mano" : "transcrito por el navegador"));
  else if (vozCliente.parcial || vozCliente.escuchando) etapas.push(E("STT", "en-curso", "reconociendo…"));
  else if (vozCliente.manual || !vozCliente.soportado) etapas.push(E("STT", "omitido", "texto escrito a mano"));
  else etapas.push(E("STT", "pendiente", ""));

  // 3. Texto confirmado: respuesta del servidor
  if (vozCliente.errorTexto) etapas.push(E("Texto", "error", vozCliente.errorTexto));
  else if (datos.caso_id) etapas.push(E("Texto", "hecho", `caso temporal ${datos.caso_id}`));
  else if (corriendo) etapas.push(E("Texto", "en-curso", "enviando…"));
  else etapas.push(E("Texto", "pendiente", "sin confirmar"));

  // 4. Motor (reglas o IA real) y 5. MCP: traza
  const ia = estado.motorVoz === "ia";
  const nombreMotor = ia ? "Agente IA" : "Motor local";
  const skill = inicio && (inicio.instrucciones || []).some((x) => /SKILL\.md$/.test(x));
  if (turnos.length) {
    etapas.push(E(nombreMotor, "hecho", ia
      ? `${turnos.length} respuesta(s) de ${inicio ? inicio.modelo : "el modelo"} · Skill ${skill ? "cargada" : "NO cargada"}`
      : `${turnos.length} decisión(es) por reglas`));
  } else if (fin && !/^el modelo terminó/.test(fin.motivo || "")) etapas.push(E(nombreMotor, "error", fin.motivo));
  else if (datos.estado === "error") etapas.push(E(nombreMotor, "error", datos.error || "error"));
  else etapas.push(E(nombreMotor, corriendo ? "en-curso" : "pendiente", ia && datos.estado === "en_curso" ? "autorizado desde la interfaz; esperando al modelo" : ""));

  if (inicio && (inicio.servidores || []).length) {
    const s = inicio.servidores[0];
    etapas.push(E("MCP", "hecho", `${s.nombre} v${s.version} · caso ${s.caso_vinculado}`));
  } else if (fin && /error al conectar/.test(fin.motivo || "")) etapas.push(E("MCP", "error", fin.motivo));
  else etapas.push(E("MCP", corriendo ? "en-curso" : "pendiente", ""));

  // 6. Búsquedas
  const b = de("buscar_sena");
  const pedidas = turnos.reduce((n, t) => n + (t.herramientas || []).filter((h) => corta(h.name) === "buscar_sena").length, 0);
  if (b.some((e) => e.es_error || e.decision === "denegar")) etapas.push(E("Búsquedas", "error", (b.find((e) => e.es_error || e.decision === "denegar") || {}).salida));
  else if (b.length && b.length >= pedidas) {
    const exactas = b.filter((e) => ((json(e.salida) || {}).resultados || []).some((r) => r.coincidencia === "exacta")).length;
    etapas.push(E("Búsquedas", "hecho", `${b.length} búsqueda(s) · ${exactas} con coincidencia exacta`));
  } else if (pedidas) etapas.push(E("Búsquedas", "en-curso", `${b.length} de ${pedidas}`));
  else etapas.push(E("Búsquedas", "pendiente", ""));

  // 7. Validación
  const v = de("validar_secuencia").slice(-1)[0];
  if (v) {
    const s = json(v.salida);
    if (v.es_error || !s || s.valida !== true) etapas.push(E("Validación", "error", v.salida));
    else etapas.push(E("Validación", "hecho", `válida · ${s.con_cobertura} con seña · ${s.sin_cobertura} sin cobertura`));
  } else etapas.push(E("Validación", "pendiente", ""));

  // 8. Política, 9. Aprobación y 10. Guardado
  const g = de("guardar_resultado")[0];
  if (esperando) etapas.push(E("Política", "en-curso", "guardar_resultado → CONFIRMAR (requiere persona)"));
  else if (herr.length) {
    const den = herr.filter((e) => e.decision === "denegar").length;
    etapas.push(E("Política", "hecho", `${herr.length - den} permitida(s) · ${den} denegada(s)`));
  } else etapas.push(E("Política", "pendiente", ""));

  if (esperando) etapas.push(E("Aprobación", "en-curso", "esperando un clic (la voz no aprueba)"));
  else if (g && g.decision === "permitir" && /persona|interfaz web local/.test(g.razon || "")) etapas.push(E("Aprobación", "hecho", "aprobada desde la interfaz"));
  else if (g && g.decision === "denegar") etapas.push(E("Aprobación", "rechazado", g.razon));
  else etapas.push(E("Aprobación", "pendiente", ""));

  if (g && g.decision === "permitir" && !g.es_error && datos.guardado) {
    etapas.push(E("Guardado", "hecho", `archivo ${(json(g.salida) || {}).archivo} (carpeta temporal)`));
  } else if (g && g.decision === "permitir" && g.es_error) etapas.push(E("Guardado", "error", g.salida));
  else if (g && g.decision === "denegar") etapas.push(E("Guardado", "rechazado", "no se escribió nada"));
  else if (fin) etapas.push(E("Guardado", "omitido", "no se pidió guardar"));
  else etapas.push(E("Guardado", "pendiente", ""));

  // 11. Resultado
  if (datos.estado === "error" && alFinal) etapas.push(E("Resultado", "error", datos.error));
  else if (fin && /^el modelo terminó/.test(fin.motivo || "")) {
    const glosas = datos.guardado && Array.isArray(datos.guardado.glosas) ? datos.guardado.glosas.join(" ") : "sin guardado";
    etapas.push(E("Resultado", datos.guardado ? "hecho" : "rechazado", glosas));
  } else if (fin) etapas.push(E("Resultado", "error", fin.motivo));
  else etapas.push(E("Resultado", corriendo ? "en-curso" : "pendiente", ""));
  return etapas;
}

const TEXTO_ESTADO = { pendiente: "pendiente", "en-curso": "en curso", hecho: "hecho", error: "error",
  rechazado: "rechazado", omitido: "omitido", "no-aplica": "no aplica" };

function pintarVoz() {
  if (estado.modo !== "voz") return;
  const datos = estado.datos || {};
  const corriendo = ["en_curso", "esperando_aprobacion"].includes(datos.estado);

  const ia = estado.motorVoz === "ia";
  $("btn-motor-reglas").setAttribute("aria-pressed", String(!ia));
  $("btn-motor-ia").setAttribute("aria-pressed", String(ia));
  $("btn-motor-ia").disabled = !vozCliente.iaHabilitada || corriendo;
  $("btn-motor-reglas").disabled = corriendo;
  $("btn-motor-ia").title = vozCliente.iaHabilitada ? "Claude Sonnet 5.5 + Skill (configuración B), por la API, con costo"
    : "Deshabilitada: inicie la demo con -PermitirApi";
  const sello = $("sello-voz");
  sello.textContent = !ia ? "MOTOR LOCAL DE REGLAS — NO ES UN LLM"
    : datos.modo_prueba ? "API DE PRUEBA LOCAL — NO ES CLAUDE" : "IA REAL · CLAUDE SONNET 5.5 + SKILL · CON COSTO";
  sello.classList.toggle("sello-ia", ia);
  $("btn-confirmar-voz").textContent = ia ? "Confirmar texto y revisar costo" : "Confirmar texto y procesar";

  const mic = $("btn-microfono");
  mic.textContent = !vozCliente.soportado ? "🎤 Micrófono no disponible"
    : vozCliente.escuchando ? "⏹ Detener micrófono" : "🎤 Activar micrófono";
  mic.disabled = corriendo;
  $("texto-voz").disabled = corriendo || vozCliente.escuchando;
  $("btn-confirmar-voz").disabled = corriendo || vozCliente.escuchando || !$("texto-voz").value.trim() || !!vozCliente.permiso;
  $("btn-seguir").setAttribute("aria-pressed", String(estado.seguir));
  $("btn-seguir").textContent = estado.seguir ? "Siguiendo en vivo" : "Seguir en vivo";

  const estados = {
    inactiva: descripcionMotorVoz(),
    en_curso: ia ? "Ejecutando con la IA real en un proceso aparte (los eventos aparecen cuando el modelo responde)…"
      : "Procesando con el motor local de reglas…",
    esperando_aprobacion: "El host espera la aprobación humana del guardado (clic en «Aprobar guardado»).",
    terminada: `Terminado · ${datos.resultado ? datos.resultado.motivo : ""} · traza en la línea de tiempo.`
      + (ia && datos.costo_estimado_usd != null ? ` Costo estimado: US$ ${datos.costo_estimado_usd.toFixed(4)}.` : ""),
    error: `Error real: ${datos.error || ""}`,
  };
  const enPantalla = estado.cursor >= estado.eventos.length - 1 ? datos.estado : "en_curso";
  $("estado-voz").textContent = vozCliente.errorTexto ? `No se procesó: ${vozCliente.errorTexto}`
    : vozCliente.mensaje ? vozCliente.mensaje
    : (datos.estado ? estados[enPantalla] : estados.inactiva);
  $("estado-voz").classList.toggle("error", !!vozCliente.errorTexto || datos.estado === "error");
  if (ia && datos.restantes != null && datos.estado !== "inactiva") {
    $("estado-voz").textContent += ` · Ejecuciones reales: quedan ${datos.restantes} de ${datos.maximo}.`;
  }
  if (ia && !vozCliente.errorTexto && datos.estado === "inactiva" && datos.restantes != null) {
    $("estado-voz").textContent = `IA real lista: quedan ${datos.restantes} de ${datos.maximo} ejecuciones en esta sesión. `
      + "Confirme el texto para ver el costo estimado; la llamada solo ocurre al pulsar «Autorizar».";
  }

  // Tiempo real (traza) frente a tiempo de visualización (escalonado en pantalla)
  const finEv = (estado.eventos || []).find((e) => e.tipo === "fin");
  const marcas = (estado.eventos || []).map((e) => Date.parse(e.t)).filter((x) => !Number.isNaN(x));
  const real = finEv && finEv.duracion_s != null ? `${finEv.duracion_s} s (duración registrada por el host)`
    : marcas.length > 1 ? `${Math.round((marcas[marcas.length - 1] - marcas[0]) / 1000)} s hasta ahora (marcas de la traza)` : "—";
  $("tiempos-voz").title = $("tiempos-voz").textContent = (estado.eventos || []).length
    ? `Tiempo real de ejecución: ${real} · Visualización: un evento ya registrado cada ${RITMO_MS / 1000} s (no es el tiempo real).`
    : "";

  const ol = $("monitor");
  ol.replaceChildren(...etapasVoz().map((x, i) => el("li", { class: `etapa ${x.est}`, title: x.detalle || "" },
    el("span", { class: "etapa-nombre" }, `${i + 1}. ${x.nombre}`),
    el("span", { class: "etapa-estado" }, TEXTO_ESTADO[x.est]),
    el("span", { class: "etapa-detalle" }, x.detalle || ""))));
}

function conectarVoz() {
  $("btn-microfono").addEventListener("click", pulsarMicrofono);
  $("btn-mic-continuar").addEventListener("click", () => {
    vozCliente.avisoAceptado = true;
    $("aviso-microfono").hidden = true;
    iniciarEscucha();
  });
  $("btn-mic-cancelar").addEventListener("click", () => {
    $("aviso-microfono").hidden = true;
    vozCliente.manual = true;
    pintar();
    $("texto-voz").focus();
  });
  $("texto-voz").addEventListener("input", () => {
    if (vozCliente.final || vozCliente.parcial) vozCliente.corregido = true;
    else vozCliente.manual = true;
    vozCliente.errorTexto = null;
    vozCliente.mensaje = null;
    pintar();
  });
  $("texto-voz").addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); iniciarVoz(); } });
  $("btn-confirmar-voz").addEventListener("click", iniciarVoz);
  $("btn-seguir").addEventListener("click", seguirEnVivo);
  $("btn-motor-reglas").addEventListener("click", () => elegirMotor("reglas"));
  $("btn-motor-ia").addEventListener("click", () => elegirMotor("ia"));
  $("btn-autorizar-ia").addEventListener("click", autorizarIA);      // único punto de la interfaz que lanza una ejecución real
  $("btn-cancelar-ia").addEventListener("click", () => { cerrarConsentimiento(); pintar(); });
}

conectarVoz();
detectarVoz();
cargarConfigIA();
setInterval(avanzarEnVivo, RITMO_MS);
