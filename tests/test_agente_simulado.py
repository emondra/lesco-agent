"""El agente completo (bucle, política, servidor MCP y traza) con el modelo simulado: sin clave ni costo."""

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "agente"))

import agente  # noqa: E402
import leer_traza  # noqa: E402


class TestAgenteSimulado(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lesco_agente_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ejecutar(self, config):
        args = agente.argumentos(["--config", str(RAIZ / "agente" / "configs" / config), "--simulado",
                                  "--auto-aprobar", "--caso", "demo-001",
                                  "--casos", str(RAIZ / "eval" / "demo" / "casos_demo.jsonl"),
                                  "--salidas", str(self.tmp / "salidas"), "--trazas", str(self.tmp / "trazas")])
        with redirect_stdout(io.StringIO()):
            return agente.ejecutar(args)

    def test_extremo_a_extremo_con_traza(self):
        resultado = self.ejecutar("B.json")
        self.assertEqual(resultado["codigo"], 0, resultado["motivo"])

        guardado = json.loads((self.tmp / "salidas" / "demo-001.json").read_text(encoding="utf-8"))
        self.assertEqual(guardado["glosas"], ["DEBER", "FIRMAR", "FACTURA", "ESPERAR", "FILA"])

        r = leer_traza.leer(resultado["traza"])
        self.assertEqual((r["configuracion"], r["caso_id"]), ("B", "demo-001"))
        self.assertEqual(r["escrituras"], 1)
        self.assertEqual(r["denegadas"], 1)            # el segundo guardado lo bloquea la política
        self.assertTrue(r["terminó_bien"])

        eventos = [json.loads(l) for l in resultado["traza"].read_text(encoding="utf-8").splitlines()]
        inicio = eventos[0]
        self.assertEqual(inicio["instrucciones"], ["agente/instrucciones_genericas.md", "skill/SKILL.md"])
        self.assertEqual(len(inicio["sha256_instrucciones"]), 64)
        denegada = [e for e in eventos if e["tipo"] == "herramienta" and e["decision"] == "denegar"][0]
        self.assertIn("máximo de 1 llamadas", denegada["razon"])

    def test_a_y_b_solo_difieren_en_instrucciones(self):
        a = json.loads((RAIZ / "agente" / "configs" / "A.json").read_text(encoding="utf-8"))
        b = json.loads((RAIZ / "agente" / "configs" / "B.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(k for k in a if a[k] != b[k]), ["descripcion", "instrucciones", "nombre"])
        self.assertEqual(b["instrucciones"][:len(a["instrucciones"])], a["instrucciones"])

    def test_cabecera_de_workspace_opcional(self):
        import os
        original = os.environ.pop("ANTHROPIC_WORKSPACE_ID", None)
        try:
            if not (RAIZ / ".env").exists():
                self.assertNotIn("anthropic-workspace-id", agente.cabeceras_api("x"))
            os.environ["ANTHROPIC_WORKSPACE_ID"] = "wrkspc_prueba"
            self.assertEqual(agente.cabeceras_api("x")["anthropic-workspace-id"], "wrkspc_prueba")
        finally:
            os.environ.pop("ANTHROPIC_WORKSPACE_ID", None)
            if original is not None:
                os.environ["ANTHROPIC_WORKSPACE_ID"] = original

    def test_sin_clave_termina_con_traza(self):
        args = agente.argumentos(["--config", str(RAIZ / "agente" / "configs" / "A.json"),
                                  "--caso", "demo-001", "--casos", str(RAIZ / "eval" / "demo" / "casos_demo.jsonl"),
                                  "--salidas", str(self.tmp / "salidas"), "--trazas", str(self.tmp / "trazas")])
        original = agente.cargar_clave
        agente.cargar_clave = lambda: None
        try:
            with redirect_stdout(io.StringIO()):
                resultado = agente.ejecutar(args)
        finally:
            agente.cargar_clave = original
        self.assertEqual(resultado["codigo"], 2)
        self.assertIn("Falta ANTHROPIC_API_KEY", leer_traza.leer(resultado["traza"])["motivo"])


if __name__ == "__main__":
    unittest.main()
