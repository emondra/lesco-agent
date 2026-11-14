#!/usr/bin/env python3
"""
Registrador de evidencia de pruebas de LESCO-Agent (versión 1.2.1).

Es un instrumento de registro: no forma parte del sistema que se evalúa. Solo biblioteca estándar.

Registrar una ejecución (solo suites unittest locales autorizadas):
    python evidencia/registrar_pruebas.py registrar --suite servidor --etiqueta etapa1-verificacion \
        --tipo verificacion_posterior \
        --verifica "Etapa 1: ejecuciones del 2026-11-13 que solo constan en la sesión"

Verificar un registro (solo lectura; no modifica nada):
    python evidencia/registrar_pruebas.py verificar evidencia/privado/<registro>/original
    python evidencia/registrar_pruebas.py verificar evidencia/privado/<registro>/candidata [--codigo]

Publicar una candidata revisada (solo con autorización explícita del autor):
    python evidencia/registrar_pruebas.py aprobar <registro> --autorizacion "<texto y fecha>"

Estructura de un registro:
    evidencia/privado/<AAAAMMDD-HHMMSS>_<etiqueta>/      (ignorado por git; nunca se publica)
        original/    inicio.json, cambios.patch, fuentes/, stdout.txt, stderr.txt, contexto.json, SHA256SUMS
        candidata/   los mismos archivos revisados; los redactados terminan en .redactado;
                     PUBLICACION.json (estado PENDIENTE_REVISION_HUMANA) y SHA256SUMS
    evidencia/INDICE.md          una fila por ejecución, también las fallidas (solo se agregan filas)
    evidencia/pruebas/<registro>/   copia de la candidata, solo tras `aprobar`
    evidencia/APROBACIONES.md    una fila por aprobación (solo se agregan filas)

Estados separados:
    resultado_suite         OK | FALLÓ | TIEMPO_AGOTADO | NO_ARRANCÓ | NO_EJECUTADA  (no afecta a la integridad)
    integridad_operativa    CONFORME | NO_CONFORME (cambió código, archivos protegidos o git status durante
                            la ejecución) | INCOMPLETO (falló el propio registrador)
    integridad criptográfica  la determina solo `verificar` recalculando los SHA-256; no se guarda en el registro
    publicación             PENDIENTE_REVISION_HUMANA en el registro; APROBADO solo si existe la fila en
                            APROBACIONES.md con el mismo sello

Controles de ejecución: (1) solo tres suites unittest locales, fijas en el código; (2) entorno mínimo sin
credenciales; (3) una guardia Python PARCIAL de red. Ninguno es un aislamiento completo de red: la guardia
solo afecta a procesos Python que la cargan, y no cubre programas que no sean Python, código nativo o ctypes,
ni procesos Python lanzados con -I, -E o -S. La garantía principal es la lista cerrada de suites, cuyo código
se revisó.

Otras garantías:
- Nunca sobrescribe: carpetas y archivos se crean en modo exclusivo; los índices solo crecen.
- No guarda variables de entorno, la ruta del intérprete, el usuario ni el nombre del equipo.
- No abre trazas/, resultados/, eval/ ni data/: solo compara tamaño y fecha de sus archivos.
- Revisa todos los archivos del registro (salidas, patch, fuentes, metadatos y parámetros) y redacta en la
  candidata lo que detecta, sin copiar lo encontrado. La detección es heurística: no sustituye la revisión humana.
- Una ejecución con pruebas fallidas produce evidencia íntegra y verificable.
"""

import argparse
import hashlib
import json
import locale
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

VERSION = "1.2.1"
RAIZ = Path(__file__).resolve().parent.parent
DIR_PRIVADO = RAIZ / "evidencia" / "privado"        # ignorado por git: originales y candidatas
DIR_PUBLICO = RAIZ / "evidencia" / "pruebas"         # solo lo que el autor aprueba (subcomando aprobar)
INDICE = RAIZ / "evidencia" / "INDICE.md"             # todas las ejecuciones, también las fallidas
APROBACIONES = RAIZ / "evidencia" / "APROBACIONES.md"
PROPIOS = ("evidencia/privado/", "evidencia/pruebas/", "evidencia/INDICE.md", "evidencia/APROBACIONES.md")
ESTADO_PUBLICACION = "PENDIENTE_REVISION_HUMANA"
PATRON_REGISTRO = re.compile(r"^\d{8}-\d{6}_[a-z0-9][a-z0-9-]{0,40}$")
PATRON_ETIQUETA = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
TIPOS = ("ejecucion", "verificacion_posterior")

# Únicos comandos que puede ejecutar el registrador: unittest local. No acepta otro comando.
SUITES = {
    "completa": ["-m", "unittest", "discover", "-s", "tests", "-v"],
    "servidor": ["-m", "unittest", "tests.test_servidor_mcp", "-v"],
    "registrador": ["-m", "unittest", "discover", "-s", "evidencia", "-p", "test_*.py", "-v"],
}
# Entorno mínimo del proceso de pruebas: solo estos nombres pasan (ninguna clave, ningún token).
ENTORNO_PERMITIDO = ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "PATH", "PATHEXT", "COMSPEC",
                     "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL",
                     "USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH")   # no son credenciales; no se registran

# Código cuyo SHA-256 se registra y que se copia a fuentes/ si no tiene seguimiento.
CODIGO = ("agente/", "mcp_server/", "tests/", "skill/", "politica/", "evidencia/registrar_pruebas.py",
          "evidencia/test_registrar_pruebas.py", "reproducir.py", ".gitattributes", ".gitignore")
CODIGO_EVAL = re.compile(r"^eval/[^/]+\.py$")              # scripts de eval/, nunca datos ni anotaciones
EXCLUIR = re.compile(r"(^|/)(__pycache__|\.env[^/]*)(/|$)")
PROTEGIDOS = ("trazas", "resultados", "eval", "data")       # solo metadatos, nunca contenido

GUARDIA_RED = '''\
# Defensa PARCIAL instalada por evidencia/registrar_pruebas.py. No es un aislamiento de red.
# Reemplaza las funciones de conexión del módulo socket en los procesos Python que la cargan
# (el proceso de pruebas y los subprocesos Python que heredan PYTHONPATH). No cubre programas
# que no sean Python, código nativo o ctypes, ni procesos Python lanzados con -I, -E o -S.
import socket


def _bloqueado(*args, **kwargs):
    raise PermissionError("red bloqueada por el registrador de evidencia")


socket.socket.connect = _bloqueado
socket.socket.connect_ex = _bloqueado
socket.socket.sendto = _bloqueado
socket.create_connection = _bloqueado
socket.getaddrinfo = _bloqueado
'''

CATEGORIAS = {
    "patron_de_clave": [r"sk-ant-[A-Za-z0-9_-]{8,}", r"ANTHROPIC_API_KEY\s*[=:]\s*\S+",
                        r"(?i)x-api-key[\"']?\s*[:=]\s*[\"']?sk-"],
    "id_workspace": [r"wrkspc_[A-Za-z0-9]{10,}"],
    "correo": [r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"],
}
# Un parche binario de git real (`git diff --binary`): la línea "GIT binary patch" sola, seguida de
# "literal <n>" o "delta <n>". Mencionar la frase en un texto o en código no basta para coincidir.
PARCHE_BINARIO_GIT = re.compile(rb"(?m)^GIT binary patch\r?\n(?:literal|delta) \d+\r?$")


# ---------------------------------------------------------------------------- utilidades
def ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def sha256_codigo(ruta: Path) -> str:
    """SHA-256 del contenido con finales de línea normalizados a LF: igual en cualquier clon."""
    return sha256(ruta.read_bytes().replace(b"\r\n", b"\n"))


def crear(ruta: Path, datos: bytes) -> None:
    """Crea un archivo nuevo; falla si ya existe (nunca sobrescribe)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("xb") as fh:
        fh.write(datos)


def json_bytes(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def git(*args: str) -> bytes:
    r = subprocess.run(["git", "--no-optional-locks", "-c", "core.quotepath=false", *args], cwd=RAIZ,
                       stdin=subprocess.DEVNULL, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} terminó con código {r.returncode}")
    return r.stdout


def es_codigo(ruta: str) -> bool:
    if EXCLUIR.search(ruta):
        return False
    return ruta.startswith(CODIGO) or bool(CODIGO_EVAL.match(ruta))


def escribir_sumas(carpeta: Path) -> str:
    """Escribe SHA256SUMS (formato de `sha256sum -c`) y devuelve su propio SHA-256 (el sello)."""
    sumas = "".join(f"{sha256_archivo(p)}  {p.relative_to(carpeta).as_posix()}\n"
                    for p in sorted(x for x in carpeta.rglob("*") if x.is_file()))
    crear(carpeta / "SHA256SUMS", sumas.encode("utf-8"))
    return sha256_archivo(carpeta / "SHA256SUMS")


def una_linea(texto: str) -> str:
    """Texto seguro para una celda de tabla Markdown."""
    return " ".join(texto.split()).replace("|", "/")


# ---------------------------------------------------------------------------- estado del repositorio
def estado_git() -> list[tuple[str, str]]:
    """Entradas de `git status` (con lo no versionado), sin lo que escribe este instrumento."""
    partes = git("status", "--porcelain=v1", "-z", "--untracked-files=all").decode("utf-8", "replace").split("\0")
    entradas, i = [], 0
    while i < len(partes):
        p, i = partes[i], i + 1
        if not p:
            continue
        xy, ruta = p[:2], p[3:]
        if xy[0] in "RC":
            i += 1                                   # con -z, el nombre de origen va en el campo siguiente
        if not ruta.startswith(PROPIOS):
            entradas.append((xy, ruta))
    return sorted(entradas)


def vista_publicable(entradas: list[tuple[str, str]]) -> list[str]:
    """Versionados y código con su nombre; el resto de lo no versionado, solo como recuento."""
    vista, otros = [], {}
    for xy, ruta in entradas:
        if xy != "??" or es_codigo(ruta):
            vista.append(f"{xy} {ruta}")
        else:
            carpeta = ruta.split("/")[0] + "/" if "/" in ruta else "(raíz)"
            otros[carpeta] = otros.get(carpeta, 0) + 1
    return vista + [f"?? {c} ({n} archivos sin seguimiento; nombres no publicados)"
                    for c, n in sorted(otros.items())]


def metadatos_protegidos() -> dict[str, list[int]]:
    """Tamaño y fecha de modificación de cada archivo protegido. No abre ningún archivo."""
    datos = {}
    for nombre in PROTEGIDOS:
        base = RAIZ / nombre
        if base.is_dir():
            for p in base.rglob("*"):
                rel = p.relative_to(RAIZ).as_posix()
                if not EXCLUIR.search(rel) and p.is_file():
                    st = p.stat()
                    datos[rel] = [st.st_size, st.st_mtime_ns]
    return datos


def codigo_actual() -> tuple[dict[str, str | None], list[str]]:
    versionados = git("ls-files", "-z").decode("utf-8").split("\0")
    sin_seguimiento = git("ls-files", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")
    nuevos = sorted(r for r in sin_seguimiento if r and es_codigo(r))
    hashes = {}
    for r in sorted({*(r for r in versionados if r and es_codigo(r)), *nuevos}):
        p = RAIZ / r
        hashes[r] = sha256_codigo(p) if p.is_file() else None      # None: borrado del árbol de trabajo
    return hashes, nuevos


def instantanea() -> dict:
    codigo, nuevos = codigo_actual()
    return {"git": estado_git(), "protegidos": metadatos_protegidos(), "codigo": codigo, "nuevos": nuevos}


def evaluar_integridad(antes: dict, despues: dict) -> dict:
    def difieren(a: dict, b: dict) -> list[str]:
        return sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))

    codigo = difieren(antes["codigo"], despues["codigo"])
    protegidos = difieren(antes["protegidos"], despues["protegidos"])
    motivos = ([f"el código cambió durante la ejecución: {', '.join(codigo)}"] if codigo else []) + \
              ([f"archivos protegidos cambiaron: {', '.join(protegidos)}"] if protegidos else []) + \
              (["git status cambió durante la ejecución"] if antes["git"] != despues["git"] else [])
    return {"codigo_cambiado": codigo, "protegidos_cambiados": protegidos,
            "git_status_igual": antes["git"] == despues["git"], "motivos_no_conformidad": motivos}


def entorno() -> dict:
    return {"python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "plataforma": platform.platform(),
            "os_name": os.name,
            "codificacion_preferida": locale.getpreferredencoding(False)}


def resumen_literal(*bloques: bytes) -> list[str]:
    texto = b"\n".join(bloques).decode("utf-8", "replace")
    return [l.strip() for l in texto.splitlines()
            if re.match(r"^\s*(Ran \d+ tests? in \S+|OK( \(.*\))?|FAILED \(.*\))\s*$", l)]


# ---------------------------------------------------------------------------- ejecución controlada
def entorno_minimo(dir_guardia: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() in ENTORNO_PERMITIDO}
    env["PYTHONPATH"] = dir_guardia          # carga sitecustomize.py (la guardia parcial) al arrancar Python
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"        # salida de texto inspeccionable; queda registrado en contexto.json
    return env


def ejecutar_suite(suite: str, tiempo_max: int) -> dict:
    """Ejecuta una suite autorizada con entorno mínimo y guardia parcial de red. Nunca un comando arbitrario."""
    comando = [sys.executable, *SUITES[suite]]
    with tempfile.TemporaryDirectory(prefix="lesco_guardia_") as tmp:      # fuera del repositorio
        Path(tmp, "sitecustomize.py").write_text(GUARDIA_RED, encoding="utf-8")
        t0 = time.monotonic()
        try:
            r = subprocess.run(comando, cwd=RAIZ, env=entorno_minimo(tmp), stdin=subprocess.DEVNULL,
                               capture_output=True, timeout=tiempo_max)
            salida, error, codigo = r.stdout, r.stderr, r.returncode
            resultado, detalle = ("OK" if codigo == 0 else "FALLÓ"), None
        except subprocess.TimeoutExpired as e:
            salida, error, codigo = e.stdout or b"", e.stderr or b"", None
            resultado, detalle = "TIEMPO_AGOTADO", f"superó {tiempo_max} s"
        except OSError as e:
            salida, error, codigo = b"", b"", None
            resultado, detalle = "NO_ARRANCÓ", type(e).__name__
        duracion = round(time.monotonic() - t0, 3)
    return {"stdout": salida, "stderr": error,
            "meta": {"fecha_fin": ahora(), "duracion_s": duracion, "codigo_salida": codigo,
                     "resultado_suite": resultado, "detalle_error": detalle}}


# ---------------------------------------------------------------------------- privacidad y candidata
def patrones_sensibles() -> dict[str, list[re.Pattern]]:
    pats = {k: [re.compile(p) for p in v] for k, v in CATEGORIAS.items()}
    hogar = Path.home()                       # solo en memoria; nunca se registra
    variantes = sorted({str(hogar), hogar.as_posix(), str(hogar).replace("\\", "\\\\")}, key=len, reverse=True)
    pats["ruta_personal"] = [re.compile(re.escape(v), re.I) for v in variantes] + [
        re.compile(rf"(?i)[\\/]+(users|home)[\\/]+{re.escape(hogar.name)}\b")]
    privados = DIR_PRIVADO / "terminos_privados.txt"   # opcional, lo escribe el autor; nunca se publica
    if privados.is_file():
        pats["termino_privado"] = [re.compile(re.escape(t.strip()), re.I)
                                   for t in privados.read_text(encoding="utf-8").splitlines() if t.strip()]
    return pats


def inspeccionable(datos: bytes) -> bool:
    """Solo el texto UTF-8 sin bytes nulos ni parches binarios de git reales se puede revisar con seguridad."""
    if b"\x00" in datos or PARCHE_BINARIO_GIT.search(datos):
        return False
    try:
        datos.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def revisar(datos: bytes, pats: dict) -> tuple[bytes, dict[str, int]]:
    """Versión redactada y número de coincidencias por categoría (nunca el texto encontrado)."""
    texto, conteo = datos.decode("utf-8", "surrogateescape"), {}
    for cat, lista in pats.items():
        for p in lista:
            texto, n = p.subn(f"[REDACTADO:{cat}]", texto)
            if n:
                conteo[cat] = conteo.get(cat, 0) + n
    return texto.encode("utf-8", "surrogateescape"), conteo


def preparar_candidata(base: Path, original: Path, sello_original: str) -> tuple[str, bool]:
    """Revisa TODOS los archivos del original (stdout, stderr, patch, fuentes/, inicio.json y contexto.json,
    que contienen los metadatos y los parámetros) y escribe la candidata a publicar."""
    candidata, pats, archivos, total = base / "candidata", patrones_sensibles(), {}, 0
    for p in sorted(x for x in original.rglob("*") if x.is_file() and x.name != "SHA256SUMS"):
        rel, datos = p.relative_to(original).as_posix(), p.read_bytes()
        if not inspeccionable(datos):             # conservador: no se publica lo que no se puede revisar
            archivos[rel] = {"publicado_como": None, "excluido": True, "identico_al_original": False,
                             "motivo": "contenido binario o no UTF-8: no inspeccionable con seguridad",
                             "sha256_original": sha256(datos), "sha256_publicado": None, "redacciones": {}}
            continue
        publicado, conteo = revisar(datos, pats)
        identico = publicado == datos
        rel_pub = rel if identico else f"{rel}.redactado"
        crear(candidata / rel_pub, publicado)
        total += sum(conteo.values())
        archivos[rel] = {"publicado_como": rel_pub, "identico_al_original": identico,
                         "sha256_original": sha256(datos), "sha256_publicado": sha256(publicado),
                         "redacciones": conteo, "excluido": False}
    redactados = sorted(r for r, d in archivos.items() if not d["excluido"] and not d["identico_al_original"])
    excluidos = sorted(r for r, d in archivos.items() if d["excluido"])
    crear(candidata / "PUBLICACION.json", json_bytes({
        "estado_publicacion": ESTADO_PUBLICACION,
        "contiene_redacciones": bool(redactados),
        "archivos_redactados": redactados,
        "aviso_redaccion": ("Los archivos terminados en .redactado NO son idénticos al original privado: "
                            "no reproducen el código ni la salida exactos. Su relación con el original "
                            "consta en los dos SHA-256 de cada archivo.") if redactados else None,
        "contiene_exclusiones": bool(excluidos),
        "archivos_excluidos": excluidos,
        "aviso_exclusion": ("Los archivos excluidos no se pudieron inspeccionar con seguridad (binarios o no "
                            "UTF-8): solo existen en el original privado; su SHA-256 consta aquí.")
                           if excluidos else None,
        "nota": ("Ningún archivo de este registro está autorizado para publicarse hasta que el autor lo "
                 "apruebe; la aprobación consta solo en evidencia/APROBACIONES.md."),
        "revision_automatica": "detecta y redacta patrones conocidos; no sustituye la revisión humana",
        "hallazgos_total": total, "sello_original": sello_original, "archivos": archivos}))
    return escribir_sumas(candidata), bool(redactados or excluidos)


def agregar_indice(nombre: str, contexto: dict, sello_original: str, sello: str, redactada: bool | None) -> None:
    nuevo = not INDICE.exists()
    with INDICE.open("a", encoding="utf-8", newline="\n") as fh:
        if nuevo:
            fh.write("# Índice de registros de pruebas\n\n"
                     "Generado por `evidencia/registrar_pruebas.py`. Incluye TODAS las ejecuciones, también las "
                     "fallidas. Solo se agregan filas. La integridad criptográfica la determina "
                     "`registrar_pruebas.py verificar`; el estado efectivo de publicación consta en "
                     "`evidencia/APROBACIONES.md`.\n\n"
                     "| Registro | Tipo | Inicio | Suite | Resultado de la suite | Integridad operativa | "
                     "Redactada o excluida | Publicación | Sello del original | Sello de la candidata |\n"
                     "|---|---|---|---|---|---|---|---|---|---|\n")
        texto_redactada = "—" if redactada is None else ("sí" if redactada else "no")
        fh.write(f"| {nombre} | {contexto['tipo']} | {contexto.get('fecha_inicio', '—')} | "
                 f"{contexto.get('suite', '—')} | {contexto.get('resultado_suite', '—')} | "
                 f"{contexto.get('integridad_operativa', '—')} | {texto_redactada} | "
                 f"{ESTADO_PUBLICACION} | `{sello_original}` | {'—' if sello == '—' else f'`{sello}`'} |\n")


# ---------------------------------------------------------------------------- registrar
def registrar(a) -> int:
    if not PATRON_ETIQUETA.match(a.etiqueta):
        sys.exit("--etiqueta: minúsculas, dígitos y '-' (máx. 41 caracteres).")
    if a.tipo == "verificacion_posterior" and not a.verifica:
        sys.exit("--tipo verificacion_posterior exige --verifica (qué ejecuciones anteriores se verifican).")
    if a.suite not in SUITES:
        sys.exit(f"Suite no autorizada. Autorizadas: {', '.join(sorted(SUITES))}.")
    inicio = datetime.now().astimezone()
    nombre = f"{inicio:%Y%m%d-%H%M%S}_{a.etiqueta}"
    base, original = DIR_PRIVADO / nombre, DIR_PRIVADO / nombre / "original"
    if (DIR_PUBLICO / nombre).exists():
        sys.exit(f"Ya existe un registro publicado {nombre}: no se sobrescribe.")
    DIR_PRIVADO.mkdir(parents=True, exist_ok=True)
    try:
        base.mkdir()                                            # exclusivo: nunca reutiliza una carpeta
    except FileExistsError:
        sys.exit(f"Ya existe {nombre}: no se sobrescribe un registro.")

    contexto = {
        "instrumento": {"nombre": "evidencia/registrar_pruebas.py", "version": VERSION},
        "registro": nombre, "etiqueta": a.etiqueta, "tipo": a.tipo, "verifica": a.verifica,
        "advertencia": ("Este registro contiene solo la ejecución hecha en las fechas indicadas. "
                        "No contiene ni reconstruye datos de ejecuciones anteriores."),
        "estado_publicacion": ESTADO_PUBLICACION,
        "integridad_criptografica": "la determina `registrar_pruebas.py verificar`; no se guarda en el registro",
        "fecha_inicio": inicio.isoformat(timespec="seconds"),
        "suite": a.suite, "comando": ["python", *SUITES[a.suite]], "directorio": ".", "entorno": entorno(),
        "control_de_ejecucion": {
            "suites_autorizadas": sorted(SUITES), "entorno_permitido": list(ENTORNO_PERMITIDO),
            "guardia_red_python": {
                "activa": True, "alcance": "parcial",
                "cubre": ("sockets creados desde Python en el proceso de pruebas y en subprocesos Python "
                          "que heredan PYTHONPATH"),
                "no_cubre": ["programas que no son Python", "código nativo o ctypes",
                             "Python lanzado con -I, -E o -S"],
                "sha256": sha256(GUARDIA_RED.encode("utf-8"))},
            "codificacion_salida": "utf-8 (PYTHONIOENCODING)"},
        "fuentes_alcance": "solo código según CODIGO y CODIGO_EVAL; el resto de lo no versionado se excluye",
    }
    paso = "estado previo"
    try:
        antes = instantanea()
        contexto["git"] = {"head": git("rev-parse", "HEAD").decode().strip(),
                           "rama": git("rev-parse", "--abbrev-ref", "HEAD").decode().strip(),
                           "status_antes": vista_publicable(antes["git"]),
                           "diff_stat": git("diff", "HEAD", "--stat").decode("utf-8", "replace").splitlines()}
        contexto["codigo_sha256_lf_antes"] = antes["codigo"]
        contexto["fuentes_sin_seguimiento"] = antes["nuevos"]
        crear(original / "inicio.json", json_bytes(contexto))

        paso = "patch y fuentes"
        crear(original / "cambios.patch", git("diff", "HEAD", "--binary", "--no-color", "--no-ext-diff"))
        for r in antes["nuevos"]:
            crear(original / "fuentes" / r, (RAIZ / r).read_bytes())

        paso = "ejecución"
        res = ejecutar_suite(a.suite, a.tiempo_max)
        contexto.update(res["meta"])
        crear(original / "stdout.txt", res["stdout"])
        crear(original / "stderr.txt", res["stderr"])

        paso = "comprobaciones posteriores"
        despues = instantanea()
        integridad = evaluar_integridad(antes, despues)
        contexto.update({
            "resumen_literal": resumen_literal(res["stdout"], res["stderr"]),
            "sha256": {"stdout.txt": sha256(res["stdout"]), "stderr.txt": sha256(res["stderr"]),
                       "cambios.patch": sha256_archivo(original / "cambios.patch")},
            "codigo_sha256_lf_despues": despues["codigo"],
            "integridad": {**integridad, "status_despues": vista_publicable(despues["git"]),
                           "protegidos_revisados": list(PROTEGIDOS)},
            "integridad_operativa": "NO_CONFORME" if integridad["motivos_no_conformidad"] else "CONFORME",
        })
    except Exception as e:                                     # el registro queda incompleto, no se pierde
        contexto.setdefault("resultado_suite", "NO_EJECUTADA")
        contexto["integridad_operativa"] = "INCOMPLETO"
        contexto["error_del_registrador"] = {"paso": paso, "tipo": type(e).__name__}

    crear(original / "contexto.json", json_bytes(contexto))
    sello_original = escribir_sumas(original)
    try:
        sello, redactada = preparar_candidata(base, original, sello_original)
    except Exception as e:                                     # el original ya está sellado
        print(f"No se pudo preparar la candidata ({type(e).__name__}); el original queda en evidencia/privado/.")
        sello, redactada = "—", None
    agregar_indice(nombre, contexto, sello_original, sello, redactada)

    print(f"Registro privado: evidencia/privado/{nombre}/ (original y candidata)")
    print(f"Resultado de la suite: {contexto.get('resultado_suite')} (no afecta a la integridad de la evidencia)")
    print(f"Integridad operativa: {contexto.get('integridad_operativa')} · publicación: {ESTADO_PUBLICACION}")
    print(f"Resumen literal: {' / '.join(contexto.get('resumen_literal', [])) or '—'}")
    pub = cargar_json(base / "candidata", "PUBLICACION.json") if sello != "—" else {}
    if pub.get("contiene_redacciones"):
        print(f"La candidata contiene archivos redactados (.redactado): {', '.join(pub['archivos_redactados'])}. "
              "Revisar antes de cualquier aprobación.")
    if pub.get("contiene_exclusiones"):
        print(f"La candidata excluye archivos no inspeccionables (solo en el original privado): "
              f"{', '.join(pub['archivos_excluidos'])}.")
    if pub and not pub.get("contiene_redacciones") and not pub.get("contiene_exclusiones"):
        print("La candidata no contiene redacciones ni exclusiones.")
    if contexto.get("integridad_operativa") != "CONFORME":
        return 4                                                # evidencia no válida
    if sello == "—":
        return 5                                                # original íntegro; sin candidata publicable
    return 0 if contexto.get("resultado_suite") == "OK" else 1  # 1 = la suite falló; la evidencia es válida


# ---------------------------------------------------------------------------- verificar (solo lectura)
def cargar_json(carpeta: Path, nombre: str) -> dict:
    """Lee nombre o nombre.redactado (la redacción conserva la sintaxis JSON)."""
    for candidato in (carpeta / nombre, carpeta / f"{nombre}.redactado"):
        if candidato.is_file():
            return json.loads(candidato.read_text(encoding="utf-8", errors="surrogateescape"))
    return {}


def verificar(carpeta: Path, con_codigo: bool) -> int:
    carpeta = carpeta.resolve()
    sumas = carpeta / "SHA256SUMS"
    if not sumas.is_file():
        print("No existe SHA256SUMS en la carpeta indicada.")
        return 2
    fallos_hash, listados = 0, set()
    for linea in sumas.read_text(encoding="utf-8").splitlines():
        esperado, _, rel = linea.partition("  ")
        p = (carpeta / rel).resolve()
        if carpeta not in p.parents:
            print(f"RUTA NO VÁLIDA {rel}")
            fallos_hash += 1
            continue
        listados.add(rel)
        real = sha256_archivo(p) if p.is_file() else None
        marca = "OK" if real == esperado else ("FALTA" if real is None else "DISTINTO")
        fallos_hash += marca != "OK"
        print(f"{marca:10} {rel}")
    for p in sorted(carpeta.rglob("*")):
        rel = p.relative_to(carpeta).as_posix()
        if p.is_file() and rel != "SHA256SUMS" and rel not in listados:
            print(f"NO LISTADO {rel}")
            fallos_hash += 1

    sello = sha256_archivo(sumas)
    nombre = carpeta.parent.name if carpeta.name in ("original", "candidata") else carpeta.name
    publicacion = cargar_json(carpeta, "PUBLICACION.json")
    filas = ([l for l in INDICE.read_text(encoding="utf-8").splitlines() if l.startswith(f"| {nombre} |")]
             if INDICE.exists() else [])
    celdas = [c.strip() for c in filas[0].strip().strip("|").split("|")] if len(filas) == 1 else []
    aprobado = False
    if publicacion:                                             # candidata o copia publicada
        sello_ok = len(celdas) >= 2 and celdas[-1] == f"`{sello}`"
        print(f"{'OK' if sello_ok else 'DISTINTO':10} sello en evidencia/INDICE.md")
        aprobado = APROBACIONES.exists() and any(
            l.startswith(f"| {nombre} |") and f"`{sello}`" in l
            for l in APROBACIONES.read_text(encoding="utf-8").splitlines())
        for rel, d in publicacion.get("archivos", {}).items():
            if d.get("excluido"):                     # informativo: una exclusión no es corrupción
                print(f"{'EXCLUIDO':10} {rel} (no inspeccionable; solo en el original privado)")
                continue
            p = carpeta / d["publicado_como"]
            coherente = d["identico_al_original"] == (d["sha256_publicado"] == d["sha256_original"])
            ok = p.is_file() and sha256_archivo(p) == d["sha256_publicado"] and coherente
            nota = "" if d["identico_al_original"] else "; REDACTADO, no idéntico al original privado"
            print(f"{'OK' if ok else 'DISTINTO':10} {d['publicado_como']} (según PUBLICACION.json{nota})")
            fallos_hash += not ok
    else:                       # original privado: su sello está en INDICE.md y no depende de la candidata
        sello_ok = len(celdas) >= 2 and celdas[-2] == f"`{sello}`"
        print(f"{'OK' if sello_ok else 'DISTINTO':10} sello del original en evidencia/INDICE.md")
        pub = cargar_json(carpeta.parent / "candidata", "PUBLICACION.json")
        if pub and pub.get("sello_original") != sello:          # si hay candidata, también debe coincidir
            print(f"{'DISTINTO':10} sello del original según candidata/PUBLICACION.json")
            sello_ok = False
        for nombre_archivo, h in cargar_json(carpeta, "contexto.json").get("sha256", {}).items():
            ok = (carpeta / nombre_archivo).is_file() and sha256_archivo(carpeta / nombre_archivo) == h
            print(f"{'OK' if ok else 'DISTINTO':10} {nombre_archivo} (según contexto.json)")
            fallos_hash += not ok

    contexto = cargar_json(carpeta, "contexto.json")
    codigo_ok = True
    if con_codigo:
        redactadas = set(publicacion.get("archivos_redactados", []))
        for rel, esperado in contexto.get("codigo_sha256_lf_antes", {}).items():
            p = (RAIZ / rel).resolve()
            real = sha256_codigo(p) if RAIZ in p.parents and p.is_file() else None
            marca = "OK" if real == esperado else ("FALTA" if real is None else "DIFIERE")
            codigo_ok &= marca == "OK"
            extra = " · su copia en fuentes/ está redactada: no reconstruible desde la evidencia pública" \
                if f"fuentes/{rel}" in redactadas else ""
            print(f"{marca:10} código actual: {rel}{extra}")

    criptografica = fallos_hash == 0 and sello_ok
    operativa = contexto.get("integridad_operativa", "—")
    print(f"Integridad criptográfica: {'VERIFICADA' if criptografica else 'NO VERIFICADA'}")
    print(f"Integridad operativa:     {operativa}")
    for motivo in contexto.get("integridad", {}).get("motivos_no_conformidad", []):
        print(f"                          {motivo}")
    print(f"Resultado de la suite:    {contexto.get('resultado_suite', '—')} (informativo)")
    print(f"Publicación:              {'APROBADO' if aprobado else ESTADO_PUBLICACION}")
    if publicacion.get("contiene_redacciones"):
        print("Contiene archivos redactados: no son idénticos al original privado.")
    if publicacion.get("contiene_exclusiones"):
        print("Contiene archivos excluidos por no ser inspeccionables: solo existen en el original privado.")
    if con_codigo:
        print(f"Código del árbol actual:  {'COINCIDE' if codigo_ok else 'DIFIERE'} con el registrado")
    integra = criptografica and operativa == "CONFORME"
    print("EVIDENCIA ÍNTEGRA" if integra else "EVIDENCIA NO ÍNTEGRA")
    return 0 if integra and (codigo_ok or not con_codigo) else 1


# ---------------------------------------------------------------------------- aprobar (autorización del autor)
def aprobar(nombre: str, autorizacion: str) -> int:
    """Copia la candidata revisada a evidencia/pruebas/ y deja constancia en APROBACIONES.md."""
    if not PATRON_REGISTRO.match(nombre):
        sys.exit("Nombre de registro inválido.")
    if not autorizacion.strip():
        sys.exit("La autorización no puede estar vacía.")
    candidata, destino = DIR_PRIVADO / nombre / "candidata", DIR_PUBLICO / nombre
    if destino.exists():
        sys.exit(f"{nombre} ya está publicado: no se sobrescribe.")
    if verificar(candidata, False) != 0:      # cripto VERIFICADA + operativa CONFORME; la suite puede haber fallado
        print("La evidencia no es íntegra: no se publica.")
        return 1
    pats = patrones_sensibles()
    restos = {p.relative_to(candidata).as_posix(): c for p in candidata.rglob("*") if p.is_file()
              for c in [revisar(p.read_bytes(), pats)[1]] if c}
    restos_autorizacion = revisar(autorizacion.encode("utf-8"), pats)[1]
    if restos or restos_autorizacion:
        print(f"Quedan coincidencias sensibles (por categoría): {restos or restos_autorizacion}. No se publica.")
        return 1
    for p in sorted(x for x in candidata.rglob("*") if x.is_file()):
        crear(destino / p.relative_to(candidata), p.read_bytes())
    if verificar(destino, False) != 0:
        print("La copia publicada no coincide con la candidata.")
        return 1
    sello = sha256_archivo(destino / "SHA256SUMS")
    contexto = cargar_json(destino, "contexto.json")
    pub = cargar_json(destino, "PUBLICACION.json")
    redactada = bool(pub.get("contiene_redacciones") or pub.get("contiene_exclusiones"))
    nuevo = not APROBACIONES.exists()
    with APROBACIONES.open("a", encoding="utf-8", newline="\n") as fh:
        if nuevo:
            fh.write("# Aprobaciones de publicación\n\nSolo se agregan filas. Un registro está APROBADO solo si "
                     "aparece aquí con el mismo sello que en INDICE.md.\n\n"
                     "| Registro | Fecha de aprobación | Resultado de la suite | Redactada o excluida | Autorización | Sello |\n"
                     "|---|---|---|---|---|---|\n")
        fh.write(f"| {nombre} | {ahora()} | {contexto.get('resultado_suite', '—')} | "
                 f"{'sí' if redactada else 'no'} | {una_linea(autorizacion)} | `{sello}` |\n")
    print(f"Publicado en evidencia/pruebas/{nombre}/ (falta commit, que también requiere autorización).")
    return 0


# ---------------------------------------------------------------------------- línea de comandos
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Registrador de evidencia de pruebas (LESCO-Agent)")
    sub = ap.add_subparsers(dest="accion", required=True)
    r = sub.add_parser("registrar", help="ejecuta una suite autorizada y guarda un registro privado")
    r.add_argument("--suite", required=True, choices=sorted(SUITES))
    r.add_argument("--etiqueta", required=True)
    r.add_argument("--tipo", required=True, choices=TIPOS)
    r.add_argument("--verifica", default=None, help="qué ejecuciones anteriores se verifican (texto)")
    r.add_argument("--tiempo-max", type=int, default=1800, help="segundos (por defecto 1800)")
    p = sub.add_parser("aprobar", help="publica una candidata revisada (requiere autorización del autor)")
    p.add_argument("registro")
    p.add_argument("--autorizacion", required=True, help="texto con la autorización y su fecha")
    v = sub.add_parser("verificar", help="recalcula los SHA-256 de un registro (solo lectura)")
    v.add_argument("carpeta", type=Path)
    v.add_argument("--codigo", action="store_true", help="compara además el código del árbol de trabajo")
    a = ap.parse_args()          # cualquier argumento extra es un error de argparse: no hay comando libre
    if a.accion == "registrar":
        return registrar(a)
    if a.accion == "aprobar":
        return aprobar(a.registro, a.autorizacion)
    return verificar(a.carpeta, a.codigo)


if __name__ == "__main__":
    sys.exit(main())
