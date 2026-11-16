#!/usr/bin/env python3
"""
Visor web LOCAL de LESCO-Agent para la defensa académica.

Tres modos:
    traza real   reproduce, sin modificarla, una de las 288 corridas formales A/B del experimento
                 (resultados/experimento/supervisor.jsonl). Es una ejecución histórica, no una
                 llamada en vivo.
    simulación   ejecuta el agente con el modelo SIMULADO (guion fijo agente/guion_simulado.json),
                 el servidor MCP real y la política de la demo, en una carpeta temporal aislada.
                 El guardado pide aprobación humana desde la interfaz.
    voz          (fase 1, sin API) una oración dictada o escrita y CONFIRMADA por una persona se procesa
                 con el MOTOR LOCAL DE REGLAS (demo_web/modelo_reglas.py, no es un LLM), el host, la
                 política de la demo y el servidor MCP reales, en una carpeta temporal aislada. Ver voz.py.

Garantías (verificadas en demo_web/tests/test_demo_web.py):
    - escucha solo en 127.0.0.1 y rechaza cabeceras Host/Origin ajenas;
    - sirve únicamente archivos de una lista fija: ninguna ruta del disco sale de la petición;
    - abre las trazas en modo lectura y nunca escribe en el repositorio;
    - no llama a la API: el modelo real, la clave y urllib quedan bloqueados en este proceso;
    - no acepta comandos: solo «iniciar simulación» y «aprobar/rechazar» con un booleano;
    - oculta rutas locales y cualquier texto con forma de clave en lo que envía al navegador.

Uso (PowerShell, desde la raíz del repositorio):
    python demo_web/servidor_demo.py --abrir          # http://127.0.0.1:8765
    Ctrl+C para cerrar.

Sin dependencias externas.
"""

import argparse
import html
import hashlib
import io
import json
import os
import re
import ipaddress
import shutil
import signal
import socket
import sys
import tempfile
import threading
import urllib.request
import webbrowser
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
WEB = AQUI / "web"
sys.path.insert(0, str(RAIZ / "agente"))
import agente  # noqa: E402
from voz import TextoInvalido, Voz  # noqa: E402  (modo de voz, fase 1: sin API)
from voz_ia import VARIABLES_API, VozIA  # noqa: E402  (fase 2: IA real en un proceso aparte; deshabilitada por defecto)

HOST = "127.0.0.1"
PUERTO_POR_DEFECTO = 8765
SUPERVISOR = RAIZ / "resultados" / "experimento" / "supervisor.jsonl"
EXCLUSIONES = RAIZ / "eval" / "exclusiones_experimento.json"
CASOS = RAIZ / "eval" / "casos.jsonl"
CONFIG_DEMO = RAIZ / "agente" / "configs" / "demo.json"
CASOS_DEMO = RAIZ / "eval" / "demo" / "casos_demo.jsonl"
CASO_DEMO = "demo-001"
PREFIJO_TEMPORAL = "lesco_demo_web_"
ESPERA_APROBACION_S = 600
MAX_CUERPO = 256
MAX_CUERPO_VOZ = 2048           # una oración de hasta 200 caracteres, en UTF-8 y JSON

# Lista blanca: la URL solo elige una entrada de este diccionario; nunca se construye una ruta con ella.
ESTATICOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/voz.js": ("voz.js", "text/javascript; charset=utf-8"),
    "/visor_cenarec.js": ("visor_cenarec.js", "text/javascript; charset=utf-8"),
    "/estilo.css": ("estilo.css", "text/css; charset=utf-8"),
}
PATRON_ID = re.compile(r"experimento/[AB]/rep[1-9]/[A-Za-z0-9][A-Za-z0-9_-]{0,39}")
PATRON_TRAZA = re.compile(r"[AB]_[A-Za-z0-9][A-Za-z0-9_-]{0,80}\.jsonl")
PATRON_CLAVE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{4,}")

# ---- Visor de señas CENAREC (capa de presentación; desactivado por defecto)
# «oficial»: iframe de la página oficial de cada entrada (solo ese dominio en frame-src).
# «prueba»: página LOCAL de sustitución, solo para pruebas automáticas (no se pide nada a CENAREC).
# Habilitarlo es una decisión de uso que depende del permiso de CENAREC, no de la viabilidad técnica.
DOMINIO_CENAREC = "https://lesco.cenarec.go.cr"
VISOR_BASES = {"desactivado": None, "oficial": f"{DOMINIO_CENAREC}/DiccLESCO.php",
               "prueba": "/prueba_cenarec/DiccLESCO.php"}
INDICE_LEXICO = RAIZ / "data" / "lexicon" / "cenarec_indice.tsv"
CABECERAS_SEGURIDAD = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
                                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
}


# ===================================================================== sin API
class _ModeloRealBloqueado:
    def __init__(self, *a, **k):
        raise agente.ErrorModelo("La demo web no llama a la API: solo usa el modelo simulado.")


def _red_bloqueada(*a, **k):
    raise OSError("La demo web no abre conexiones de red salientes.")


_RED_LOCAL_INSTALADA = False


def _es_local(host) -> bool:
    if isinstance(host, str) and host.lower() in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


def _solo_red_local(evento: str, args) -> None:
    """Gancho de auditoría: el proceso web solo puede conectarse a 127.0.0.1/::1 (ni la API ni ningún otro sitio)."""
    if evento == "socket.connect":
        direccion = args[1]
        if isinstance(direccion, tuple) and direccion and not _es_local(direccion[0]):
            raise OSError("la demo web solo admite conexiones locales")
    elif evento == "socket.getaddrinfo":
        if not _es_local(args[0]):
            raise OSError("la demo web no resuelve nombres externos")


def blindar_sin_api() -> None:
    """Hace imposible una llamada pagada desde este proceso, aunque haya una clave configurada."""
    global _RED_LOCAL_INSTALADA
    if not _RED_LOCAL_INSTALADA:                       # los ganchos de auditoría no se pueden quitar: uno solo
        sys.addaudithook(_solo_red_local)
        _RED_LOCAL_INSTALADA = True
    agente.ModeloClaude = _ModeloRealBloqueado
    agente.cargar_clave = lambda: None
    urllib.request.urlopen = _red_bloqueada
    os.environ.pop("ANTHROPIC_API_KEY", None)          # tampoco la heredan los subprocesos MCP
    os.environ.pop("ANTHROPIC_WORKSPACE_ID", None)


# ===================================================================== privacidad
class Limpiador:
    """Sustituye rutas locales y textos con forma de clave antes de enviarlos al navegador."""

    def __init__(self):
        self.pares: list[tuple[str, str]] = []
        self.agregar(RAIZ, "<repo>")
        self.agregar(Path.home(), "<usuario>")
        self.agregar(Path(tempfile.gettempdir()), "<temporal>")

    def agregar(self, ruta: Path, marcador: str) -> None:
        s = str(ruta)
        for v in {s, s.replace("\\", "/"), s.replace("\\", "\\\\")}:
            self.pares.append((v, marcador))
        self.pares.sort(key=lambda p: len(p[0]), reverse=True)   # la más específica primero

    def ocultar(self, valor: str) -> None:
        """Oculta literalmente un valor sensible (p. ej., la clave capturada al iniciar) en todo lo que se envía."""
        if valor and len(valor) >= 8:
            self.pares.append((valor, "<clave oculta>"))
            self.pares.sort(key=lambda p: len(p[0]), reverse=True)

    def texto(self, s: str) -> str:
        for ruta, marcador in self.pares:
            if ruta.lower() in s.lower():
                s = re.sub(re.escape(ruta), marcador, s, flags=re.IGNORECASE)
        return PATRON_CLAVE.sub("<clave oculta>", s)

    def __call__(self, obj):
        if isinstance(obj, str):
            return self.texto(obj)
        if isinstance(obj, list):
            return [self(x) for x in obj]
        if isinstance(obj, dict):
            return {self.texto(k): self(v) for k, v in obj.items()}
        return obj


def leer_jsonl(texto: str, tolerar_ultima: bool = False) -> list[dict]:
    lineas = [l for l in texto.splitlines() if l.strip()]
    eventos = []
    for i, linea in enumerate(lineas):
        try:
            eventos.append(json.loads(linea))
        except json.JSONDecodeError:
            if tolerar_ultima and i == len(lineas) - 1:   # línea a medio escribir durante la simulación
                break
            raise
    return eventos


# ===================================================================== trazas reales
def cargar_corridas() -> dict[str, dict]:
    """Índice de las corridas formales (válidas D19, código 0), construido solo desde el manifiesto."""
    textos = {}
    for linea in CASOS.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            c = json.loads(linea)
            textos[c["caso_id"]] = c["texto"]
    excluidas = {e["ruta"] for e in json.loads(EXCLUSIONES.read_text(encoding="utf-8"))["trazas_excluidas"]}
    corridas = {}
    for linea in SUPERVISOR.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        r = json.loads(linea)
        idc, conf, rep, caso, nombre = (r.get("id_corrida"), r.get("configuracion"), r.get("repeticion"),
                                        r.get("caso_id"), r.get("traza"))
        if (r.get("experimento") != "experimento" or r.get("valida_D19") is not True or r.get("codigo") != 0
                or not isinstance(idc, str) or not PATRON_ID.fullmatch(idc)
                or idc != f"experimento/{conf}/rep{rep}/{caso}"
                or not isinstance(nombre, str) or not PATRON_TRAZA.fullmatch(nombre)):
            continue
        relativa = f"trazas/experimento/{conf}/rep{rep}/{nombre}"
        if relativa in excluidas:
            continue
        ruta = RAIZ / relativa
        if not ruta.is_file():
            continue
        corridas[idc] = {
            "id": idc, "configuracion": conf, "repeticion": rep, "caso_id": caso,
            "texto": textos.get(caso, ""), "fecha": r.get("fecha", ""), "modelo": r.get("modelo", ""),
            "traza": relativa, "tokens_entrada": r.get("tokens_entrada"), "tokens_salida": r.get("tokens_salida"),
            "costo_estimado_usd": r.get("costo_estimado_usd"), "duracion_s": r.get("duracion_s"),
            "_ruta": ruta,
            "_guardado": RAIZ / "resultados" / "experimento" / conf / f"rep{rep}" / f"{caso}.json",
        }
    return corridas


def corta(nombre: str) -> str:
    return str(nombre).split("__")[-1]


def publico(meta: dict) -> dict:
    return {k: v for k, v in meta.items() if not k.startswith("_")}


def leer_corrida(meta: dict, limpiar: Limpiador) -> dict:
    datos = meta["_ruta"].read_bytes()                   # solo lectura
    guardado = None
    if meta["_guardado"].is_file():
        guardado = json.loads(meta["_guardado"].read_text(encoding="utf-8"))
    return limpiar({
        "origen": "traza_real",
        "aviso": "Ejecución histórica real del experimento (modelo claude-sonnet-5-5 vía API, "
                 f"{meta['fecha']}). Se reproduce desde la traza guardada: no hay llamada en vivo.",
        "corrida": publico(meta),
        "sha256_traza": hashlib.sha256(datos).hexdigest(),
        "eventos": leer_jsonl(datos.decode("utf-8")),
        "guardado": guardado,
        "ruta_guardado": f"resultados/experimento/{meta['configuracion']}/rep{meta['repeticion']}/{meta['caso_id']}.json",
    })


# ===================================================================== simulación
class Simulacion:
    """Una simulación a la vez, en una carpeta temporal propia; la aprobación llega desde la interfaz."""

    def __init__(self, limpiador: Limpiador, silencioso: bool = False, espera_s: float = ESPERA_APROBACION_S,
                 ejecucion=None):
        self.limpiar = limpiador
        self.ejecucion = ejecucion or threading.Lock()   # compartido con el modo de voz: una ejecución a la vez
        self.silencioso = silencioso
        self.espera_s = espera_s
        self.lock = threading.Lock()
        self.aprobacion = threading.Event()
        self.estado = "inactiva"
        self.carpeta: Path | None = None
        self.pendiente = None
        self.respuesta = None
        self.resultado = None
        self.error = None
        self.numero = 0
        self.solicitudes = 0          # aprobaciones pedidas en la simulación actual
        self.cerrando = False
        self.hilo: threading.Thread | None = None

    # ---- ciclo de vida
    def iniciar(self) -> bool:
        with self.lock:
            if self.estado in ("en_curso", "esperando_aprobacion"):
                return False
            if not self.ejecucion.acquire(blocking=False):
                return False
            self._borrar_carpeta()
            self.carpeta = Path(tempfile.mkdtemp(prefix=PREFIJO_TEMPORAL))
            self.estado, self.pendiente, self.respuesta = "en_curso", None, None
            self.resultado = self.error = None
            self.solicitudes, self.cerrando = 0, False
            self.aprobacion.clear()
            self.numero += 1
            self.hilo = threading.Thread(target=self._correr, name="simulacion-lesco", daemon=True)
            self.hilo.start()
            return True

    def _correr(self) -> None:
        original = agente.pedir_aprobacion
        agente.pedir_aprobacion = self._pedir_aprobacion
        try:
            args = agente.argumentos(["--config", str(CONFIG_DEMO), "--simulado", "--caso", CASO_DEMO,
                                      "--casos", str(CASOS_DEMO), "--salidas", str(self.carpeta / "salidas"),
                                      "--trazas", str(self.carpeta / "trazas")])
            if not args.simulado or args.auto_aprobar:
                raise RuntimeError("la demo solo admite el modelo simulado y aprobación humana")
            # La salida de consola del agente incluye rutas locales: no se muestra en la terminal.
            with redirect_stdout(io.StringIO()):
                r = agente.ejecutar(args)
            with self.lock:
                self.resultado = {"codigo": r["codigo"], "motivo": r["motivo"]}
                self.estado = "terminada"
        except Exception as e:  # se muestra en la interfaz; el plan B es la traza histórica
            with self.lock:
                self.error = f"{type(e).__name__}: {e}"
                self.estado = "error"
        finally:
            agente.pedir_aprobacion = original
            self.ejecucion.release()

    def _pedir_aprobacion(self, nombre: str, argumentos: dict, auto: bool) -> tuple[bool, str]:
        with self.lock:
            if self.cerrando:
                return False, "denegada: la demo se estaba cerrando"
            self.estado = "esperando_aprobacion"
            self.pendiente = {"nombre": nombre, "argumentos": argumentos}
            self.respuesta = None
            self.solicitudes += 1
        if not self.silencioso:
            print(f"[demo web] esperando aprobación de {corta(nombre)} en la interfaz…", file=sys.stderr, flush=True)
        respondida = self.aprobacion.wait(self.espera_s)
        with self.lock:
            aprobada = bool(respondida and self.respuesta is True)
            self.pendiente, self.estado = None, "en_curso"
            self.aprobacion.clear()
        if not respondida:
            return False, "denegada: nadie respondió en la interfaz de la demo dentro del tiempo límite"
        if aprobada:
            return True, "aprobada por una persona en la interfaz web local de la demo"
        return False, "rechazada por una persona en la interfaz web local de la demo"

    def responder(self, aprobar: bool) -> bool:
        with self.lock:
            if self.estado != "esperando_aprobacion" or self.aprobacion.is_set():
                return False
            self.respuesta = aprobar
            self.aprobacion.set()
            return True

    # ---- lectura
    def instantanea(self) -> dict:
        with self.lock:
            estado, carpeta = self.estado, self.carpeta
            datos = {"origen": "simulacion", "estado": estado, "numero": self.numero,
                     "solicitudes_aprobacion": self.solicitudes,
                     "pendiente": self.pendiente, "resultado": self.resultado, "error": self.error}
        eventos, guardado = [], None
        if carpeta is not None:
            trazas = sorted((carpeta / "trazas").glob("*.jsonl"))
            if trazas:
                eventos = leer_jsonl(trazas[-1].read_text(encoding="utf-8"), tolerar_ultima=True)
            archivo = carpeta / "salidas" / f"{CASO_DEMO}.json"
            if archivo.is_file():
                try:
                    guardado = json.loads(archivo.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    guardado = None
        datos.update(eventos=eventos, guardado=guardado,
                     aviso="Agente con modelo SIMULADO: los turnos del modelo son un guion fijo "
                           "(agente/guion_simulado.json), no decisiones autónomas. El servidor MCP, la "
                           "política y la traza son los reales. Sin API. Carpeta temporal aislada.")
        limpiar = self.limpiar
        if carpeta is not None:
            limpiar = Limpiador()
            limpiar.pares = list(self.limpiar.pares)
            limpiar.agregar(carpeta, "<carpeta temporal aislada>")
        return limpiar(datos)

    # ---- limpieza (solo la carpeta temporal que esta clase creó)
    def _borrar_carpeta(self) -> None:
        c = self.carpeta
        if (c is not None and c.name.startswith(PREFIJO_TEMPORAL)
                and c.resolve().parent == Path(tempfile.gettempdir()).resolve()):
            shutil.rmtree(c, ignore_errors=True)
        self.carpeta = None

    def cerrar(self) -> None:
        with self.lock:
            self.cerrando = True
            self.respuesta = False
            self.aprobacion.set()
        if self.hilo is not None:
            self.hilo.join(timeout=15)
        with self.lock:
            self._borrar_carpeta()


# ===================================================================== HTTP
class Manejador(BaseHTTPRequestHandler):
    server_version = "LESCO-demo"
    sys_version = ""

    # ---- comprobaciones
    def _permitidos(self) -> set[str]:
        puerto = self.server.server_address[1]
        return {f"127.0.0.1:{puerto}", f"localhost:{puerto}"}

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in self._permitidos()

    def _origen_ok(self) -> bool:
        origen = self.headers.get("Origin")
        return origen is None or origen in {f"http://{h}" for h in self._permitidos()}

    def _origen_estricto_ok(self) -> bool:
        """Para las acciones con costo (/api/voz-ia/*): Origin OBLIGATORIO y propio, cabecera propia de la
        interfaz (fuerza una verificación previa CORS que la demo nunca concede) y, si el navegador la envía,
        Sec-Fetch-Site same-origin."""
        origen = self.headers.get("Origin")
        sitio = self.headers.get("Sec-Fetch-Site")
        return (origen in {f"http://{h}" for h in self._permitidos()}
                and self.headers.get("X-Lesco-Demo") == "1"
                and sitio in (None, "same-origin"))

    # ---- respuestas
    def _enviar(self, codigo: int, cuerpo: bytes, tipo: str, extra: dict | None = None) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        for k, v in {**getattr(self.server, "cabeceras", CABECERAS_SEGURIDAD), **(extra or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, codigo: int, datos) -> None:
        self._enviar(codigo, json.dumps(datos, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, codigo: int, mensaje: str) -> None:
        self._json(codigo, {"error": mensaje})

    def _pagina_de_prueba(self, consulta: str) -> None:
        """Sustituto LOCAL de una entrada de CENAREC, solo en modo «prueba». No contiene video ni nada del sitio:
        solo el idw y la glosa del índice local, rotulados como contenido de prueba."""
        valores = parse_qs(consulta, keep_blank_values=True)
        idw = valores.get("idw", [""])
        if set(valores) != {"idw"} or len(idw) != 1 or not re.fullmatch(r"[1-9]\d{0,4}", idw[0]) \
                or int(idw[0]) not in self.server.glosas:
            return self._error(404, "entrada de prueba desconocida")
        glosa = html.escape(self.server.glosas[int(idw[0])])
        cuerpo = (f"<!doctype html><html lang='es'><meta charset='utf-8'><title>PRUEBA LOCAL · {glosa}</title>"
                  "<body style='font-family:Segoe UI,Arial,sans-serif;margin:0;background:#fff;color:#14181f'>"
                  "<div style='background:#b42318;color:#fff;font-weight:800;padding:10px 16px;font-size:20px'>"
                  "PÁGINA DE PRUEBA LOCAL — NO ES CONTENIDO DE CENAREC</div>"
                  f"<div style='padding:16px 20px'><h1 style='margin:0 0 4px'>{glosa}</h1>"
                  f"<p style='margin:0 0 14px;color:#4a5361'>idw={int(idw[0])} · glosa tomada del índice local "
                  "data/lexicon/cenarec_indice.tsv</p>"
                  "<div style='width:640px;height:360px;border:3px dashed #9a5b00;display:flex;align-items:center;"
                  "justify-content:center;text-align:center;font-size:22px;color:#9a5b00;background:#fdf3e1'>"
                  "Aquí estaría el reproductor oficial de CENAREC.<br>Esta prueba no contiene ni descarga videos.</div>"
                  "</div></body></html>").encode("utf-8")
        return self._enviar(200, cuerpo, "text/html; charset=utf-8", {
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'self'"})

    # ---- métodos
    def do_GET(self) -> None:
        if not self._host_ok():
            return self._error(403, "solo se admite 127.0.0.1 o localhost")
        partes = urlsplit(self.path)
        ruta = partes.path
        if ruta in ESTATICOS:
            nombre, tipo = ESTATICOS[ruta]
            return self._enviar(200, (WEB / nombre).read_bytes(), tipo)
        if ruta == "/api/info":
            return self._json(200, {"nombre": "LESCO-Agent · visor local", "host": HOST, "sin_api": True,
                                    "corridas": len(self.server.corridas),
                                    "visor_cenarec": {"modo": self.server.visor,
                                                      "base": VISOR_BASES[self.server.visor]},
                                    "ia_real": {"habilitada": self.server.voz_ia.habilitada,
                                                "maximo": self.server.voz_ia.restantes() + self.server.voz_ia.usadas}})
        if ruta == "/prueba_cenarec/DiccLESCO.php" and self.server.visor == "prueba":
            return self._pagina_de_prueba(partes.query)
        if ruta == "/api/corridas":
            return self._json(200, {"corridas": [publico(m) for m in self.server.corridas.values()]})
        if ruta == "/api/corrida":
            idc = parse_qs(partes.query).get("id", [""])[0]
            meta = self.server.corridas.get(idc) if PATRON_ID.fullmatch(idc or "") else None
            if meta is None:
                return self._error(404, "corrida desconocida")
            return self._json(200, leer_corrida(meta, self.server.limpiador))
        if ruta == "/api/simulacion":
            return self._json(200, self.server.simulacion.instantanea())
        if ruta == "/api/voz":
            return self._json(200, self.server.voz.instantanea())
        if ruta == "/api/voz-ia":
            return self._json(200, self.server.voz_ia.instantanea())
        return self._error(404, "no encontrado")

    def do_POST(self) -> None:
        try:
            largo = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            largo = None
        # El cuerpo se lee (hasta 64 KiB) ANTES de cualquier respuesta: si se responde sin leerlo,
        # Windows puede abortar la conexión y el cliente no llega a ver el código de error.
        crudo = self.rfile.read(min(largo, 65536)) if largo and largo > 0 else b""
        if not self._host_ok() or not self._origen_ok():
            return self._error(403, "origen no permitido")
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self._error(415, "se espera application/json")
        if largo is None:
            return self._error(400, "Content-Length inválido")
        limite = MAX_CUERPO_VOZ if urlsplit(self.path).path in ("/api/voz/iniciar", "/api/voz-ia/preparar") else MAX_CUERPO
        if largo < 0 or largo > limite:
            return self._error(413, "cuerpo demasiado grande")
        try:
            cuerpo = json.loads(crudo.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._error(400, "JSON inválido")
        if not isinstance(cuerpo, dict):
            return self._error(400, "se espera un objeto JSON")
        ruta = urlsplit(self.path).path
        if ruta.startswith("/api/voz-ia/") and not self._origen_estricto_ok():
            return self._error(403, "solicitud no admitida para acciones con costo (origen o cabeceras)")
        sim = self.server.simulacion
        if ruta == "/api/simulacion/iniciar":
            if cuerpo:
                return self._error(400, "esta acción no admite parámetros")
            if not sim.iniciar():
                return self._error(409, "ya hay una ejecución en curso (simulación o voz)")
            return self._json(202, {"iniciada": True})
        if ruta == "/api/simulacion/aprobacion":
            if set(cuerpo) != {"aprobar"} or not isinstance(cuerpo["aprobar"], bool):
                return self._error(400, "se espera exactamente {\"aprobar\": true|false}")
            if not sim.responder(cuerpo["aprobar"]):
                return self._error(409, "no hay ninguna aprobación pendiente")
            return self._json(200, {"registrada": True, "aprobar": cuerpo["aprobar"]})
        voz = self.server.voz
        if ruta == "/api/voz/iniciar":
            # El texto es un DATO no confiable: se valida y solo se usa como transcripción del caso temporal.
            if set(cuerpo) != {"texto"} or not isinstance(cuerpo["texto"], str):
                return self._error(400, "se espera exactamente {\"texto\": \"<oración>\"}")
            try:
                iniciada, detalle = voz.iniciar(cuerpo["texto"])
            except TextoInvalido as e:
                return self._error(400, f"texto no válido: {e}")
            if not iniciada:
                return self._error(409, detalle)
            return self._json(202, {"iniciada": True, "caso_id": detalle})
        if ruta == "/api/voz/aprobacion":
            if set(cuerpo) != {"aprobar"} or not isinstance(cuerpo["aprobar"], bool):
                return self._error(400, "se espera exactamente {\"aprobar\": true|false}")
            if not voz.responder(cuerpo["aprobar"]):
                return self._error(409, "no hay ninguna aprobación pendiente")
            return self._json(200, {"registrada": True, "aprobar": cuerpo["aprobar"]})
        ia = self.server.voz_ia
        if ruta == "/api/voz-ia/preparar":
            # Solo prepara: valida el texto y emite un permiso de un solo uso. No lanza nada.
            if set(cuerpo) != {"texto"} or not isinstance(cuerpo["texto"], str):
                return self._error(400, "se espera exactamente {\"texto\": \"<oración>\"}")
            try:
                codigo, datos = ia.preparar(cuerpo["texto"])
            except TextoInvalido as e:
                return self._error(400, f"texto no válido: {e}")
            return self._json(codigo, datos)
        if ruta == "/api/voz-ia/autorizar":
            # Clic explícito de una persona: canjea el permiso y lanza UNA ejecución real.
            if set(cuerpo) != {"token"} or not isinstance(cuerpo["token"], str) or len(cuerpo["token"]) > 64:
                return self._error(400, "se espera exactamente {\"token\": \"<permiso>\"}")
            codigo, datos = ia.autorizar(cuerpo["token"])
            return self._json(codigo, datos)
        if ruta == "/api/voz-ia/cancelar":
            if cuerpo:
                return self._error(400, "esta acción no admite parámetros")
            ia.cancelar()
            return self._json(200, {"cancelado": True})
        if ruta == "/api/voz-ia/aprobacion":
            if set(cuerpo) != {"aprobar"} or not isinstance(cuerpo["aprobar"], bool):
                return self._error(400, "se espera exactamente {\"aprobar\": true|false}")
            if not ia.responder(cuerpo["aprobar"]):
                return self._error(409, "no hay ninguna aprobación pendiente")
            return self._json(200, {"registrada": True, "aprobar": cuerpo["aprobar"]})
        return self._error(404, "no encontrado")

    def _no_permitido(self) -> None:
        self._error(405, "método no permitido")

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _no_permitido

    def log_message(self, formato: str, *args) -> None:
        if self.command == "GET" and urlsplit(self.path).path in ("/api/simulacion", "/api/voz", "/api/voz-ia"):
            return                                     # sondeo de la interfaz: no se registra
        if not self.server.silencioso:
            sys.stderr.write(f"[demo web] {self.command} {urlsplit(self.path).path} -> {args[1] if len(args) > 1 else ''}\n")


class ServidorDemo(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def cabeceras_para(visor: str) -> dict:
    """Cabeceras de seguridad según el visor. Solo el modo «oficial» admite marcos de otro origen, y solo de CENAREC."""
    cab = dict(CABECERAS_SEGURIDAD)
    if visor == "oficial":
        cab["Content-Security-Policy"] += f"; frame-src {DOMINIO_CENAREC}"
        cab["Permissions-Policy"] += f', autoplay=(self "{DOMINIO_CENAREC}"), fullscreen=(self "{DOMINIO_CENAREC}")'
    elif visor == "prueba":
        cab["Content-Security-Policy"] += "; frame-src 'self'"
        cab["Permissions-Policy"] += ", autoplay=(self), fullscreen=(self)"
    return cab


def cargar_glosas() -> dict[int, str]:
    glosas = {}
    for linea in INDICE_LEXICO.read_text(encoding="utf-8").splitlines()[1:]:
        if linea.strip():
            idw, _, glosa = linea.partition("\t")
            glosas[int(idw)] = glosa
    return glosas


def crear_servidor(puerto: int = PUERTO_POR_DEFECTO, silencioso: bool = False,
                   espera_aprobacion_s: float = ESPERA_APROBACION_S, visor: str = "desactivado",
                   permitir_api: bool = False, api_prueba=None) -> ServidorDemo:
    if visor not in VISOR_BASES:
        raise ValueError(f"modo de visor desconocido: {visor!r}")
    if api_prueba is not None and not permitir_api:
        raise ValueError("api_prueba exige permitir_api")
    # Fase 2: si se permite la API (y no es una prueba), las variables de la clave se retiran de ESTE proceso y
    # se guardan solo para el entorno del proceso hijo. Nunca se registran ni se envían al navegador.
    entorno_api = ({k: os.environ[k] for k in VARIABLES_API if os.environ.get(k)}
                   if permitir_api and api_prueba is None else {})
    blindar_sin_api()
    servidor = ServidorDemo((HOST, puerto), Manejador)
    servidor.visor = visor
    servidor.cabeceras = cabeceras_para(visor)
    servidor.glosas = cargar_glosas() if visor == "prueba" else {}
    servidor.silencioso = silencioso
    servidor.limpiador = Limpiador()
    servidor.corridas = cargar_corridas()
    servidor.ejecucion = threading.Lock()
    servidor.simulacion = Simulacion(servidor.limpiador, silencioso, espera_aprobacion_s, servidor.ejecucion)
    servidor.voz = Voz(servidor.limpiador, servidor.ejecucion, silencioso, espera_aprobacion_s)
    for valor in entorno_api.values():
        servidor.limpiador.ocultar(valor)               # defensa adicional: el valor literal nunca sale
    servidor.voz_ia = VozIA(servidor.limpiador, servidor.ejecucion, habilitada=permitir_api,
                            entorno_api=entorno_api, silencioso=silencioso, espera_s=espera_aprobacion_s,
                            modo_prueba=api_prueba)
    return servidor


def _interrumpir(*_):
    raise KeyboardInterrupt


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Visor web local de LESCO-Agent (solo 127.0.0.1, sin API).")
    ap.add_argument("--puerto", type=int, default=PUERTO_POR_DEFECTO, help="puerto local (1024-65535)")
    ap.add_argument("--abrir", action="store_true", help="abre el navegador predeterminado")
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--visor-cenarec", action="store_true",
                       help="habilita el visor de señas con la página OFICIAL de CENAREC en un iframe "
                            "(usar solo con las condiciones de uso y el permiso de CENAREC confirmados)")
    grupo.add_argument("--visor-cenarec-prueba", action="store_true",
                       help="habilita el visor con una página LOCAL de prueba (no contacta a CENAREC)")
    ap.add_argument("--permitir-api", action="store_true",
                    help="habilita «Voz con IA real» (claude-sonnet-5-5, configuración B) en un proceso aparte; "
                         "cada ejecución requiere «Autorizar» en la interfaz y tiene costo. Máximo 5 por sesión.")
    a = ap.parse_args()
    if not 1024 <= a.puerto <= 65535:
        ap.error("el puerto debe estar entre 1024 y 65535")
    try:
        visor = "oficial" if a.visor_cenarec else "prueba" if a.visor_cenarec_prueba else "desactivado"
        servidor = crear_servidor(a.puerto, visor=visor, permitir_api=a.permitir_api)
    except OSError as e:
        print(f"No se pudo abrir 127.0.0.1:{a.puerto} ({e}). ¿Ya hay una demo abierta? Pruebe --puerto 8766.")
        return 1
    url = f"http://{HOST}:{a.puerto}/"
    print("LESCO-Agent · visor local de la demostración")
    print(f"  {url}")
    print(f"  {len(servidor.corridas)} corridas formales disponibles · modelo simulado · sin API · solo 127.0.0.1")
    print("  Modo de voz: motor local de reglas (no es un LLM); el audio lo procesa el navegador.")
    if servidor.visor == "oficial":
        print("  Visor CENAREC HABILITADO (página oficial en iframe). Úselo solo con las condiciones de uso y el")
        print("  permiso de CENAREC confirmados: que sea técnicamente posible no es una autorización.")
    elif servidor.visor == "prueba":
        print("  Visor CENAREC en modo PRUEBA: página local de sustitución, no contacta a CENAREC.")
    else:
        print("  Visor CENAREC desactivado (se habilita con --visor-cenarec).")
    if servidor.voz_ia.habilitada:
        print("  IA REAL HABILITADA: «Voz con IA real» usa la API con costo (≈US$0,06 por frase, estimación).")
        print("  Cada ejecución requiere «Autorizar» en la interfaz; máximo 5 por sesión y presupuesto estimado de US$1,00; sin reintentos.")
    else:
        print("  IA real deshabilitada (se habilita con --permitir-api).")
    print("  Ctrl+C para cerrar.", flush=True)
    if hasattr(signal, "SIGBREAK"):                    # Windows: Ctrl+Break también cierra limpio
        signal.signal(signal.SIGBREAK, _interrumpir)
    if a.abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        print("\nCerrando la demo…")
    finally:
        servidor.simulacion.cerrar()
        servidor.voz.cerrar()
        servidor.voz_ia.cerrar()
        servidor.server_close()
    print("Demo cerrada. Carpeta temporal eliminada.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
