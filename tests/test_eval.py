import json
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "eval"))

import anotador_llm  # noqa: E402
from kappa import kappa_cohen  # noqa: E402
from tokenizar import palabras, plantilla, sugerencia  # noqa: E402


class TestTokenizador(unittest.TestCase):
    def test_palabras_sin_puntuacion(self):
        self.assertEqual(palabras("¿Cuánto debo pagar?"), ["Cuánto", "debo", "pagar"])
        self.assertEqual(palabras("Espere en la fila, por favor."), ["Espere", "en", "la", "fila", "por", "favor"])

    def test_sugerencia_respeta_tildes(self):
        self.assertEqual(sugerencia("que"), "OMITIR")
        self.assertEqual(sugerencia("qué"), "")       # interrogativo: no se omite
        self.assertEqual(sugerencia("Él"), "OMITIR")
        self.assertEqual(sugerencia("sí"), "")        # ambiguo: decide el anotador

    def test_plantilla_del_conjunto(self):
        filas = plantilla(RAIZ / "eval" / "casos.jsonl")
        self.assertEqual(len({f["caso_id"] for f in filas}), 48)
        self.assertTrue(all(f["etiqueta"] == "" for f in filas))


class TestCasos(unittest.TestCase):
    def test_sin_solapamiento_con_piloto_y_sin_datos_personales(self):
        leer = lambda r: [json.loads(l) for l in (RAIZ / r).read_text(encoding="utf-8").splitlines() if l]
        casos, piloto = leer("eval/casos.jsonl"), leer("eval/piloto/casos_piloto.jsonl")
        self.assertFalse({c["texto"] for c in casos} & {p["texto"] for p in piloto})
        for c in casos + piloto:
            self.assertNotRegex(c["texto"], r"\d")          # sin cédulas, teléfonos ni fechas en cifras
            self.assertNotRegex(c["texto"], r"@")


class TestKappa(unittest.TestCase):
    def test_acuerdo_perfecto(self):
        self.assertEqual(kappa_cohen(["a", "b", "a"], ["a", "b", "a"]), 1.0)

    def test_valor_conocido(self):
        # Ejemplo clásico 2×2: 20 sí-sí, 5 sí-no, 10 no-sí, 15 no-no → kappa = 0,4
        a = ["s"] * 25 + ["n"] * 25
        b = ["s"] * 20 + ["n"] * 5 + ["s"] * 10 + ["n"] * 15
        self.assertAlmostEqual(kappa_cohen(a, b), 0.4)

    def test_informe_sin_rutas_absolutas(self):
        from kappa import ruta_mostrable
        self.assertEqual(ruta_mostrable(RAIZ / "eval" / "desacuerdos.tsv"), "eval/desacuerdos.tsv")
        self.assertEqual(ruta_mostrable(Path("eval/desacuerdos.tsv")), "eval/desacuerdos.tsv"
                         if Path.cwd().resolve() == RAIZ.resolve() else "desacuerdos.tsv")
        fuera = Path(RAIZ.anchor) / "otra_carpeta" / "privado" / "x.tsv"
        self.assertEqual(ruta_mostrable(fuera), "x.tsv")


class TestValidacionAnotador2(unittest.TestCase):
    filas = [{"pos": 0}, {"pos": 1}, {"pos": 2}]

    def test_valida(self):
        et = [{"pos": 0, "etiqueta": "CENAREC-1482"}, {"pos": 1, "etiqueta": "+"},
              {"pos": 2, "etiqueta": "SIN_COBERTURA"}]
        self.assertEqual(anotador_llm.validar(et, self.filas, {1482}), [])

    def test_detecta_id_inventado_y_mas_huerfano(self):
        et = [{"pos": 0, "etiqueta": "+"}, {"pos": 1, "etiqueta": "CENAREC-99999"},
              {"pos": 2, "etiqueta": "PAGAR"}]
        self.assertEqual(len(anotador_llm.validar(et, self.filas, {1482})), 3)

    def test_detecta_posiciones(self):
        self.assertTrue(anotador_llm.validar([{"pos": 0, "etiqueta": "OMITIR"}], self.filas, set()))


class TestPromptYAislamientoAnotadorLLM(unittest.TestCase):
    """E1/E2 (2026-11-14): --prompt y guardas de aislamiento de eval/anotador_llm.py.
    Sin API y sin escribir en eval/anotaciones/: los prompts alternativos van a una carpeta temporal."""

    A = anotador_llm.DIR_ANOT
    OFICIAL = anotador_llm.RUTA_PROMPT

    def setUp(self):
        import tempfile, shutil
        self.tmp = Path(tempfile.mkdtemp(prefix="lesco_prompt_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.alternativo = self.tmp / "anotador_alt_v1.md"
        texto = self.OFICIAL.read_text(encoding="utf-8")
        self.alternativo.write_text(texto.replace("Eres el anotador 2", "Eres el anotador alternativo", 1),
                                    encoding="utf-8")

    @staticmethod
    def relativa(ruta: Path) -> Path:
        """La misma ruta, escrita de forma relativa al directorio actual y con un rodeo '..'."""
        import os
        rel = Path(os.path.relpath(ruta, Path.cwd()))
        return rel.parent / ".." / rel.parent.name / rel.name

    def aisla(self, prompt, registro, salida):
        return anotador_llm.problemas_de_aislamiento(Path(prompt), Path(registro), Path(salida))

    # ---- prompt
    def test_prompt_por_defecto_igual_al_oficial_explicito(self):
        import hashlib
        h = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()
        defecto = anotador_llm.prompt_sistema()
        self.assertEqual(h(defecto), h(anotador_llm.prompt_sistema(self.OFICIAL)))
        self.assertEqual(h(defecto), h(anotador_llm.prompt_sistema(self.relativa(self.OFICIAL))))
        self.assertNotIn("{guia}", defecto)
        self.assertNotIn("{indice}", defecto)

    def test_prompt_alternativo_cambia_el_contenido_compuesto(self):
        defecto = anotador_llm.prompt_sistema()
        alt = anotador_llm.prompt_sistema(self.alternativo)
        self.assertNotEqual(defecto, alt)
        self.assertIn("Eres el anotador alternativo", alt)
        self.assertNotIn("Eres el anotador 2", alt)
        # La guía y el índice se insertan igual: solo cambia la parte propia del prompt.
        self.assertEqual(defecto.split("=== GUÍA DE ANOTACIÓN ===")[1], alt.split("=== GUÍA DE ANOTACIÓN ===")[1])

    # ---- guardas
    def test_permite_las_configuraciones_legitimas(self):
        self.assertEqual(self.aisla(self.OFICIAL, self.A / "anotador2_respuestas.jsonl", self.A / "anotador2.tsv"), [])
        self.assertEqual(self.aisla(self.alternativo, self.tmp / "r.jsonl", self.tmp / "a.tsv"), [])

    def test_rechaza_anotador1_y_plantilla(self):
        for nombre in ("anotador1.tsv", "plantilla.tsv"):
            for prompt in (self.OFICIAL, self.alternativo):
                with self.subTest(nombre=nombre, prompt=prompt.name):
                    self.assertTrue(self.aisla(prompt, self.tmp / "r.jsonl", self.A / nombre))
                    self.assertTrue(self.aisla(prompt, self.A / nombre, self.tmp / "a.tsv"))

    def test_prompt_alternativo_no_escribe_en_archivos_del_anotador2(self):
        for nombre in ("anotador2.tsv", "anotador2_respuestas.jsonl"):
            with self.subTest(nombre=nombre):
                self.assertTrue(self.aisla(self.alternativo, self.A / nombre, self.tmp / "a.tsv"))
                self.assertTrue(self.aisla(self.alternativo, self.tmp / "r.jsonl", self.A / nombre))

    def test_rechaza_registro_igual_a_salida(self):
        self.assertTrue(self.aisla(self.alternativo, self.tmp / "x.tsv", self.tmp / "x.tsv"))
        self.assertTrue(self.aisla(self.alternativo, self.tmp / "x.tsv", self.relativa(self.tmp / "x.tsv")))

    def test_variantes_relativas_no_eluden_las_guardas(self):
        for nombre in ("anotador1.tsv", "plantilla.tsv"):
            with self.subTest(nombre=nombre):
                self.assertTrue(self.aisla(self.OFICIAL, self.tmp / "r.jsonl", self.relativa(self.A / nombre)))
        for nombre in ("anotador2.tsv", "anotador2_respuestas.jsonl"):
            with self.subTest(nombre=nombre):
                self.assertTrue(self.aisla(self.alternativo, self.tmp / "r.jsonl", self.relativa(self.A / nombre)))

    @unittest.skipUnless(sys.platform.startswith("win"), "solo en Windows (sistema de archivos sin distinción de mayúsculas)")
    def test_variantes_de_mayusculas_no_eluden_las_guardas(self):
        for nombre in ("anotador1.tsv", "plantilla.tsv"):
            with self.subTest(nombre=nombre):
                self.assertTrue(self.aisla(self.OFICIAL, self.tmp / "r.jsonl", Path(str(self.A / nombre).upper())))
        for nombre in ("anotador2.tsv", "anotador2_respuestas.jsonl"):
            with self.subTest(nombre=nombre):
                self.assertTrue(self.aisla(self.alternativo, self.tmp / "r.jsonl", Path(str(self.A / nombre).upper())))
        # Un prompt alternativo escrito con otras mayúsculas sigue sin ser el oficial... y el oficial con otras
        # mayúsculas sigue siendo el oficial (puede escribir en los archivos del anotador 2).
        self.assertEqual(self.aisla(Path(str(self.OFICIAL).upper()), self.A / "anotador2_respuestas.jsonl",
                                    self.A / "anotador2.tsv"), [])

    @unittest.skipUnless(sys.platform.startswith("win"), "solo en Windows (sistema de archivos sin distinción de mayúsculas)")
    def test_mayusculas_en_rutas_que_no_existen(self):
        # E2.1: directorio nuevo, archivos inexistentes: x.tsv y X.TSV son el mismo archivo en Windows.
        nuevo = self.tmp / "nuevo_dir"
        self.assertFalse(nuevo.exists())
        self.assertTrue(self.aisla(self.alternativo, nuevo / "x.tsv", nuevo / "X.TSV"))
        self.assertTrue(self.aisla(self.alternativo, nuevo / "x.tsv", Path(str(nuevo / "x.tsv").upper())))
        # Archivos protegidos que no existen (DIR_ANOT temporal): las mayúsculas tampoco eluden la guarda.
        from unittest import mock
        with mock.patch.object(anotador_llm, "DIR_ANOT", nuevo):
            for nombre in ("anotador1.tsv", "plantilla.tsv"):
                with self.subTest(nombre=nombre):
                    self.assertTrue(self.aisla(self.alternativo, self.tmp / "r.jsonl", nuevo / nombre.upper()))
            for nombre in ("anotador2.tsv", "anotador2_respuestas.jsonl"):
                with self.subTest(nombre=nombre):
                    self.assertTrue(self.aisla(self.alternativo, self.tmp / "r.jsonl", nuevo / nombre.upper()))
        self.assertFalse(nuevo.exists())

    def test_configuracion_rechazada_termina_antes_de_la_api(self):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        prohibido = mock.Mock(side_effect=AssertionError("no debía llamarse"))
        argv = ["anotador_llm.py", "--prompt", str(self.alternativo),
                "--registro", str(self.tmp / "r.jsonl"), "--salida", str(self.A / "anotador1.tsv")]
        # anotador1.tsv no se versiona: en un clon limpio no existe. Se comprueba que el archivo
        # destino queda exactamente como estaba (con su contenido, o sin existir).
        destino = self.A / "anotador1.tsv"
        antes = destino.read_bytes() if destino.exists() else None
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(anotador_llm, "cargar_clave", prohibido), \
                mock.patch.object(anotador_llm, "pedir", prohibido), \
                mock.patch.object(anotador_llm, "leer_tsv", prohibido), \
                mock.patch.object(anotador_llm, "escribir_tsv", prohibido), \
                redirect_stdout(io.StringIO()) as salida:
            codigo = anotador_llm.main()
        self.assertEqual(codigo, 3)
        self.assertIn("Configuración rechazada", salida.getvalue())
        prohibido.assert_not_called()
        self.assertEqual(destino.read_bytes() if destino.exists() else None, antes)
        self.assertFalse((self.tmp / "r.jsonl").exists())


class TestReanudacionAnotadorLLM(unittest.TestCase):
    """E2.1 (2026-11-14): la reanudación y el TSV usan solo respuestas del mismo prompt y del mismo modelo
    (comparación exacta). Datos 100 % sintéticos en una carpeta temporal; pedir() y cargar_clave() simulados:
    ninguna prueba llama a la API ni lee archivos de eval/anotaciones/."""

    MODELO = "modelo-sintetico-a"

    def setUp(self):
        import tempfile, shutil
        from tokenizar import escribir_tsv
        self.tmp = Path(tempfile.mkdtemp(prefix="lesco_reanudar_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.prompt = self.tmp / "prompt_sintetico_v1.md"
        self.prompt.write_text("Prompt sintético.\n{guia}\n{indice}\n", encoding="utf-8")
        self.sha = __import__("hashlib").sha256(anotador_llm.prompt_sistema(self.prompt).encode("utf-8")).hexdigest()
        self.plantilla = self.tmp / "plantilla.tsv"
        filas = [{"caso_id": c, "pos": p, "palabra": w, "sugerencia": "", "etiqueta": ""}
                 for c, ws in (("s1", ["alfa", "beta"]), ("s2", ["gamma"])) for p, w in enumerate(ws)]
        escribir_tsv(filas, self.plantilla)
        self.registro = self.tmp / "respuestas.jsonl"
        self.salida = self.tmp / "anotacion.tsv"

    def linea(self, caso, n, etiqueta="SIN_COBERTURA", sha=None, modelo=None, problemas=()):
        return {"caso_id": caso, "intento": 1, "modelo": modelo or self.MODELO, "sha256_prompt": sha or self.sha,
                "fecha": "2026-11-14T00:00:00", "stop_reason": "end_turn", "uso": {},
                "etiquetas": [{"pos": i, "etiqueta": etiqueta, "motivo": "s"} for i in range(n)],
                "problemas": list(problemas)}

    def escribir_registro(self, *lineas):
        self.registro.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lineas), encoding="utf-8")

    def respuesta(self, n, modelo=None):
        texto = json.dumps({"etiquetas": [{"pos": i, "etiqueta": "SIN_COBERTURA", "motivo": "s"} for i in range(n)]})
        return {"model": modelo or self.MODELO, "stop_reason": "end_turn", "usage": {},
                "content": [{"type": "text", "text": texto}]}

    def ejecutar(self, pedir=None, extra=()):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        pedir = pedir or mock.Mock(side_effect=AssertionError("pedir no debía llamarse"))
        argv = ["anotador_llm.py", "--plantilla", str(self.plantilla), "--prompt", str(self.prompt),
                "--modelo", self.MODELO, "--registro", str(self.registro), "--salida", str(self.salida), *extra]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(anotador_llm, "pedir", pedir), \
                mock.patch.object(anotador_llm, "cargar_clave", mock.Mock(return_value="clave-sintetica")), \
                redirect_stdout(io.StringIO()) as out:
            codigo = anotador_llm.main()
        return codigo, out.getvalue(), pedir

    def etiquetas_tsv(self):
        from tokenizar import leer_tsv
        return [(f["caso_id"], f["pos"], f["etiqueta"]) for f in leer_tsv(self.salida)]

    # 2. registro con dos modelos
    def test_registro_con_otro_modelo_se_rechaza_antes_de_la_api(self):
        self.escribir_registro(self.linea("s1", 2), self.linea("s2", 1, modelo="otro-modelo"))
        codigo, out, pedir = self.ejecutar()
        self.assertEqual(codigo, 3)
        self.assertIn("otro modelo", out)
        pedir.assert_not_called()
        self.assertFalse(self.salida.exists())

    # 3. registro con dos hashes de prompt
    def test_registro_con_otro_prompt_se_rechaza_antes_de_la_api(self):
        self.escribir_registro(self.linea("s1", 2), self.linea("s2", 1, sha="0" * 64))
        codigo, out, pedir = self.ejecutar()
        self.assertEqual(codigo, 3)
        self.assertIn("otro prompt", out)
        pedir.assert_not_called()
        self.assertFalse(self.salida.exists())

    # 4. reanudación válida
    def test_reanudacion_no_repite_casos_completos(self):
        from unittest import mock
        self.escribir_registro(self.linea("s1", 2))
        pedir = mock.Mock(return_value=self.respuesta(1))
        codigo, _, pedir = self.ejecutar(pedir)
        self.assertEqual(codigo, 0)
        self.assertEqual(pedir.call_count, 1)                       # solo s2
        self.assertIn("Caso s2", pedir.call_args.args[2])
        codigo, _, _ = self.ejecutar()                               # todo completo: no se pide nada
        self.assertEqual(codigo, 0)

    # 5. reconstrucción del TSV
    def test_tsv_solo_con_el_prompt_y_modelo_autorizados(self):
        # Intentos fallidos de otro modelo/prompt no son "válidos": no bloquean, pero tampoco entran al TSV.
        self.escribir_registro(self.linea("s1", 2, etiqueta="OMITIR", modelo="otro-modelo", problemas=["x"]),
                               self.linea("s1", 2, etiqueta="SIN_COBERTURA"),
                               self.linea("s2", 1, etiqueta="OMITIR", sha="1" * 64, problemas=["x"]),
                               self.linea("s2", 1, etiqueta="SIN_COBERTURA"))
        codigo, _, _ = self.ejecutar()
        self.assertEqual(codigo, 0)
        self.assertEqual(self.etiquetas_tsv(), [("s1", 0, "SIN_COBERTURA"), ("s1", 1, "SIN_COBERTURA"),
                                                ("s2", 0, "SIN_COBERTURA")])

    def test_registro_valido_filtra_por_prompt_y_modelo(self):
        self.escribir_registro(self.linea("s1", 2, modelo="otro-modelo"), self.linea("s2", 1, sha="2" * 64),
                               self.linea("s2", 1))
        self.assertEqual(set(anotador_llm.registro_valido(self.registro)), {"s1", "s2"})          # firma antigua
        filtrado = anotador_llm.registro_valido(self.registro, self.sha, self.MODELO)
        self.assertEqual(set(filtrado), {"s2"})
        self.assertEqual(filtrado["s2"]["sha256_prompt"], self.sha)
        self.assertEqual(anotador_llm.registro_valido(self.registro, self.sha, self.MODELO + "-x"), {})  # exacta

    def test_modelo_declarado_distinto_detiene_sin_mas_solicitudes(self):
        from unittest import mock
        pedir = mock.Mock(return_value=self.respuesta(2, modelo=self.MODELO + "-20260101"))
        codigo, out, pedir = self.ejecutar(pedir)
        self.assertEqual(codigo, 4)
        self.assertEqual(pedir.call_count, 1)                        # ni reintento ni otro caso
        self.assertFalse(self.salida.exists())                       # no se escribe el TSV
        registro = [json.loads(l) for l in self.registro.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(registro), 1)
        self.assertEqual(registro[0]["modelo"], self.MODELO + "-20260101")   # se registra lo declarado
        self.assertTrue(registro[0]["problemas"])                    # y no cuenta como respuesta válida

    # 6. compatibilidad con el anotador 2 (sin leer sus archivos)
    def test_compatibilidad_valores_por_defecto_del_anotador2(self):
        import inspect
        self.assertEqual(anotador_llm.MODELO, "claude-opus-5-5")
        self.assertEqual(anotador_llm.RUTA_PROMPT.name, "anotador2_v1.md")
        firma = inspect.signature(anotador_llm.registro_valido)
        self.assertEqual(list(firma.parameters)[0], "ruta")
        self.assertTrue(all(p.default is None for n, p in firma.parameters.items() if n != "ruta"))
        # Un registro "como el del anotador 2" (un único prompt y un único modelo) no se rechaza.
        sha2 = __import__("hashlib").sha256(anotador_llm.prompt_sistema().encode("utf-8")).hexdigest()
        self.escribir_registro(*[self.linea(c, 1, sha=sha2, modelo="claude-opus-5-5") for c in ("s1", "s2")])
        self.assertEqual(anotador_llm.identidades_ajenas(self.registro, sha2, "claude-opus-5-5"), [])


class TestReferenciasD20(unittest.TestCase):
    """D20 (2026-11-14): referencias R1/R2 (una anotación) y Rc (consenso por caso). Datos sintéticos."""

    @staticmethod
    def filas(etiquetas_por_caso):
        return [{"caso_id": c, "pos": p, "palabra": f"w{p}", "sugerencia": "", "etiqueta": e}
                for c, es in etiquetas_por_caso for p, e in enumerate(es)]

    def test_referencia_unica_exige_etiquetas_validas(self):
        import construir_referencia as cr
        buenas = self.filas([("s1", ["CENAREC-1", "OMITIR"]), ("s2", ["SIN_COBERTURA"])])
        self.assertEqual(cr.referencia_unica(buenas), buenas)
        for mala in ("", "PAGAR", " OMITIR"):
            with self.subTest(mala=mala), self.assertRaises(SystemExit):
                cr.referencia_unica(self.filas([("s1", ["CENAREC-1", mala])]))

    def test_consenso_solo_casos_con_acuerdo_total(self):
        import construir_referencia as cr
        a = self.filas([("s1", ["CENAREC-1", "OMITIR"]), ("s2", ["CENAREC-2", "+"]), ("s3", ["SIN_COBERTURA"])])
        b = self.filas([("s1", ["CENAREC-1", "OMITIR"]), ("s2", ["CENAREC-2", "OMITIR"]), ("s3", ["SIN_COBERTURA"])])
        final, excluidos = cr.consenso(a, b)
        self.assertEqual(excluidos, ["s2"])
        self.assertEqual([(f["caso_id"], f["pos"], f["etiqueta"]) for f in final],
                         [("s1", 0, "CENAREC-1"), ("s1", 1, "OMITIR"), ("s3", 0, "SIN_COBERTURA")])
        self.assertEqual(cr.secuencia([f for f in final if f["caso_id"] == "s3"]), ["SIN_COBERTURA:w0"])

    def test_consenso_rechaza_plantillas_distintas_o_incompletas(self):
        import construir_referencia as cr
        a = self.filas([("s1", ["CENAREC-1", "OMITIR"])])
        with self.assertRaises(SystemExit):
            cr.consenso(a, self.filas([("s1", ["CENAREC-1"])]))            # otras palabras
        with self.assertRaises(SystemExit):
            cr.consenso(a, self.filas([("s1", ["CENAREC-1", ""])]))        # anotación incompleta

    def test_cli_modos_nuevos_escriben_solo_la_referencia_pedida(self):
        import io, tempfile, shutil
        from contextlib import redirect_stdout
        from unittest import mock
        from tokenizar import escribir_tsv
        import construir_referencia as cr
        tmp = Path(tempfile.mkdtemp(prefix="lesco_ref_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        a, b = tmp / "a.tsv", tmp / "b.tsv"
        escribir_tsv(self.filas([("s1", ["CENAREC-1"]), ("s2", ["CENAREC-2"])]), a)
        escribir_tsv(self.filas([("s1", ["CENAREC-1"]), ("s2", ["SIN_COBERTURA"])]), b)
        meta = tmp / "meta.jsonl"
        meta.write_text('{"caso_id": "s1", "motivos": []}\n{"caso_id": "s2", "motivos": ["sinonimo"]}\n', encoding="utf-8")
        adjudicada = tmp / "no_debe_existir.tsv"
        casos = (["--modo", "unico", "--anotacion", str(a), "--salida", str(tmp / "r.jsonl")],
                 ["--modo", "consenso", "--anotador1", str(a), "--anotador2", str(b), "--salida", str(tmp / "rc.jsonl")])
        for extra in casos:
            argv = ["construir_referencia.py", "--meta", str(meta), "--adjudicada", str(adjudicada), *extra]
            with mock.patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
                self.assertEqual(cr.main(), 0)
        r = [json.loads(l) for l in (tmp / "r.jsonl").read_text(encoding="utf-8").splitlines()]
        rc = [json.loads(l) for l in (tmp / "rc.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([x["caso_id"] for x in r], ["s1", "s2"])
        self.assertEqual(r[1]["dificultad"], "dificil")                 # motivo previsto 'sinonimo' (D20)
        self.assertEqual([x["caso_id"] for x in rc], ["s1"])
        self.assertFalse(adjudicada.exists())                           # los modos D20 no escriben TSV adjudicado


if __name__ == "__main__":
    unittest.main()
