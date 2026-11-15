"""
Puntuación según docs/metricas.md (versión 1). Sin dependencias externas.

Lo usa reproducir.py; las funciones están separadas para poder probarlas.
"""

import hashlib
import json
import random
import re
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


class ErrorVinculacion(Exception):
    """Hay ejecuciones esperadas sin traza o sin consistencia documental con su caso: no se puntúa nada."""


# Mismo formato de caso_id que agente/agente.py y mcp_server/servidor_lesco.py, aplicado con fullmatch.
PATRON_CASO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}")
CAMPOS_HERRAMIENTA = {"nombre": str, "decision": str, "argumentos": dict, "es_error": bool}
# Prefijos con que agente/agente.py cierra una ejecución que no llegó a completarse por un fallo
# técnico (API, autenticación, red o servidor MCP). Son los mismos que usa
# agente/ejecutar_casos.py:ya_terminado para reintentarla. No son errores lingüísticos del agente.
PREFIJOS_FALLO_TECNICO = ("error del modelo", "error al conectar")


def _breve(valor) -> str:
    """Representación segura de un caso_id para mensajes: solo se muestra si cumple por completo el
    formato permitido; cualquier otro valor se sustituye, sin mostrar ningún fragmento."""
    if isinstance(valor, str) and PATRON_CASO.fullmatch(valor):
        return repr(valor)
    return "'identificador inválido'"


def problemas_de_cierre(eventos: list[dict]) -> list[str]:
    """La ejecución terminó y su final es puntuable: hay un único evento 'fin', es el último, su
    'motivo' es texto no vacío y no indica un fallo técnico. Los mensajes nunca incluyen el motivo
    (puede contener respuestas de la API o identificadores de solicitud). Lista vacía = puntuable.
    Un final normal con resultado lingüístico incorrecto, o un límite de pasos, sigue siendo puntuable."""
    fines = [n for n, e in enumerate(eventos) if e["tipo"] == "fin"]
    if not fines:
        return ["la traza no tiene evento 'fin' (ejecución interrumpida o incompleta)"]
    if len(fines) > 1:
        return [f"la traza tiene {len(fines)} eventos 'fin'"]
    if fines[0] != len(eventos) - 1:
        return ["el evento 'fin' no es el último de la traza"]
    motivo = eventos[-1].get("motivo")
    if not isinstance(motivo, str) or not motivo.strip():
        return ["el evento 'fin' no tiene un 'motivo' de texto"]
    if motivo.startswith(PREFIJOS_FALLO_TECNICO):
        return ["la ejecución terminó por un fallo técnico (modelo, autenticación o conexión); "
                "no es puntuable"]
    return []


def problemas_de_validez(ruta_traza: Path, caso: str, archivo: Path) -> list[str]:
    """Consistencia documental entre la traza de una ejecución y su resultado, antes de puntuarla.

    No cambia ninguna métrica. Comprueba lo que la traza y el archivo DECLARAN; no demuestra
    autenticidad criptográfica ni qué proceso escribió el archivo (eso depende del registro de
    evidencia y de git):
    0. la traza se puede leer: cada línea es un objeto JSON con 'tipo', y los eventos 'herramienta'
       tienen los campos que usa agente/leer_traza.py con su tipo;
    0b. la ejecución terminó con un único evento 'fin' final, con 'motivo' de texto y sin fallo
        técnico (problemas_de_cierre);
    1. la traza tiene evento 'inicio' de ese caso;
    2. todos los servidores MCP registrados declaran vinculación a ese caso (campo 'servidores');
    3. ningún guardar_resultado exitoso de la traza apunta a otro caso;
    4. existe <caso>.json si y solo si la traza registra exactamente un guardado exitoso del caso;
    5. el archivo, si existe, es un objeto JSON que declara ese mismo caso_id;
    6. y contiene 'secuencia' como lista de textos.
    Los mensajes indican línea o archivo, nunca el contenido. Lista vacía = consistente."""
    try:
        lineas = ruta_traza.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return [f"no se pudo leer la traza {ruta_traza.name} como texto UTF-8"]
    eventos, problemas = [], []
    for n, linea in enumerate(lineas, start=1):
        if not linea.strip():
            continue
        try:
            evento = json.loads(linea)
        except ValueError:
            problemas.append(f"la traza contiene JSON mal formado en la línea {n}")
            continue
        if not isinstance(evento, dict):
            problemas.append(f"la línea {n} de la traza no es un objeto JSON")
            continue
        if not isinstance(evento.get("tipo"), str):
            problemas.append(f"la línea {n} de la traza no tiene 'tipo'")
            continue
        if evento["tipo"] == "herramienta" and (
                any(not isinstance(evento.get(c), t) for c, t in CAMPOS_HERRAMIENTA.items())
                or not isinstance(evento.get("salida", ""), str)):
            problemas.append(f"la línea {n} de la traza (herramienta) no tiene los campos esperados")
            continue
        eventos.append(evento)
    if problemas:
        return problemas                      # una traza ilegible no permite comprobar nada más
    cierre = problemas_de_cierre(eventos)
    if cierre:
        return cierre                         # sin un final puntuable no se comprueba nada más
    inicio = next((e for e in eventos if e.get("tipo") == "inicio"), None)
    if inicio is None:
        return ["la traza no tiene evento 'inicio' (la ejecución no llegó a arrancar)"]
    problemas = []
    if inicio.get("caso_id") != caso:
        problemas.append(f"la traza es del caso {_breve(inicio.get('caso_id'))}")
    servidores = inicio.get("servidores")
    if not isinstance(servidores, list) or not servidores:
        problemas.append("la traza no registra servidores vinculados (sin evidencia de --caso)")
    else:
        for s in servidores:
            if not isinstance(s, dict) or s.get("caso_vinculado") != caso or not s.get("version"):
                problemas.append(f"servidor sin vinculación declarada al caso {caso!r}")
    guardados = [e for e in eventos if e.get("tipo") == "herramienta"
                 and str(e.get("nombre", "")).endswith("__guardar_resultado")
                 and e.get("decision") == "permitir" and not e.get("es_error")]
    propios = [e for e in guardados if e["argumentos"].get("caso_id") == caso]
    if len(propios) != len(guardados):
        problemas.append("la traza registra un guardado exitoso de otro caso")
    if archivo.exists():
        if len(propios) != 1:
            problemas.append(f"existe {archivo.name} pero la traza registra {len(propios)} guardados "
                             "exitosos del caso")
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (ValueError, OSError):                      # incluye UnicodeDecodeError
            problemas.append(f"{archivo.name} no se pudo leer como JSON")
        else:
            if not isinstance(datos, dict):
                problemas.append(f"{archivo.name} no es un objeto JSON")
            else:
                if datos.get("caso_id") != caso:
                    problemas.append(f"{archivo.name} declara caso_id {_breve(datos.get('caso_id'))}")
                if "secuencia" not in datos:
                    problemas.append(f"{archivo.name} no contiene 'secuencia'")
                elif not (isinstance(datos["secuencia"], list)
                          and all(isinstance(x, str) for x in datos["secuencia"])):
                    problemas.append(f"{archivo.name}: 'secuencia' no es una lista de textos")
    elif propios:
        problemas.append(f"la traza registra un guardado exitoso pero no existe {archivo.name}")
    return problemas


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


def cargar_exclusiones(ruta: Path, raiz: Path = RAIZ) -> frozenset[str]:
    """Trazas excluidas explícitamente del análisis (eval/exclusiones_experimento.json). Devuelve sus
    rutas resueltas. Falla cerrado (ErrorVinculacion) si una traza listada existe y su SHA-256 no
    coincide: una exclusión solo vale para el archivo exacto que se registró. Sin archivo: ninguna."""
    if not ruta.exists():
        return frozenset()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    excluidas, problemas = set(), []
    for e in datos.get("trazas_excluidas", []):
        p = (raiz / e["ruta"]).resolve()
        if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() != e["sha256"]:
            problemas.append(f"la traza excluida {Path(e['ruta']).name} cambió (SHA-256 distinto)")
        excluidas.add(str(p))
    if problemas:
        raise ErrorVinculacion(problemas)
    return frozenset(excluidas)


def ultima_traza(carpeta: Path, config: str, caso: str, excluidas: frozenset[str] = frozenset()) -> Path | None:
    trazas = sorted(t for t in carpeta.glob(f"{config}_{caso}_*.jsonl") if str(t.resolve()) not in excluidas)
    return trazas[-1] if trazas else None


def evaluar(experimento: str, referencia: dict[str, dict], raiz: Path = RAIZ, *,
            configuraciones: list[str] | None = None, repeticiones: int | None = None,
            excluidas: frozenset[str] = frozenset()) -> list[dict]:
    """Una fila por configuración × repetición × caso de la referencia.

    Conjunto esperado: `configuraciones` y `repeticiones` (rep1..repN) si se indican (reproducir.py
    siempre los indica); si no, se deducen de las carpetas existentes. Falla cerrado (ErrorVinculacion,
    sin puntuaciones parciales) si la referencia está vacía, si no hay trazas, configuraciones o
    repeticiones, si falta o sobra una configuración o repetición esperada, si falta la traza de una
    ejecución esperada o si alguna no es documentalmente consistente (problemas_de_validez)."""
    if not referencia:
        raise ErrorVinculacion(["la referencia está vacía: no hay casos que evaluar"])
    if repeticiones is not None and repeticiones < 1:
        raise ValueError("repeticiones debe ser 1 o más")
    base_trazas = raiz / "trazas" / experimento
    if not base_trazas.is_dir():
        raise ErrorVinculacion([f"no existe trazas/{experimento}"])
    presentes = {p.name: p for p in base_trazas.iterdir() if p.is_dir()}
    invalidas = []
    if configuraciones is None:
        esperadas = sorted(presentes)
        if not esperadas:
            raise ErrorVinculacion([f"trazas/{experimento} no contiene configuraciones"])
    else:
        esperadas = list(configuraciones)
        invalidas += [f"{c}: falta la configuración esperada" for c in esperadas if c not in presentes]
        invalidas += [f"{c}: configuración no esperada" for c in sorted(presentes) if c not in esperadas]
    reps_por_config = {c: {p.name for p in presentes[c].iterdir() if p.is_dir()}
                       for c in esperadas if c in presentes}
    if repeticiones is None:
        reps_esperadas = sorted(set().union(*reps_por_config.values()))
        if reps_por_config and not reps_esperadas:
            invalidas.append("ninguna configuración contiene repeticiones")
    else:
        reps_esperadas = [f"rep{k}" for k in range(1, repeticiones + 1)]
        for c, reps in reps_por_config.items():
            invalidas += [f"{c}/{r}: repetición no esperada" for r in sorted(reps - set(reps_esperadas))]
    filas = []
    for config in esperadas:
        if config not in presentes:
            continue                                   # ya registrada como configuración ausente
        for rep in reps_esperadas:
            if rep not in reps_por_config[config]:
                invalidas.append(f"{config}/{rep}: falta la carpeta de la repetición")
                continue
            dir_rep = presentes[config] / rep
            dir_res = raiz / "resultados" / experimento / config / rep
            for caso, ref in referencia.items():
                traza = ultima_traza(dir_rep, config, caso, excluidas)
                if traza is None:
                    invalidas.append(f"{config}/{rep}/{caso}: no hay traza de la ejecución esperada")
                    continue
                archivo = dir_res / f"{caso}.json"
                problemas = problemas_de_validez(traza, caso, archivo)
                if problemas:
                    invalidas.append(f"{config}/{rep}/{caso}: " + "; ".join(problemas))
                    continue
                salida = json.loads(archivo.read_text(encoding="utf-8"))["secuencia"] if archivo.exists() else None
                filas.append({"configuracion": config, "repeticion": rep, "caso_id": caso,
                              "dificultad": ref["dificultad"],
                              **puntuar_caso(salida, ref["secuencia"]), **proceso_desde_traza(traza)})
    if invalidas:
        raise ErrorVinculacion(invalidas)
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
