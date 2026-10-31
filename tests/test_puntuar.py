import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "eval"))
sys.path.insert(0, str(RAIZ / "agente"))

import agente  # noqa: E402
from construir_referencia import adjudicar, motivos_de, secuencia  # noqa: E402
from puntuar import agregar, diferencia_pareada, evaluar, puntuar_caso  # noqa: E402


class TestPuntuarCaso(unittest.TestCase):
    def test_identica(self):
        r = puntuar_caso(["CENAREC-1", "SIN_COBERTURA:cédula"], ["CENAREC-1", "SIN_COBERTURA:cedula"])
        self.assertEqual((r["exacta"], r["f1"], r["sin_cobertura_ok"]), (1.0, 1.0, 1.0))

    def test_orden_distinto_no_es_exacta_pero_f1_completo(self):
        r = puntuar_caso(["CENAREC-2", "CENAREC-1"], ["CENAREC-1", "CENAREC-2"])
        self.assertEqual((r["exacta"], r["f1"]), (0.0, 1.0))

    def test_parcial_con_multiconjuntos(self):
        r = puntuar_caso(["CENAREC-1", "CENAREC-1", "CENAREC-9"], ["CENAREC-1", "CENAREC-2"])
        self.assertAlmostEqual(r["precision"], 1 / 3)
        self.assertAlmostEqual(r["exhaustividad"], 1 / 2)
        self.assertAlmostEqual(r["f1"], 0.4)

    def test_no_guardado(self):
        r = puntuar_caso(None, ["CENAREC-1"])
        self.assertEqual((r["guardado"], r["f1"], r["exacta"]), (0.0, 0.0, 0.0))
        self.assertIsNone(r["sin_cobertura_ok"])


class TestReferencia(unittest.TestCase):
    filas = [{"caso_id": "c", "pos": 0, "palabra": "Espere", "etiqueta": "CENAREC-666"},
             {"caso_id": "c", "pos": 1, "palabra": "por", "etiqueta": "CENAREC-1482"},
             {"caso_id": "c", "pos": 2, "palabra": "favor", "etiqueta": "+"},
             {"caso_id": "c", "pos": 3, "palabra": "cédula", "etiqueta": "SIN_COBERTURA"},
             {"caso_id": "c", "pos": 4, "palabra": "la", "etiqueta": "OMITIR"}]

    def test_secuencia_y_motivos(self):
        self.assertEqual(secuencia(self.filas), ["CENAREC-666", "CENAREC-1482", "SIN_COBERTURA:cédula"])
        self.assertEqual(motivos_de(self.filas, ["sinonimo", "otro"]), ["multipalabra", "sin_cobertura", "sinonimo"])

    def test_adjudicacion_exige_decision(self):
        a1 = [{"caso_id": "c", "pos": 0, "etiqueta": "CENAREC-1"}]
        a2 = [{"caso_id": "c", "pos": 0, "etiqueta": "CENAREC-2"}]
        with self.assertRaises(SystemExit):
            adjudicar(a1, a2, [])
        final = adjudicar(a1, a2, [{"caso_id": "c", "pos": "0", "decision": "CENAREC-2"}])
        self.assertEqual(final[0]["etiqueta"], "CENAREC-2")


class TestAgregacion(unittest.TestCase):
    def test_diferencia_pareada_determinista(self):
        filas = [{"caso_id": f"c{i}", "configuracion": cfg, "repeticion": "rep1", "f1": v}
                 for i in range(10) for cfg, v in (("A", 0.5), ("B", 0.7))]
        d1, d2 = diferencia_pareada(filas, "f1"), diferencia_pareada(filas, "f1")
        self.assertAlmostEqual(d1["media"], 0.2)
        self.assertEqual(d1, d2)

    def test_media_y_de_entre_repeticiones(self):
        filas = [{"caso_id": "c1", "configuracion": "A", "repeticion": r, "dificultad": "normal", "f1": v}
                 for r, v in (("rep1", 0.4), ("rep2", 0.6), ("rep3", 0.8))]
        media, de, n = agregar(filas, ["f1"])["A"]["f1"]
        self.assertAlmostEqual(media, 0.6)
        self.assertAlmostEqual(de, 0.2)
        self.assertEqual(n, 1)


class TestDeExtremoAExtremo(unittest.TestCase):
    """Trazas reales del agente (modelo simulado) → puntuación."""

    def test_evaluar_desde_trazas(self):
        tmp = Path(tempfile.mkdtemp(prefix="lesco_puntuar_"))
        try:
            for cfg in ("A", "B"):
                args = agente.argumentos([
                    "--config", str(RAIZ / "agente" / "configs" / f"{cfg}.json"), "--simulado", "--caso", "demo-001",
                    "--casos", str(RAIZ / "eval" / "demo" / "casos_demo.jsonl"),
                    "--salidas", str(tmp / "resultados" / "x" / cfg / "rep1"),
                    "--trazas", str(tmp / "trazas" / "x" / cfg / "rep1"), "--repeticion", "1"])
                with redirect_stdout(io.StringIO()):
                    agente.ejecutar(args)
            ref = {"demo-001": {"dificultad": "normal",
                                "secuencia": ["CENAREC-296", "CENAREC-325", "CENAREC-324", "CENAREC-666", "CENAREC-318"]}}
            filas = evaluar("x", ref, raiz=tmp)
            self.assertEqual(len(filas), 2)
            for f in filas:
                self.assertEqual((f["exacta"], f["f1"], f["guardado"]), (1.0, 1.0, 1.0))
                self.assertEqual(f["denegadas"], 1)
                self.assertIsNone(f["costo_usd"])      # modelo "simulado": sin precio
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
