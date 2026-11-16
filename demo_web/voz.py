"""
Adaptador del modo de voz de la demo web (fase 1, sin API).

Recibe un texto CONFIRMADO por una persona (dictado con el reconocimiento del navegador o escrito a
mano), lo valida como dato no confiable, crea un caso temporal vinculado a ese texto y ejecuta el
host real de agente/agente.py con el MOTOR LOCAL DE REGLAS (demo_web/modelo_reglas.py, no es un LLM),
el servidor MCP real y politica/politica_demo.json. Todo se escribe en una carpeta temporal propia
(%TEMP%\\lesco_demo_web_voz_*), que se borra al iniciar otra ejecución o al cerrar la demo.

No se modifican el agente, el servidor MCP, las configuraciones ni el dataset. El audio nunca llega
aquí: el reconocimiento ocurre en el navegador y este módulo solo recibe texto.

Metadatos de origen: el host escribe modelo="simulado" en el evento «inicio» de la traza para
cualquier modelo que no sea la API. Este adaptador no toca la traza; añade, aparte, un archivo
origen.json en la carpeta temporal y el campo «motor» en su respuesta, que identifican el origen real.
"""

import io
import json
import re
import shutil
import sys
import tempfile
import threading
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ / "agente"))
sys.path.insert(0, str(AQUI))
import agente  # noqa: E402
from modelo_reglas import ETIQUETA, MAX_PALABRA, MAX_PALABRAS, ModeloReglas, palabras_de_contenido  # noqa: E402

CONFIG_VOZ = AQUI / "configs" / "voz.json"
PREFIJO_TEMPORAL = "lesco_demo_web_voz_"
MAX_CARACTERES = 200
# Solo texto de una oración: letras (con tildes, ñ, ü), dígitos, espacios y puntuación común.
# Sin barras, comillas invertidas, llaves, signos de comandos ni caracteres de control.
PERMITIDOS = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ .,;:¿?¡!'\"«»()\-]+")
MOTOR = {
    "tipo": "motor_local_de_reglas",
    "etiqueta": ETIQUETA,
    "es_llm": False,
    "usa_api": False,
    "usa_skill": False,
    "reglas": "demo_web/modelo_reglas.py (R1–R6): palabras tal cual sin lematizar, solo coincidencias "
              "exactas, SIN_COBERTURA si no hay exacta, validar, guardar una vez con aprobación humana.",
    "nota_traza": "El evento «inicio» de la traza dice modelo=\"simulado\" porque el host así nombra a "
                  "cualquier modelo que no sea la API; aquí corresponde al motor local de reglas, no al "
                  "guion fijo ni a un LLM.",
}


class TextoInvalido(ValueError):
    pass


def validar_texto(texto) -> str:
    """Normaliza y valida el texto confirmado. Devuelve el texto limpio o lanza TextoInvalido."""
    if not isinstance(texto, str):
        raise TextoInvalido("el texto debe ser una cadena")
    if re.search(r"[\x00-\x1f\x7f]", texto.replace("\n", " ").replace("\t", " ")):
        raise TextoInvalido("el texto contiene caracteres de control")
    limpio = " ".join(texto.split())
    if not limpio:
        raise TextoInvalido("el texto está vacío")
    if len(limpio) > MAX_CARACTERES:
        raise TextoInvalido(f"el texto supera {MAX_CARACTERES} caracteres; dicte una sola oración")
    if not PERMITIDOS.fullmatch(limpio):
        malos = sorted(set(c for c in limpio if not PERMITIDOS.fullmatch(c)))
        raise TextoInvalido("el texto contiene caracteres no admitidos: " + " ".join(repr(c) for c in malos))
    contenido = palabras_de_contenido(limpio)
    if not contenido:
        raise TextoInvalido("la oración no tiene palabras de contenido que buscar")
    if len(contenido) > MAX_PALABRAS:
        raise TextoInvalido(f"la oración tiene {len(contenido)} palabras de contenido; el máximo es {MAX_PALABRAS}")
    largas = [p for p in contenido if len(p) > MAX_PALABRA]
    if largas:
        raise TextoInvalido(f"hay palabras de más de {MAX_PALABRA} caracteres")
    return limpio


def _leer_jsonl(texto: str) -> list[dict]:
    eventos = []
    lineas = [l for l in texto.splitlines() if l.strip()]
    for i, linea in enumerate(lineas):
        try:
            eventos.append(json.loads(linea))
        except json.JSONDecodeError:
            if i == len(lineas) - 1:     # última línea a medio escribir
                break
            raise
    return eventos


class Voz:
    """Una ejecución a la vez (candado compartido con la simulación); aprobación solo desde la interfaz."""

    def __init__(self, limpiador, ejecucion: threading.Lock, silencioso: bool = False, espera_s: float = 600):
        self.limpiar = limpiador
        self.ejecucion = ejecucion
        self.silencioso = silencioso
        self.espera_s = espera_s
        self.lock = threading.Lock()
        self.aprobacion = threading.Event()
        self.estado = "inactiva"
        self.carpeta: Path | None = None
        self.caso_id = None
        self.texto = None
        self.pendiente = None
        self.respuesta = None
        self.resultado = None
        self.error = None
        self.numero = 0
        self.solicitudes = 0
        self.cerrando = False
        self.hilo: threading.Thread | None = None

    # ---- ciclo de vida
    def iniciar(self, texto) -> tuple[bool, str]:
        """(True, caso_id) si arrancó; (False, motivo) si no. Lanza TextoInvalido si el texto no vale."""
        limpio = validar_texto(texto)
        with self.lock:
            if self.estado in ("en_curso", "esperando_aprobacion"):
                return False, "ya hay una ejecución por voz en curso"
            if not self.ejecucion.acquire(blocking=False):
                return False, "ya hay otra ejecución en curso (simulación); espere a que termine"
            try:
                self._borrar_carpeta()
                self.numero += 1
                self.caso_id = f"voz-{self.numero:03d}"
                self.texto = limpio
                self.carpeta = Path(tempfile.mkdtemp(prefix=PREFIJO_TEMPORAL))
                casos = self.carpeta / "casos_voz.jsonl"
                casos.write_text(json.dumps({"caso_id": self.caso_id, "texto": limpio}, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
                (self.carpeta / "origen.json").write_text(json.dumps(
                    {**MOTOR, "caso_id": self.caso_id, "creado": datetime.now().isoformat(timespec="seconds"),
                     "entrada": "texto confirmado por una persona en la interfaz (dictado o escrito)"},
                    ensure_ascii=False, indent=2), encoding="utf-8")
                self.estado, self.pendiente, self.respuesta = "en_curso", None, None
                self.resultado = self.error = None
                self.solicitudes, self.cerrando = 0, False
                self.aprobacion.clear()
                self.hilo = threading.Thread(target=self._correr, name="voz-lesco", daemon=True)
                self.hilo.start()
            except Exception:
                self.ejecucion.release()
                raise
            return True, self.caso_id

    def _correr(self) -> None:
        aprobacion_original, modelo_original = agente.pedir_aprobacion, agente.ModeloSimulado
        caso = self.caso_id
        agente.pedir_aprobacion = self._pedir_aprobacion
        # El host instancia ModeloSimulado(ruta_guion) con --simulado: aquí se sustituye por el motor de
        # reglas (la ruta del guion se ignora: el guion fijo NO se usa en este modo).
        agente.ModeloSimulado = lambda _ruta: ModeloReglas(caso)
        try:
            args = agente.argumentos(["--config", str(CONFIG_VOZ), "--simulado", "--caso", caso,
                                      "--casos", str(self.carpeta / "casos_voz.jsonl"),
                                      "--salidas", str(self.carpeta / "salidas"),
                                      "--trazas", str(self.carpeta / "trazas")])
            if not args.simulado or args.auto_aprobar:
                raise RuntimeError("el modo de voz solo admite el motor local y aprobación humana")
            with redirect_stdout(io.StringIO()):      # la consola del agente incluye rutas locales
                r = agente.ejecutar(args)
            with self.lock:
                self.resultado = {"codigo": r["codigo"], "motivo": r["motivo"]}
                self.estado = "terminada"
        except Exception as e:
            with self.lock:
                self.error = f"{type(e).__name__}: {e}"
                self.estado = "error"
        finally:
            agente.pedir_aprobacion, agente.ModeloSimulado = aprobacion_original, modelo_original
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
            print(f"[demo web] voz: esperando aprobación de {nombre.split('__')[-1]} en la interfaz…",
                  file=sys.stderr, flush=True)
        respondida = self.aprobacion.wait(self.espera_s)
        with self.lock:
            aprobada = bool(respondida and self.respuesta is True)
            self.pendiente, self.estado = None, "en_curso"
            self.aprobacion.clear()
        if not respondida:
            return False, "denegada: nadie respondió en la interfaz de la demo dentro del tiempo límite"
        if aprobada:
            return True, "aprobada por una persona en la interfaz web local de la demo (clic, no voz)"
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
            carpeta = self.carpeta
            datos = {"origen": "voz", "estado": self.estado, "numero": self.numero, "caso_id": self.caso_id,
                     "texto_confirmado": self.texto, "pendiente": self.pendiente, "resultado": self.resultado,
                     "error": self.error, "solicitudes_aprobacion": self.solicitudes, "motor": MOTOR}
        eventos, guardado, origen = [], None, None
        if carpeta is not None:
            trazas = sorted((carpeta / "trazas").glob("*.jsonl"))
            if trazas:
                eventos = _leer_jsonl(trazas[-1].read_text(encoding="utf-8"))
            archivo = carpeta / "salidas" / f"{self.caso_id}.json"
            if archivo.is_file():
                try:
                    guardado = json.loads(archivo.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    guardado = None
            if (carpeta / "origen.json").is_file():
                origen = json.loads((carpeta / "origen.json").read_text(encoding="utf-8"))
        datos.update(eventos=eventos, guardado=guardado, origen_registrado=origen,
                     aviso=f"{ETIQUETA}. Decide con reglas fijas y visibles (demo_web/modelo_reglas.py); el "
                           "servidor MCP, la política, la aprobación y la traza son los reales. Sin API. "
                           "Carpeta temporal aislada.")
        limpiar = self.limpiar
        if carpeta is not None:
            limpiar = type(self.limpiar)()
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
