"""Pruebas del validador agregado del anotador 2 (eval/validar_anotador2.py).

Todos los datos son sintéticos y se construyen en una carpeta temporal. Ninguna prueba lee
eval/anotaciones/ (anotador 1 ni anotador 2), .env ni evidencia/privado/, ni usa la API.
Solo las pruebas de coherencia leen archivos versionados y no privados (prompt v1, guía e índice).
"""

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "eval"))

import validar_anotador2 as v  # noqa: E402
import anotador_llm  # noqa: E402  (solo para comparar reglas; no se llama a la API)

# --- Datos sintéticos (todos inventados y fáciles de buscar en la salida) ---
CASOS = {
    "qcasoalfa": [("zafiroA", ""), ("zafiroB", ""), ("zafiroC", "OMITIR")],
    "qcasobeta": [("turquesaD", ""), ("turquesaE", "")],
}
ETIQUETAS_OK = {
    "qcasoalfa": ["CENAREC-9001", "+", "OMITIR"],
    "qcasobeta": ["SIN_COBERTURA", "CENAREC-9003"],
}
INDICE = "idw\tglosa\n9001\tGLOSAALFA\n9002\tGLOSABETA\n9003\tGLOSAGAMMA\n"
PROMPT = "PROMPT SINTETICO {guia} FIN {indice}"
GUIA = "GUIA SINTETICA\n"
SHA_VIGENTE = hashlib.sha256(("PROMPT SINTETICO " + GUIA.strip() + " FIN " + INDICE.strip()).encode("utf-8")).hexdigest()
SHA_ANTIGUO = "0" * 64
MOTIVO = "motivoSECRETO"
# Cadenas que nunca deben aparecer en la salida del validador.
PRIVADAS = ["zafiro", "turquesa", "qcaso", "CENAREC-900", "SIN_COBERTURA", "OMITIR", MOTIVO, "SECRETO", "GLOSA"]
CABECERA = "caso_id\tpos\tpalabra\tsugerencia\tetiqueta"


def sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def registro(caso, etiquetas=None, sha_prompt=SHA_VIGENTE, problemas=(), intento=1, **extra) -> dict:
    etiquetas = ETIQUETAS_OK[caso] if etiquetas is None else etiquetas
    r = {"caso_id": caso, "intento": intento, "modelo": "claude-sintetico-1", "sha256_prompt": sha_prompt,
         "fecha": "2026-01-02T03:04:05", "stop_reason": "end_turn",
         "uso": {"input_tokens": 10, "output_tokens": 5},
         "etiquetas": [{"pos": i, "etiqueta": e, "motivo": MOTIVO} for i, e in enumerate(etiquetas)],
         "problemas": list(problemas)}
    r.update(extra)
    return r


def filas_tsv(etiquetas: dict | None = None) -> list[str]:
    etiquetas = ETIQUETAS_OK if etiquetas is None else etiquetas
    return [f"{c}\t{i}\t{p}\t{s}\t{etiquetas[c][i]}" for c, ps in CASOS.items() for i, (p, s) in enumerate(ps)]


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)
        self.rutas = {n: self.d / f for n, f in (("plantilla", "plantilla.tsv"), ("registro", "registro.jsonl"),
                                                 ("tsv", "a2.tsv"), ("prompt", "prompt.md"),
                                                 ("guia", "guia.md"), ("indice", "indice.tsv"))}
        self.rutas["prompt"].write_text(PROMPT, encoding="utf-8")
        self.rutas["guia"].write_text(GUIA, encoding="utf-8")
        self.rutas["indice"].write_text(INDICE, encoding="utf-8")
        plantilla = [f"{c}\t{i}\t{p}\t{s}\t" for c, ps in CASOS.items() for i, (p, s) in enumerate(ps)]
        self.rutas["plantilla"].write_text("\n".join([CABECERA, *plantilla]) + "\n", encoding="utf-8")
        self.escribir_registro([registro("qcasoalfa"), registro("qcasobeta")])
        self.escribir_tsv(filas_tsv())

    def tearDown(self):
        self._tmp.cleanup()

    def escribir_registro(self, registros, lineas_extra=()):
        lineas = [json.dumps(r, ensure_ascii=False) for r in registros] + list(lineas_extra)
        self.rutas["registro"].write_text("\n".join(lineas) + "\n", encoding="utf-8")

    def escribir_tsv(self, filas, cabecera=CABECERA):
        self.rutas["tsv"].write_text("\n".join([cabecera, *filas]) + "\n", encoding="utf-8")

    def ejecutar(self, argv=None):
        """Ejecuta main() con rutas sintéticas. Comprueba en cada llamada que no se modificó ninguna
        entrada y que la salida no contiene datos sintéticos ni rutas."""
        antes = {p.name: sha(p) for p in self.d.iterdir()}
        argv = argv if argv is not None else [x for n, r in self.rutas.items() for x in (f"--{n}", str(r))]
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                codigo = v.main(argv)
            except SystemExit as e:  # errores de argparse
                codigo = e.code
        salida = buf.getvalue()
        self.assertEqual({p.name: sha(p) for p in self.d.iterdir()}, antes, "se modificó una entrada")
        for s in PRIVADAS + [str(self.d), self.d.name]:
            self.assertNotIn(s, salida, f"la salida contiene un dato sintético o una ruta: {s!r}")
        return codigo, salida


class TestLegitimos(Base):
    def test_completo_valido(self):
        codigo, salida = self.ejecutar()
        self.assertEqual(codigo, 0)
        self.assertIn("VÁLIDO (código 0)", salida)
        self.assertIn("casos completos 2 de 2", salida)
        self.assertIn("casos con respuesta seleccionada 2 de 2", salida)

    def test_intento_con_problemas_y_despues_valido(self):
        self.escribir_registro([
            registro("qcasoalfa", ["XSECRETO", "+", "OMITIR"], problemas=["pos 0: etiqueta inválida 'XSECRETO'"]),
            registro("qcasoalfa", intento=2), registro("qcasobeta")])
        codigo, salida = self.ejecutar()
        self.assertEqual(codigo, 0)
        self.assertIn("'intentos_con_problemas': 1", salida)
        self.assertIn("'etiqueta_invalida': 1", salida)

    def test_reemplazo_legitimo_de_prompt_anterior(self):
        self.escribir_registro([registro("qcasoalfa", sha_prompt=SHA_ANTIGUO), registro("qcasoalfa"),
                                registro("qcasobeta")])
        codigo, salida = self.ejecutar()
        self.assertEqual(codigo, 0)
        self.assertIn("'reemplazos_legitimos': 1", salida)

    def test_metadatos_inesperados_se_sanean(self):
        self.escribir_registro([
            registro("qcasoalfa", modelo="modelo SECRETO libre", fecha="hoy SECRETO", stop_reason="Fin SECRETO",
                     uso={"clave SECRETO": 3}),
            registro("qcasobeta", sha_prompt=SHA_VIGENTE)])
        codigo, salida = self.ejecutar()
        self.assertEqual(codigo, 0)          # los metadatos no afectan a la validez
        self.assertIn("<formato inesperado>", salida)
        self.assertIn("valores de uso no reconocidos 1", salida)


class TestRegistroInconsistente(Base):
    def comprobar(self, registros, clave, lineas_extra=()):
        self.escribir_registro(registros, lineas_extra)
        codigo, salida = self.ejecutar()
        self.assertEqual(codigo, 1)
        self.assertIn(clave, salida)
        self.assertIn("INCOMPLETO O INVÁLIDO (código 1)", salida)

    def test_duplicados_vigentes_identicos(self):
        self.comprobar([registro("qcasoalfa"), registro("qcasoalfa"), registro("qcasobeta")],
                       "'duplicados_identicos': 1")

    def test_duplicados_vigentes_contradictorios(self):
        self.comprobar([registro("qcasoalfa"), registro("qcasoalfa", ["CENAREC-9002", "+", "OMITIR"]),
                        registro("qcasobeta")], "'duplicados_contradictorios': 1")

    def test_caso_sin_respuesta(self):
        self.comprobar([registro("qcasoalfa")], "'sin_valida': 1")

    def test_solo_prompt_antiguo(self):
        self.comprobar([registro("qcasoalfa", sha_prompt=SHA_ANTIGUO), registro("qcasobeta")], "'sin_vigente': 1")

    def test_ultima_valida_no_vigente(self):
        self.comprobar([registro("qcasoalfa"), registro("qcasoalfa", sha_prompt=SHA_ANTIGUO),
                        registro("qcasobeta")], "'ultima_no_vigente': 1")

    def test_registros_malformados(self):
        sin_problemas = registro("qcasoalfa"); del sin_problemas["problemas"]
        etiquetas_no_lista = registro("qcasoalfa", etiquetas=[]); etiquetas_no_lista["etiquetas"] = "SECRETO"
        intento_booleano = registro("qcasoalfa", intento=True)
        self.comprobar([sin_problemas, etiquetas_no_lista, intento_booleano, registro("qcasoalfa"),
                        registro("qcasobeta")], "'malformados': 3")

    def test_caso_ajeno(self):
        self.comprobar([registro("qcasoalfa"), registro("qcasobeta"),
                        dict(registro("qcasoalfa"), caso_id="qcasoSECRETOajeno")], "'ajenos': 1")

    def test_json_ilegible(self):
        self.comprobar([registro("qcasoalfa"), registro("qcasobeta")], "líneas ilegibles 2",
                       lineas_extra=["{no es json SECRETO", "[1, 2]"])

    def test_no_revalida(self):
        for nombre, etiquetas in (("id inexistente", ["CENAREC-9999", "+", "OMITIR"]),
                                  ("mas huérfano", ["+", "+", "OMITIR"]),
                                  ("posiciones", ["CENAREC-9001", "+"])):
            with self.subTest(nombre):
                self.comprobar([registro("qcasoalfa", etiquetas), registro("qcasobeta")], "'no_revalida': 1")


class TestTsv(Base):
    def comprobar(self, filas, clave):
        self.escribir_tsv(filas)
        codigo, salida = self.ejecutar()
        self.assertEqual(codigo, 1)
        self.assertIn(clave, salida)

    def con(self, caso, pos, etiqueta):
        e = {c: list(v) for c, v in ETIQUETAS_OK.items()}
        e[caso][pos] = etiqueta
        return filas_tsv(e)

    def test_etiqueta_distinta_de_la_seleccionada(self):
        self.comprobar(self.con("qcasoalfa", 0, "CENAREC-9002"), "'etiquetas_distintas': 1")

    def test_etiqueta_vacia(self):
        self.comprobar(self.con("qcasobeta", 1, ""), "'etiquetas_vacias': 1")

    def test_etiqueta_invalida(self):
        self.comprobar(self.con("qcasobeta", 0, "cenarec-1"), "'etiquetas_invalidas': 1")

    def test_posicion_faltante(self):
        filas = filas_tsv(); del filas[2]
        self.comprobar(filas, "'posiciones_solo_en_registro': 1")

    def test_posicion_sobrante(self):
        filas = filas_tsv(); filas.insert(3, "qcasoalfa\t3\tzafiroZ\t\tOMITIR")
        self.comprobar(filas, "'posiciones_solo_en_tsv': 1")

    def test_caso_faltante(self):
        self.comprobar([f for f in filas_tsv() if not f.startswith("qcasobeta")], "'casos_faltantes': 1")

    def test_caso_ajeno(self):
        self.comprobar(filas_tsv() + ["qcasogamma\t0\tzafiroX\t\tOMITIR"], "'casos_ajenos': 1")

    def test_defectos_de_formato(self):
        base = filas_tsv()
        for nombre, filas, clave in (
                ("4 columnas", base[:1] + ["qcasoalfa\t1\tzafiroB\t"] + base[2:], "'columnas': 1"),
                ("6 columnas", base[:1] + ["qcasoalfa\t1\tzafiroB\t\t+\textra"] + base[2:], "'columnas': 1"),
                ("posición no numérica", base[:1] + ["qcasoalfa\tx\tzafiroB\t\t+"] + base[2:], "'posicion': 1"),
                ("fila repetida", base + [base[0]], "'duplicada': 1"),
                ("línea vacía intermedia", base[:2] + [""] + base[2:], "'linea_vacia': 1")):
            with self.subTest(nombre):
                self.comprobar(filas, clave)


class TestCodigo2(Base):
    def test_encabezado_tsv_incorrecto(self):
        for nombre, cabecera in (("falta columna", "caso_id\tpos\tpalabra\tetiqueta"),
                                 ("columna duplicada", CABECERA + "\tetiqueta"),
                                 ("otro orden", "pos\tcaso_id\tpalabra\tsugerencia\tetiqueta")):
            with self.subTest(nombre):
                self.escribir_tsv(filas_tsv(), cabecera=cabecera)
                codigo, salida = self.ejecutar()
                self.assertEqual(codigo, 2)
                self.assertIn("ERROR de lectura: encabezado en tsv", salida)

    def test_plantilla_defectuosa(self):
        texto = self.rutas["plantilla"].read_text(encoding="utf-8") + "qcasoalfa\t0\tzafiroA\t\t\n"
        self.rutas["plantilla"].write_text(texto, encoding="utf-8")
        codigo, salida = self.ejecutar()
        self.assertEqual(codigo, 2)
        self.assertIn("ERROR de lectura: filas en plantilla", salida)

    def test_entrada_inexistente(self):
        argv = [x for n, r in self.rutas.items() for x in (f"--{n}", str(r) if n != "registro"
                                                             else str(self.d / "noexiste_SECRETO.jsonl"))]
        codigo, salida = self.ejecutar(argv)
        self.assertEqual(codigo, 2)
        self.assertIn("en registro", salida)

    def test_argumento_desconocido_sin_repetir_valores(self):
        codigo, salida = self.ejecutar(["--desconocido", str(self.d / "ruta_SECRETO")])
        self.assertEqual(codigo, 2)
        self.assertIn("ERROR de argumentos (mensaje suprimido)", salida)


class TestCoherenciaConAnotadorLlm(Base):
    """Las reglas del validador coinciden con eval/anotador_llm.py (sin llamar a la API)."""

    def test_prompt_igual_que_prompt_sistema(self):
        leer = lambda r: (RAIZ / r).read_text(encoding="utf-8")  # noqa: E731  archivos versionados
        propio = v.componer_prompt(leer("eval/prompts/anotador2_v1.md"), leer("eval/guia_anotacion.md"),
                                   leer("data/lexicon/cenarec_indice.tsv"))
        self.assertEqual(hashlib.sha256(propio.encode("utf-8")).hexdigest(),
                         hashlib.sha256(anotador_llm.prompt_sistema().encode("utf-8")).hexdigest())

    def test_revalidar_equivale_a_validar(self):
        filas = [{"pos": i} for i in range(3)]
        ids = {9001, 9002}
        for et in (["CENAREC-9001", "+", "OMITIR"], ["SIN_COBERTURA", "OMITIR", "OMITIR"],
                   ["CENAREC-9003", "+", "OMITIR"], ["+", "+", "OMITIR"], ["cenarec-1", "OMITIR", "OMITIR"],
                   ["CENAREC-9001", "+"], ["CENAREC-9001", "CENAREC-9002", "+"]):
            with self.subTest(et):
                etiquetas = [{"pos": i, "etiqueta": e, "motivo": MOTIVO} for i, e in enumerate(et)]
                self.assertEqual(v.revalidar(etiquetas, [0, 1, 2], ids),
                                 anotador_llm.validar(etiquetas, filas, ids) == [])

    def test_seleccion_igual_que_registro_valido(self):
        self.escribir_registro([
            registro("qcasoalfa", ["XSECRETO", "+", "OMITIR"], problemas=["pos 0: etiqueta inválida 'XSECRETO'"]),
            registro("qcasoalfa", ["CENAREC-9002", "+", "OMITIR"], sha_prompt=SHA_ANTIGUO),
            registro("qcasoalfa"), registro("qcasobeta")])
        texto = self.rutas["registro"].read_text(encoding="utf-8")
        registros, _ = v.leer_registro(texto)
        posiciones = {c: list(range(len(ps))) for c, ps in CASOS.items()}
        seleccion, _ = v.seleccionar(registros, posiciones, SHA_VIGENTE, {9001, 9002, 9003})
        referencia = anotador_llm.registro_valido(self.rutas["registro"])
        self.assertEqual(set(seleccion), set(referencia))
        for caso in seleccion:
            self.assertEqual(seleccion[caso]["etiquetas"], referencia[caso]["etiquetas"])


if __name__ == "__main__":
    unittest.main()
