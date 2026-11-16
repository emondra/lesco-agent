"""Pruebas del Visor de señas CENAREC (capa de presentación). No contactan a CENAREC: usan el modo «prueba»,
que sirve una página LOCAL de sustitución.

    python -m unittest discover -s demo_web/tests -v
"""

import json
import re
import sys
import threading
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DEMO = AQUI.parent
RAIZ = DEMO.parent
sys.path.insert(0, str(DEMO))
sys.path.insert(0, str(AQUI))

import servidor_demo as sd  # noqa: E402
from test_demo_web import BaseServidor  # noqa: E402

JS = (DEMO / "web" / "visor_cenarec.js").read_text(encoding="utf-8")
HTML = " ".join((DEMO / "web" / "index.html").read_text(encoding="utf-8").split())


class BaseVisor(BaseServidor):
    VISOR = "desactivado"

    def setUp(self):
        self.srv = sd.crear_servidor(0, silencioso=True, espera_aprobacion_s=30, visor=self.VISOR)
        self.puerto = self.srv.server_address[1]
        self.hilo = threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.hilo.start()

    def csp(self, ruta="/"):
        _, _, h = self.pedir("GET", ruta)
        return h["Content-Security-Policy"], h["Permissions-Policy"], h.get("X-Frame-Options")


class TestVisorDesactivadoPorDefecto(BaseVisor):
    def test_sin_marcos_de_otro_origen_ni_pagina_de_prueba(self):
        csp, permisos, xfo = self.csp()
        self.assertNotIn("frame-src", csp)
        self.assertNotIn("cenarec", csp + permisos)
        self.assertEqual(xfo, "DENY")
        self.assertEqual(self.json("GET", "/api/info")[1]["visor_cenarec"], {"modo": "desactivado", "base": None})
        self.assertEqual(self.pedir("GET", "/prueba_cenarec/DiccLESCO.php?idw=325")[0], 404)

    def test_crear_servidor_rechaza_modos_desconocidos(self):
        with self.assertRaises(ValueError):
            sd.crear_servidor(0, silencioso=True, visor="https://otro.example")


class TestVisorOficial(BaseVisor):
    VISOR = "oficial"

    def test_solo_el_dominio_oficial_en_frame_src(self):
        csp, permisos, xfo = self.csp()
        marcos = re.findall(r"frame-src ([^;]+)", csp)
        self.assertEqual(marcos, ["https://lesco.cenarec.go.cr"])
        self.assertIn("default-src 'self'", csp)
        self.assertIn('autoplay=(self "https://lesco.cenarec.go.cr")', permisos)
        self.assertIn("microphone=(self)", permisos)
        self.assertEqual(xfo, "DENY")                     # la demo misma sigue sin poder incrustarse

    def test_base_oficial_exacta_y_sin_pagina_de_prueba(self):
        v = self.json("GET", "/api/info")[1]["visor_cenarec"]
        self.assertEqual(v, {"modo": "oficial", "base": "https://lesco.cenarec.go.cr/DiccLESCO.php"})
        self.assertEqual(self.pedir("GET", "/prueba_cenarec/DiccLESCO.php?idw=325")[0], 404)


class TestVisorPrueba(BaseVisor):
    VISOR = "prueba"

    def test_pagina_local_de_prueba(self):
        estado, texto, h = self.pedir("GET", "/prueba_cenarec/DiccLESCO.php?idw=325")
        self.assertEqual(estado, 200)
        self.assertIn("PÁGINA DE PRUEBA LOCAL — NO ES CONTENIDO DE CENAREC", texto)
        self.assertIn("FIRMAR", texto)
        self.assertNotIn("<video", texto)
        self.assertNotIn("http", texto)                    # no enlaza ni carga nada externo
        self.assertEqual(h["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", h["Content-Security-Policy"])
        csp, _, xfo = self.csp()
        self.assertEqual(re.findall(r"frame-src ([^;]+)", csp), ["'self'"])
        self.assertEqual(xfo, "DENY")

    def test_solo_ids_enteros_del_indice(self):
        for consulta in ("idw=0", "idw=-1", "idw=abc", "idw=99999", "idw=325&x=1", "idw=325&idw=1",
                         "idw=325%0a", "idw=../../.env", "idw=", "x=325", "idw=00325"):
            self.assertEqual(self.pedir("GET", f"/prueba_cenarec/DiccLESCO.php?{consulta}")[0], 404, consulta)

    def test_glosa_escapada(self):
        self.srv.glosas[99998] = "<script>alert(1)</script>"
        _, texto, _ = self.pedir("GET", "/prueba_cenarec/DiccLESCO.php?idw=99998")
        self.assertNotIn("<script>", texto)
        self.assertIn("&lt;script&gt;", texto)


class TestInterfazDelVisor(unittest.TestCase):
    def test_textos_obligatorios_y_controles(self):
        self.assertIn("Visor de señas CENAREC", HTML)
        self.assertIn("Fuente: Diccionario LESCO, CENAREC", HTML)
        self.assertIn("La sucesión de entradas del diccionario no constituye una traducción gramatical validada a LESCO", HTML)
        self.assertIn("▶ Ver señas CENAREC", HTML)
        for ident in ("btn-ver-senas", "btn-visor-cerrar", "btn-sena-anterior", "btn-sena-siguiente"):
            self.assertIn(f'id="{ident}"', HTML)
            self.assertIn(f'$("{ident}").addEventListener', JS)
        self.assertIn('id="visor-enlace"', HTML)          # «Abrir página oficial»

    def test_sin_iframe_hasta_que_se_pide(self):
        self.assertNotIn("<iframe", HTML)                 # el marco solo lo crea mostrarEntrada()
        self.assertEqual(JS.count('el("iframe"'), 1)

    def test_direccion_solo_desde_la_evidencia_validada(self):
        self.assertIn(r"/^https:\/\/lesco\.cenarec\.go\.cr\/DiccLESCO\.php\?idw=([1-9]\d{0,4})$/", JS)
        self.assertIn("d.elementos && d.validada", JS)
        self.assertIn("Number(idw)", JS)
        self.assertNotIn("texto-voz", JS)                 # nunca lee lo que escribe o dicta el usuario
        self.assertNotIn("innerHTML", JS)
        self.assertNotIn("eval(", JS)

    def test_sin_reproduccion_automatica_ni_duraciones(self):
        for prohibido in ("setInterval", "setTimeout", ".play(", "duration", "ended", ".mp4"):
            self.assertNotIn(prohibido, JS, prohibido)

    def test_no_afirma_carga_verificada(self):
        self.assertIn("no puede verificar", JS)
        self.assertNotRegex(JS, r"(?i)video (cargado|cargó correctamente)")


if __name__ == "__main__":
    unittest.main()
