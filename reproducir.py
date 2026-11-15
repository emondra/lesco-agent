#!/usr/bin/env python3
"""
Regenera todas las tablas del artículo desde las trazas y los resultados guardados (requisito S8).

    python reproducir.py                       # experimento principal
    python reproducir.py --experimento piloto --referencia eval/piloto/referencia.jsonl

No llama a la API: solo lee trazas/<experimento>/ y resultados/<experimento>/. Escribe:
    resultados/tablas/<experimento>_filas.csv     una fila por configuración × repetición × caso
    resultados/tablas/<experimento>_resumen.md    tablas de media ± DE y comparación B − A

Definiciones: docs/metricas.md.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "eval"))

from puntuar import (METRICAS_CALIDAD, METRICAS_PROCESO, PRECIOS, REMUESTREOS, SEMILLA,  # noqa: E402
                     ErrorVinculacion, agregar, cargar_exclusiones, diferencia_pareada, evaluar)

# Conjunto esperado del experimento. No hay manifiesto: se usan los mismos valores por defecto que
# agente/ejecutar_casos.py (--configs A B, --repeticiones 3), que coinciden con docs/metricas.md §4.
# tests/test_puntuar.py comprueba que ambas fuentes de código no diverjan.
CONFIGURACIONES_PROTOCOLO = ["A", "B"]
REPETICIONES_PROTOCOLO = 3


def fmt(v, dec=3):
    return "—" if v is None else f"{v:.{dec}f}"


def tabla(agregado: dict, metricas: list[str], dec: int = 3) -> list[str]:
    configs = list(agregado)
    lineas = ["| Métrica | " + " | ".join(f"{c} (media ± DE)" for c in configs) + " |",
              "|---|" + "---|" * len(configs)]
    for m in metricas:
        celdas = [f"{fmt(agregado[c][m][0], dec)} ± {fmt(agregado[c][m][1], dec)}" for c in configs]
        lineas.append(f"| {m} | " + " | ".join(celdas) + " |")
    n = {c: agregado[c][metricas[0]][2] for c in configs}
    lineas.append("")
    lineas.append("Casos por configuración: " + ", ".join(f"{c} = {n[c]}" for c in configs) + ".")
    return lineas


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Regenera las tablas desde las trazas")
    ap.add_argument("--experimento", default="experimento")
    ap.add_argument("--referencia", type=Path, default=RAIZ / "eval" / "referencia.jsonl")
    ap.add_argument("--salida", type=Path, default=RAIZ / "resultados" / "tablas")
    ap.add_argument("--configs", nargs="+", default=CONFIGURACIONES_PROTOCOLO,
                    help="configuraciones esperadas (por defecto, las de ejecutar_casos.py)")
    ap.add_argument("--repeticiones", type=int, default=REPETICIONES_PROTOCOLO,
                    help="repeticiones esperadas por configuración (por defecto, las de ejecutar_casos.py)")
    ap.add_argument("--exclusiones", type=Path, default=RAIZ / "eval" / "exclusiones_experimento.json",
                    help="trazas excluidas explícitamente del análisis (por ruta y SHA-256)")
    a = ap.parse_args()
    if a.repeticiones < 1:
        ap.error("--repeticiones debe ser 1 o más")

    if not a.referencia.exists():
        print(f"No existe {a.referencia}: primero se construye la referencia (eval/construir_referencia.py).")
        return 2
    if not (RAIZ / "trazas" / a.experimento).exists():
        print(f"No hay trazas en trazas/{a.experimento}/.")
        return 2
    referencia = {r["caso_id"]: r for r in map(json.loads, a.referencia.read_text(encoding="utf-8").splitlines()) if r}
    try:
        excluidas = cargar_exclusiones(a.exclusiones)
        if excluidas:
            print(f"Trazas excluidas explícitamente del análisis: {len(excluidas)} ({a.exclusiones.name}).")
        filas = evaluar(a.experimento, referencia, configuraciones=a.configs, repeticiones=a.repeticiones,
                        excluidas=excluidas)
    except ErrorVinculacion as e:
        print("No se generan tablas: hay ejecuciones esperadas sin traza o sin consistencia documental "
              "con su caso:")
        for linea in e.args[0]:
            print(f"  - {linea}")
        return 3
    if not filas:
        print("No se encontraron ejecuciones que coincidan con la referencia.")
        return 2

    a.salida.mkdir(parents=True, exist_ok=True)
    ruta_csv = a.salida / f"{a.experimento}_filas.csv"
    with ruta_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)

    md = [f"# Resultados: {a.experimento}", "",
          f"Generado por `python reproducir.py --experimento {a.experimento}` desde "
          f"`trazas/{a.experimento}/` y `resultados/{a.experimento}/`. Definiciones en `docs/metricas.md`.",
          f"Ejecuciones puntuadas: {len(filas)}. Costo con precios de lista al 2026-10-06: "
          + ", ".join(f"{m} {p[0]}/{p[1]} US$ por MTok" for m, p in PRECIOS.items()) + ".", ""]
    for titulo, sub in (("Todos los casos", None), ("Casos normales", "normal"), ("Casos difíciles", "dificil")):
        agregado = agregar(filas, METRICAS_CALIDAD, sub)
        if agregado:
            md += [f"## Calidad — {titulo}", "", *tabla(agregado, METRICAS_CALIDAD), ""]
    md += ["## Proceso y costo — todos los casos", "", *tabla(agregar(filas, METRICAS_PROCESO), METRICAS_PROCESO, 2), ""]

    configs = sorted({f["configuracion"] for f in filas})
    if {"A", "B"} <= set(configs):
        md += ["## Comparación pareada B − A (por caso, promediando repeticiones)", "",
               f"IC 95 % por bootstrap pareado sobre casos ({REMUESTREOS} remuestreos, semilla {SEMILLA}).", "",
               "| Métrica | Casos | Media B − A | IC 95 % |", "|---|---|---|---|"]
        for m in ("f1", "exacta", "tokens_entrada", "duracion_s", "costo_usd"):
            d = diferencia_pareada(filas, m)
            if d:
                md.append(f"| {m} | {d['n_casos']} | {fmt(d['media'], 4)} | "
                          f"[{fmt(d['ic95'][0], 4)}, {fmt(d['ic95'][1], 4)}] |")
        md.append("")
    ruta_md = a.salida / f"{a.experimento}_resumen.md"
    ruta_md.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\nEscrito {ruta_csv} y {ruta_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
