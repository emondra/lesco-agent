"""Pruebas de extremo a extremo: el servidor MCP real, hablado por stdio con el cliente del agente."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "agente"))

from mcp_cliente import ClienteMCP, ErrorMCP  # noqa: E402


class TestServidorMCP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.salidas = Path(tempfile.mkdtemp(prefix="lesco_salidas_"))
        cls.cli = ClienteMCP("lesco", [sys.executable, "mcp_server/servidor_lesco.py",
                                       "--salidas", str(cls.salidas)], cwd=str(RAIZ))
        cls.info = cls.cli.iniciar()

    @classmethod
    def tearDownClass(cls):
        cls.cli.cerrar()
        shutil.rmtree(cls.salidas, ignore_errors=True)

    def llamar(self, nombre, args):
        texto, es_error = self.cli.llamar(nombre, args)
        return (texto if es_error else json.loads(texto)), es_error

    def test_inicializacion(self):
        self.assertEqual(self.info["serverInfo"]["name"], "lesco-cenarec")
        self.assertIn("tools", self.info["capabilities"])

    def test_catalogo_con_esquemas_estrictos(self):
        herramientas = {h["name"]: h for h in self.cli.listar_herramientas()}
        self.assertEqual(set(herramientas), {"buscar_sena", "validar_secuencia", "guardar_resultado"})
        for h in herramientas.values():
            self.assertFalse(h["inputSchema"]["additionalProperties"])
            self.assertIn("Úsela", h["description"])

    def test_buscar(self):
        datos, es_error = self.llamar("buscar_sena", {"texto": "pagar"})
        self.assertFalse(es_error)
        self.assertEqual(datos["resultados"][0]["id"], "CENAREC-195")

    def test_argumento_no_permitido(self):
        texto, es_error = self.llamar("buscar_sena", {"texto": "pagar", "ruta": "/etc"})
        self.assertTrue(es_error)
        self.assertIn("argumentos no permitidos", texto)

    def test_argumento_faltante(self):
        texto, es_error = self.llamar("validar_secuencia", {})
        self.assertTrue(es_error)
        self.assertIn("faltan argumentos obligatorios", texto)

    def test_guardar_una_sola_vez(self):
        args = {"caso_id": "prueba-001", "texto_fuente": "Debe pagar en la fila.",
                "secuencia": ["CENAREC-296", "CENAREC-195", "CENAREC-318"]}
        datos, es_error = self.llamar("guardar_resultado", args)
        self.assertFalse(es_error, datos)
        guardado = json.loads((self.salidas / "prueba-001.json").read_text(encoding="utf-8"))
        self.assertEqual(guardado["glosas"], ["DEBER", "PAGAR", "FILA"])
        texto, es_error = self.llamar("guardar_resultado", args)
        self.assertTrue(es_error)
        self.assertIn("no se sobrescribe", texto)

    def test_guardar_rechaza_ids_inventados(self):
        args = {"caso_id": "prueba-002", "texto_fuente": "Traiga la cédula.",
                "secuencia": ["CENAREC-380", "CENAREC-99999"]}
        texto, es_error = self.llamar("guardar_resultado", args)
        self.assertTrue(es_error)
        self.assertIn("no existe en el diccionario", texto)
        self.assertFalse((self.salidas / "prueba-002.json").exists())

    def test_guardar_rechaza_rutas(self):
        for caso in ["../fuera", "a/b", "C:\\x", ".oculto", "x" * 41]:
            with self.subTest(caso=caso):
                texto, es_error = self.llamar("guardar_resultado", {
                    "caso_id": caso, "texto_fuente": "Hola.", "secuencia": ["CENAREC-1479"]})
                self.assertTrue(es_error)
                self.assertIn("'caso_id' inválido", texto)
        self.assertEqual([p.name for p in self.salidas.parent.glob("fuera*")], [])

    def test_herramienta_desconocida(self):
        texto, es_error = self.llamar("borrar_todo", {})
        self.assertTrue(es_error)
        self.assertIn("Herramienta desconocida", texto)

    def test_metodo_desconocido(self):
        with self.assertRaises(ErrorMCP):
            self.cli._pedir("resources/list")


if __name__ == "__main__":
    unittest.main()
