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


if __name__ == "__main__":
    unittest.main()
