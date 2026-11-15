#!/usr/bin/env python3
"""
Ejecución SUPERVISADA del experimento formal (A/B × repeticiones × casos), por tramos y en primer plano.

    python agente/ejecutar_supervisado.py --tope-usd 18.00 --max-corridas 30
    python agente/ejecutar_supervisado.py --tope-usd 18.00 --max-corridas 30 --solo-plan   # sin API

Usa exactamente las mismas configuraciones, el mismo orden (repetición → caso → configuración) y la misma
estructura de carpetas que agente/ejecutar_casos.py; A y B siguen difiriendo solo en la Skill. Lo que añade:

- Sin reintentos automáticos: en este proceso, ModeloClaude.REINTENTOS = 0 (un 429, 529, 5xx o fallo de red
  termina la corrida como fallo técnico) y cada solicitud HTTP tiene un tiempo máximo (--t-http).
- Identidad del modelo: si la API declara un modelo distinto del configurado, la corrida falla.
- Una corrida nunca se repite sola: si una corrida ya tiene una traza (válida o no), no se vuelve a lanzar.
  Si hay alguna fallida, el tramo no empieza: requiere una decisión humana.
- Trazas excluidas explícitamente (eval/exclusiones_experimento.json, por ruta y SHA-256) no cuentan como
  corridas hechas ni se analizan.
- Antes de CADA corrida: umbral preventivo de gasto (gasto estimado del experimento + reserva ≤ tope) y de
  tiempo (no se inicia una corrida después de --t-nueva segundos).
- Después de cada corrida: comprobación documental D18/D19 (puntuar.problemas_de_validez) y una línea en
  resultados/<experimento>/supervisor.jsonl con identificadores, modelo, versión de configuración e
  instrucciones (SHA-256), tokens y costo estimado. Ante cualquier fallo técnico o inconsistencia, se detiene.

El gasto es una ESTIMACIÓN desde los tokens de las trazas (eval/puntuar.py, PRECIOS); no es un límite
monetario garantizado. El único límite estricto es el de la consola de Anthropic.

Códigos de salida: 0 todo el plan hecho · 10 tramo completo, quedan corridas · 3 precondición o exclusión
inválida · 4 hay corridas fallidas previas (decisión humana) · 5 una corrida falló o es inconsistente ·
8 umbral de gasto · 9 límite de tiempo.
"""

import argparse
import hashlib
import io
import json
import sys
import time
import urllib.request
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ / "eval"))

import agente  # noqa: E402
import puntuar  # noqa: E402


def sha256_archivo(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def leer_casos(ruta: Path) -> list[str]:
    return [json.loads(l)["caso_id"] for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def plan(casos: list[str], configs: list[str], repeticiones: int) -> list[tuple[str, str, int]]:
    """Mismo orden que agente/ejecutar_casos.py: repetición → caso → configuración."""
    return [(config, caso, rep) for rep in range(1, repeticiones + 1) for caso in casos for config in configs]


def carpetas(raiz: Path, experimento: str, config: str, rep: int) -> tuple[Path, Path]:
    return (raiz / "trazas" / experimento / config / f"rep{rep}",
            raiz / "resultados" / experimento / config / f"rep{rep}")


def estado(raiz: Path, experimento: str, config: str, caso: str, rep: int, excluidas: frozenset[str]) -> str:
    """'pendiente' (sin trazas no excluidas), 'hecha' (la última traza es válida) o 'fallida'."""
    dir_t, dir_r = carpetas(raiz, experimento, config, rep)
    traza = puntuar.ultima_traza(dir_t, config, caso, excluidas)
    if traza is None:
        return "pendiente"
    return "hecha" if not puntuar.problemas_de_validez(traza, caso, dir_r / f"{caso}.json") else "fallida"


def gasto_estimado(raiz: Path, experimento: str, excluidas: frozenset[str]) -> float:
    total = 0.0
    base = raiz / "trazas" / experimento
    for t in sorted(base.glob("*/rep*/*.jsonl")) if base.exists() else []:
        if str(t.resolve()) in excluidas:
            continue
        costo = puntuar.proceso_desde_traza(t)["costo_usd"]
        total += costo or 0.0
    return total


def sin_reintentos(t_http: float) -> None:
    """En este proceso: ningún reintento automático, tiempo máximo por solicitud e identidad de modelo."""
    agente.ModeloClaude.REINTENTOS = 0
    original_urlopen = urllib.request.urlopen

    def urlopen_limitado(req, *a, **k):
        k["timeout"] = t_http
        return original_urlopen(req, *a, **k)
    agente.urllib.request.urlopen = urlopen_limitado

    original_responder = agente.ModeloClaude.responder

    def responder_con_identidad(self, *a, **k):
        r = original_responder(self, *a, **k)
        if r.get("model") != self.modelo:
            raise agente.ErrorModelo(f"modelo declarado {r.get('model')!r} distinto del configurado {self.modelo!r}")
        return r
    agente.ModeloClaude.responder = responder_con_identidad


def main(argv: list[str] | None = None, raiz: Path = RAIZ) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Ejecución supervisada del experimento formal")
    ap.add_argument("--tope-usd", type=float, required=True, help="umbral preventivo de gasto estimado del experimento")
    ap.add_argument("--max-corridas", type=int, required=True, help="corridas como máximo en este tramo")
    ap.add_argument("--reserva-usd", type=float, default=0.15, help="reserva por corrida para el umbral (estimación)")
    ap.add_argument("--configs", nargs="+", default=["A", "B"])
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--casos", type=Path, default=raiz / "eval" / "casos.jsonl")
    ap.add_argument("--experimento", default="experimento")
    ap.add_argument("--exclusiones", type=Path, default=raiz / "eval" / "exclusiones_experimento.json")
    ap.add_argument("--t-nueva", type=float, default=420, help="no iniciar corridas después de estos segundos")
    ap.add_argument("--t-http", type=float, default=150, help="tiempo máximo por solicitud HTTP")
    ap.add_argument("--solo-plan", action="store_true", help="solo muestra el estado y el plan; no llama a la API")
    a = ap.parse_args(argv)
    if a.max_corridas < 1 or a.repeticiones < 1:
        ap.error("--max-corridas y --repeticiones deben ser 1 o más")
    inicio = time.monotonic()

    try:
        excluidas = puntuar.cargar_exclusiones(a.exclusiones, raiz)
    except puntuar.ErrorVinculacion as e:
        print("PRECONDICIÓN FALLIDA:", "; ".join(e.args[0]))
        return 3
    configs_rutas = {c: AQUI / "configs" / f"{c}.json" for c in a.configs}
    for c, ruta in configs_rutas.items():
        if not ruta.exists():
            print(f"PRECONDICIÓN FALLIDA: no existe la configuración {c}")
            return 3
    version = {}
    for c, ruta in configs_rutas.items():
        conf = json.loads(ruta.read_text(encoding="utf-8"))
        version[c] = {"modelo": conf["modelo"], "sha256_config": sha256_archivo(ruta),
                      "sha256_instrucciones": hashlib.sha256("".join(
                          sha256_archivo(raiz / i) for i in conf["instrucciones"]).encode()).hexdigest()}

    todo = plan(leer_casos(a.casos), a.configs, a.repeticiones)
    estados = {k: estado(raiz, a.experimento, *k, excluidas) for k in todo}
    fallidas = [k for k, v in estados.items() if v == "fallida"]
    pendientes = [k for k, v in estados.items() if v == "pendiente"]
    gasto = gasto_estimado(raiz, a.experimento, excluidas)
    print(f"plan: {len(todo)} corridas | hechas {sum(v == 'hecha' for v in estados.values())} | "
          f"pendientes {len(pendientes)} | fallidas {len(fallidas)} | excluidas registradas {len(excluidas)} | "
          f"gasto estimado del experimento US$ {gasto:.4f} | tope US$ {a.tope_usd:.2f}")
    if fallidas:
        print("Hay corridas fallidas previas; no se repiten automáticamente (decisión humana):")
        for config, caso, rep in fallidas[:20]:
            print(f"  - {config}/rep{rep}/{caso}")
        return 4
    if a.solo_plan:
        tramo = pendientes[:a.max_corridas]
        print(f"tramo previsto: {len(tramo)} corridas" + (f", de {tramo[0]} a {tramo[-1]}" if tramo else ""))
        return 0 if not pendientes else 10
    if not pendientes:
        print("No quedan corridas pendientes.")
        return 0

    sin_reintentos(a.t_http)
    manifiesto = raiz / "resultados" / a.experimento / "supervisor.jsonl"
    manifiesto.parent.mkdir(parents=True, exist_ok=True)
    hechas = 0
    for config, caso, rep in pendientes:
        if hechas >= a.max_corridas:
            break
        if gasto + a.reserva_usd > a.tope_usd:
            print(f"UMBRAL PREVENTIVO: gasto estimado US$ {gasto:.4f} + reserva {a.reserva_usd:.2f} > tope "
                  f"{a.tope_usd:.2f}. No se inicia {config}/rep{rep}/{caso}.")
            return 8
        if time.monotonic() - inicio >= a.t_nueva:
            print(f"TIEMPO: no se inician corridas después de {a.t_nueva:.0f} s.")
            return 9
        dir_t, dir_r = carpetas(raiz, a.experimento, config, rep)
        args = agente.argumentos(["--config", str(configs_rutas[config]), "--caso", caso, "--casos", str(a.casos),
                                  "--salidas", str(dir_r), "--trazas", str(dir_t), "--repeticion", str(rep)])
        t0 = time.monotonic()
        with redirect_stdout(io.StringIO()):
            r = agente.ejecutar(args)
        traza = Path(r["traza"])
        problemas = puntuar.problemas_de_validez(traza, caso, dir_r / f"{caso}.json")
        proceso = puntuar.proceso_desde_traza(traza)
        costo = proceso["costo_usd"] or 0.0
        gasto += costo
        hechas += 1
        linea = {"fecha": datetime.now().isoformat(timespec="seconds"), "experimento": a.experimento,
                 "configuracion": config, "caso_id": caso, "repeticion": rep,
                 "id_corrida": f"{a.experimento}/{config}/rep{rep}/{caso}", **version[config],
                 "modelo_traza": proceso["modelo"], "traza": traza.name, "codigo": r["codigo"],
                 "motivo": r["motivo"][:120], "valida_D19": not problemas,
                 "tokens_entrada": proceso["tokens_entrada"], "tokens_salida": proceso["tokens_salida"],
                 "costo_estimado_usd": round(costo, 6), "duracion_s": round(time.monotonic() - t0, 1)}
        with manifiesto.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(linea, ensure_ascii=False) + "\n")
        print(f"[{hechas}] {config}/rep{rep}/{caso}: {'ok' if not problemas else 'NO VÁLIDA'} | código {r['codigo']} | "
              f"US$ {costo:.4f} | acumulado US$ {gasto:.4f}")
        if problemas:
            print("DETENIDO: la corrida falló o no es consistente (no se repite):", "; ".join(problemas)[:300])
            return 5
    quedan = len(pendientes) - hechas
    print(f"tramo: {hechas} corridas | quedan {quedan} | gasto estimado del experimento US$ {gasto:.4f} | "
          f"{time.monotonic() - inicio:.0f} s")
    return 0 if quedan == 0 else 10


if __name__ == "__main__":
    sys.exit(main())
