#!/usr/bin/env python3
"""
Construye la referencia a partir de las dos anotaciones y la adjudicación (guía v1, §10).

    python eval/construir_referencia.py

Entradas:
    eval/anotaciones/anotador1.tsv, eval/anotaciones/anotador2.tsv
    eval/desacuerdos.tsv  (de eval/kappa.py, con la columna `decision` llena en cada fila)
Salidas:
    eval/anotaciones/adjudicada.tsv   etiqueta final por palabra
    eval/referencia.jsonl             secuencia de referencia, dificultad y motivos por caso

Donde los anotadores coinciden, esa es la etiqueta final; donde no, la `decision` registrada.
"""

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "eval"))
from tokenizar import ETIQUETAS_VALIDAS, escribir_tsv, leer_tsv  # noqa: E402

LARGO_MINIMO = 12   # guía §9.5


def secuencia(filas: list[dict]) -> list[str]:
    salida = []
    for f in filas:
        if f["etiqueta"] in ("OMITIR", "+"):
            continue
        salida.append(f"SIN_COBERTURA:{f['palabra']}" if f["etiqueta"] == "SIN_COBERTURA" else f["etiqueta"])
    return salida


def motivos_de(filas: list[dict], motivos_meta: list[str]) -> list[str]:
    motivos = set()
    if any(f["etiqueta"] == "SIN_COBERTURA" for f in filas):
        motivos.add("sin_cobertura")
    if any(f["etiqueta"] == "+" for f in filas):
        motivos.add("multipalabra")
    if len(filas) >= LARGO_MINIMO:
        motivos.add("largo")
    motivos |= {m for m in motivos_meta if m in ("variante_sentido", "sinonimo")}
    return sorted(motivos)


def adjudicar(a1: list[dict], a2: list[dict], desacuerdos: list[dict]) -> list[dict]:
    if [(f["caso_id"], f["pos"]) for f in a1] != [(f["caso_id"], f["pos"]) for f in a2]:
        raise SystemExit("Las anotaciones no tienen las mismas palabras.")
    decisiones = {(d["caso_id"], int(d["pos"])): d.get("decision", "").strip() for d in desacuerdos}
    final, faltan = [], []
    for x, y in zip(a1, a2):
        clave = (x["caso_id"], x["pos"])
        if x["etiqueta"] == y["etiqueta"]:
            etiqueta = x["etiqueta"]
        else:
            etiqueta = decisiones.get(clave, "")
            if not ETIQUETAS_VALIDAS.match(etiqueta):
                faltan.append(clave)
        final.append({**x, "etiqueta": etiqueta})
    if faltan:
        raise SystemExit(f"Faltan {len(faltan)} decisiones válidas en desacuerdos.tsv, p. ej. {faltan[:5]}")
    return final


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = RAIZ / "eval"
    ap = argparse.ArgumentParser(description="Construye eval/referencia.jsonl")
    ap.add_argument("--anotador1", type=Path, default=d / "anotaciones" / "anotador1.tsv")
    ap.add_argument("--anotador2", type=Path, default=d / "anotaciones" / "anotador2.tsv")
    ap.add_argument("--desacuerdos", type=Path, default=d / "desacuerdos.tsv")
    ap.add_argument("--meta", type=Path, default=d / "casos_meta.jsonl")
    ap.add_argument("--adjudicada", type=Path, default=d / "anotaciones" / "adjudicada.tsv")
    ap.add_argument("--salida", type=Path, default=d / "referencia.jsonl")
    a = ap.parse_args()

    filas_des = []
    if a.desacuerdos.exists():
        lineas = a.desacuerdos.read_text(encoding="utf-8").splitlines()
        cols = lineas[0].split("\t")
        filas_des = [dict(zip(cols, l.split("\t") + [""] * len(cols))) for l in lineas[1:] if l.strip()]
    final = adjudicar(leer_tsv(a.anotador1), leer_tsv(a.anotador2), filas_des)
    escribir_tsv(final, a.adjudicada)

    meta = {m["caso_id"]: m for m in map(json.loads, a.meta.read_text(encoding="utf-8").splitlines()) if m}
    por_caso: dict[str, list[dict]] = {}
    for f in final:
        por_caso.setdefault(f["caso_id"], []).append(f)
    registros = []
    for caso, filas in por_caso.items():
        motivos = motivos_de(filas, meta.get(caso, {}).get("motivos", []))
        registros.append({"caso_id": caso, "secuencia": secuencia(filas),
                          "dificultad": "dificil" if motivos else "normal", "motivos": motivos})
    a.salida.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros), encoding="utf-8")
    dificiles = sum(r["dificultad"] == "dificil" for r in registros)
    print(f"{a.salida}: {len(registros)} casos, {dificiles} difíciles ({dificiles / len(registros):.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
