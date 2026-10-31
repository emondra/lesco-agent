"""
Cliente MCP mínimo por stdio, con la interfaz que usa agente.py del kit de la clase 3:

    cli = ClienteMCP("lesco", ["python", "mcp_server/servidor_lesco.py"], cwd=".")
    info = cli.iniciar()                      # initialize + notifications/initialized
    herramientas = cli.listar_herramientas()  # tools/list
    texto, es_error = cli.llamar("buscar_sena", {"texto": "pagar"})
    cli.cerrar()

El kit original no se recibió completo; este archivo se escribió para el proyecto
(decisión D13). Sin dependencias externas: JSON-RPC 2.0, un mensaje por línea.
"""

import json
import queue
import subprocess
import threading

VERSION_PROTOCOLO = "2025-06-18"
ESPERA_S = 30


class ErrorMCP(Exception):
    pass


class ClienteMCP:
    def __init__(self, nombre: str, comando: list[str], cwd: str | None = None):
        self.nombre = nombre
        self.comando = comando
        self.cwd = cwd
        self.proc: subprocess.Popen | None = None
        self.siguiente_id = 1
        self.respuestas: queue.Queue = queue.Queue()

    # ------------------------------------------------------------------ transporte
    def _leer(self) -> None:
        for linea in self.proc.stdout:
            if linea.strip():
                self.respuestas.put(linea)
        self.respuestas.put(None)   # el servidor cerró stdout

    def _enviar(self, mensaje: dict) -> None:
        if self.proc is None or self.proc.poll() is not None:
            raise ErrorMCP(f"{self.nombre}: el servidor no está en ejecución")
        self.proc.stdin.write(json.dumps(mensaje, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _pedir(self, metodo: str, params: dict | None = None) -> dict:
        id_msg = self.siguiente_id
        self.siguiente_id += 1
        self._enviar({"jsonrpc": "2.0", "id": id_msg, "method": metodo, "params": params or {}})
        while True:
            try:
                linea = self.respuestas.get(timeout=ESPERA_S)
            except queue.Empty:
                raise ErrorMCP(f"{self.nombre}: sin respuesta a {metodo} en {ESPERA_S} s") from None
            if linea is None:
                raise ErrorMCP(f"{self.nombre}: el servidor terminó (código {self.proc.poll()})")
            try:
                msg = json.loads(linea)
            except json.JSONDecodeError:
                raise ErrorMCP(f"{self.nombre}: respuesta que no es JSON: {linea[:200]!r}") from None
            if msg.get("id") != id_msg:
                continue            # notificaciones u otras respuestas: se ignoran
            if "error" in msg:
                e = msg["error"]
                raise ErrorMCP(f"{self.nombre}: {metodo} falló ({e.get('code')}): {e.get('message')}")
            return msg.get("result", {})

    # ------------------------------------------------------------------ API del kit
    def iniciar(self) -> dict:
        try:
            self.proc = subprocess.Popen(self.comando, cwd=self.cwd, stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                         text=True, encoding="utf-8", bufsize=1)
        except OSError as e:
            raise ErrorMCP(f"{self.nombre}: no se pudo iniciar {self.comando}: {e}") from None
        threading.Thread(target=self._leer, daemon=True).start()
        info = self._pedir("initialize", {
            "protocolVersion": VERSION_PROTOCOLO,
            "capabilities": {},
            "clientInfo": {"name": "lesco-agent", "version": "0.1.0"},
        })
        self._enviar({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return info

    def listar_herramientas(self) -> list[dict]:
        return self._pedir("tools/list").get("tools", [])

    def llamar(self, herramienta: str, argumentos: dict) -> tuple[str, bool]:
        try:
            r = self._pedir("tools/call", {"name": herramienta, "arguments": argumentos})
        except ErrorMCP as e:
            return str(e), True
        texto = "\n".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
        return texto, bool(r.get("isError"))

    def cerrar(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
