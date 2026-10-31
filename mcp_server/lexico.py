"""
Vocabulario LESCO del CENAREC: carga, búsqueda y validación de secuencias.

No depende de MCP: el servidor lo envuelve y las pruebas lo usan directamente.
Toda decisión de "qué existe" sale de data/lexicon/cenarec_indice.tsv; aquí no se
inventa ni se completa ninguna glosa.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_INDICE = RAIZ / "data" / "lexicon" / "cenarec_indice.tsv"
URL_ENTRADA = "https://lesco.cenarec.go.cr/DiccLESCO.php?idw={idw}"

PREFIJO_ID = "CENAREC-"
SIN_COBERTURA = "SIN_COBERTURA"
MAX_SECUENCIA = 60
MAX_TEXTO_BUSQUEDA = 80
MAX_TEXTO_SIN_COBERTURA = 40

PATRON_ID = re.compile(r"^CENAREC-(\d{1,5})$")
PATRON_SIN_COBERTURA = re.compile(r"^SIN_COBERTURA:(.+)$")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes (conserva la ñ), solo letras y dígitos separados por un espacio."""
    t = texto.lower().replace("ñ", "\0")
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = t.replace("\0", "ñ")
    t = re.sub(r"[^0-9a-zñ]+", " ", t)
    return t.strip()


def sentidos_de(glosa: str) -> tuple[list[str], list[str]]:
    """
    Separa una glosa en sentidos buscables y aclaraciones.

    Convenciones de la fuente: '/' separa sentidos (CONTINUAR/SEGUIR), '-N' marca una
    variante (ABRIR-2), '(...)' aclara (CAFÉ (BEBIDA)) y '^' une compuestos (SORDO^MUDO).
    """
    aclaraciones = [normalizar(a) for a in re.findall(r"\(([^)]*)\)", glosa)]
    sin_parentesis = re.sub(r"\([^)]*\)", " ", glosa)
    sentidos = []
    for parte in sin_parentesis.split("/"):
        parte = re.sub(r"-\d+$", "", parte.strip())
        clave = normalizar(parte.replace("^", " "))
        if clave and clave not in sentidos:
            sentidos.append(clave)
    return sentidos, [a for a in aclaraciones if a]


@dataclass
class Entrada:
    idw: int
    glosa: str
    sentidos: list[str] = field(default_factory=list)
    aclaraciones: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{PREFIJO_ID}{self.idw}"

    @property
    def url(self) -> str:
        return URL_ENTRADA.format(idw=self.idw)

    def como_dict(self) -> dict:
        return {"id": self.id, "glosa": self.glosa, "url": self.url}


class ErrorEntrada(ValueError):
    """Entrada inválida para una herramienta; el mensaje se devuelve tal cual al agente."""


class Lexico:
    def __init__(self, ruta: Path = RUTA_INDICE):
        self.ruta = ruta
        self.entradas: dict[int, Entrada] = {}
        lineas = ruta.read_text(encoding="utf-8").splitlines()
        if not lineas or lineas[0] != "idw\tglosa":
            raise ValueError(f"{ruta}: encabezado inesperado")
        for n, linea in enumerate(lineas[1:], start=2):
            if not linea.strip():
                continue
            idw_txt, _, glosa = linea.partition("\t")
            if not idw_txt.isdigit() or not glosa:
                raise ValueError(f"{ruta}:{n}: línea mal formada")
            idw = int(idw_txt)
            if idw in self.entradas:
                raise ValueError(f"{ruta}:{n}: idw repetido {idw}")
            sentidos, aclaraciones = sentidos_de(glosa)
            self.entradas[idw] = Entrada(idw, glosa, sentidos, aclaraciones)

    def __len__(self) -> int:
        return len(self.entradas)

    def obtener(self, id_entrada: str) -> Entrada | None:
        m = PATRON_ID.match(id_entrada)
        return self.entradas.get(int(m.group(1))) if m else None

    # ------------------------------------------------------------------ búsqueda
    def buscar(self, texto: str, max_resultados: int = 5) -> dict:
        if not isinstance(texto, str) or not texto.strip():
            raise ErrorEntrada("'texto' no puede estar vacío. Envíe una palabra o expresión en español.")
        if len(texto) > MAX_TEXTO_BUSQUEDA:
            raise ErrorEntrada(f"'texto' supera {MAX_TEXTO_BUSQUEDA} caracteres. Busque un concepto a la vez, "
                               "no una frase completa.")
        if CONTROL.search(texto):
            raise ErrorEntrada("'texto' contiene caracteres de control.")
        if not isinstance(max_resultados, int) or isinstance(max_resultados, bool) \
                or not 1 <= max_resultados <= 10:
            raise ErrorEntrada("'max_resultados' debe ser un entero entre 1 y 10.")

        consulta = normalizar(texto)
        if not consulta:
            raise ErrorEntrada("'texto' no contiene letras ni dígitos.")
        palabras = set(consulta.split())

        exactas, parciales = [], []
        for e in self.entradas.values():
            if consulta in e.sentidos:
                exactas.append(e)
            elif any(palabras <= set(s.split()) for s in e.sentidos):
                parciales.append(e)
        parciales.sort(key=lambda e: (min(len(s) for s in e.sentidos), e.idw))
        exactas.sort(key=lambda e: e.idw)

        resultados = [{**e.como_dict(), "coincidencia": "exacta"} for e in exactas]
        resultados += [{**e.como_dict(), "coincidencia": "parcial"} for e in parciales]
        total = len(resultados)
        return {
            "consulta": consulta,
            "total_coincidencias": total,
            "resultados": resultados[:max_resultados],
            "nota": ("Sin coincidencias: el concepto no está en el diccionario. Pruebe con otra forma "
                     "(infinitivo, singular, sinónimo) o marque el segmento como SIN_COBERTURA:<texto>."
                     if total == 0 else
                     "Las coincidencias 'parcial' contienen la palabra buscada dentro de una glosa más larga; "
                     "verifique que el sentido corresponde antes de usarlas."),
        }

    # ------------------------------------------------------------------ validación
    def validar(self, secuencia) -> dict:
        if not isinstance(secuencia, list):
            raise ErrorEntrada("'secuencia' debe ser una lista de cadenas.")
        if not secuencia:
            raise ErrorEntrada("'secuencia' está vacía. Incluya al menos un elemento.")
        if len(secuencia) > MAX_SECUENCIA:
            raise ErrorEntrada(f"'secuencia' tiene {len(secuencia)} elementos; el máximo es {MAX_SECUENCIA}.")

        errores, elementos = [], []
        for i, valor in enumerate(secuencia):
            if not isinstance(valor, str):
                errores.append({"posicion": i, "valor": repr(valor), "error": "debe ser una cadena"})
                continue
            m = PATRON_SIN_COBERTURA.match(valor)
            if m:
                texto = m.group(1).strip()
                if not texto or len(texto) > MAX_TEXTO_SIN_COBERTURA or CONTROL.search(texto):
                    errores.append({"posicion": i, "valor": valor,
                                    "error": f"el texto tras SIN_COBERTURA: debe tener entre 1 y "
                                             f"{MAX_TEXTO_SIN_COBERTURA} caracteres, sin caracteres de control"})
                else:
                    elementos.append({"posicion": i, "tipo": "sin_cobertura", "texto": texto})
                continue
            if not PATRON_ID.match(valor):
                errores.append({"posicion": i, "valor": valor,
                                "error": "formato inválido: use 'CENAREC-<número>' tal como lo devuelve "
                                         "buscar_sena, o 'SIN_COBERTURA:<texto>'"})
                continue
            entrada = self.obtener(valor)
            if entrada is None:
                errores.append({"posicion": i, "valor": valor,
                                "error": "ese ID no existe en el diccionario; no invente IDs, use buscar_sena"})
                continue
            elementos.append({"posicion": i, "tipo": "sena", **entrada.como_dict()})

        return {
            "valida": not errores,
            "elementos": elementos,
            "errores": errores,
            "con_cobertura": sum(1 for e in elementos if e["tipo"] == "sena"),
            "sin_cobertura": sum(1 for e in elementos if e["tipo"] == "sin_cobertura"),
        }
