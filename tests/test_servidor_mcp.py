"""Pruebas de extremo a extremo: el servidor MCP real, hablado por stdio con el cliente del agente."""

import json
import os
import shutil
import subprocess
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
        casos = cls.salidas.parent / f"{cls.salidas.name}_casos.jsonl"
        casos.write_text(json.dumps({"caso_id": "c1", "texto": "Debe pagar en la caja.",
                                     "referencia": ["CENAREC-296"]}, ensure_ascii=False) + "\n",
                         encoding="utf-8")
        cls.casos = casos
        cls.cli = ClienteMCP("lesco", [sys.executable, "mcp_server/servidor_lesco.py",
                                       "--salidas", str(cls.salidas), "--casos", str(casos)], cwd=str(RAIZ))
        cls.info = cls.cli.iniciar()

    @classmethod
    def tearDownClass(cls):
        cls.cli.cerrar()
        shutil.rmtree(cls.salidas, ignore_errors=True)
        cls.casos.unlink(missing_ok=True)

    def llamar(self, nombre, args):
        texto, es_error = self.cli.llamar(nombre, args)
        return (texto if es_error else json.loads(texto)), es_error

    def test_inicializacion(self):
        self.assertEqual(self.info["serverInfo"]["name"], "lesco-cenarec")
        self.assertIn("tools", self.info["capabilities"])

    def test_catalogo_con_esquemas_estrictos(self):
        herramientas = {h["name"]: h for h in self.cli.listar_herramientas()}
        self.assertEqual(set(herramientas), {"obtener_transcripcion", "buscar_sena",
                                             "validar_secuencia", "guardar_resultado"})
        for h in herramientas.values():
            self.assertFalse(h["inputSchema"]["additionalProperties"])
            self.assertIn("Úsela", h["description"])

    def test_transcripcion_sin_etiquetas_de_referencia(self):
        datos, es_error = self.llamar("obtener_transcripcion", {"caso_id": "c1"})
        self.assertFalse(es_error)
        self.assertEqual(datos, {"caso_id": "c1", "transcripcion": "Debe pagar en la caja."})

    def test_transcripcion_de_caso_inexistente(self):
        texto, es_error = self.llamar("obtener_transcripcion", {"caso_id": "c999"})
        self.assertTrue(es_error)
        self.assertIn("no hay transcripción", texto)

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


class TestServidorVinculado(unittest.TestCase):
    """Modo vinculado (--caso): el servidor solo entrega y guarda el caso autorizado al iniciar."""

    TEXTOS = {"c1": "Debe pagar en la caja.", "c2": "Necesita firmar la factura."}

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="lesco_vinculado_"))
        cls.casos = cls.tmp / "casos.jsonl"
        cls.casos.write_text("".join(json.dumps({"caso_id": c, "texto": t}, ensure_ascii=False) + "\n"
                                     for c, t in cls.TEXTOS.items()), encoding="utf-8")
        cls.salidas = cls.tmp / "salidas"
        cls.cli = ClienteMCP("lesco", [sys.executable, "mcp_server/servidor_lesco.py",
                                       "--casos", str(cls.casos), "--caso", "c1",
                                       "--salidas", str(cls.salidas)], cwd=str(RAIZ))
        cls.cli.iniciar()

    @classmethod
    def tearDownClass(cls):
        cls.cli.cerrar()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def llamar(self, nombre, args):
        texto, es_error = self.cli.llamar(nombre, args)
        return (texto if es_error else json.loads(texto)), es_error

    def guardar(self, caso_id):
        return self.llamar("guardar_resultado", {"caso_id": caso_id, "texto_fuente": self.TEXTOS["c1"],
                                                 "secuencia": ["CENAREC-296", "CENAREC-195"]})

    def archivos(self):
        return {p.name for p in self.salidas.glob("*")} if self.salidas.exists() else set()

    def test_p1_guarda_caso_autorizado(self):
        datos, es_error = self.guardar("c1")
        self.assertFalse(es_error, datos)
        self.assertEqual(datos["caso_id"], "c1")
        guardado = json.loads((self.salidas / "c1.json").read_text(encoding="utf-8"))
        self.assertEqual(guardado["glosas"], ["DEBER", "PAGAR"])

    def test_p2_transcripcion_del_caso_autorizado(self):
        datos, es_error = self.llamar("obtener_transcripcion", {"caso_id": "c1"})
        self.assertFalse(es_error)
        self.assertEqual(datos, {"caso_id": "c1", "transcripcion": self.TEXTOS["c1"]})

    def test_n1_rechaza_guardar_otro_caso(self):
        for caso in ("c2", "C1"):   # C1: en Windows sería el mismo archivo que c1.json
            with self.subTest(caso=caso):
                texto, es_error = self.guardar(caso)
                self.assertTrue(es_error)
                self.assertIn("solo puede guardar el caso 'c1'", texto)
                self.assertIn("No se guardó nada", texto)
        self.assertLessEqual(self.archivos(), {"c1.json"})

    def test_n2_rechaza_guardar_caso_inexistente(self):
        texto, es_error = self.guardar("c999")
        self.assertTrue(es_error)
        self.assertIn("solo puede guardar el caso 'c1'", texto)
        self.assertNotIn("c999.json", self.archivos())

    def test_n3_no_entrega_transcripcion_de_otro_caso(self):
        texto, es_error = self.llamar("obtener_transcripcion", {"caso_id": "c2"})
        self.assertTrue(es_error)
        self.assertIn("no hay transcripción para el caso 'c2'", texto)
        self.assertNotIn(self.TEXTOS["c2"], texto)

    def test_n4_no_arranca_con_caso_invalido_o_inexistente(self):
        entorno = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        casos = ["--casos", str(self.casos)]
        situaciones = [
            (casos + ["--caso", "c999"], "no existe en el archivo de casos"),
            (casos + ["--caso", "../x"], "--caso inválido"),
            (casos + ["--caso", ""], "--caso inválido"),
            (casos + ["--caso", "x" * 41], "--caso inválido"),
            (["--caso", "c1"], "--caso exige --casos"),
        ]
        for args, mensaje in situaciones:
            with self.subTest(args=args):
                r = subprocess.run([sys.executable, "mcp_server/servidor_lesco.py", *args,
                                    "--salidas", str(self.tmp / "salidas_n4")],
                                   cwd=str(RAIZ), input="", capture_output=True, text=True,
                                   encoding="utf-8", env=entorno, timeout=30)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn(mensaje, r.stderr)
                self.assertEqual(r.stdout, "")    # no habló el protocolo: no llegó a arrancar
        self.assertFalse((self.tmp / "salidas_n4").exists())

    def test_n5_mantiene_rechazo_de_formato_invalido(self):
        for caso in ["../fuera", "a/b", "C:\\x", ".oculto", "x" * 41, ""]:
            with self.subTest(caso=caso):
                texto, es_error = self.guardar(caso)
                self.assertTrue(es_error)
                self.assertIn("'caso_id' inválido", texto)    # el formato se valida antes que la vinculación
                self.assertNotIn("solo puede guardar", texto)
        self.assertEqual(list(self.tmp.glob("fuera*")), [])


if __name__ == "__main__":
    unittest.main()
