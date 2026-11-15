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

Modos añadidos por D20 (2026-11-14; docs/metricas.md, registro de cambios), sin adjudicación:

    python eval/construir_referencia.py --modo unico --anotacion <anotacion.tsv> --salida <r.jsonl>
    python eval/construir_referencia.py --modo consenso --anotador1 <a.tsv> --anotador2 <b.tsv> --salida <rc.jsonl>

  unico     la referencia es una sola anotación completa (R1 = anotador 2; R2 = anotador LLM A).
  consenso  solo los casos con todas sus etiquetas iguales en las dos anotaciones (Rc); informa cuántos
            casos y cuáles se excluyen. En estos modos no se escribe ningún TSV adjudicado.
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


def referencia_unica(filas: list[dict]) -> list[dict]:
    """D20: una sola anotación como referencia (R1 o R2). Exige una etiqueta válida en cada palabra."""
    invalidas = [(f["caso_id"], f["pos"]) for f in filas if not ETIQUETAS_VALIDAS.match(f["etiqueta"])]
    if invalidas:
        raise SystemExit(f"La anotación tiene {len(invalidas)} etiquetas vacías o inválidas, p. ej. {invalidas[:5]}")
    return list(filas)


def consenso(a1: list[dict], a2: list[dict]) -> tuple[list[dict], list[str]]:
    """D20 (Rc): solo los casos cuyas etiquetas coinciden en TODAS sus palabras. Devuelve las filas de esos
    casos y la lista de caso_id excluidos, en el orden de la plantilla."""
    if [(f["caso_id"], f["pos"]) for f in a1] != [(f["caso_id"], f["pos"]) for f in a2]:
        raise SystemExit("Las anotaciones no tienen las mismas palabras.")
    referencia_unica(a1), referencia_unica(a2)
    por_caso: dict[str, list[tuple[dict, dict]]] = {}
    for x, y in zip(a1, a2):
        por_caso.setdefault(x["caso_id"], []).append((x, y))
    final, excluidos = [], []
    for caso, pares in por_caso.items():
        if all(x["etiqueta"] == y["etiqueta"] for x, y in pares):
            final += [x for x, _ in pares]
        else:
            excluidos.append(caso)
    return final, excluidos


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
    ap.add_argument("--modo", choices=("adjudicada", "unico", "consenso"), default="adjudicada")
    ap.add_argument("--anotacion", type=Path, default=None, help="modo unico: la anotación de referencia")
    a = ap.parse_args()

    if a.modo == "unico":
        if a.anotacion is None:
            ap.error("--modo unico exige --anotacion")
        final = referencia_unica(leer_tsv(a.anotacion))
    elif a.modo == "consenso":
        final, excluidos = consenso(leer_tsv(a.anotador1), leer_tsv(a.anotador2))
        print(f"consenso: {len(excluidos)} casos excluidos por desacuerdo: {', '.join(excluidos) or 'ninguno'}")
        if not final:
            raise SystemExit("Ningún caso con acuerdo total: no hay referencia de consenso.")
    else:
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
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros), encoding="utf-8")
    dificiles = sum(r["dificultad"] == "dificil" for r in registros)
    print(f"{a.salida}: {len(registros)} casos, {dificiles} difíciles ({dificiles / len(registros):.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
