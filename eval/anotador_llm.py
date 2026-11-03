#!/usr/bin/env python3
"""
Anotador 2 (D10): claude-opus-5-5 etiqueta la plantilla palabra por palabra.

    python eval/anotador_llm.py                    # todos los casos de la plantilla
    python eval/anotador_llm.py --solo c001 c002   # algunos casos

Independencia: el prompt (eval/prompts/anotador2_v1.md) contiene solo la guía, el índice y la
plantilla del caso. Nunca ve las etiquetas del anotador 1 ni salidas del agente.

Reproducibilidad: cada respuesta cruda se agrega a eval/anotaciones/anotador2_respuestas.jsonl
con el modelo, el SHA-256 del prompt de sistema, el uso de tokens y la fecha. Es reanudable: los
casos con una respuesta válida ya registrada no se vuelven a pedir. El TSV final se reconstruye
siempre desde ese registro.

La clave se lee como en el agente (ANTHROPIC_API_KEY o .env); nunca se escribe en disco.
"""

import argparse
import hashlib
import json
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


def prompt_sistema() -> str:
    plantilla = RUTA_PROMPT.read_text(encoding="utf-8")
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


def registro_valido(ruta: Path) -> dict[str, dict]:
    validos = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            r = json.loads(linea)
            if not r["problemas"]:
                validos[r["caso_id"]] = r
    return validos


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Anotador 2 con claude-opus-5-5")
    ap.add_argument("--plantilla", type=Path, default=DIR_ANOT / "plantilla.tsv")
    ap.add_argument("--registro", type=Path, default=DIR_ANOT / "anotador2_respuestas.jsonl")
    ap.add_argument("--salida", type=Path, default=DIR_ANOT / "anotador2.tsv")
    ap.add_argument("--modelo", default=MODELO)
    ap.add_argument("--solo", nargs="*", default=None)
    a = ap.parse_args()

    filas = leer_tsv(a.plantilla)
    por_caso: dict[str, list[dict]] = {}
    for f in filas:
        por_caso.setdefault(f["caso_id"], []).append(f)
    casos = [c for c in por_caso if not a.solo or c in a.solo]

    sistema = prompt_sistema()
    sha = hashlib.sha256(sistema.encode("utf-8")).hexdigest()
    idws = {int(l.split("\t")[0]) for l in RUTA_INDICE.read_text(encoding="utf-8").splitlines()[1:] if l}
    hechos = registro_valido(a.registro)
    pendientes = [c for c in casos if c not in hechos or hechos[c]["sha256_prompt"] != sha]
    print(f"{len(casos)} casos; {len(casos) - len(pendientes)} ya anotados con este prompt; "
          f"{len(pendientes)} por pedir (prompt {sha[:12]})")

    if pendientes:
        clave = cargar_clave()
        if not clave:
            print("Falta ANTHROPIC_API_KEY (variable de entorno o .env).")
            return 2
    for caso in pendientes:
        for intento in range(1, 3):
            r = pedir(clave, sistema, mensaje_caso(caso, por_caso[caso]), a.modelo)
            texto = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
            try:
                etiquetas = json.loads(texto)["etiquetas"]
                problemas = validar(etiquetas, por_caso[caso], idws)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                etiquetas, problemas = [], [f"respuesta no utilizable: {e}"]
            with a.registro.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "caso_id": caso, "intento": intento, "modelo": r.get("model", a.modelo),
                    "sha256_prompt": sha, "fecha": datetime.now().isoformat(timespec="seconds"),
                    "stop_reason": r.get("stop_reason"), "uso": r.get("usage", {}),
                    "etiquetas": etiquetas, "problemas": problemas,
                }, ensure_ascii=False) + "\n")
            print(f"  {caso} intento {intento}: {'ok' if not problemas else '; '.join(problemas)}")
            if not problemas:
                break

    hechos = registro_valido(a.registro)
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
