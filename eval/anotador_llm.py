#!/usr/bin/env python3
"""
Anotador LLM: un modelo etiqueta la plantilla palabra por palabra. Sin opciones, es el anotador 2
(D10): claude-opus-5-5 con eval/prompts/anotador2_v1.md y sus archivos de siempre.

    python eval/anotador_llm.py                    # anotador 2, todos los casos de la plantilla
    python eval/anotador_llm.py --solo c001 c002   # anotador 2, algunos casos
    python eval/anotador_llm.py --prompt <prompt.md> --modelo <modelo> \
        --registro <respuestas.jsonl> --salida <anotacion.tsv>   # otro anotador LLM

Aislamiento: --registro y --salida nunca pueden ser anotador1.tsv ni plantilla.tsv, ni el mismo
archivo; y un prompt distinto del oficial del anotador 2 no puede escribir en sus archivos. Se
comprueba con rutas resueltas, antes de leer la clave o llamar a la API.

Independencia: el prompt contiene solo la guía, el índice y la plantilla del caso. Nunca ve las
etiquetas de otro anotador ni salidas del agente.

Reproducibilidad: cada respuesta cruda se agrega a eval/anotaciones/anotador2_respuestas.jsonl
con el modelo, el SHA-256 del prompt de sistema, el uso de tokens y la fecha. Es reanudable: los
casos con una respuesta válida ya registrada con el MISMO prompt y el MISMO modelo (comparación
exacta) no se vuelven a pedir. Un registro con respuestas válidas de otro prompt u otro modelo se
rechaza antes de llamar a la API; si la API declara un modelo distinto del pedido, se detiene sin más
solicitudes. El TSV final se reconstruye siempre desde ese registro, solo con ese prompt y ese modelo.

La clave se lee como en el agente (ANTHROPIC_API_KEY o .env); nunca se escribe en disco.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "agente"))
sys.path.insert(0, str(RAIZ / "eval"))

from agente import cabeceras_api, cargar_clave  # noqa: E402
from tokenizar import ETIQUETAS_VALIDAS, escribir_tsv, leer_tsv  # noqa: E402

URL = "https://api.anthropic.com/v1/messages"
MODELO = "claude-opus-5-5"
RUTA_PROMPT = RAIZ / "eval" / "prompts" / "anotador2_v1.md"
RUTA_GUIA = RAIZ / "eval" / "guia_anotacion.md"
RUTA_INDICE = RAIZ / "data" / "lexicon" / "cenarec_indice.tsv"
DIR_ANOT = RAIZ / "eval" / "anotaciones"

ESQUEMA = {
    "type": "object",
    "properties": {
        "etiquetas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pos": {"type": "integer"},
                    "etiqueta": {"type": "string"},
                    "motivo": {"type": "string"},
                },
                "required": ["pos", "etiqueta", "motivo"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["etiquetas"],
    "additionalProperties": False,
}


def prompt_sistema(ruta: Path = RUTA_PROMPT) -> str:
    plantilla = ruta.read_text(encoding="utf-8")
    return plantilla.replace("{guia}", RUTA_GUIA.read_text(encoding="utf-8").strip()) \
                    .replace("{indice}", RUTA_INDICE.read_text(encoding="utf-8").strip())


def mensaje_caso(caso_id: str, filas: list[dict]) -> str:
    tabla = "\n".join(f"{f['pos']}\t{f['palabra']}\t{f['sugerencia']}" for f in filas)
    return (f"Caso {caso_id}. Frase: «{' '.join(f['palabra'] for f in filas)}»\n\n"
            f"Etiqueta cada palabra (pos<TAB>palabra<TAB>sugerencia):\n{tabla}")


def validar(etiquetas: list[dict], filas: list[dict], idws: set[int]) -> list[str]:
    """Devuelve la lista de problemas; vacía si la anotación es utilizable."""
    problemas = []
    if [e.get("pos") for e in etiquetas] != [f["pos"] for f in filas]:
        return [f"posiciones {[e.get('pos') for e in etiquetas]} != {[f['pos'] for f in filas]}"]
    anterior = None
    for e in etiquetas:
        et = e["etiqueta"].strip()
        if not ETIQUETAS_VALIDAS.match(et):
            problemas.append(f"pos {e['pos']}: etiqueta inválida {et!r}")
        elif et.startswith("CENAREC-") and int(et.split("-")[1]) not in idws:
            problemas.append(f"pos {e['pos']}: {et} no existe en el índice")
        elif et == "+" and not (anterior or "").startswith(("CENAREC-", "+")):
            problemas.append(f"pos {e['pos']}: '+' sin una entrada anterior")
        anterior = et
    return problemas


def pedir(clave: str, sistema: str, mensaje: str, modelo: str) -> dict:
    cuerpo = json.dumps({
        "model": modelo,
        "max_tokens": 16000,
        "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": mensaje}],
        "output_config": {"effort": "high", "format": {"type": "json_schema", "schema": ESQUEMA}},
    }).encode("utf-8")
    for intento in range(5):
        req = urllib.request.Request(URL, data=cuerpo, method="POST", headers=cabeceras_api(clave))
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")
            if (e.code in (429, 529) or e.code >= 500) and intento < 4:
                time.sleep(int(e.headers.get("retry-after") or 0) or 5 * 2 ** intento)
                continue
            raise SystemExit(f"Error de la API ({e.code}): {detalle[:500]}") from None
    raise SystemExit("reintentos agotados")


def registro_valido(ruta: Path, sha: str | None = None, modelo: str | None = None) -> dict[str, dict]:
    """Última respuesta válida (sin problemas) de cada caso. Sin sha ni modelo, como siempre. Con ellos,
    solo las de ese SHA-256 de prompt compuesto y ese modelo, con comparación EXACTA del campo 'modelo'
    (el que declaró la API); nunca por prefijo ni por alias."""
    validos = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            r = json.loads(linea)
            if r["problemas"]:
                continue
            if sha is not None and r.get("sha256_prompt") != sha:
                continue
            if modelo is not None and r.get("modelo") != modelo:
                continue
            validos[r["caso_id"]] = r
    return validos


def identidades_ajenas(ruta: Path, sha: str, modelo: str) -> list[str]:
    """Problemas si el registro contiene respuestas VÁLIDAS de otro prompt u otro modelo (comparación
    exacta). Un registro pertenece a un solo anotador. Solo informa recuentos, nunca etiquetas."""
    otros_sha = otros_modelo = 0
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            r = json.loads(linea)
            if r["problemas"]:
                continue
            otros_sha += r.get("sha256_prompt") != sha
            otros_modelo += r.get("modelo") != modelo
    problemas = []
    if otros_sha:
        problemas.append(f"el registro tiene {otros_sha} respuestas válidas de otro prompt (SHA-256 distinto)")
    if otros_modelo:
        problemas.append(f"el registro tiene {otros_modelo} respuestas válidas de otro modelo distinto de {modelo}")
    return problemas


def _clave_ruta(ruta: Path) -> str:
    """Ruta comparable: resuelta y con os.path.normcase (en Windows, sin distinción de mayúsculas y con la
    misma barra), también si el archivo todavía no existe."""
    return os.path.normcase(str(ruta.resolve()))


def problemas_de_aislamiento(prompt: Path, registro: Path, salida: Path) -> list[str]:
    """Destinos prohibidos, con rutas resueltas (una variante relativa no elude la comprobación).
    Lista vacía = se puede continuar. Se llama antes de leer la clave o de escribir nada."""
    p, r, s = _clave_ruta(prompt), _clave_ruta(registro), _clave_ruta(salida)
    problemas = []
    if r == s:
        problemas.append("--registro y --salida no pueden ser el mismo archivo")
    for protegido in (DIR_ANOT / "anotador1.tsv", DIR_ANOT / "plantilla.tsv"):
        if _clave_ruta(protegido) in (r, s):
            problemas.append(f"no se puede escribir en {protegido.name}")
    if p != _clave_ruta(RUTA_PROMPT):
        for del_a2 in (DIR_ANOT / "anotador2.tsv", DIR_ANOT / "anotador2_respuestas.jsonl"):
            if _clave_ruta(del_a2) in (r, s):
                problemas.append(f"un prompt distinto de {RUTA_PROMPT.name} no puede escribir en {del_a2.name}")
    return problemas


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Anotador LLM (por defecto, el anotador 2 con claude-opus-5-5)")
    ap.add_argument("--plantilla", type=Path, default=DIR_ANOT / "plantilla.tsv")
    ap.add_argument("--registro", type=Path, default=DIR_ANOT / "anotador2_respuestas.jsonl")
    ap.add_argument("--salida", type=Path, default=DIR_ANOT / "anotador2.tsv")
    ap.add_argument("--prompt", type=Path, default=RUTA_PROMPT)
    ap.add_argument("--modelo", default=MODELO)
    ap.add_argument("--solo", nargs="*", default=None)
    a = ap.parse_args()

    aislamiento = problemas_de_aislamiento(a.prompt, a.registro, a.salida)
    if aislamiento:
        print("Configuración rechazada (no se llamó a la API ni se escribió nada):")
        for problema in aislamiento:
            print(f"  - {problema}")
        return 3

    filas = leer_tsv(a.plantilla)
    por_caso: dict[str, list[dict]] = {}
    for f in filas:
        por_caso.setdefault(f["caso_id"], []).append(f)
    casos = [c for c in por_caso if not a.solo or c in a.solo]

    sistema = prompt_sistema(a.prompt)
    sha = hashlib.sha256(sistema.encode("utf-8")).hexdigest()
    idws = {int(l.split("\t")[0]) for l in RUTA_INDICE.read_text(encoding="utf-8").splitlines()[1:] if l}
    ajenas = identidades_ajenas(a.registro, sha, a.modelo)
    if ajenas:
        print("Registro rechazado: un registro pertenece a un solo anotador (prompt + modelo). "
              "No se llamó a la API ni se escribió nada:")
        for problema in ajenas:
            print(f"  - {problema}")
        return 3
    hechos = registro_valido(a.registro, sha, a.modelo)
    pendientes = [c for c in casos if c not in hechos]
    print(f"{len(casos)} casos; {len(casos) - len(pendientes)} ya anotados con este prompt y modelo; "
          f"{len(pendientes)} por pedir (prompt {sha[:12]}, modelo {a.modelo})")

    if pendientes:
        clave = cargar_clave()
        if not clave:
            print("Falta ANTHROPIC_API_KEY (variable de entorno o .env).")
            return 2
    for caso in pendientes:
        for intento in range(1, 3):
            r = pedir(clave, sistema, mensaje_caso(caso, por_caso[caso]), a.modelo)
            declarado = r.get("model")          # sin valor por defecto: no se presume el modelo
            texto = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
            try:
                etiquetas = json.loads(texto)["etiquetas"]
                problemas = validar(etiquetas, por_caso[caso], idws)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                etiquetas, problemas = [], [f"respuesta no utilizable: {e}"]
            distinto = declarado != a.modelo    # comparación exacta, sin alias
            if distinto:
                problemas = [f"modelo declarado por la API {declarado!r} distinto del solicitado {a.modelo!r}"] + problemas
            with a.registro.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "caso_id": caso, "intento": intento, "modelo": declarado,
                    "sha256_prompt": sha, "fecha": datetime.now().isoformat(timespec="seconds"),
                    "stop_reason": r.get("stop_reason"), "uso": r.get("usage", {}),
                    "etiquetas": etiquetas, "problemas": problemas,
                }, ensure_ascii=False) + "\n")
            print(f"  {caso} intento {intento}: {'ok' if not problemas else '; '.join(problemas)}")
            if distinto:
                print("Detenido: la API declaró otro modelo. No se hacen más solicitudes ni se escribe el TSV.")
                return 4
            if not problemas:
                break

    hechos = registro_valido(a.registro, sha, a.modelo)   # el TSV nunca mezcla prompts ni modelos
    faltan = [c for c in por_caso if c not in hechos]
    salida = []
    for caso, fs in por_caso.items():
        etiquetas = {e["pos"]: e["etiqueta"].strip() for e in hechos[caso]["etiquetas"]} if caso in hechos else {}
        salida += [{**f, "etiqueta": etiquetas.get(f["pos"], "")} for f in fs]
    escribir_tsv(salida, a.salida)
    print(f"\n{a.salida}: {len(por_caso) - len(faltan)} de {len(por_caso)} casos anotados"
          + (f"; faltan {', '.join(faltan)}" if faltan else ""))
    return 0 if not faltan else 1


if __name__ == "__main__":
    sys.exit(main())
