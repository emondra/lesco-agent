import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "mcp_server"))

from lexico import ErrorEntrada, Lexico, normalizar, sentidos_de  # noqa: E402


class TestNormalizacion(unittest.TestCase):
    def test_tildes_mayusculas_y_signos(self):
        self.assertEqual(normalizar("¿Cuánto?"), "cuanto")
        self.assertEqual(normalizar("  Á-PARTIR-DE  "), "a partir de")

    def test_conserva_enie(self):
        self.assertEqual(normalizar("MAÑANA"), "mañana")
        self.assertNotEqual(normalizar("año"), normalizar("ano"))

    def test_sentidos_de_glosas(self):
        self.assertEqual(sentidos_de("CONTINUAR/SEGUIR"), (["continuar", "seguir"], []))
        self.assertEqual(sentidos_de("ABRIR-2"), (["abrir"], []))
        self.assertEqual(sentidos_de("CAFÉ (BEBIDA)"), (["cafe"], ["bebida"]))
        self.assertEqual(sentidos_de("PEQUEÑO(ENTIDAD HORIZONTAL)"), (["pequeño"], ["entidad horizontal"]))
        self.assertEqual(sentidos_de("SORDO^MUDO"), (["sordo mudo"], []))
        self.assertEqual(sentidos_de("PENSAR-2/ACORDARSE-DE"), (["pensar", "acordarse de"], []))


class TestLexico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = Lexico()

    def test_carga_indice_completo(self):
        self.assertEqual(len(self.lex), 1104)

    def ids(self, resultado, coincidencia=None):
        return [r["id"] for r in resultado["resultados"]
                if coincidencia is None or r["coincidencia"] == coincidencia]

    def test_busqueda_exacta(self):
        self.assertIn("CENAREC-195", self.ids(self.lex.buscar("pagar"), "exacta"))
        self.assertIn("CENAREC-325", self.ids(self.lex.buscar("Firmar"), "exacta"))

    def test_variantes_numeradas_aparecen_juntas(self):
        exactas = self.ids(self.lex.buscar("abrir"), "exacta")
        self.assertIn("CENAREC-58", exactas)
        self.assertIn("CENAREC-900", exactas)

    def test_sentido_tras_barra(self):
        self.assertIn("CENAREC-152", self.ids(self.lex.buscar("seguir"), "exacta"))

    def test_exactas_antes_que_parciales(self):
        r = self.lex.buscar("mañana", max_resultados=10)
        self.assertEqual(r["resultados"][0]["id"], "CENAREC-32")
        self.assertIn("CENAREC-14", self.ids(r, "parcial"))   # EN-LA-MAÑANA

    def test_sin_coincidencias(self):
        r = self.lex.buscar("cédula")
        self.assertEqual(r["total_coincidencias"], 0)
        self.assertIn("SIN_COBERTURA", r["nota"])

    def test_resultado_incluye_url_de_la_fuente(self):
        r = self.lex.buscar("pagar")["resultados"][0]
        self.assertEqual(r["url"], "https://lesco.cenarec.go.cr/DiccLESCO.php?idw=195")

    def test_busqueda_rechaza_entradas_invalidas(self):
        for texto in ["", "   ", "x" * 81, "pa\x00gar", "¿?", 5]:
            with self.subTest(texto=texto), self.assertRaises(ErrorEntrada):
                self.lex.buscar(texto)
        for n in [0, 11, True, "3"]:
            with self.subTest(max_resultados=n), self.assertRaises(ErrorEntrada):
                self.lex.buscar("pagar", n)

    def test_validar_secuencia_correcta(self):
        r = self.lex.validar(["CENAREC-195", "SIN_COBERTURA:cédula"])
        self.assertTrue(r["valida"])
        self.assertEqual((r["con_cobertura"], r["sin_cobertura"]), (1, 1))
        self.assertEqual(r["elementos"][0]["glosa"], "PAGAR")

    def test_validar_detecta_id_inexistente_y_formato(self):
        r = self.lex.validar(["CENAREC-4", "PAGAR", "CENAREC-195", 7, "SIN_COBERTURA:"])
        self.assertFalse(r["valida"])
        self.assertEqual([e["posicion"] for e in r["errores"]], [0, 1, 3, 4])

    def test_validar_rechaza_estructura(self):
        for secuencia in [[], "CENAREC-195", ["CENAREC-195"] * 61]:
            with self.subTest(n=len(secuencia)), self.assertRaises(ErrorEntrada):
                self.lex.validar(secuencia)


if __name__ == "__main__":
    unittest.main()
