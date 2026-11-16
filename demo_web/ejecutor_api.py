#!/usr/bin/env python3
"""
Ejecutor AISLADO del modo «Voz con IA real» (fase 2).

Lo lanza demo_web/voz_ia.py como proceso hijo, UNA vez por ejecución autorizada desde la interfaz. Es el único
proceso de la demo que puede llamar a la API: el servidor web sigue bloqueado (servidor_demo.blindar_sin_api).

    - Ejecuta el host real de agente/agente.py (sin modificarlo) con demo_web/configs/voz_api.json:
      claude-sonnet-5-5, instrucciones genéricas + SKILL.md (configuración B), politica_demo.json y el
      servidor MCP real vinculado al caso temporal.
    - Sin reintentos automáticos: usa ejecutar_supervisado.sin_reintentos (REINTENTOS=0, tiempo máximo por
      solicitud y comprobación de la identidad del modelo).
    - Credenciales: si llegan por el entorno, se RETIRAN de os.environ al empezar (así el servidor MCP que
      lanza el agente no las hereda) y se entregan al agente solo en memoria. Si no llegan, el agente las
      busca en .env como siempre (única lectura de .env de la demo, y solo en este proceso). Nunca se imprimen
      ni se envían al servidor web.
    - Presupuesto de tokens comprobado ANTES de cada solicitud (estimación conservadora de la entrada + el
      máximo de salida): el host del agente solo lo comprueba después de cada paso.
    - La aprobación de guardar se pide al proceso padre por el canal de protocolo; el padre solo la concede
      cuando la interfaz envía «Aprobar guardado» (el servidor no puede verificar un clic físico).

Protocolo: una línea JSON por mensaje.
    hijo → padre (stdout):  {"tipo": "aprobacion", "nombre", "argumentos"} | {"tipo": "fin", "codigo", "motivo"}
                            | {"tipo": "error", "mensaje"}
    padre → hijo (stdin):   {"aprobar": true|false}
La salida de consola del agente se desvía a stderr para que no se mezcle con el protocolo.

Modos de PRUEBA (solo los usa el conjunto de pruebas; el servidor web nunca los ofrece al navegador):
    --prueba-sin-clave        el agente no encuentra clave; ninguna conexión de red es posible.
    --prueba-api-local PUERTO  las solicitudes van a http://127.0.0.1:PUERTO/v1/messages con una clave
                              ficticia; cualquier otra dirección se bloquea y .env no se lee.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ / "agente"))
sys.path.insert(0, str(RAIZ / "eval"))
import agente  # noqa: E402
import ejecutar_supervisado  # noqa: E402

CONFIG = AQUI / "configs" / "voz_api.json"
T_HTTP = 120                                   # segundos por solicitud HTTP
VARIABLES_API = ("ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID")
CARACTERES_POR_TOKEN = 3                       # estimación CONSERVADORA (sobreestima los tokens de entrada)
PATRON_CLAVE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{4,}")
CLAVE_FICTICIA = "clave-de-prueba-local"


def _sin_red(*a, **k):
    raise OSError("red bloqueada en el modo de prueba del ejecutor")


def retirar_credenciales() -> dict:
    """Quita las variables de la API del entorno de este proceso (y de sus descendientes) y las devuelve."""
    return {k: os.environ.pop(k) for k in VARIABLES_API if k in os.environ}


def entregar_credenciales(credenciales: dict) -> None:
    """Entrega al agente, en memoria, las credenciales retiradas del entorno."""
    if credenciales.get("ANTHROPIC_API_KEY"):
        clave = credenciales["ANTHROPIC_API_KEY"]
        agente.cargar_clave = lambda: clave
    if credenciales.get("ANTHROPIC_WORKSPACE_ID"):
        workspace, original = credenciales["ANTHROPIC_WORKSPACE_ID"], agente.cabeceras_api
        agente.cabeceras_api = lambda c: {**original(c), "anthropic-workspace-id": workspace}


def vigilar_presupuesto(presupuesto_tokens: int) -> dict:
    """Antes de cada solicitud: si lo acumulado + la entrada estimada + el máximo de salida puede superar el
    presupuesto, la solicitud NO se envía. Devuelve el contador (para pruebas)."""
    cuenta = {"acumulado": 0, "solicitudes": 0}
    original = agente.ModeloClaude.responder

    def responder_vigilado(self, sistema, mensajes, herramientas):
        entrada = len(json.dumps({"system": sistema, "messages": mensajes, "tools": herramientas},
                                 ensure_ascii=False)) // CARACTERES_POR_TOKEN + 1
        if cuenta["acumulado"] + entrada + self.max_tokens > presupuesto_tokens:
            raise agente.ErrorModelo(
                f"presupuesto de {presupuesto_tokens} tokens: la siguiente solicitud podría superarlo "
                f"(acumulado {cuenta['acumulado']} + entrada estimada {entrada} + salida máxima {self.max_tokens}); no se envió")
        r = original(self, sistema, mensajes, herramientas)
        uso = r.get("usage", {})
        cuenta["acumulado"] += int(uso.get("input_tokens", 0)) + int(uso.get("output_tokens", 0))
        cuenta["solicitudes"] += 1
        return r
    agente.ModeloClaude.responder = responder_vigilado
    return cuenta


def preparar_modo_prueba(a) -> None:
    """Modos de prueba: nunca leen .env, nunca usan una clave real y nunca salen de 127.0.0.1."""
    cabeceras = lambda clave: {"x-api-key": clave, "anthropic-version": "2023-06-01",  # noqa: E731
                               "content-type": "application/json"}
    agente.cabeceras_api = cabeceras
    if a.prueba_sin_clave:
        agente.cargar_clave = lambda: None
        urllib.request.urlopen = _sin_red
    elif a.prueba_api_local:
        url = f"http://127.0.0.1:{a.prueba_api_local}/v1/messages"
        agente.ModeloClaude.URL = url
        agente.cargar_clave = lambda: CLAVE_FICTICIA
        original = urllib.request.urlopen

        def solo_local(req, *ar, **kw):
            destino = req.full_url if hasattr(req, "full_url") else str(req)
            if destino != url:
                raise OSError("el modo de prueba solo admite la API local")
            return original(req, *ar, **kw)
        urllib.request.urlopen = solo_local


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ejecutor aislado del modo «Voz con IA real» (demo web).")
    ap.add_argument("--caso", required=True, type=agente.caso_valido)
    ap.add_argument("--casos", required=True)
    ap.add_argument("--salidas", required=True)
    ap.add_argument("--trazas", required=True)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--prueba-sin-clave", action="store_true")
    g.add_argument("--prueba-api-local", type=int, default=None)
    a = ap.parse_args(argv)

    protocolo = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr                      # la consola del agente no entra en el canal de protocolo
    entrada = sys.stdin

    def enviar(datos: dict) -> None:
        protocolo.write(json.dumps(datos, ensure_ascii=False) + "\n")
        protocolo.flush()

    def pedir_aprobacion(nombre: str, argumentos: dict, auto: bool) -> tuple[bool, str]:
        enviar({"tipo": "aprobacion", "nombre": nombre, "argumentos": argumentos})
        linea = entrada.readline()
        try:
            respuesta = json.loads(linea) if linea.strip() else {}
        except json.JSONDecodeError:
            respuesta = {}
        if respuesta.get("aprobar") is True:
            return True, "aprobada desde la interfaz web local (botón «Aprobar guardado»; no por voz)"
        if respuesta.get("aprobar") is False:
            return False, respuesta.get("razon") or "rechazada desde la interfaz web local (botón «Rechazar»)"
        return False, "denegada: no llegó una respuesta válida de la interfaz"

    try:
        credenciales = retirar_credenciales()          # antes de que el agente lance el servidor MCP
        if a.prueba_sin_clave or a.prueba_api_local:
            credenciales = {}                         # los modos de prueba nunca usan una clave del entorno
            preparar_modo_prueba(a)
        else:
            entregar_credenciales(credenciales)
        ejecutar_supervisado.sin_reintentos(T_HTTP)   # después del modo de prueba: lo envuelve, no lo sustituye
        limites = json.loads(CONFIG.read_text(encoding="utf-8"))["limites"]
        vigilar_presupuesto(int(limites["presupuesto_tokens"]))
        agente.pedir_aprobacion = pedir_aprobacion
        args = agente.argumentos(["--config", str(CONFIG), "--caso", a.caso, "--casos", a.casos,
                                  "--salidas", a.salidas, "--trazas", a.trazas])
        if args.simulado or args.auto_aprobar:
            raise RuntimeError("el ejecutor de IA real no admite --simulado ni --auto-aprobar")
        r = agente.ejecutar(args)
        enviar({"tipo": "fin", "codigo": r["codigo"], "motivo": PATRON_CLAVE.sub("<clave oculta>", str(r["motivo"]))})
        return 0
    except Exception as e:  # se informa sin detalles sensibles; el padre lo muestra y se detiene
        enviar({"tipo": "error", "mensaje": PATRON_CLAVE.sub("<clave oculta>", f"{type(e).__name__}: {e}")[:600]})
        return 1


if __name__ == "__main__":
    sys.exit(main())
