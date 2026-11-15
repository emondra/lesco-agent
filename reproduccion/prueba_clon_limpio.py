"""Prueba de reproducción en un clon limpio, sin API.

Crea, FUERA del repositorio, una copia limpia con exactamente los archivos que se publicarían
(versionados más los no ignorados: `git ls-files -co --exclude-standard`), sin la clave de la API en
el entorno, y comprueba que:
  1. la suite de pruebas pasa;
  2. la tabla de F7 se regenera idéntica desde las trazas;
  3. sin el paquete privado, `reproducir.py` se niega a puntuar (código 2: falta la referencia);
  4. con `--paquete`, el kappa y las tres referencias se regeneran idénticos, y las tres tablas de
     calidad se generan (y se comparan con las tablas locales si existen; no se publican);
  5. (si existe el generador de figuras y hay matplotlib) las figuras se regeneran.

Uso:
  python reproduccion/prueba_clon_limpio.py <carpeta_nueva_fuera_del_repo> [--paquete <carpeta>]
Código 0 si todo coincide; 1 si algo falla; 2 si el destino no es válido.
"""
from __future__ import annotations

import argparse
import filecmp
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REFERENCIAS = {"r1_opus": ("unico", "anotador2.tsv"), "r2_fable": ("unico", "anotador_llm_a.tsv"),
               "rc_consenso": ("consenso", None)}


def archivos_publicables() -> list[str]:
    salida = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=RAIZ,
                            capture_output=True, check=True).stdout.decode("utf-8")
    return sorted(p for p in salida.split("\0") if p)


def ejecutar(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    entorno = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID")}
    entorno["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, *cmd], cwd=cwd, env=entorno, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prueba de reproducción en un clon limpio (sin API)")
    ap.add_argument("destino", type=Path)
    ap.add_argument("--paquete", type=Path, help="paquete privado de reproducción (preparar_paquete.py)")
    a = ap.parse_args(argv)
    clon = a.destino.resolve()
    if clon == RAIZ or RAIZ in clon.parents or clon.exists():
        print("El destino debe ser una carpeta NUEVA fuera del repositorio.", file=sys.stderr)
        return 2

    archivos = archivos_publicables()
    for rel in archivos:
        (clon / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / rel, clon / rel)
    if (clon / ".env").exists():
        print("ERROR: .env entró en la copia.", file=sys.stderr)
        return 1
    print(f"Copia limpia: {len(archivos)} archivos en una carpeta nueva.")
    resultados: list[tuple[str, bool, str]] = []
    trabajo = clon / "_prueba"
    trabajo.mkdir()

    p = ejecutar(["-m", "unittest", "discover", "-s", "tests"], clon)
    ultima = (p.stderr.strip().splitlines() or ["(sin salida)"])[-1]
    total = next((l for l in p.stderr.splitlines() if l.startswith("Ran ")), "")
    resultados.append(("Suite de pruebas", p.returncode == 0, f"{total}; {ultima}"))

    p = ejecutar(["eval/evaluar_ataques.py", "--salida", str(trabajo / "f7.md")], clon)
    igual = p.returncode == 0 and filecmp.cmp(trabajo / "f7.md", clon / "resultados/ataques/resumen.md",
                                              shallow=False)
    resultados.append(("F7 regenerado idéntico", igual, f"código {p.returncode}"))

    p = ejecutar(["reproducir.py", "--experimento", "experimento", "--referencia",
                  "eval/referencias/r1_opus.jsonl", "--salida", str(trabajo / "sin_paquete")], clon)
    resultados.append(("Sin paquete privado: reproducir.py se niega (código 2)", p.returncode == 2,
                       f"código {p.returncode}"))

    if a.paquete:
        paquete = a.paquete.resolve()
        shutil.copytree(paquete / "eval", clon / "eval", dirs_exist_ok=True)
        anot = clon / "eval" / "anotaciones"
        p = ejecutar(["eval/kappa.py", str(anot / "anotador2.tsv"), str(anot / "anotador_llm_a.tsv"),
                      "--informe", str(trabajo / "acuerdo.md"), "--desacuerdos", str(trabajo / "des.tsv")],
                     clon)
        ok = p.returncode == 0 and "| contenido | 166 | 0.976 | 0.975 |" in p.stdout and filecmp.cmp(
            trabajo / "des.tsv", clon / "eval" / "desacuerdos.tsv", shallow=False)
        resultados.append(("Kappa 0,975 y desacuerdos idénticos", ok, f"código {p.returncode}"))
        for nombre, (modo, anotacion) in REFERENCIAS.items():
            salida = trabajo / f"{nombre}.jsonl"
            if modo == "unico":
                cmd = ["eval/construir_referencia.py", "--modo", "unico", "--anotacion",
                       str(anot / anotacion), "--salida", str(salida)]
            else:
                cmd = ["eval/construir_referencia.py", "--modo", "consenso", "--anotador1",
                       str(anot / "anotador2.tsv"), "--anotador2", str(anot / "anotador_llm_a.tsv"),
                       "--salida", str(salida)]
            p = ejecutar(cmd, clon)
            ok = p.returncode == 0 and filecmp.cmp(salida, clon / "eval/referencias" / f"{nombre}.jsonl",
                                                   shallow=False)
            resultados.append((f"Referencia {nombre} reconstruida idéntica", ok, f"código {p.returncode}"))
            p = ejecutar(["reproducir.py", "--experimento", "experimento", "--referencia",
                          f"eval/referencias/{nombre}.jsonl", "--salida", str(trabajo / nombre)], clon)
            # Las tablas completas no se publican: se comparan con las del clon si existen o, si no,
            # con las de la copia local de trabajo (entrega académica). Si no hay ninguna, solo se
            # comprueba que se generen.
            patron = next((d / nombre for d in (clon / "resultados/tablas", RAIZ / "resultados/tablas")
                           if (d / nombre).is_dir()), None)
            ok = p.returncode == 0 and (patron is None or all(
                filecmp.cmp(trabajo / nombre / f, patron / f, shallow=False)
                for f in ("experimento_resumen.md", "experimento_filas.csv")))
            detalle = f"código {p.returncode}; " + ("comparadas con las tablas locales" if patron
                                                     else "generadas, sin tablas de comparación")
            resultados.append((f"Tablas {nombre}", ok, detalle))

    figuras = clon / "articulo" / "generar_figuras.py"
    if figuras.exists() and importlib.util.find_spec("matplotlib"):
        p = ejecutar([str(figuras.relative_to(clon))], clon)
        resultados.append(("Figuras regeneradas", p.returncode == 0, f"código {p.returncode}"))

    print()
    for nombre, ok, detalle in resultados:
        print(f"[{'OK ' if ok else 'FALLA'}] {nombre} ({detalle})")
    return 0 if all(ok for _, ok, _ in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
