"""
Puntuación según docs/metricas.md (versión 1). Sin dependencias externas.

Lo usa reproducir.py; las funciones están separadas para poder probarlas.
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, stdev

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "agente"))
import leer_traza  # noqa: E402

METRICAS_CALIDAD = ["exacta", "precision", "exhaustividad", "f1", "sin_cobertura_ok", "guardado"]
METRICAS_PROCESO = ["tokens_entrada", "tokens_salida", "costo_usd", "duracion_s", "pasos", "llamadas",
                    "denegadas", "errores", "ids_rechazados", "termino_bien"]

# US$ por millón de tokens (entrada, salida); precios de lista vigentes al 2026-10-06.
PRECIOS = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0), "claude-haiku-5-5": (0.10, 0.50)}
SEMILLA = 20261117
REMUESTREOS = 10_000


def normalizar(elemento: str) -> str:
    return "SIN_COBERTURA" if elemento.startswith("SIN_COBERTURA") else elemento


def puntuar_caso(salida: list[str] | None, referencia: list[str]) -> dict:
    guardado = salida is not None
    s = [normalizar(e) for e in (salida or [])]
    r = [normalizar(e) for e in referencia]
    comunes = sum((Counter(s) & Counter(r)).values())
    precision = comunes / len(s) if s else 0.0
    exhaustividad = comunes / len(r) if r else 0.0
    f1 = 2 * precision * exhaustividad / (precision + exhaustividad) if precision + exhaustividad else 0.0
    sc_ref = r.count("SIN_COBERTURA")
    return {
        "exacta": float(s == r),
        "precision": precision,
        "exhaustividad": exhaustividad,
        "f1": f1,
        "sin_cobertura_ok": min(s.count("SIN_COBERTURA"), sc_ref) / sc_ref if sc_ref else None,
        "guardado": float(guardado),
    }


def proceso_desde_traza(ruta: Path) -> dict:
    r = leer_traza.leer(ruta)
    eventos = [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
    rechazados = sum(1 for e in eventos if e["tipo"] == "herramienta"
                     and "no existe en el diccionario" in e.get("salida", ""))
    precio = PRECIOS.get(r["modelo"])
    costo = (r["tokens_entrada"] * precio[0] + r["tokens_salida"] * precio[1]) / 1e6 if precio else None
    return {"tokens_entrada": r["tokens_entrada"], "tokens_salida": r["tokens_salida"], "costo_usd": costo,
            "duracion_s": r["duracion_s"], "pasos": r["pasos"], "llamadas": r["llamadas"],
            "denegadas": r["denegadas"], "errores": r["errores"], "ids_rechazados": rechazados,
            "termino_bien": float(r["terminó_bien"]), "modelo": r["modelo"], "traza": ruta.name}


def ultima_traza(carpeta: Path, config: str, caso: str) -> Path | None:
    trazas = sorted(carpeta.glob(f"{config}_{caso}_*.jsonl"))
    return trazas[-1] if trazas else None


def evaluar(experimento: str, referencia: dict[str, dict], raiz: Path = RAIZ) -> list[dict]:
    """Una fila por configuración × repetición × caso de la referencia."""
    filas = []
    base_trazas = raiz / "trazas" / experimento
    for dir_config in sorted(p for p in base_trazas.iterdir() if p.is_dir()):
        config = dir_config.name
        for dir_rep in sorted(p for p in dir_config.iterdir() if p.is_dir()):
            rep = dir_rep.name
            dir_res = raiz / "resultados" / experimento / config / rep
            for caso, ref in referencia.items():
                traza = ultima_traza(dir_rep, config, caso)
                if traza is None:
                    continue
                archivo = dir_res / f"{caso}.json"
                salida = json.loads(archivo.read_text(encoding="utf-8"))["secuencia"] if archivo.exists() else None
                filas.append({"configuracion": config, "repeticion": rep, "caso_id": caso,
                              "dificultad": ref["dificultad"],
                              **puntuar_caso(salida, ref["secuencia"]), **proceso_desde_traza(traza)})
    return filas


def _media(valores):
    v = [x for x in valores if x is not None]
    return mean(v) if v else None


def agregar(filas: list[dict], metricas: list[str], subconjunto: str | None = None) -> dict:
    """{config: {metrica: (media entre repeticiones, DE entre repeticiones, n_casos)}}"""
    sel = [f for f in filas if subconjunto is None or f["dificultad"] == subconjunto]
    salida = {}
    for config in sorted({f["configuracion"] for f in sel}):
        reps = sorted({f["repeticion"] for f in sel if f["configuracion"] == config})
        salida[config] = {}
        for m in metricas:
            medias = [_media(f[m] for f in sel if f["configuracion"] == config and f["repeticion"] == r)
                      for r in reps]
            medias = [x for x in medias if x is not None]
            n = len({f["caso_id"] for f in sel if f["configuracion"] == config})
            salida[config][m] = (mean(medias) if medias else None,
                                 stdev(medias) if len(medias) > 1 else None, n)
    return salida


def diferencia_pareada(filas: list[dict], metrica: str, a: str = "A", b: str = "B") -> dict | None:
    """Media de (B − A) por caso (promediando repeticiones) e IC 95 % por bootstrap pareado."""
    por_caso: dict[str, dict[str, list[float]]] = {}
    for f in filas:
        if f[metrica] is not None:
            por_caso.setdefault(f["caso_id"], {}).setdefault(f["configuracion"], []).append(f[metrica])
    difs = [mean(v[b]) - mean(v[a]) for v in por_caso.values() if a in v and b in v]
    if not difs:
        return None
    rng = random.Random(SEMILLA)
    remuestras = sorted(mean(rng.choices(difs, k=len(difs))) for _ in range(REMUESTREOS))
    return {"n_casos": len(difs), "media": mean(difs),
            "ic95": (remuestras[int(0.025 * REMUESTREOS)], remuestras[int(0.975 * REMUESTREOS) - 1])}
