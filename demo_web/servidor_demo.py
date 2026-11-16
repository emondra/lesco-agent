#!/usr/bin/env python3
"""
Visor web LOCAL de LESCO-Agent para la defensa académica.

Dos modos:
    traza real   reproduce, sin modificarla, una de las 288 corridas formales A/B del experimento
                 (resultados/experimento/supervisor.jsonl). Es una ejecución histórica, no una
                 llamada en vivo.
    simulación   ejecuta el agente con el modelo SIMULADO (guion fijo agente/guion_simulado.json),
                 el servidor MCP real y la política de la demo, en una carpeta temporal aislada.
                 El guardado pide aprobación humana desde la interfaz.

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
import hashlib
import io
import json
import os
import re
import shutil
import signal
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

# Lista blanca: la URL solo elige una entrada de este diccionario; nunca se construye una ruta con ella.
ESTATICOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/estilo.css": ("estilo.css", "text/css; charset=utf-8"),
}
PATRON_ID = re.compile(r"experimento/[AB]/rep[1-9]/[A-Za-z0-9][A-Za-z0-9_-]{0,39}")
PATRON_TRAZA = re.compile(r"[AB]_[A-Za-z0-9][A-Za-z0-9_-]{0,80}\.jsonl")
PATRON_CLAVE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{4,}")
CABECERAS_SEGURIDAD = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
                                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}


# ===================================================================== sin API
class _ModeloRealBloqueado:
    def __init__(self, *a, **k):
        raise agente.ErrorModelo("La demo web no llama a la API: solo usa el modelo simulado.")


def _red_bloqueada(*a, **k):
    raise OSError("La demo web no abre conexiones de red salientes.")


def blindar_sin_api() -> None:
    """Hace imposible una llamada pagada desde este proceso, aunque haya una clave configurada."""
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

    def __init__(self, limpiador: Limpiador, silencioso: bool = False, espera_s: float = ESPERA_APROBACION_S):
        self.limpiar = limpiador
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

    # ---- respuestas
    def _enviar(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        for k, v in CABECERAS_SEGURIDAD.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, codigo: int, datos) -> None:
        self._enviar(codigo, json.dumps(datos, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, codigo: int, mensaje: str) -> None:
        self._json(codigo, {"error": mensaje})

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
                                    "corridas": len(self.server.corridas)})
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
        return self._error(404, "no encontrado")

    def do_POST(self) -> None:
        if not self._host_ok() or not self._origen_ok():
            return self._error(403, "origen no permitido")
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self._error(415, "se espera application/json")
        try:
            largo = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._error(400, "Content-Length inválido")
        if largo < 0 or largo > MAX_CUERPO:
            return self._error(413, "cuerpo demasiado grande")
        try:
            cuerpo = json.loads(self.rfile.read(largo).decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._error(400, "JSON inválido")
        if not isinstance(cuerpo, dict):
            return self._error(400, "se espera un objeto JSON")
        ruta = urlsplit(self.path).path
        sim = self.server.simulacion
        if ruta == "/api/simulacion/iniciar":
            if cuerpo:
                return self._error(400, "esta acción no admite parámetros")
            if not sim.iniciar():
                return self._error(409, "ya hay una simulación en curso")
            return self._json(202, {"iniciada": True})
        if ruta == "/api/simulacion/aprobacion":
            if set(cuerpo) != {"aprobar"} or not isinstance(cuerpo["aprobar"], bool):
                return self._error(400, "se espera exactamente {\"aprobar\": true|false}")
            if not sim.responder(cuerpo["aprobar"]):
                return self._error(409, "no hay ninguna aprobación pendiente")
            return self._json(200, {"registrada": True, "aprobar": cuerpo["aprobar"]})
        return self._error(404, "no encontrado")

    def _no_permitido(self) -> None:
        self._error(405, "método no permitido")

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _no_permitido

    def log_message(self, formato: str, *args) -> None:
        if self.command == "GET" and urlsplit(self.path).path == "/api/simulacion":
            return                                     # sondeo de la interfaz: no se registra
        if not self.server.silencioso:
            sys.stderr.write(f"[demo web] {self.command} {urlsplit(self.path).path} -> {args[1] if len(args) > 1 else ''}\n")


class ServidorDemo(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def crear_servidor(puerto: int = PUERTO_POR_DEFECTO, silencioso: bool = False,
                   espera_aprobacion_s: float = ESPERA_APROBACION_S) -> ServidorDemo:
    blindar_sin_api()
    servidor = ServidorDemo((HOST, puerto), Manejador)
    servidor.silencioso = silencioso
    servidor.limpiador = Limpiador()
    servidor.corridas = cargar_corridas()
    servidor.simulacion = Simulacion(servidor.limpiador, silencioso, espera_aprobacion_s)
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
    a = ap.parse_args()
    if not 1024 <= a.puerto <= 65535:
        ap.error("el puerto debe estar entre 1024 y 65535")
    try:
        servidor = crear_servidor(a.puerto)
    except OSError as e:
        print(f"No se pudo abrir 127.0.0.1:{a.puerto} ({e}). ¿Ya hay una demo abierta? Pruebe --puerto 8766.")
        return 1
    url = f"http://{HOST}:{a.puerto}/"
    print("LESCO-Agent · visor local de la demostración")
    print(f"  {url}")
    print(f"  {len(servidor.corridas)} corridas formales disponibles · modelo simulado · sin API · solo 127.0.0.1")
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
        servidor.server_close()
    print("Demo cerrada. Carpeta temporal eliminada.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
