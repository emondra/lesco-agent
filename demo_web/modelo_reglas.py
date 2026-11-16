"""
MOTOR LOCAL DE REGLAS — NO ES UN LLM.

Motor determinista para el modo de voz de la demo web. Tiene la misma interfaz que los modelos del
agente (responder(sistema, mensajes, herramientas) -> respuesta con el formato de la API), así que el
host real de agente/agente.py lo ejecuta con su bucle, su política, su aprobación humana y su traza,
contra el servidor MCP real. No lee las instrucciones ni la Skill y no hace inferencia.

Reglas (siempre las mismas, en este orden):
    R1  pedir la transcripción del caso con obtener_transcripcion;
    R2  separar palabras con eval/tokenizar.palabras y quitar las de la lista cerrada OMITIR de la guía
        de anotación (artículos, preposiciones, pronombres…); buscar cada palabra restante TAL CUAL
        con buscar_sena (sin lematizar: «firme» no encuentra FIRMAR);
    R3  aceptar solo coincidencias «exacta». Si hay varias exactas, se toma la de menor número CENAREC
        (orden en que las devuelve el servidor). Si no hay exacta, SIN_COBERTURA:<palabra>.
        Las coincidencias «parcial» nunca se aceptan;
    R4  validar la secuencia con validar_secuencia;
    R5  si es válida, pedir UNA vez guardar_resultado (la política del host decide y pide aprobación);
    R6  terminar con un mensaje construido a partir de las respuestas reales del servidor.

Ante un error de una herramienta o una respuesta inesperada, el motor se detiene y lo informa: no
inventa glosas, IDs ni resultados.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "eval"))
from tokenizar import OMITIR, palabras  # noqa: E402

ETIQUETA = "MOTOR LOCAL DE REGLAS — NO ES UN LLM"
MAX_PALABRAS = 30          # por debajo del tope de 40 búsquedas de la política de la demo
MAX_PALABRA = 40           # longitud máxima del texto tras SIN_COBERTURA: en el servidor


def palabras_de_contenido(texto: str) -> list[str]:
    """Palabras que el motor buscará, en orden y sin repetir (comparación en minúsculas)."""
    vistas, salida = set(), []
    for p in palabras(texto):
        clave = p.lower()
        if clave in OMITIR or clave in vistas:
            continue
        vistas.add(clave)
        salida.append(clave)
    return salida


def _texto_de_resultado(contenido, maximo: int = 300) -> str:
    """Texto real de un tool_result, sin el envoltorio de «dato no confiable» que añade el host."""
    texto = contenido if isinstance(contenido, str) else json.dumps(contenido, ensure_ascii=False)
    separador = "\n\n"
    if texto.startswith("<resultado_de_herramienta>") and separador in texto:
        texto = texto.split(separador, 1)[1].rsplit("</resultado_de_herramienta>", 1)[0]
    return texto.strip()[:maximo]


def _json_de_resultado(contenido) -> dict | None:
    """Extrae el JSON de un tool_result, esté o no envuelto como dato no confiable."""
    texto = contenido if isinstance(contenido, str) else json.dumps(contenido)
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fin <= inicio:
        return None
    try:
        dato = json.loads(texto[inicio:fin + 1])
    except json.JSONDecodeError:
        return None
    return dato if isinstance(dato, dict) else None


class ModeloReglas:
    """Motor determinista. Cada turno se decide solo con las respuestas reales de las herramientas."""

    es_llm = False

    def __init__(self, caso_id: str):
        self.caso_id = caso_id
        self.fase = "transcripcion"
        self.texto = ""
        self.buscadas: list[str] = []
        self.secuencia: list[str] = []

    # ---- formato de respuesta igual al de la API (sin tokens: no hay modelo de lenguaje)
    @staticmethod
    def _respuesta(texto: str, herramientas: list[tuple[str, dict]] | None = None) -> dict:
        contenido = [{"type": "text", "text": texto}]
        for j, (nombre, entrada) in enumerate(herramientas or []):
            contenido.append({"type": "tool_use", "id": f"reglas_{j}_{nombre}", "name": nombre, "input": entrada})
        return {"content": contenido, "stop_reason": "tool_use" if herramientas else "end_turn",
                "usage": {"input_tokens": 0, "output_tokens": 0}}

    def _fin(self, texto: str) -> dict:
        self.fase = "terminado"
        return self._respuesta(texto)

    @staticmethod
    def _resultados(mensajes: list) -> list[dict]:
        """tool_result del último mensaje del host, en orden."""
        if not mensajes or not isinstance(mensajes[-1].get("content"), list):
            return []
        return [b for b in mensajes[-1]["content"] if isinstance(b, dict) and b.get("type") == "tool_result"]

    def responder(self, sistema: str, mensajes: list, herramientas: list) -> dict:
        if self.fase == "transcripcion":
            self.fase = "buscar"
            return self._respuesta("Regla R1: pido la transcripción del caso.",
                                   [("lesco__obtener_transcripcion", {"caso_id": self.caso_id})])

        resultados = self._resultados(mensajes)
        errores = [r for r in resultados if r.get("is_error")]

        if self.fase == "buscar":
            dato = _json_de_resultado(resultados[0]["content"]) if resultados and not errores else None
            if not dato or not isinstance(dato.get("transcripcion"), str):
                return self._fin("Me detengo: no se obtuvo la transcripción. Respuesta del host: "
                                 + (_texto_de_resultado(resultados[0]["content"]) if resultados else "sin respuesta"))
            self.texto = dato["transcripcion"]
            self.buscadas = palabras_de_contenido(self.texto)[:MAX_PALABRAS]
            if not self.buscadas:
                return self._fin("Me detengo: la frase no tiene palabras de contenido para buscar.")
            self.fase = "validar"
            return self._respuesta(
                f"Regla R2: busco {len(self.buscadas)} palabra(s) tal cual, sin lematizar: "
                + ", ".join(self.buscadas) + ".",
                [("lesco__buscar_sena", {"texto": p}) for p in self.buscadas])

        if self.fase == "validar":
            if errores or len(resultados) != len(self.buscadas):
                detalle = _texto_de_resultado(errores[0]["content"]) if errores else "faltan respuestas de búsqueda"
                return self._fin(f"Me detengo: una búsqueda falló ({detalle}). No invento la secuencia.")
            notas = []
            for palabra, r in zip(self.buscadas, resultados):
                dato = _json_de_resultado(r["content"]) or {}
                exactas = [x for x in dato.get("resultados", []) if x.get("coincidencia") == "exacta"]
                if exactas:
                    self.secuencia.append(exactas[0]["id"])
                    notas.append(f"{palabra}→{exactas[0]['glosa']}"
                                 + (f" (de {len(exactas)} exactas, la de menor número)" if len(exactas) > 1 else ""))
                else:
                    self.secuencia.append(f"SIN_COBERTURA:{palabra[:MAX_PALABRA]}")
                    notas.append(f"{palabra}→SIN_COBERTURA")
            self.fase = "guardar"
            return self._respuesta("Regla R3: acepto solo coincidencias exactas. " + "; ".join(notas) + ". "
                                   "Regla R4: valido la secuencia.",
                                   [("lesco__validar_secuencia", {"secuencia": list(self.secuencia)})])

        if self.fase == "guardar":
            dato = _json_de_resultado(resultados[0]["content"]) if resultados and not errores else None
            if not dato or dato.get("valida") is not True:
                detalle = (_texto_de_resultado(resultados[0]["content"]) if resultados else "sin respuesta")
                return self._fin(f"Me detengo: el servidor no validó la secuencia ({detalle}). No se guarda.")
            self.fase = "cerrar"
            return self._respuesta(
                "Regla R5: la secuencia es válida; pido guardarla una sola vez (decide la política del host).",
                [("lesco__guardar_resultado", {
                    "caso_id": self.caso_id, "texto_fuente": self.texto, "secuencia": list(self.secuencia),
                    "notas": "Generado por el motor local de reglas de la demo web (no es un LLM)."})])

        if self.fase == "cerrar":
            dato = _json_de_resultado(resultados[0]["content"]) if resultados and not errores else None
            if dato and dato.get("guardado") is True:
                return self._fin(f"Regla R6: el servidor guardó {dato.get('elementos')} elemento(s) del caso "
                                 f"{dato.get('caso_id')}, {dato.get('sin_cobertura')} sin cobertura.")
            detalle = _texto_de_resultado(resultados[0]["content"]) if resultados else "sin respuesta"
            return self._fin(f"Regla R6: no se guardó nada. Respuesta del host: {detalle}")

        return self._fin("Motor terminado.")
