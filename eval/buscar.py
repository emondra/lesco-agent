#!/usr/bin/env python3
"""
Buscador de ayuda para anotar (el mismo motor que la herramienta buscar_sena del agente).

    python eval/buscar.py pagar
    python eval/buscar.py "en la mañana" esperar fila
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp_server"))
from lexico import ErrorEntrada, Lexico  # noqa: E402

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    lex = Lexico()
    for consulta in sys.argv[1:]:
        try:
            r = lex.buscar(consulta, 10)
        except ErrorEntrada as e:
            print(f"\n{consulta!r}: {e}")
            continue
        print(f"\n{consulta!r}: {r['total_coincidencias']} coincidencias")
        for x in r["resultados"]:
            print(f"  {x['id']:14} {x['coincidencia']:8} {x['glosa']:32} {x['url']}")
        if not r["resultados"]:
            print("  (sin coincidencias → sinónimo o SIN_COBERTURA)")
