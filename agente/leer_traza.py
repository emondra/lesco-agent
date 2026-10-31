#!/usr/bin/env python3
"""
Resume una o varias trazas del agente. Es la base de las métricas del proyecto final.

Uso:
    python leer_traza.py trazas/ejecucion_20260929_183518.jsonl
    python leer_traza.py trazas/*.jsonl --csv metricas.csv

Por cada ejecución: pasos, llamadas por herramienta, decisiones de la política, errores,
tokens, duración y motivo de parada. Con varias trazas, además, promedios: así se compara
una configuración contra otra (con y sin skill, con y sin envoltura de resultados, etc.).
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

# LESCO-Agent: la única herramienta de escritura del servidor propio (en el kit eran
# crear_ticket y guardar_borrador_correo).
ESCRITURAS = ("guardar_resultado",)


def leer(ruta: Path) -> dict:
    eventos = [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
    inicio = next((e for e in eventos if e["tipo"] == "inicio"), {})
    fin = next((e for e in eventos if e["tipo"] == "fin"), {})
    herramientas = [e for e in eventos if e["tipo"] == "herramienta"]
    firmas = Counter(json.dumps([h["nombre"], h["argumentos"]], sort_keys=True) for h in herramientas)
    return {
        "archivo": ruta.name,
        "configuracion": inicio.get("configuracion", "?"),
        "caso_id": inicio.get("caso_id", "?"),
        "repeticion": inicio.get("repeticion"),
        "modelo": inicio.get("modelo", "?"),
        "pasos": fin.get("pasos", 0),
        "motivo": fin.get("motivo", "sin evento de fin (ejecución interrumpida)"),
        "llamadas": len(herramientas),
        "por_herramienta": dict(Counter(h["nombre"] for h in herramientas)),
        "denegadas": sum(1 for h in herramientas if h["decision"] == "denegar"),
        "errores": sum(1 for h in herramientas if h["es_error"] and h["decision"] == "permitir"),
        "repetidas": sum(n - 1 for n in firmas.values() if n > 1),
        "escrituras": sum(1 for h in herramientas
                          if h["decision"] == "permitir" and not h["es_error"]
                          and h["nombre"].split("__")[-1] in ESCRITURAS),
        "tokens_entrada": fin.get("tokens_entrada", 0),
        "tokens_salida": fin.get("tokens_salida", 0),
        "duracion_s": fin.get("duracion_s", 0),
        "terminó_bien": str(fin.get("motivo", "")).startswith("el modelo terminó"),
    }


def imprimir(r: dict) -> None:
    print(f"\n{r['archivo']}  ·  modelo {r['modelo']}  ·  config {r['configuracion']}  ·  caso {r['caso_id']}")
    print(f"  parada      : {r['motivo']}")
    print(f"  pasos       : {r['pasos']}   llamadas: {r['llamadas']}   "
          f"denegadas: {r['denegadas']}   errores: {r['errores']}   repetidas: {r['repetidas']}")
    print(f"  escrituras  : {r['escrituras']} efectivas")
    print(f"  tokens      : {r['tokens_entrada']} + {r['tokens_salida']}   duración: {r['duracion_s']} s")
    for nombre, n in sorted(r["por_herramienta"].items(), key=lambda kv: -kv[1]):
        print(f"    {n:2} x {nombre}")
    alertas = []
    if r["repetidas"]:
        alertas.append("llamadas idénticas repetidas: el agente no aprovechó el resultado anterior")
    if r["denegadas"]:
        alertas.append("hubo acciones denegadas: revisen de dónde salió la intención")
    if not r["terminó_bien"]:
        alertas.append("no terminó por decisión propia: revisen el criterio de parada")
    for a in alertas:
        print(f"  ! {a}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("trazas", nargs="+", type=Path)
    ap.add_argument("--csv", type=Path, help="exporta una fila por ejecución")
    a = ap.parse_args()
    filas = []
    for t in a.trazas:
        if not t.exists():
            sys.exit(f"No existe {t}")
        filas.append(leer(t))
        imprimir(filas[-1])

    if len(filas) > 1:
        print("\n== Promedio de", len(filas), "ejecuciones")
        for k in ("pasos", "llamadas", "denegadas", "errores", "tokens_entrada", "duracion_s"):
            print(f"  {k:15}: {mean(f[k] for f in filas):.1f}")
        print(f"  terminaron bien: {sum(f['terminó_bien'] for f in filas)} de {len(filas)}")

    if a.csv:
        campos = [k for k in filas[0] if k != "por_herramienta"]
        with a.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            w.writerows(filas)
        print(f"\nEscrito {a.csv}")
