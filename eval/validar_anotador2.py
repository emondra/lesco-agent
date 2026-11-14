#!/usr/bin/env python3
"""
Validación técnica agregada del anotador 2 (F5). Solo lee y solo imprime cifras.

    python eval/validar_anotador2.py
    python eval/validar_anotador2.py --registro RUTA --tsv RUTA

Comprueba que el registro de eval/anotador_llm.py (anotador2_respuestas.jsonl) y anotador2.tsv
estén completos y sean coherentes con la plantilla, el índice y el prompt vigente. NO evalúa la
calidad lingüística de las etiquetas (eso lo hacen el kappa y la adjudicación) ni demuestra la
independencia de los anotadores.

Protocolo (no se modifica): la respuesta de un caso es la que usa eval/anotador_llm.py, es decir, el
último registro sin problemas del caso (registro_valido), y con ella se construye el TSV. Son
legítimos los intentos con problemas y las respuestas válidas con un prompt anterior seguidas de una
válida con el vigente. Reglas de VALIDACIÓN más estrictas que el script de anotación (impiden el 0):
  1. la respuesta seleccionada debe tener el prompt vigente;
  2. no puede haber más de una respuesta válida con el prompt vigente para un mismo caso;
  3. el TSV se lee de forma estricta (encabezado exacto, 5 columnas, posición entera, sin filas
     repetidas), a diferencia de eval/tokenizar.leer_tsv, que completa las columnas faltantes.

Privacidad: nunca imprime etiquetas, palabras, respuestas, identificadores de caso, rutas, el texto
de los problemas registrados ni distribuciones de etiquetas. Los metadatos del registro (modelo,
fechas, stop_reason, intento, prefijo del SHA-256 del prompt y claves de uso) solo se imprimen si
tienen el formato esperado; si no, como "<formato inesperado>". Los errores muestran solo su tipo y
el nombre lógico de la entrada. Las huellas SHA-256 identifican la versión de cada entrada sin
mostrar su contenido.

Sin escritura, red ni API: no importa agente.py ni anotador_llm.py (cargan el cliente de la API).

Códigos de salida:
  0  completo y válido;
  1  incompleto o inválido (cualquier inconsistencia, defecto o caso sin respuesta seleccionable);
  2  error de lectura o de formato de una entrada, plantilla defectuosa, error inesperado o
     argumentos inválidos (sin repetir los valores recibidos).

Origen: deriva del script temporal no versionado validar_anotador2_agregado.py
(SHA-256 D591098139B69E7CF150025CDBC8663E3D29F98E042EFDEAADC2C3DB4ECB1B13), con el que se hizo la
validación del 2026-11-13. Aquella validación sigue atribuida a ese script; este archivo es una
versión revisada y no lo sustituye.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "eval"))
from tokenizar import ETIQUETAS_VALIDAS  # noqa: E402  (módulo sin efectos secundarios)

ANOT = RAIZ / "eval" / "anotaciones"
COLUMNAS_TSV = ["caso_id", "pos", "palabra", "sugerencia", "etiqueta"]  # = eval/tokenizar.escribir_tsv
# Campos que escribe eval/anotador_llm.py (líneas 167-172) y que la validación necesita, con su tipo.
CAMPOS_REGISTRO = {"caso_id": str, "intento": int, "sha256_prompt": str, "etiquetas": list, "problemas": list}
CLAVES_USO = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
INESPERADO = "<formato inesperado>"
# Mensajes que produce eval/anotador_llm.py (validar() y respuestas no utilizables).
CATEGORIAS = (
    ("posiciones", re.compile(r"posiciones ")),
    ("etiqueta_invalida", re.compile(r"pos \d+: etiqueta inválida ")),
    ("id_inexistente", re.compile(r"pos \d+: CENAREC-\d+ no existe en el índice$")),
    ("mas_huerfano", re.compile(r"pos \d+: '\+' sin una entrada anterior$")),
    ("respuesta_no_utilizable", re.compile(r"respuesta no utilizable")),
)
BLOQUEAN_REGISTRO = ("malformados", "ajenos", "sin_valida", "sin_vigente", "duplicados_identicos",
                     "duplicados_contradictorios", "ultima_no_vigente", "no_revalida")
BLOQUEAN_TSV = ("casos_ajenos", "casos_faltantes", "casos_desalineados", "etiquetas_vacias",
                "etiquetas_invalidas", "casos_sin_seleccion", "posiciones_solo_en_tsv",
                "posiciones_solo_en_registro", "etiquetas_distintas")
_RE_POS = re.compile(r"[0-9]{1,4}")
_RE_MODELO = re.compile(r"[a-z0-9][a-z0-9.\-]{0,63}")
_RE_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_RE_HEX = re.compile(r"[0-9a-f]{64}")
_RE_STOP = re.compile(r"[a-z_]{1,32}")


class ErrorLectura(Exception):
    """Una entrada no se pudo leer o no tiene el formato mínimo. Solo guarda su nombre lógico y el tipo."""

    def __init__(self, entrada: str, tipo: str):
        super().__init__(entrada)
        self.entrada, self.tipo = entrada, tipo


class _Argumentos(argparse.ArgumentParser):
    """ArgumentParser que no repite en sus errores los valores recibidos (podrían ser rutas)."""

    def error(self, message):  # noqa: ARG002  el mensaje original se descarta a propósito
        print("ERROR de argumentos (mensaje suprimido). Use --help para ver las opciones.")
        raise SystemExit(2)


# --- Lectura (solo lectura) ---

def _leer_texto(entrada: str, ruta: Path, codificacion: str = "utf-8-sig") -> str:
    try:
        return ruta.read_text(encoding=codificacion)
    except (OSError, UnicodeDecodeError) as e:
        raise ErrorLectura(entrada, type(e).__name__) from None


def sha256_archivo(entrada: str, ruta: Path) -> str:
    """SHA-256 de los bytes del archivo, leído en bloques de 64 KiB (solo lectura, modo "rb")."""
    h = hashlib.sha256()
    try:
        with ruta.open("rb") as fh:
            for bloque in iter(lambda: fh.read(65536), b""):
                h.update(bloque)
    except OSError as e:
        raise ErrorLectura(entrada, type(e).__name__) from None
    return h.hexdigest()


def componer_prompt(prompt: str, guia: str, indice: str) -> str:
    """Igual que eval/anotador_llm.prompt_sistema(); lo comprueba tests/test_validar_anotador2.py."""
    return prompt.replace("{guia}", guia.strip()).replace("{indice}", indice.strip())


def ids_indice(texto: str) -> set[int]:
    try:
        return {int(l.split("\t")[0]) for l in texto.splitlines()[1:] if l}
    except ValueError:
        raise ErrorLectura("indice", "formato") from None


def leer_tabla(entrada: str, texto: str) -> tuple[list[dict], dict]:
    """Lectura estricta del TSV que escribe eval/tokenizar.escribir_tsv (siempre 5 columnas).

    Un encabezado distinto del esperado (columnas faltantes, sobrantes, duplicadas o en otro orden)
    lanza ErrorLectura. Las filas defectuosas no se descartan en silencio: se excluyen y se cuentan
    por tipo (línea vacía intermedia, número de columnas, posición no entera, fila repetida).
    """
    lineas = texto.splitlines()
    if not lineas or lineas[0].split("\t") != COLUMNAS_TSV:
        raise ErrorLectura(entrada, "encabezado")
    filas, defectos, vistos = [], Counter(), set()
    for linea in lineas[1:]:
        if not linea.strip():
            defectos["linea_vacia"] += 1
            continue
        campos = linea.split("\t")
        if len(campos) != len(COLUMNAS_TSV):
            defectos["columnas"] += 1
            continue
        fila = dict(zip(COLUMNAS_TSV, campos))
        if not _RE_POS.fullmatch(fila["pos"]):
            defectos["posicion"] += 1
            continue
        fila["pos"] = int(fila["pos"])
        if (fila["caso_id"], fila["pos"]) in vistos:
            defectos["duplicada"] += 1
            continue
        vistos.add((fila["caso_id"], fila["pos"]))
        filas.append(fila)
    return filas, dict(defectos)


def leer_registro(texto: str) -> tuple[list[dict], int]:
    """Registros que son objetos JSON y recuento de líneas ilegibles (JSON inválido o no objeto)."""
    registros, ilegibles = [], 0
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        try:
            r = json.loads(linea)
        except ValueError:
            ilegibles += 1
            continue
        if isinstance(r, dict):
            registros.append(r)
        else:
            ilegibles += 1
    return registros, ilegibles


# --- Reglas ---

def revalidar(etiquetas, posiciones: list[int], ids: set[int]) -> bool:
    """Mismas reglas que eval/anotador_llm.validar(): True si no hay problemas."""
    if not isinstance(etiquetas, list) or not all(isinstance(e, dict) for e in etiquetas):
        return False
    if [e.get("pos") for e in etiquetas] != posiciones:
        return False
    anterior = None
    for e in etiquetas:
        et = e.get("etiqueta")
        if not isinstance(et, str):
            return False
        et = et.strip()
        if not ETIQUETAS_VALIDAS.match(et):
            return False
        if et.startswith("CENAREC-") and int(et.split("-")[1]) not in ids:
            return False
        if et == "+" and not (anterior or "").startswith(("CENAREC-", "+")):
            return False
        anterior = et
    return True


def _bien_formado(r: dict) -> bool:
    return all(isinstance(r.get(k), t) and not (t is int and isinstance(r.get(k), bool))
               for k, t in CAMPOS_REGISTRO.items())


def seleccionar(registros: list[dict], posiciones: dict[str, list[int]], sha_vigente: str,
                ids: set[int]) -> tuple[dict[str, dict], dict]:
    """Elige, por caso, la respuesta que usa el protocolo de eval/anotador_llm.py y clasifica el resto.

    Selección: la ÚLTIMA respuesta sin problemas del caso (= registro_valido), siempre que tenga el
    prompt vigente, sea la única válida con ese prompt y supere revalidar().
    Legítimo (no bloquea): intentos con problemas; respuestas válidas con un prompt anterior seguidas
    de una válida con el vigente ("reemplazos_legitimos").
    Inconsistente (impide el código 0): ver BLOQUEAN_REGISTRO.
    Devuelve la selección (solo para uso interno; nunca se imprime) y recuentos.
    """
    cont = Counter()
    validos: dict[str, list[dict]] = {}
    for r in registros:
        if not _bien_formado(r):
            cont["malformados"] += 1
        elif r["caso_id"] not in posiciones:
            cont["ajenos"] += 1
        elif r["problemas"]:
            cont["intentos_con_problemas"] += 1
        else:
            validos.setdefault(r["caso_id"], []).append(r)
    seleccion: dict[str, dict] = {}
    for caso, pos in posiciones.items():
        vs = validos.get(caso, [])
        vigentes = [r for r in vs if r["sha256_prompt"] == sha_vigente]
        if not vs:
            cont["sin_valida"] += 1
        elif not vigentes:
            cont["sin_vigente"] += 1
        elif len(vigentes) > 1:
            iguales = all(v["etiquetas"] == vigentes[0]["etiquetas"] for v in vigentes[1:])
            cont["duplicados_identicos" if iguales else "duplicados_contradictorios"] += 1
        elif vs[-1] is not vigentes[0]:
            cont["ultima_no_vigente"] += 1
        elif not revalidar(vigentes[0]["etiquetas"], pos, ids):
            cont["no_revalida"] += 1
        else:
            if len(vs) > 1:
                cont["reemplazos_legitimos"] += 1
            seleccion[caso] = vigentes[0]
    return seleccion, dict(cont)


def comparar_tsv(tsv: list[dict], plantilla_por_caso: dict[str, list[dict]],
                 seleccion: dict[str, dict]) -> dict:
    """Compara el TSV con la plantilla (filas) y con la respuesta seleccionada de cada caso
    (posiciones y etiquetas). Solo devuelve recuentos."""
    cont = Counter()
    tsv_por_caso: dict[str, list[dict]] = {}
    for f in tsv:
        tsv_por_caso.setdefault(f["caso_id"], []).append(f)
    cont["casos_ajenos"] = sum(1 for c in tsv_por_caso if c not in plantilla_por_caso)
    for caso, filas_plantilla in plantilla_por_caso.items():
        filas = tsv_por_caso.get(caso, [])
        if not filas:
            cont["casos_faltantes"] += 1
            continue
        alineado = [(f["pos"], f["palabra"]) for f in filas] == [(f["pos"], f["palabra"]) for f in filas_plantilla]
        cont["casos_desalineados"] += not alineado
        en_tsv = {f["pos"]: f["etiqueta"].strip() for f in filas}
        vacias = sum(1 for v in en_tsv.values() if not v)
        invalidas = sum(1 for v in en_tsv.values() if v and not ETIQUETAS_VALIDAS.match(v))
        cont["etiquetas_vacias"] += vacias
        cont["etiquetas_invalidas"] += invalidas
        sel = seleccion.get(caso)
        if sel is None:
            cont["casos_sin_seleccion"] += 1
            continue
        esperado = {e["pos"]: e["etiqueta"].strip() for e in sel["etiquetas"]}
        cont["posiciones_solo_en_tsv"] += len(en_tsv.keys() - esperado.keys())
        cont["posiciones_solo_en_registro"] += len(esperado.keys() - en_tsv.keys())
        distintas = sum(1 for p in en_tsv.keys() & esperado.keys() if en_tsv[p] != esperado[p])
        cont["etiquetas_distintas"] += distintas
        if alineado and en_tsv.keys() == esperado.keys() and not distintas and not vacias and not invalidas:
            cont["casos_completos"] += 1
    return dict(cont)


# --- Saneado de metadatos antes de imprimir ---

def _seguro(valor, patron: re.Pattern) -> str:
    return valor if isinstance(valor, str) and patron.fullmatch(valor) else INESPERADO


def _prefijo_hex(valor) -> str:
    s = _seguro(valor, _RE_HEX)
    return s[:12] if s != INESPERADO else s


def _intento(valor) -> str:
    return str(valor) if isinstance(valor, int) and not isinstance(valor, bool) and 1 <= valor <= 99 else INESPERADO


def _categoria(problema) -> str:
    if isinstance(problema, str):
        for nombre, patron in CATEGORIAS:
            if patron.match(problema):
                return nombre
    return "otra"


# --- Análisis: solo recuentos y valores saneados ---

def analizar(plantilla: list[dict], registros: list[dict], ilegibles: int, tsv: list[dict],
             tsv_defectos: dict, sha_vigente: str, ids: set[int]) -> dict:
    por_caso: dict[str, list[dict]] = {}
    for f in plantilla:
        por_caso.setdefault(f["caso_id"], []).append(f)
    posiciones = {c: [f["pos"] for f in fs] for c, fs in por_caso.items()}
    seleccion, reg = seleccionar(registros, posiciones, sha_vigente, ids)   # la selección no sale de aquí
    tsv_res = comparar_tsv(tsv, por_caso, seleccion)

    fechas = [_seguro(r.get("fecha"), _RE_FECHA) for r in registros if r.get("fecha") is not None]
    fechas_ok = sorted(f for f in fechas if f != INESPERADO)
    uso, uso_desconocidas = Counter(), 0
    for r in registros:
        u = r.get("uso")
        for k, v in (u.items() if isinstance(u, dict) else []):
            if k in CLAVES_USO and isinstance(v, int) and not isinstance(v, bool):
                uso[k] += v
            else:
                uso_desconocidas += 1
    return {
        "plantilla_palabras": len(plantilla), "plantilla_casos": len(por_caso),
        "reg_lineas": len(registros), "reg_ilegibles": ilegibles,
        "registro": reg, "seleccionados": len(seleccion),
        "modelos": dict(Counter(_seguro(r.get("modelo"), _RE_MODELO) for r in registros)),
        "stop": dict(Counter(_seguro(r.get("stop_reason"), _RE_STOP) for r in registros)),
        "prompts": dict(Counter(_prefijo_hex(r.get("sha256_prompt")) for r in registros)),
        "prompts_vigentes": sum(1 for r in registros if r.get("sha256_prompt") == sha_vigente),
        "fecha_primera": fechas_ok[0] if fechas_ok else "—",
        "fecha_ultima": fechas_ok[-1] if fechas_ok else "—",
        "fechas_inesperadas": fechas.count(INESPERADO),
        "intentos": dict(sorted(Counter(_intento(r.get("intento")) for r in registros).items())),
        "problemas": dict(Counter(_categoria(p) for r in registros if isinstance(r.get("problemas"), list)
                                  for p in r["problemas"])),
        "uso": dict(uso), "uso_desconocidas": uso_desconocidas,
        "tsv_filas": len(tsv), "tsv_defectos": dict(tsv_defectos), "tsv": tsv_res,
    }


def codigo(res: dict) -> int:
    """0 = completo y válido; 1 = incompleto o inválido. (El 2 lo devuelve main.)"""
    n = res["plantilla_casos"]
    valido = (n > 0 and res["reg_ilegibles"] == 0
              and all(res["registro"].get(k, 0) == 0 for k in BLOQUEAN_REGISTRO)
              and res["seleccionados"] == n
              and sum(res["tsv_defectos"].values()) == 0
              and all(res["tsv"].get(k, 0) == 0 for k in BLOQUEAN_TSV)
              and res["tsv"].get("casos_completos", 0) == n)
    return 0 if valido else 1


def informe(res: dict, huellas: dict) -> list[str]:
    n, reg, t = res["plantilla_casos"], res["registro"], res["tsv"]
    return [
        "Validación técnica agregada del anotador 2 (solo cifras)",
        "Huellas SHA-256: " + " · ".join(f"{k} {v}" for k, v in huellas.items()),
        f"[Plantilla] palabras {res['plantilla_palabras']} · casos {n}",
        f"[Registro] objetos JSON {res['reg_lineas']} · líneas ilegibles {res['reg_ilegibles']}",
        f"  modelos declarados {res['modelos']} · stop_reason {res['stop']}",
        f"  SHA-256 del prompt (prefijo: registros) {res['prompts']} · con el prompt vigente {res['prompts_vigentes']}",
        f"  fechas: primera {res['fecha_primera']} · última {res['fecha_ultima']} · "
        f"con formato inesperado {res['fechas_inesperadas']}",
        f"  intentos por número {res['intentos']} · problemas por categoría {res['problemas']}",
        f"  uso de tokens {res['uso']} · valores de uso no reconocidos {res['uso_desconocidas']}",
        f"  clasificación {dict(sorted(reg.items()))}",
        f"  casos con respuesta seleccionada {res['seleccionados']} de {n}",
        f"[TSV] filas leídas {res['tsv_filas']} · defectos de formato {dict(sorted(res['tsv_defectos'].items()))}",
        f"  comparación {dict(sorted((k, v) for k, v in t.items() if k != 'casos_completos'))}",
        f"  casos completos {t.get('casos_completos', 0)} de {n}",
        "Resultado: " + ("VÁLIDO (código 0)" if codigo(res) == 0 else "INCOMPLETO O INVÁLIDO (código 1)"),
        "Alcance: completitud técnica; no evalúa la calidad lingüística ni demuestra la independencia.",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = _Argumentos(description="Validación técnica agregada del anotador 2 (solo cifras)")
    ap.add_argument("--plantilla", type=Path, default=ANOT / "plantilla.tsv")
    ap.add_argument("--registro", type=Path, default=ANOT / "anotador2_respuestas.jsonl")
    ap.add_argument("--tsv", type=Path, default=ANOT / "anotador2.tsv")
    ap.add_argument("--prompt", type=Path, default=RAIZ / "eval" / "prompts" / "anotador2_v1.md")
    ap.add_argument("--guia", type=Path, default=RAIZ / "eval" / "guia_anotacion.md")
    ap.add_argument("--indice", type=Path, default=RAIZ / "data" / "lexicon" / "cenarec_indice.tsv")
    a = ap.parse_args(argv)
    try:
        # Prompt, guía e índice con la misma codificación que eval/anotador_llm.py.
        indice = _leer_texto("indice", a.indice, "utf-8")
        prompt = componer_prompt(_leer_texto("prompt", a.prompt, "utf-8"),
                                 _leer_texto("guia", a.guia, "utf-8"), indice)
        sha_vigente = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        ids = ids_indice(indice)
        plantilla, defectos_plantilla = leer_tabla("plantilla", _leer_texto("plantilla", a.plantilla))
        if defectos_plantilla:
            raise ErrorLectura("plantilla", "filas")
        tsv, defectos_tsv = leer_tabla("tsv", _leer_texto("tsv", a.tsv))
        registros, ilegibles = leer_registro(_leer_texto("registro", a.registro, "utf-8"))
        huellas = {n: sha256_archivo(n, r) for n, r in (("plantilla", a.plantilla), ("registro", a.registro),
                                                         ("tsv", a.tsv))}
        huellas["prompt_compuesto"] = sha_vigente
        res = analizar(plantilla, registros, ilegibles, tsv, defectos_tsv, sha_vigente, ids)
    except ErrorLectura as e:
        print(f"ERROR de lectura: {e.tipo} en {e.entrada}")
        return 2
    except Exception as e:  # noqa: BLE001  el mensaje podría contener contenido: se suprime
        print(f"ERROR: {type(e).__name__} (mensaje suprimido)")
        return 2
    print("\n".join(informe(res, huellas)))
    return codigo(res)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
