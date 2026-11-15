#!/usr/bin/env python3
"""
Acuerdo entre anotadores (guía v1, §10): kappa de Cohen sobre las etiquetas por palabra.

    python eval/kappa.py eval/anotaciones/anotador1.tsv eval/anotaciones/anotador2.tsv

Se reporta sobre dos conjuntos de palabras:
  - todas: incluye las sugeridas como OMITIR en la plantilla (inflan el acuerdo);
  - contenido: solo las palabras SIN sugerencia en la plantilla (cifra principal).
Además: acuerdo exacto por caso (todas sus etiquetas iguales). Escribe eval/acuerdo.md y la
lista de desacuerdos en eval/desacuerdos.tsv para la adjudicación.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "eval"))
from tokenizar import leer_tsv  # noqa: E402


def kappa_cohen(a: list[str], b: list[str]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("listas vacías o de distinto largo")
    n = len(a)
    observado = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    esperado = sum(ca[k] * cb[k] for k in ca) / (n * n)
    if esperado == 1:
        return 1.0
    return (observado - esperado) / (1 - esperado)


def emparejar(f1: list[dict], f2: list[dict]) -> list[tuple[dict, dict]]:
    claves1 = [(f["caso_id"], f["pos"], f["palabra"]) for f in f1]
    claves2 = [(f["caso_id"], f["pos"], f["palabra"]) for f in f2]
    if claves1 != claves2:
        raise SystemExit("Las dos anotaciones no tienen las mismas palabras en el mismo orden.")
    vacias = [k for k, f, g in zip(claves1, f1, f2) if not f["etiqueta"] or not g["etiqueta"]]
    if vacias:
        raise SystemExit(f"Hay {len(vacias)} palabras sin etiqueta, p. ej. {vacias[:3]}")
    return list(zip(f1, f2))


def informe(pares: list[tuple[dict, dict]]) -> tuple[dict, list[tuple[dict, dict]]]:
    contenido = [(x, y) for x, y in pares if not x["sugerencia"]]
    casos: dict[str, bool] = {}
    for x, y in pares:
        casos[x["caso_id"]] = casos.get(x["caso_id"], True) and x["etiqueta"] == y["etiqueta"]
    res = {}
    for nombre, grupo in (("todas", pares), ("contenido", contenido)):
        a = [x["etiqueta"] for x, _ in grupo]
        b = [y["etiqueta"] for _, y in grupo]
        res[nombre] = {"n": len(grupo), "acuerdo": sum(p == q for p, q in zip(a, b)) / len(grupo),
                       "kappa": kappa_cohen(a, b)}
    res["casos"] = {"n": len(casos), "identicos": sum(casos.values())}
    return res, [(x, y) for x, y in pares if x["etiqueta"] != y["etiqueta"]]


def ruta_mostrable(ruta: Path) -> str:
    """Ruta para el informe: relativa a la raíz del proyecto, sin revelar rutas locales absolutas."""
    try:
        return ruta.resolve().relative_to(RAIZ.resolve()).as_posix()
    except ValueError:
        return ruta.name


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Kappa de Cohen entre dos anotaciones")
    ap.add_argument("anotador1", type=Path)
    ap.add_argument("anotador2", type=Path)
    ap.add_argument("--informe", type=Path, default=RAIZ / "eval" / "acuerdo.md")
    ap.add_argument("--desacuerdos", type=Path, default=RAIZ / "eval" / "desacuerdos.tsv")
    a = ap.parse_args()

    res, desacuerdos = informe(emparejar(leer_tsv(a.anotador1), leer_tsv(a.anotador2)))
    lineas = [
        "# Acuerdo entre anotadores",
        "",
        f"Anotador 1: `{ruta_mostrable(a.anotador1)}` · Anotador 2: `{ruta_mostrable(a.anotador2)}`",
        "",
        "| Conjunto | Palabras | Acuerdo observado | Kappa de Cohen |",
        "|---|---|---|---|",
        *(f"| {k} | {v['n']} | {v['acuerdo']:.3f} | {v['kappa']:.3f} |"
          for k, v in res.items() if k != "casos"),
        "",
        f"Casos con todas las etiquetas idénticas: {res['casos']['identicos']} de {res['casos']['n']}.",
        "",
        "La cifra principal es *contenido* (palabras sin sugerencia en la plantilla).",
        f"Desacuerdos para adjudicar: {len(desacuerdos)} (`{ruta_mostrable(a.desacuerdos)}`).",
    ]
    a.informe.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    columnas = ["caso_id", "pos", "palabra", "anotador1", "anotador2", "decision", "motivo"]
    a.desacuerdos.write_text("\n".join(["\t".join(columnas)] + [
        "\t".join([x["caso_id"], str(x["pos"]), x["palabra"], x["etiqueta"], y["etiqueta"], "", ""])
        for x, y in desacuerdos]) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
