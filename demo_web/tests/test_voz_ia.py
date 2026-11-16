"""Pruebas de «Voz con IA real» (fase 2) SIN llamadas pagadas.

Todas las ejecuciones usan la API FALSA local (tests/api_falsa.py) o el modo sin clave del ejecutor. La única
prueba con la configuración de producción (clave en el entorno) nunca autoriza una ejecución y además
impide lanzar el proceso hijo.

    python -m unittest discover -s demo_web/tests -v
"""

import json
import os
import sys
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

AQUI = Path(__file__).resolve().parent
DEMO = AQUI.parent
RAIZ = DEMO.parent
sys.path.insert(0, str(DEMO))
sys.path.insert(0, str(AQUI))

import api_falsa  # noqa: E402
import servidor_demo as sd  # noqa: E402
import voz_ia  # noqa: E402
from test_demo_web import BaseServidor  # noqa: E402

TEXTO = "El banco cierra a las cuatro."


class BaseIA(BaseServidor):
    MODO_API = "ok"              # modo de la API falsa; None = sin API falsa
    API_PRUEBA = "local"         # "local" | "sin_clave" | None (deshabilitada)

    def setUp(self):
        self.falsa = api_falsa.iniciar(self.MODO_API) if self.API_PRUEBA == "local" else None
        prueba = ("local", self.falsa.server_address[1]) if self.API_PRUEBA == "local" else \
            "sin_clave" if self.API_PRUEBA == "sin_clave" else None
        self.srv = sd.crear_servidor(0, silencioso=True, espera_aprobacion_s=30,
                                     permitir_api=prueba is not None, api_prueba=prueba)
        self.ia = self.srv.voz_ia
        self.puerto = self.srv.server_address[1]
        self._espera = mock.patch.object(voz_ia, "ESPERA_MINIMA_S", 0)   # su prueba específica la restablece
        self._espera.start()
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def tearDown(self):
        self._espera.stop()
        self.ia.cerrar()
        super().tearDown()
        if self.falsa:
            self.falsa.shutdown()
            self.falsa.server_close()

    def pedir(self, metodo, ruta, cuerpo=None, cabeceras=None, crudo=None):
        # La interfaz legítima envía Origin propio y la cabecera X-Lesco-Demo en las acciones con costo.
        if metodo == "POST" and ruta.startswith("/api/voz-ia/") and cabeceras is None:
            cabeceras = {"Origin": f"http://127.0.0.1:{self.puerto}", "X-Lesco-Demo": "1"}
        return super().pedir(metodo, ruta, cuerpo, cabeceras, crudo)

    def esperar_ia(self, *estados, limite=60):
        fin = time.time() + limite
        while time.time() < fin:
            _, d = self.json("GET", "/api/voz-ia")
            if d["estado"] in estados:
                return d
            time.sleep(0.1)
        self.fail(f"la IA no llegó a {estados}; último estado: {d['estado']} · error: {d.get('error')}")

    def preparar(self, texto=TEXTO):
        estado, d = self.json("POST", "/api/voz-ia/preparar", {"texto": texto})
        self.assertEqual(estado, 200, d)
        return d["token"]

    def ejecutar(self, aprobar=True):
        token = self.preparar()
        estado, d = self.json("POST", "/api/voz-ia/autorizar", {"token": token})
        self.assertEqual(estado, 202, d)
        d = self.esperar_ia("esperando_aprobacion", "terminada", "error")
        if d["estado"] == "esperando_aprobacion":
            self.assertEqual(self.json("POST", "/api/voz-ia/aprobacion", {"aprobar": aprobar})[0], 200)
            d = self.esperar_ia("terminada", "error")
        return d


class TestIADeshabilitadaPorDefecto(BaseIA):
    API_PRUEBA = None

    def test_sin_permitir_api_no_hay_nada_que_autorizar(self):
        _, d = self.json("GET", "/api/voz-ia")
        self.assertFalse(d["habilitada"])
        self.assertFalse(self.json("GET", "/api/info")[1]["ia_real"]["habilitada"])
        self.assertEqual(self.json("POST", "/api/voz-ia/preparar", {"texto": TEXTO})[0], 403)
        self.assertEqual(self.json("POST", "/api/voz-ia/autorizar", {"token": "x" * 32})[0], 403)
        self.assertEqual((self.ia.usadas, self.ia.lanzados), (0, 0))


class TestConsentimientoYLimites(BaseIA):
    def test_preparar_no_llama_a_la_api(self):
        _, d = self.json("POST", "/api/voz-ia/preparar", {"texto": TEXTO})
        time.sleep(0.5)
        self.assertEqual((self.falsa.solicitudes, self.ia.lanzados, self.ia.usadas), (0, 0, 0))
        self.assertEqual(d["restantes"], 5)
        self.assertIn("no es un tope garantizado", d["estimacion"]["nota"])
        self.assertAlmostEqual(d["estimacion"]["media_usd"], 0.0635, places=3)

    def test_permiso_falso_vencido_o_reutilizado(self):
        self.preparar()
        self.assertEqual(self.json("POST", "/api/voz-ia/autorizar", {"token": "x" * 32})[0], 403)
        # el intento fallido también consume el permiso: hay que volver a preparar
        token = self.preparar()
        with mock.patch.object(voz_ia, "VIGENCIA_PERMISO_S", -1):
            token = self.preparar()
        self.assertEqual(self.json("POST", "/api/voz-ia/autorizar", {"token": token})[0], 403)   # vencido
        token = self.preparar()
        self.json("POST", "/api/voz-ia/cancelar", {})
        self.assertEqual(self.json("POST", "/api/voz-ia/autorizar", {"token": token})[0], 403)   # cancelado
        self.assertEqual((self.falsa.solicitudes, self.ia.lanzados, self.ia.usadas), (0, 0, 0))

    def test_cuerpos_no_validos(self):
        for ruta, cuerpo in (("/api/voz-ia/preparar", {"texto": TEXTO, "autorizar": True}),
                             ("/api/voz-ia/preparar", {"texto": "firme; del *"}),
                             ("/api/voz-ia/autorizar", {"token": "x", "texto": TEXTO}),
                             ("/api/voz-ia/autorizar", {"token": 5}),
                             ("/api/voz-ia/autorizar", {"token": "x" * 100}),
                             ("/api/voz-ia/cancelar", {"x": 1})):
            self.assertEqual(self.json("POST", ruta, cuerpo)[0], 400, (ruta, cuerpo))
        self.assertEqual(self.pedir("POST", "/api/voz-ia/preparar", crudo=json.dumps({"texto": "a" * 3000}))[0], 413)
        self.assertEqual(self.json("POST", "/api/voz-ia/aprobacion", {"aprobar": True})[0], 409)
        self.assertEqual(self.falsa.solicitudes, 0)

    def test_maximo_cinco_por_sesion(self):
        self.ia.usadas = 5
        self.assertEqual(self.json("POST", "/api/voz-ia/preparar", {"texto": TEXTO})[0], 429)
        self.ia.usadas = 4
        token = self.preparar()
        self.ia.usadas = 5                                 # se agotó entre preparar y autorizar
        self.assertEqual(self.json("POST", "/api/voz-ia/autorizar", {"token": token})[0], 429)
        self.assertEqual(self.falsa.solicitudes, 0)

    def test_una_ejecucion_a_la_vez(self):
        self.assertEqual(self.json("POST", "/api/simulacion/iniciar", {})[0], 202)
        self.esperar_estado("esperando_aprobacion")
        token = self.preparar()
        self.assertEqual(self.json("POST", "/api/voz-ia/autorizar", {"token": token})[0], 409)
        self.assertEqual((self.ia.usadas, self.falsa.solicitudes), (0, 0))
        self.json("POST", "/api/simulacion/aprobacion", {"aprobar": False})


class TestFlujoConApiFalsa(BaseIA):
    def test_flujo_completo(self):
        d = self.ejecutar(aprobar=True)
        self.assertEqual(d["estado"], "terminada", d.get("error"))
        ini = d["eventos"][0]
        self.assertEqual((ini["modelo"], ini["configuracion"]), ("claude-sonnet-5-5", "voz-ia"))
        self.assertEqual(ini["instrucciones"], ["agente/instrucciones_genericas.md", "skill/SKILL.md"])
        self.assertEqual(ini["limites"], {"max_pasos": 10, "presupuesto_tokens": 60000, "max_tokens_por_respuesta": 4000})
        self.assertEqual(ini["politica"], "politica/politica_demo.json")
        self.assertEqual(d["guardado"]["glosas"], ["BANCO", "SIN_COBERTURA:cierra", "CUATRO"])  # respuestas de la API falsa
        g = [e for e in d["eventos"] if e["tipo"] == "herramienta" and e["nombre"].endswith("guardar_resultado")]
        self.assertEqual((len(g), g[0]["decision"]), (1, "permitir"))
        self.assertIn("botón «Aprobar guardado»", g[0]["razon"])
        self.assertEqual(self.falsa.claves, {"clave-de-prueba-local"})   # nunca una clave real
        self.assertEqual(self.falsa.modelos, {"claude-sonnet-5-5"})
        self.assertEqual((d["usadas"], d["restantes"], self.ia.lanzados), (1, 4, 1))
        self.assertGreater(d["costo_estimado_usd"], 0)
        self.assertEqual(d["modo_prueba"], "api_local")
        # el servidor web sigue sin poder llamar a la API
        with self.assertRaises(OSError):
            urllib.request.urlopen("https://api.anthropic.com/v1/messages")

    def test_rechazo_no_guarda(self):
        d = self.ejecutar(aprobar=False)
        g = [e for e in d["eventos"] if e["tipo"] == "herramienta" and e["nombre"].endswith("guardar_resultado")]
        self.assertTrue(g and all(x["decision"] == "denegar" for x in g))
        self.assertIn("rechazada desde la interfaz", g[0]["razon"])
        self.assertIsNone(d["guardado"])

    def test_cerrar_detiene_el_proceso_y_limpia(self):
        token = self.preparar()
        self.json("POST", "/api/voz-ia/autorizar", {"token": token})
        self.esperar_ia("esperando_aprobacion")
        carpeta, proceso = self.ia.carpeta, self.ia.proceso
        self.assertNotIn(RAIZ.resolve(), carpeta.resolve().parents)
        self.ia.cerrar()
        self.assertIsNotNone(proceso.poll())
        self.assertFalse(carpeta.exists())


class TestErrorSinReintentos(BaseIA):
    MODO_API = "error500"

    def test_un_error_500_no_se_reintenta(self):
        d = self.ejecutar()
        self.assertEqual(self.falsa.solicitudes, 1)               # sin reintentos automáticos
        fin = d["eventos"][-1]
        self.assertEqual(fin["tipo"], "fin")
        self.assertIn("500", fin["motivo"])
        self.assertIsNone(d["guardado"])
        self.assertEqual(d["restantes"], 4)                       # la ejecución cuenta aunque falle


class TestErrorSinRevelarSecretos(BaseIA):
    MODO_API = "error401"

    def test_texto_con_forma_de_clave_se_oculta(self):
        self.ejecutar()
        _, texto, _ = self.pedir("GET", "/api/voz-ia")
        self.assertNotIn(api_falsa.CLAVE_FINGIDA, texto)
        self.assertIn("<clave oculta>", texto)
        self.assertIn("401", texto)


class TestCredencialesInexistentes(BaseIA):
    API_PRUEBA = "sin_clave"

    def test_sin_clave_se_detiene_e_informa(self):
        d = self.ejecutar()
        self.assertIn("Falta ANTHROPIC_API_KEY", d["eventos"][-1]["motivo"])
        self.assertIsNone(d["guardado"])
        self.assertEqual(len([e for e in d["eventos"] if e["tipo"] == "respuesta_modelo"]), 0)


class TestAislamientoDeLaClave(unittest.TestCase):
    def test_produccion_la_clave_solo_va_al_entorno_del_hijo(self):
        ficticia = "sk" + "-" + "ant" + "-" + "solo" + "-" + "prueba" + "-" + "1234"
        anterior = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = ficticia
        try:
            with mock.patch.object(voz_ia.VozIA, "_correr", side_effect=AssertionError("no debe lanzarse")):
                srv = sd.crear_servidor(0, silencioso=True, permitir_api=True)
            try:
                self.assertNotIn("ANTHROPIC_API_KEY", os.environ)            # fuera del proceso web
                self.assertEqual(srv.voz_ia.entorno()["ANTHROPIC_API_KEY"], ficticia)   # solo para el hijo
                srv.voz_ia.caso_id, srv.voz_ia.carpeta = "vozia-001", Path("x")
                self.assertFalse([c for c in srv.voz_ia.comando() if c.startswith("--prueba")])
                self.assertNotIn(ficticia, json.dumps(srv.voz_ia.instantanea()))
                with self.assertRaises(sd.agente.ErrorModelo):
                    sd.agente.ModeloClaude("claude-sonnet-5-5", 10)
                with self.assertRaises(OSError):
                    urllib.request.urlopen("https://api.anthropic.com/v1/messages")
            finally:
                srv.server_close()
        finally:
            os.environ.pop("ANTHROPIC_API_KEY", None)
            if anterior is not None:
                os.environ["ANTHROPIC_API_KEY"] = anterior

    def test_modos_de_prueba_nunca_pasan_la_clave(self):
        ia = voz_ia.VozIA(sd.Limpiador(), threading.Lock(), habilitada=True,
                          entorno_api={"ANTHROPIC_API_KEY": "no-debe-pasar"}, modo_prueba=("local", 1))
        self.assertNotIn("ANTHROPIC_API_KEY", ia.entorno())
        ia.caso_id, ia.carpeta = "vozia-001", Path("x")
        self.assertIn("--prueba-api-local", ia.comando())

    def test_api_prueba_exige_permitir_api(self):
        with self.assertRaises(ValueError):
            sd.crear_servidor(0, silencioso=True, api_prueba="sin_clave")


class TestInterfazIA(unittest.TestCase):
    JS = (DEMO / "web" / "voz.js").read_text(encoding="utf-8")
    HTML = " ".join((DEMO / "web" / "index.html").read_text(encoding="utf-8").split())

    def test_solo_un_clic_autoriza(self):
        self.assertEqual(self.JS.count("/api/voz-ia/autorizar"), 1)
        self.assertEqual(self.JS.count("autorizarIA"), 2)                  # definición + clic del botón
        self.assertIn('$("btn-autorizar-ia").addEventListener("click", autorizarIA)', self.JS)
        self.assertIn('if (ev.key === "Enter") { ev.preventDefault(); iniciarVoz(); }', self.JS)   # Enter solo prepara
        self.assertIn("Autorizar esta ejecución (con costo)", self.HTML)
        self.assertIn('id="btn-motor-ia" type="button" aria-pressed="false" disabled', self.HTML)

    def test_estimacion_y_tiempos_rotulados(self):
        self.assertIn("Es una estimación, no un tope garantizado", self.JS)
        self.assertIn("no es el tiempo real", self.JS)


if __name__ == "__main__":
    unittest.main()
