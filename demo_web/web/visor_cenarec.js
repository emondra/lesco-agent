/* LESCO-Agent · Visor de señas CENAREC (capa de presentación, opción A: iframe de la página oficial).
   - Solo se activa si el servidor se inició con el visor habilitado (/api/info → visor_cenarec.modo).
   - Las entradas salen EXCLUSIVAMENTE de la secuencia validada por el servidor MCP (validar_secuencia):
     de cada `url` oficial se toma el idw entero; nunca se usa texto del usuario.
   - El iframe no existe hasta que una persona pide ver una entrada, y se elimina al cerrar o cambiar.
   - No hay reproducción automática ni tiempos supuestos: la navegación entre señas es manual.
   - La demo no puede verificar si la página o el video de otro sitio cargaron, y no lo afirma.
   Se carga después de app.js y usa sus funciones (pintar, pedir, el, $). */
"use strict";

const URL_OFICIAL_ENTRADA = /^https:\/\/lesco\.cenarec\.go\.cr\/DiccLESCO\.php\?idw=([1-9]\d{0,4})$/;
const PAGINA_ANCHO = 1000;   // tamaño lógico de la página incrustada; se escala para caber
const PAGINA_ALTO = 760;

const visor = { modo: "desactivado", base: null, disponibles: [], entradas: [], indice: 0, abierto: false, firma: "" };

async function cargarConfigVisor() {
  try {
    const info = await pedir("/api/info");
    const v = info.visor_cenarec || {};
    if (["oficial", "prueba"].includes(v.modo) && typeof v.base === "string") { visor.modo = v.modo; visor.base = v.base; }
  } catch { /* sin configuración: el visor queda desactivado */ }
  pintar();
}

function visorHabilitado() { return visor.modo !== "desactivado" && !!visor.base; }

function urlOficial(idw) { return `https://lesco.cenarec.go.cr/DiccLESCO.php?idw=${idw}`; }

function srcDelMarco(idw) {
  // El idw es siempre un entero validado; la base la fija el servidor (oficial o página local de prueba).
  return `${visor.base}?idw=${Number(idw)}`;
}

function entradasDe(elementos) {
  return elementos.map((x) => {
    if (x.tipo !== "sena") return { tipo: "sin_cobertura", glosa: "SIN_COBERTURA", texto: x.texto || "" };
    const m = typeof x.url === "string" ? URL_OFICIAL_ENTRADA.exec(x.url) : null;
    if (!m) return { tipo: "sin_url", glosa: x.glosa, id: x.id };   // nunca se construye una dirección sin evidencia
    return { tipo: "sena", glosa: x.glosa, id: x.id, idw: Number(m[1]) };
  });
}

function pintarVisor(d) {
  const habilitado = visorHabilitado();
  visor.disponibles = d && d.elementos && d.validada ? entradasDe(d.elementos) : [];
  $("btn-ver-senas").hidden = !(habilitado && visor.disponibles.length);
  $("secuencia").classList.toggle("con-visor", habilitado && visor.disponibles.length > 0);
  const firma = JSON.stringify(visor.disponibles.map((e) => e.id || e.texto));
  if (visor.abierto && firma !== visor.firma) cerrarVisor();   // cambió la secuencia o el modo
}

// ---------------------------------------------------------------- abrir, navegar, cerrar
function abrirVisor(indice) {
  if (!visorHabilitado() || !visor.disponibles.length) return;
  visor.entradas = visor.disponibles.slice();
  visor.firma = JSON.stringify(visor.entradas.map((e) => e.id || e.texto));
  visor.abierto = true;
  document.body.classList.add("visor-abierto");
  $("visor-cenarec").hidden = false;
  $("visor-prueba").hidden = visor.modo !== "prueba";
  mostrarEntrada(Math.max(0, Math.min(indice || 0, visor.entradas.length - 1)));
  $("btn-visor-cerrar").focus();
}

function quitarMarco() {
  const marco = $("visor-marco");
  const f = marco.querySelector("iframe");
  if (f) f.src = "about:blank";          // detiene cualquier reproducción antes de eliminarlo
  marco.replaceChildren();
}

function cerrarVisor() {
  quitarMarco();
  visor.abierto = false;
  document.body.classList.remove("visor-abierto");
  $("visor-cenarec").hidden = true;
  if (!$("btn-ver-senas").hidden) $("btn-ver-senas").focus();
}

function mostrarEntrada(i) {
  visor.indice = i;
  const e = visor.entradas[i];
  const n = visor.entradas.length;

  $("visor-entradas").replaceChildren(...visor.entradas.map((x, j) => {
    const b = el("button", { type: "button", class: x.tipo === "sena" ? "" : "sin-video", "aria-current": String(j === i),
                             title: x.tipo === "sena" ? `${x.glosa} · ${x.id}` : "sin video" },
      el("span", { class: "glosa" }, `${j + 1}. ${x.glosa}`),
      el("span", { class: "id" }, x.tipo === "sena" ? x.id : x.tipo === "sin_cobertura" ? `«${x.texto}» · sin video` : "sin dirección oficial"));
    b.addEventListener("click", () => mostrarEntrada(j));
    return el("li", {}, b);
  }));

  $("visor-posicion").textContent = `Entrada ${i + 1} de ${n}: ${e.glosa}${e.id ? ` (${e.id})` : ""}`;
  $("btn-sena-anterior").disabled = i <= 0;
  $("btn-sena-siguiente").disabled = i >= n - 1;

  quitarMarco();
  const enlace = $("visor-enlace");
  const marco = $("visor-marco");
  if (e.tipo !== "sena") {
    enlace.hidden = true;
    enlace.removeAttribute("href");
    marco.append(el("p", { class: "visor-aviso" }, e.tipo === "sin_cobertura"
      ? `SIN_COBERTURA: «${e.texto}» no está en el diccionario. No hay video para esta posición.`
      : "Esta entrada no trae una dirección oficial en la evidencia; no se muestra ningún video."));
    $("visor-estado").textContent = "No se carga ninguna página para esta posición.";
    return;
  }
  enlace.href = urlOficial(e.idw);
  enlace.hidden = false;
  if (navigator.onLine === false) {
    marco.append(el("p", { class: "visor-aviso" },
      "Sin conexión a Internet: la página de CENAREC no está disponible ahora. Use «Abrir página oficial» cuando haya conexión."));
    $("visor-estado").textContent = "No se intentó cargar la página: el navegador informa que no hay conexión.";
    return;
  }
  const escala = el("div", { class: "visor-escala" });
  escala.append(el("iframe", {
    src: srcDelMarco(e.idw), title: `${e.glosa} — Diccionario LESCO, CENAREC`, width: PAGINA_ANCHO, height: PAGINA_ALTO,
    allow: "autoplay; fullscreen", allowfullscreen: true, referrerpolicy: "no-referrer", loading: "eager",
    sandbox: "allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-presentation",
  }));
  marco.append(escala);
  ajustarEscala();
  $("visor-estado").textContent = visor.modo === "prueba"
    ? "Página LOCAL de prueba (no es CENAREC). La demo no verifica la carga del marco."
    : "Página oficial solicitada al navegador. La demo no puede verificar si la página o el video cargaron: "
      + "si no aparece, use «Abrir página oficial». Para ver la seña, pulse ▶ en el reproductor de CENAREC.";
}

function ajustarEscala() {
  const marco = $("visor-marco");
  const escala = marco.querySelector(".visor-escala");
  if (!escala) return;
  const r = marco.getBoundingClientRect();
  const k = Math.max(0.3, Math.min(1, (r.width - 8) / PAGINA_ANCHO, (r.height - 8) / PAGINA_ALTO));
  escala.style.width = `${PAGINA_ANCHO}px`;
  escala.style.height = `${PAGINA_ALTO}px`;
  escala.style.transform = `scale(${k})`;
  escala.style.marginRight = `${-(PAGINA_ANCHO * (1 - k))}px`;     // ocupa solo el espacio escalado
  escala.style.marginBottom = `${-(PAGINA_ALTO * (1 - k))}px`;
}

function anteriorSena() { if (visor.abierto && visor.indice > 0) mostrarEntrada(visor.indice - 1); }
function siguienteSena() { if (visor.abierto && visor.indice < visor.entradas.length - 1) mostrarEntrada(visor.indice + 1); }

function conectarVisor() {
  $("btn-ver-senas").addEventListener("click", () => abrirVisor(0));
  $("btn-visor-cerrar").addEventListener("click", cerrarVisor);
  $("btn-sena-anterior").addEventListener("click", anteriorSena);
  $("btn-sena-siguiente").addEventListener("click", siguienteSena);
  $("secuencia").addEventListener("click", (ev) => {
    if (!visorHabilitado() || ev.target.closest("a")) return;    // el enlace al diccionario sigue funcionando
    const li = ev.target.closest("li");
    if (li) abrirVisor([...$("secuencia").children].indexOf(li));
  });
  document.addEventListener("keydown", (ev) => {
    if (!visor.abierto) return;
    if (ev.key === "Escape") { ev.preventDefault(); cerrarVisor(); }
    else if (ev.key === "ArrowRight" || ev.key === "PageDown") { ev.preventDefault(); siguienteSena(); }
    else if (ev.key === "ArrowLeft" || ev.key === "PageUp") { ev.preventDefault(); anteriorSena(); }
  });
  window.addEventListener("resize", ajustarEscala);
}

conectarVisor();
cargarConfigVisor();
