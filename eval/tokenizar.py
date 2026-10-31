#!/usr/bin/env python3
"""
Tokenizador determinista y plantilla de anotación (guía v1, §2–§3).

    python eval/tokenizar.py                       # escribe eval/anotaciones/plantilla.tsv
    python eval/tokenizar.py --casos OTRO.jsonl --salida OTRA.tsv

Cada palabra (secuencia de letras o dígitos) es una fila. La columna `sugerencia` trae
`OMITIR` para las palabras de la lista cerrada de la guía; el resto queda vacía. La
sugerencia es solo una ayuda: si la palabra forma parte de una expresión de varias
palabras (§4) o es un auxiliar/cópula (§3), el anotador decide. Los dos anotadores
reciben exactamente la misma plantilla.
"""

import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PALABRA = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")

# Lista cerrada de la guía v1, §3. Se compara en minúsculas y CON tildes:
# "que" (conjunción) se omite, "qué" (interrogativo) no; "el" y "él" se omiten ambos.
# "sí" no se incluye: puede ser pronombre (se omite) o afirmación (no se omite).
# Los auxiliares y las cópulas no se sugieren: dependen del contexto.
OMITIR = {
    "el", "la", "los", "las", "lo", "un", "una", "unos", "unas",
    "a", "al", "ante", "bajo", "de", "del", "en", "entre", "hacia", "por", "según", "tras",
    "y", "e", "ni", "que",
    "yo", "tú", "vos", "usted", "ustedes", "él", "ella", "ellos", "ellas", "nosotros", "nosotras",
    "me", "te", "se", "le", "les", "nos", "mí", "ti",
    "mi", "mis", "tu", "tus", "su", "sus", "nuestro", "nuestra", "nuestros", "nuestras",
}

ETIQUETAS_VALIDAS = re.compile(r"^(CENAREC-\d{1,5}|\+|SIN_COBERTURA|OMITIR)$")


def palabras(texto: str) -> list[str]:
    return PALABRA.findall(texto)


def sugerencia(palabra: str) -> str:
    return "OMITIR" if palabra.lower() in OMITIR else ""


def plantilla(ruta_casos: Path) -> list[dict]:
    filas = []
    for linea in ruta_casos.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        caso = json.loads(linea)
        for pos, p in enumerate(palabras(caso["texto"])):
            filas.append({"caso_id": caso["caso_id"], "pos": pos, "palabra": p,
                          "sugerencia": sugerencia(p), "etiqueta": ""})
    return filas


def escribir_tsv(filas: list[dict], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    columnas = ["caso_id", "pos", "palabra", "sugerencia", "etiqueta"]
    lineas = ["\t".join(columnas)] + ["\t".join(str(f[c]) for c in columnas) for f in filas]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def leer_tsv(ruta: Path) -> list[dict]:
    lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
    columnas = lineas[0].split("\t")
    filas = []
    for n, linea in enumerate(lineas[1:], start=2):
        if not linea.strip():
            continue
        valores = linea.split("\t") + [""] * (len(columnas) - len(linea.split("\t")))
        fila = dict(zip(columnas, valores))
        fila["pos"] = int(fila["pos"])
        fila["etiqueta"] = fila["etiqueta"].strip()
        if fila["etiqueta"] and not ETIQUETAS_VALIDAS.match(fila["etiqueta"]):
            raise ValueError(f"{ruta}:{n}: etiqueta inválida {fila['etiqueta']!r}")
        filas.append(fila)
    return filas


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Genera la plantilla de anotación por palabra")
    ap.add_argument("--casos", type=Path, default=RAIZ / "eval" / "casos.jsonl")
    ap.add_argument("--salida", type=Path, default=RAIZ / "eval" / "anotaciones" / "plantilla.tsv")
    a = ap.parse_args()
    filas = plantilla(a.casos)
    escribir_tsv(filas, a.salida)
    sugeridas = sum(1 for f in filas if f["sugerencia"])
    print(f"{a.salida}: {len(filas)} palabras, {sugeridas} con sugerencia OMITIR, "
          f"{len(filas) - sugeridas} por etiquetar")
