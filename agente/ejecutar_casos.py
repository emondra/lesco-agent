#!/usr/bin/env python3
"""
Ejecuta el agente sobre un conjunto de casos, para varias configuraciones y repeticiones.

    python agente/ejecutar_casos.py --configs A B --repeticiones 3 --casos eval/casos.jsonl

Estructura de salida (una carpeta por configuración y repetición, para que guardar_resultado
nunca choque entre ejecuciones):

    trazas/<experimento>/<config>/rep<k>/<config>_<caso>_<fecha>.jsonl
    resultados/<experimento>/<config>/rep<k>/<caso>.json

Orden: repetición → caso → configuración (A y B alternadas), para que una deriva del servicio
durante la corrida no favorezca a una configuración. Es reanudable: si ya existe una traza
terminada de un caso en su carpeta, ese caso se salta.
"""

import argparse
import io
import json
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))

import agente  # noqa: E402


def leer_casos(ruta: Path) -> list[str]:
    return [json.loads(l)["caso_id"] for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def ya_terminado(carpeta: Path, config: str, caso: str) -> bool:
    for traza in carpeta.glob(f"{config}_{caso}_*.jsonl"):
        lineas = traza.read_text(encoding="utf-8").splitlines()
        if lineas and json.loads(lineas[-1]).get("tipo") == "fin" \
                and not json.loads(lineas[-1]).get("motivo", "").startswith(("error del modelo", "error al conectar")):
            return True
    return False


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--configs", nargs="+", default=["A", "B"])
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--casos", type=Path, default=RAIZ / "eval" / "casos.jsonl")
    ap.add_argument("--experimento", default="experimento", help="nombre de la carpeta bajo trazas/ y resultados/")
    ap.add_argument("--solo", nargs="*", default=None, help="limitar a estos caso_id")
    ap.add_argument("--limite", type=int, default=None, help="procesar solo los primeros N casos")
    ap.add_argument("--simulado", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="muestra la salida completa del agente")
    a = ap.parse_args()

    casos = leer_casos(a.casos)
    if a.solo:
        casos = [c for c in casos if c in set(a.solo)]
    if a.limite:
        casos = casos[:a.limite]
    total = len(casos) * len(a.configs) * a.repeticiones
    print(f"{len(casos)} casos × {len(a.configs)} configuraciones × {a.repeticiones} repeticiones = {total}")

    hechos = saltados = fallidos = 0
    inicio = time.time()
    for rep in range(1, a.repeticiones + 1):
        for caso in casos:
            for config in a.configs:
                trazas = RAIZ / "trazas" / a.experimento / config / f"rep{rep}"
                salidas = RAIZ / "resultados" / a.experimento / config / f"rep{rep}"
                if ya_terminado(trazas, config, caso):
                    saltados += 1
                    continue
                lista = ["--config", str(AQUI / "configs" / f"{config}.json"), "--caso", caso,
                         "--casos", str(a.casos), "--salidas", str(salidas), "--trazas", str(trazas),
                         "--repeticion", str(rep)]
                if a.simulado:
                    lista += ["--simulado", "--auto-aprobar"]
                args = agente.argumentos(lista)
                if a.verbose:
                    r = agente.ejecutar(args)
                else:
                    with redirect_stdout(io.StringIO()):
                        r = agente.ejecutar(args)
                hechos += 1
                fallidos += r["codigo"] != 0
                n = hechos + saltados
                print(f"[{n}/{total}] rep{rep} {config} {caso}: {r['motivo']}  ({time.time() - inicio:.0f} s)")
                if r["motivo"].startswith("error del modelo") and "Falta ANTHROPIC_API_KEY" in r["motivo"]:
                    print("Sin clave de la API: se detiene la corrida.")
                    return 2
    print(f"\nEjecutados: {hechos}   saltados (ya terminados): {saltados}   sin terminar bien: {fallidos}")
    return 0 if fallidos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
