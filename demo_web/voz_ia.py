"""
Modo «Voz con IA real» (fase 2) del lado del servidor web. Deshabilitado por defecto.

    preparar(texto)   valida la oración (como el modo de voz) y devuelve un PERMISO de un solo uso con la
                      estimación de costo y las ejecuciones restantes. No lanza nada ni contacta a nadie.
    autorizar(token)  canjea el permiso cuando la interfaz envía «Autorizar esta ejecución» y lanza UN proceso
                      hijo demo_web/ejecutor_api.py. Solo aquí puede producirse una llamada a la API.
                      El servidor no puede verificar un clic físico: la autorización se apoya en controles
                      verificables (permiso de un solo uso ligado al texto, vigencia, espera mínima tras
                      mostrar el costo, mismo origen con cabecera propia, tope y presupuesto de sesión).

Garantías:
    - El servidor web nunca llama a la API: la ejecución real ocurre en el proceso hijo.
    - Sin --permitir-api al iniciar la demo, preparar y autorizar responden 403 y no se lanza nada.
    - Máximo MAXIMO_POR_SESION ejecuciones por sesión del servidor; cuentan al autorizar, terminen como terminen.
    - Presupuesto ESTIMADO de la sesión (PRESUPUESTO_SESION_USD): no se autoriza una ejecución si lo estimado ya
      gastado + el peor caso teórico de una ejecución lo superaría. Es una estimación con la tabla de precios
      del proyecto, no la facturación del proveedor.
    - Sin reintentos automáticos: si el proceso hijo falla, se informa y no se relanza.
    - La clave nunca llega al navegador: si existe en el entorno al iniciar, solo se pasa al entorno del proceso
      hijo; las respuestas pasan por el Limpiador (rutas y textos con forma de clave).
    - La aprobación de guardar llega solo por /api/voz-ia/aprobacion desde la interfaz; la voz y el modelo no
      autorizan nada.
    - Al cerrar o al vencer el tiempo máximo se termina el ÁRBOL de procesos (ejecutor y servidor MCP).
"""

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ / "eval"))
from voz import TextoInvalido, _leer_jsonl, validar_texto  # noqa: E402

EJECUTOR = AQUI / "ejecutor_api.py"
CONFIG = AQUI / "configs" / "voz_api.json"
SUPERVISOR = RAIZ / "resultados" / "experimento" / "supervisor.jsonl"
PREFIJO_TEMPORAL = "lesco_demo_web_vozia_"
MAXIMO_POR_SESION = 5
VIGENCIA_PERMISO_S = 120
ESPERA_MINIMA_S = 1.5              # entre mostrar el costo (preparar) y autorizar
PRESUPUESTO_SESION_USD = 1.00      # presupuesto ESTIMADO por sesión del servidor (no es facturación)
# Variables que el proceso hijo necesita para funcionar en Windows/POSIX (y proxy/certificados si existen).
ENTORNO_PERMITIDO = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP", "TMPDIR",
                     "HOMEDRIVE", "HOMEPATH", "USERPROFILE", "HOME", "LOCALAPPDATA", "APPDATA",
                     "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
                     "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "LANG", "LC_ALL")
LIMITE_TOTAL_S = 900               # tiempo máximo de un proceso hijo (incluye la espera de aprobación)
VARIABLES_API = ("ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID")
MODELO = "claude-sonnet-5-5"


class PermisoInvalido(Exception):
    pass


def estimacion_desde_experimento() -> dict:
    """Estimación de costo a partir de las 144 corridas B del experimento (solo lectura)."""
    costos = []
    for linea in SUPERVISOR.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            r = json.loads(linea)
            if r.get("configuracion") == "B" and isinstance(r.get("costo_estimado_usd"), (int, float)):
                costos.append(r["costo_estimado_usd"])
    if not costos:
        return {"media_usd": None, "max_observado_usd": None, "corridas": 0}
    return {"media_usd": round(sum(costos) / len(costos), 4), "max_observado_usd": round(max(costos), 4),
            "corridas": len(costos),
            "nota": "Estimación desde las corridas B del experimento; no es un tope garantizado. El presupuesto "
                    "de 60 000 tokens detiene el bucle después del paso que lo supera."}


def limites_de_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))["limites"]


def peor_caso_por_ejecucion() -> float | None:
    """Peor caso TEÓRICO estimado de una ejecución: todo el presupuesto de tokens cobrado al precio más alto
    (el de salida). Supone que el presupuesto se respeta (el ejecutor lo comprueba antes de cada solicitud con
    una estimación conservadora); no es la facturación del proveedor."""
    try:
        from puntuar import PRECIOS
    except Exception:
        return None
    precio = PRECIOS.get(MODELO)
    return round(limites_de_config()["presupuesto_tokens"] * max(precio) / 1e6, 4) if precio else None


def costo_estimado(modelo: str, entrada: int, salida: int) -> float | None:
    try:
        from puntuar import PRECIOS
    except Exception:
        return None
    precio = PRECIOS.get(modelo)
    return round((entrada * precio[0] + salida * precio[1]) / 1e6, 6) if precio else None


class VozIA:
    def __init__(self, limpiador, ejecucion: threading.Lock, habilitada: bool = False,
                 entorno_api: dict | None = None, silencioso: bool = False, espera_s: float = 600,
                 modo_prueba=None):
        self.limpiar = limpiador
        self.ejecucion = ejecucion
        self.habilitada = habilitada
        self._entorno_api = dict(entorno_api or {})       # nunca se serializa ni se registra
        self.silencioso = silencioso
        self.espera_s = espera_s
        self.modo_prueba = modo_prueba                     # None | "sin_clave" | ("local", puerto) — solo pruebas
        self.estimacion = estimacion_desde_experimento()
        self.reserva = peor_caso_por_ejecucion()
        self.presupuesto_usd = PRESUPUESTO_SESION_USD
        self.gastos: list[float] = []                       # costo ESTIMADO de cada ejecución terminada
        self.lock = threading.Lock()
        self.usadas = 0
        self.lanzados = 0
        self.permiso = None                                # {"token", "texto", "expira"}
        self.estado = "inactiva"
        self.carpeta: Path | None = None
        self.caso_id = None
        self.texto = None
        self.pendiente = None
        self.resultado = None
        self.error = None
        self.cerrando = False
        self.proceso: subprocess.Popen | None = None
        self.hilo: threading.Thread | None = None
        self._respuesta = threading.Event()
        self._aprobar = None

    # ---------------------------------------------------------------- consentimiento
    def restantes(self) -> int:
        return max(0, MAXIMO_POR_SESION - self.usadas)

    def gastado(self) -> float:
        return round(sum(self.gastos), 6)

    def presupuesto(self) -> dict:
        return {"limite_usd": self.presupuesto_usd, "gastado_estimado_usd": self.gastado(),
                "reserva_por_ejecucion_usd": self.reserva,
                "nota": "Presupuesto ESTIMADO de esta sesión del servidor (se reinicia al reiniciar la demo): bloquea "
                        "nuevas ejecuciones si lo estimado + el peor caso teórico de una ejecución lo superaría. No es "
                        "el gasto facturado: ese solo lo informa el proveedor."}

    def _sin_presupuesto(self) -> str | None:
        if self.reserva is None:
            return "no se pudo calcular el peor caso de costo: no se autorizan ejecuciones"
        if self.gastado() + self.reserva > self.presupuesto_usd + 1e-9:
            return (f"presupuesto estimado de la sesión agotado: gastado ≈US$ {self.gastado():.4f} + peor caso "
                    f"US$ {self.reserva:.2f} superaría US$ {self.presupuesto_usd:.2f}")
        return None

    def preparar(self, texto) -> tuple[int, dict]:
        if not self.habilitada:
            return 403, {"error": "La IA real está deshabilitada. Inicie la demo con --permitir-api (-PermitirApi)."}
        limpio = validar_texto(texto)                      # lanza TextoInvalido
        with self.lock:
            if self.estado in ("en_curso", "esperando_aprobacion"):
                return 409, {"error": "ya hay una ejecución con IA en curso"}
            if self.restantes() == 0:
                return 429, {"error": f"se alcanzó el máximo de {MAXIMO_POR_SESION} ejecuciones reales en esta sesión"}
            if self._sin_presupuesto():
                return 429, {"error": self._sin_presupuesto()}
            ahora = time.monotonic()
            self.permiso = {"token": secrets.token_urlsafe(24), "texto": limpio, "emitido": ahora,
                            "expira": ahora + VIGENCIA_PERMISO_S}
            return 200, {"token": self.permiso["token"], "texto": limpio, "modelo": MODELO,
                         "configuracion": "B (instrucciones genéricas + SKILL.md)",
                         "estimacion": self.estimacion, "restantes": self.restantes(),
                         "maximo": MAXIMO_POR_SESION, "vigencia_s": VIGENCIA_PERMISO_S,
                         "espera_minima_s": ESPERA_MINIMA_S, "presupuesto": self.presupuesto(),
                         "limites": limites_de_config()}

    def cancelar(self) -> None:
        with self.lock:
            self.permiso = None

    def autorizar(self, token) -> tuple[int, dict]:
        if not self.habilitada:
            return 403, {"error": "La IA real está deshabilitada."}
        with self.lock:
            p, self.permiso = self.permiso, None           # un solo uso, también si falla
            if not p or not isinstance(token, str) or not secrets.compare_digest(token, p["token"]):
                return 403, {"error": "permiso inexistente o ya usado: confirme el texto otra vez"}
            ahora = time.monotonic()
            if ahora > p["expira"]:
                return 403, {"error": "el permiso venció: confirme el texto otra vez"}
            if ahora - p["emitido"] < ESPERA_MINIMA_S:
                return 403, {"error": "autorización demasiado rápida tras mostrar el costo: confirme el texto otra vez"}
            if self._sin_presupuesto():
                return 429, {"error": self._sin_presupuesto()}
            if self.restantes() == 0:
                return 429, {"error": f"se alcanzó el máximo de {MAXIMO_POR_SESION} ejecuciones reales en esta sesión"}
            if self.estado in ("en_curso", "esperando_aprobacion"):
                return 409, {"error": "ya hay una ejecución con IA en curso"}
            if not self.ejecucion.acquire(blocking=False):
                return 409, {"error": "ya hay otra ejecución en curso (simulación o voz); espere a que termine"}
            try:
                self._borrar_carpeta()
                self.usadas += 1
                self.caso_id = f"vozia-{self.usadas:03d}"
                self.texto = p["texto"]
                self.carpeta = Path(tempfile.mkdtemp(prefix=PREFIJO_TEMPORAL))
                (self.carpeta / "casos_voz_ia.jsonl").write_text(
                    json.dumps({"caso_id": self.caso_id, "texto": self.texto}, ensure_ascii=False) + "\n", encoding="utf-8")
                (self.carpeta / "origen.json").write_text(json.dumps({
                    "tipo": "ia_real", "es_llm": True, "usa_api": True, "modelo": MODELO, "configuracion": "B",
                    "caso_id": self.caso_id, "autorizada": datetime.now().isoformat(timespec="seconds"),
                    "autorizacion": "botón «Autorizar» de la interfaz local (permiso de un solo uso; no voz)",
                    "ejecucion_de_la_sesion": self.usadas,
                    "maximo_por_sesion": MAXIMO_POR_SESION, "modo_prueba": self._modo_prueba_texto()},
                    ensure_ascii=False, indent=2), encoding="utf-8")
                self.estado, self.pendiente, self.resultado, self.error = "en_curso", None, None, None
                self.cerrando = False
                self._respuesta.clear()
                self.hilo = threading.Thread(target=self._correr, name="voz-ia-lesco", daemon=True)
                self.hilo.start()
            except Exception:
                self.ejecucion.release()
                raise
            return 202, {"iniciada": True, "caso_id": self.caso_id, "restantes": self.restantes()}

    # ---------------------------------------------------------------- proceso hijo
    def _modo_prueba_texto(self):
        if self.modo_prueba is None:
            return None
        return "sin_clave" if self.modo_prueba == "sin_clave" else "api_local"

    def comando(self) -> list[str]:
        c = [sys.executable, str(EJECUTOR), "--caso", self.caso_id,
             "--casos", str(self.carpeta / "casos_voz_ia.jsonl"),
             "--salidas", str(self.carpeta / "salidas"), "--trazas", str(self.carpeta / "trazas")]
        if self.modo_prueba == "sin_clave":
            c.append("--prueba-sin-clave")
        elif isinstance(self.modo_prueba, tuple) and self.modo_prueba[0] == "local":
            c += ["--prueba-api-local", str(int(self.modo_prueba[1]))]
        return c

    def entorno(self) -> dict:
        """Entorno MÍNIMO del proceso hijo: solo las variables de ENTORNO_PERMITIDO (+ las de la API en producción)."""
        env = {k: v for k, v in os.environ.items() if k.upper() in ENTORNO_PERMITIDO}
        if self.modo_prueba is None:
            env.update(self._entorno_api)                  # solo el hijo la recibe; si no hay, el agente usa .env
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _correr(self) -> None:
        stderr_cola = []
        try:
            grupo = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                     else {"start_new_session": True})        # para poder terminar el árbol completo
            self.proceso = subprocess.Popen(self.comando(), cwd=str(RAIZ), env=self.entorno(),
                                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, encoding="utf-8", errors="replace", **grupo)
            self.lanzados += 1
            threading.Thread(target=self._leer_stderr, args=(stderr_cola,), daemon=True).start()
            vigilante = threading.Timer(LIMITE_TOTAL_S, self._matar, args=("se superó el tiempo máximo de la ejecución",))
            vigilante.daemon = True
            vigilante.start()
            final = None
            for linea in self.proceso.stdout:
                try:
                    msg = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                if msg.get("tipo") == "aprobacion":
                    aprobada, razon = self._esperar_aprobacion(msg.get("nombre"), msg.get("argumentos"))
                    self._escribir({"aprobar": aprobada, "razon": razon})
                elif msg.get("tipo") in ("fin", "error"):
                    final = msg
            self.proceso.wait(timeout=30)
            vigilante.cancel()
            self._registrar_gasto()
            with self.lock:
                if final and final["tipo"] == "fin":
                    self.resultado = {"codigo": final.get("codigo"), "motivo": final.get("motivo")}
                    self.estado = "terminada"
                else:
                    detalle = final.get("mensaje") if final else "el proceso terminó sin informar un resultado"
                    self.error = f"{detalle} (código de salida {self.proceso.returncode})"
                    self.estado = "error"
        except Exception as e:
            with self.lock:
                self.error = f"{type(e).__name__}: {e}"
                self.estado = "error"
        finally:
            self._matar(None)
            if len(self.gastos) < self.usadas:             # sin registro (error o corte): se cuenta el peor caso
                with self.lock:
                    self.gastos.append(self.reserva or 0.0)
            if self.proceso is not None:
                try:
                    self.proceso.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
                for canal in (self.proceso.stdin, self.proceso.stdout, self.proceso.stderr):
                    try:
                        canal.close()
                    except Exception:
                        pass
            self.ejecucion.release()

    def _registrar_gasto(self) -> None:
        """Costo estimado desde los tokens de la traza; si no hay evento «fin», el peor caso (conservador)."""
        fin = None
        if self.carpeta is not None:
            trazas = sorted((self.carpeta / "trazas").glob("*.jsonl"))
            if trazas:
                fin = next((e for e in _leer_jsonl(trazas[-1].read_text(encoding="utf-8")) if e.get("tipo") == "fin"), None)
        costo = costo_estimado(MODELO, fin.get("tokens_entrada", 0), fin.get("tokens_salida", 0)) if fin else None
        with self.lock:
            if len(self.gastos) < self.usadas:
                self.gastos.append(costo if costo is not None else (self.reserva or 0.0))

    def _leer_stderr(self, cola: list) -> None:
        for linea in self.proceso.stderr:                  # se descarta: puede llevar rutas locales
            cola.append(linea)
            del cola[:-20]

    def _escribir(self, datos: dict) -> None:
        try:
            self.proceso.stdin.write(json.dumps(datos, ensure_ascii=False) + "\n")
            self.proceso.stdin.flush()
        except (OSError, ValueError):
            pass

    def _matar(self, motivo) -> None:
        """Termina el ÁRBOL de procesos del hijo (ejecutor + servidor MCP que lanzó el agente)."""
        p = self.proceso
        if p is None or p.poll() is not None:
            return
        if motivo:
            with self.lock:
                self.error = motivo
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, timeout=15)
            else:
                import signal
                os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            pass
        if p.poll() is None:
            p.kill()

    def _esperar_aprobacion(self, nombre, argumentos) -> tuple[bool, str]:
        with self.lock:
            if self.cerrando:
                return False, "denegada: la demo se estaba cerrando"
            self.estado = "esperando_aprobacion"
            self.pendiente = {"nombre": nombre, "argumentos": argumentos}
            self._aprobar = None
            self._respuesta.clear()
        respondida = self._respuesta.wait(self.espera_s)
        with self.lock:
            aprobada = bool(respondida and self._aprobar is True)
            self.pendiente, self.estado = None, "en_curso"
        if not respondida:
            return False, "denegada: nadie respondió en la interfaz de la demo dentro del tiempo límite"
        if aprobada:
            return True, ""
        return False, ("denegada: la demo se estaba cerrando" if self.cerrando
                       else "rechazada desde la interfaz web local (botón «Rechazar»)")

    def responder(self, aprobar: bool) -> bool:
        with self.lock:
            if self.estado != "esperando_aprobacion" or self._respuesta.is_set():
                return False
            self._aprobar = aprobar
            self._respuesta.set()
            return True

    # ---------------------------------------------------------------- lectura
    def instantanea(self) -> dict:
        with self.lock:
            carpeta = self.carpeta
            datos = {"origen": "voz_ia", "habilitada": self.habilitada, "estado": self.estado,
                     "caso_id": self.caso_id, "texto_confirmado": self.texto, "pendiente": self.pendiente,
                     "resultado": self.resultado, "error": self.error, "usadas": self.usadas,
                     "maximo": MAXIMO_POR_SESION, "restantes": self.restantes(), "estimacion": self.estimacion,
                     "presupuesto": self.presupuesto(), "limites": limites_de_config(),
                     "modelo": MODELO, "modo_prueba": self._modo_prueba_texto(),
                     "motor": {"tipo": "ia_real", "es_llm": True, "usa_api": True, "modelo": MODELO,
                               "configuracion": "B (instrucciones genéricas + SKILL.md)"}}
        eventos, guardado = [], None
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
        fin = next((e for e in eventos if e.get("tipo") == "fin"), None)
        datos["costo_estimado_usd"] = (costo_estimado(MODELO, fin.get("tokens_entrada", 0), fin.get("tokens_salida", 0))
                                       if fin else None)
        datos.update(eventos=eventos, guardado=guardado,
                     aviso="IA REAL: claude-sonnet-5-5 con la Skill (configuración B), por la API, con costo. "
                           "Ejecutada en un proceso aparte tras «Autorizar» en la interfaz; servidor MCP, política y "
                           "traza reales.")
        limpiar = self.limpiar
        if carpeta is not None:
            limpiar = type(self.limpiar)()
            limpiar.pares = list(self.limpiar.pares)
            limpiar.agregar(carpeta, "<carpeta temporal aislada>")
        return limpiar(datos)

    # ---------------------------------------------------------------- limpieza
    def _borrar_carpeta(self) -> None:
        c = self.carpeta
        if (c is not None and c.name.startswith(PREFIJO_TEMPORAL)
                and c.resolve().parent == Path(tempfile.gettempdir()).resolve()):
            shutil.rmtree(c, ignore_errors=True)
        self.carpeta = None

    def cerrar(self) -> None:
        with self.lock:
            self.cerrando = True
            self.permiso = None
            self._aprobar = False
            self._respuesta.set()
        if self.hilo is not None:
            self.hilo.join(timeout=20)
        self._matar(None)
        with self.lock:
            self._borrar_carpeta()
