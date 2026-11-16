"""Pruebas del visor web local (demo_web/servidor_demo.py): sin API, solo 127.0.0.1, solo lectura.

    python -m unittest discover -s demo_web/tests -v
"""

import hashlib
import http.client
import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DEMO = AQUI.parent
RAIZ = DEMO.parent
sys.path.insert(0, str(DEMO))

import servidor_demo as sd  # noqa: E402


def huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def huellas_de(carpeta: Path) -> dict[str, str]:
    return {str(p.relative_to(RAIZ)): huella(p) for p in sorted(carpeta.rglob("*")) if p.is_file()}


class BaseServidor(unittest.TestCase):
    ESPERA_APROBACION = 30

    def setUp(self):
        self.srv = sd.crear_servidor(0, silencioso=True, espera_aprobacion_s=self.ESPERA_APROBACION)
        self.puerto = self.srv.server_address[1]
        self.hilo = threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.hilo.start()

    def tearDown(self):
        self.srv.simulacion.cerrar()
        self.srv.shutdown()
        self.srv.server_close()

    def pedir(self, metodo, ruta, cuerpo=None, cabeceras=None, crudo=None):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        h = {"Content-Type": "application/json"} if (cuerpo is not None or crudo is not None) else {}
        h.update(cabeceras or {})
        datos = crudo if crudo is not None else (json.dumps(cuerpo) if cuerpo is not None else None)
        c.request(metodo, ruta, body=datos, headers=h)
        r = c.getresponse()
        texto = r.read().decode("utf-8")
        c.close()
        return r.status, texto, dict(r.getheaders())

    def json(self, metodo, ruta, cuerpo=None, **kw):
        estado, texto, _ = self.pedir(metodo, ruta, cuerpo, **kw)
        return estado, (json.loads(texto) if texto else None)

    def esperar_estado(self, *estados, limite=30):
        fin = time.time() + limite
        while time.time() < fin:
            _, d = self.json("GET", "/api/simulacion")
            if d["estado"] in estados:
                return d
            time.sleep(0.1)
        self.fail(f"la simulación no llegó a {estados}; último estado: {d['estado']}")


class TestSeguridadRed(BaseServidor):
    def test_escucha_solo_en_localhost(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")

    def test_host_ajeno_rechazado(self):
        estado, _, _ = self.pedir("GET", "/api/corridas", cabeceras={"Host": "atacante.example:80"})
        self.assertEqual(estado, 403)

    def test_origen_ajeno_rechazado_en_post(self):
        estado, _, _ = self.pedir("POST", "/api/simulacion/iniciar", {}, cabeceras={"Origin": "http://atacante.example"})
        self.assertEqual(estado, 403)
        self.assertEqual(self.srv.simulacion.estado, "inactiva")

    def test_post_exige_json(self):
        estado, _, _ = self.pedir("POST", "/api/simulacion/iniciar", crudo="{}",
                                  cabeceras={"Content-Type": "text/plain"})
        self.assertEqual(estado, 415)

    def test_metodos_de_escritura_no_permitidos(self):
        for metodo in ("PUT", "DELETE", "PATCH"):
            estado, _, _ = self.pedir(metodo, "/api/corrida?id=experimento/A/rep1/c001")
            self.assertEqual(estado, 405, metodo)

    def test_cabeceras_de_seguridad(self):
        estado, _, h = self.pedir("GET", "/")
        self.assertEqual(estado, 200)
        self.assertIn("default-src 'self'", h["Content-Security-Policy"])
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertEqual(h["X-Frame-Options"], "DENY")


class TestArchivosYRutas(BaseServidor):
    def test_estaticos_de_la_lista_blanca(self):
        for ruta in ("/", "/index.html", "/app.js", "/estilo.css"):
            estado, texto, _ = self.pedir("GET", ruta)
            self.assertEqual(estado, 200, ruta)
            self.assertTrue(texto)

    def test_rutas_arbitrarias_no_se_sirven(self):
        for ruta in ("/../.env", "/..%2f..%2f.env", "/servidor_demo.py", "/web/app.js", "/README.md",
                     "/C:/Windows/win.ini", "//etc/passwd", "/trazas/experimento/A/rep1/x.jsonl"):
            estado, _, _ = self.pedir("GET", ruta)
            self.assertEqual(estado, 404, ruta)

    def test_corrida_solo_por_identificador_del_manifiesto(self):
        for ident in ("../../.env", "experimento/A/rep1/../../../.env", "experimento/C/rep1/c001",
                      "experimento/A/rep1/c999", "trazas/experimento/A/rep1/A_c001_20261114_072445_357974.jsonl", ""):
            estado, _ = self.json("GET", f"/api/corrida?id={urllib.request.quote(ident, safe='')}")
            self.assertEqual(estado, 404, ident)


class TestTrazasReales(BaseServidor):
    def test_288_corridas_formales_sin_la_del_401(self):
        estado, d = self.json("GET", "/api/corridas")
        self.assertEqual(estado, 200)
        corridas = d["corridas"]
        self.assertEqual(len(corridas), 288)
        self.assertEqual(len({c["id"] for c in corridas}), 288)
        self.assertEqual({c["configuracion"] for c in corridas}, {"A", "B"})
        self.assertNotIn("trazas/experimento/A/rep1/A_c001_20261114_072445_357974.jsonl", {c["traza"] for c in corridas})
        self.assertTrue(all(not k.startswith("_") for c in corridas for k in c))

    def test_reproduce_sin_modificar_la_traza(self):
        meta = self.srv.corridas["experimento/B/rep1/c015"]
        antes = huella(meta["_ruta"])
        estado, d = self.json("GET", "/api/corrida?id=experimento/B/rep1/c015")
        self.assertEqual(estado, 200)
        self.assertEqual(d["origen"], "traza_real")
        self.assertIn("no hay llamada en vivo", d["aviso"])
        self.assertEqual(d["sha256_traza"], antes)
        self.assertEqual(huella(meta["_ruta"]), antes)
        self.assertEqual(d["eventos"][0]["tipo"], "inicio")
        self.assertEqual(d["eventos"][-1]["tipo"], "fin")
        self.assertEqual(d["eventos"][0]["configuracion"], "B")
        self.assertIn("SIN_COBERTURA:formulario", d["guardado"]["glosas"])

    def test_enlaces_del_diccionario_vienen_de_la_evidencia(self):
        _, d = self.json("GET", "/api/corrida?id=experimento/A/rep1/c001")
        salidas = " ".join(e.get("salida", "") for e in d["eventos"] if e["tipo"] == "herramienta")
        self.assertIn("https://lesco.cenarec.go.cr/DiccLESCO.php?idw=", salidas)


class TestSimulacion(BaseServidor):
    def setUp(self):
        self.salidas_demo = RAIZ / "resultados" / "salidas" / "demo"
        self.antes_demo = huellas_de(self.salidas_demo) if self.salidas_demo.exists() else {}
        self.antes_trazas_demo = huellas_de(RAIZ / "trazas" / "demo") if (RAIZ / "trazas" / "demo").exists() else {}
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.assertEqual(huellas_de(self.salidas_demo) if self.salidas_demo.exists() else {}, self.antes_demo)
        self.assertEqual(huellas_de(RAIZ / "trazas" / "demo") if (RAIZ / "trazas" / "demo").exists() else {},
                         self.antes_trazas_demo)

    def test_flujo_completo_con_aprobacion(self):
        estado, _ = self.json("POST", "/api/simulacion/iniciar", {})
        self.assertEqual(estado, 202)
        carpeta = self.srv.simulacion.carpeta
        self.assertTrue(carpeta.name.startswith(sd.PREFIJO_TEMPORAL))
        self.assertNotIn(RAIZ.resolve(), carpeta.resolve().parents)

        d = self.esperar_estado("esperando_aprobacion")
        self.assertEqual(d["pendiente"]["nombre"], "lesco__guardar_resultado")
        self.assertEqual(self.json("POST", "/api/simulacion/iniciar", {})[0], 409)   # una a la vez
        self.assertEqual(self.json("POST", "/api/simulacion/aprobacion", {"aprobar": True})[0], 200)

        d = self.esperar_estado("terminada")
        self.assertEqual(d["resultado"]["codigo"], 0)
        self.assertIn("SIMULADO", d["aviso"])
        nombres = [e["nombre"].split("__")[-1] for e in d["eventos"] if e["tipo"] == "herramienta"]
        self.assertEqual(nombres[0], "obtener_transcripcion")
        self.assertIn("buscar_sena", nombres)
        self.assertIn("validar_secuencia", nombres)
        guardados = [e for e in d["eventos"] if e["tipo"] == "herramienta" and e["nombre"].endswith("guardar_resultado")]
        self.assertEqual(len(guardados), 2)
        self.assertEqual((guardados[0]["decision"], guardados[0]["es_error"]), ("permitir", False))
        self.assertIn("persona en la interfaz", guardados[0]["razon"])
        self.assertEqual(guardados[1]["decision"], "denegar")
        self.assertIn("máximo de 1 llamadas", guardados[1]["razon"])
        self.assertEqual(d["guardado"]["glosas"], ["DEBER", "FIRMAR", "FACTURA", "ESPERAR", "FILA"])
        self.assertEqual(d["eventos"][0]["modelo"], "simulado")

    def esperar_solicitud(self, n, limite=30):
        fin = time.time() + limite
        while time.time() < fin:
            _, d = self.json("GET", "/api/simulacion")
            if d["estado"] == "esperando_aprobacion" and d["solicitudes_aprobacion"] == n:
                return d
            time.sleep(0.1)
        self.fail(f"no llegó la solicitud de aprobación número {n}")

    def test_rechazo_no_guarda_nada(self):
        # Un guardado rechazado no consume el cupo de escritura: el guion lo intenta otra vez y el host
        # vuelve a pedir aprobación. Se rechazan ambos.
        self.json("POST", "/api/simulacion/iniciar", {})
        self.esperar_solicitud(1)
        self.json("POST", "/api/simulacion/aprobacion", {"aprobar": False})
        self.esperar_solicitud(2)
        self.json("POST", "/api/simulacion/aprobacion", {"aprobar": False})
        d = self.esperar_estado("terminada")
        guardados = [e for e in d["eventos"] if e["tipo"] == "herramienta" and e["nombre"].endswith("guardar_resultado")]
        self.assertEqual(len(guardados), 2)
        self.assertTrue(all(e["decision"] == "denegar" for e in guardados))
        self.assertTrue(all("rechazada por una persona" in e["razon"] for e in guardados))
        self.assertIsNone(d["guardado"])

    def test_aprobacion_mal_formada_o_sin_pendiente(self):
        self.assertEqual(self.json("POST", "/api/simulacion/aprobacion", {"aprobar": True})[0], 409)
        for cuerpo in ({"aprobar": "sí"}, {"aprobar": 1}, {"aprobar": True, "comando": "dir"}, {}):
            self.assertEqual(self.json("POST", "/api/simulacion/aprobacion", cuerpo)[0], 400, cuerpo)
        self.assertEqual(self.json("POST", "/api/simulacion/iniciar", {"comando": "del *"})[0], 400)
        self.assertEqual(self.pedir("POST", "/api/simulacion/iniciar", crudo="x" * 1000)[0], 413)

    def test_cerrar_elimina_la_carpeta_temporal(self):
        self.json("POST", "/api/simulacion/iniciar", {})
        carpeta = self.srv.simulacion.carpeta
        self.esperar_estado("esperando_aprobacion")
        self.srv.simulacion.cerrar()                 # equivale a Ctrl+C con la aprobación pendiente
        self.assertFalse(carpeta.exists())

    def test_no_muestra_rutas_locales(self):
        self.json("POST", "/api/simulacion/iniciar", {})
        self.esperar_estado("esperando_aprobacion")
        self.json("POST", "/api/simulacion/aprobacion", {"aprobar": True})
        self.esperar_estado("terminada")
        _, texto, _ = self.pedir("GET", "/api/simulacion")
        _, texto_real, _ = self.pedir("GET", "/api/corrida?id=experimento/A/rep2/c010")
        for t in (texto, texto_real):
            for privado in (str(RAIZ), str(Path.home()), tempfile.gettempdir(), Path.home().name):
                self.assertNotIn(privado.lower(), t.lower())


class TestSinAPI(unittest.TestCase):
    def test_modelo_real_y_red_bloqueados(self):
        srv = sd.crear_servidor(0, silencioso=True)
        try:
            import os
            self.assertNotIn("ANTHROPIC_API_KEY", os.environ)
            with self.assertRaises(sd.agente.ErrorModelo):
                sd.agente.ModeloClaude("claude-sonnet-5-5", 10)
            self.assertIsNone(sd.agente.cargar_clave())
            with self.assertRaises(OSError):
                urllib.request.urlopen("https://api.anthropic.com/v1/messages")
        finally:
            srv.server_close()


class TestLimpiador(unittest.TestCase):
    def test_sustituye_rutas_y_claves(self):
        limpiar = sd.Limpiador()
        tmp = Path(tempfile.gettempdir()) / "lesco_demo_web_x"
        limpiar.agregar(tmp, "<carpeta temporal aislada>")
        # Valor FICTICIO armado por fragmentos: no aparece literal en el código ni es una credencial.
        prefijo = "sk" + "-" + "ant" + "-"
        ficticia = prefijo + "prueba" + "-" + "ficticia" + "-" + "0000"
        entrada = {"a": f"{RAIZ}\\agente", "b": str(tmp / "salidas").replace("\\", "/"),
                   "c": json.dumps({"r": str(Path.home() / "x")}), "d": f"clave {ficticia}"}
        salida = json.dumps(limpiar(entrada))
        for privado in (str(RAIZ), str(Path.home()), ficticia, prefijo):
            self.assertNotIn(privado.lower(), salida.lower())
        self.assertIn("<clave oculta>", salida)
        self.assertIn("<carpeta temporal aislada>", salida)
        self.assertIn("<repo>", salida)


class TestArchivosWeb(unittest.TestCase):
    def test_interfaz_sin_recursos_externos_ni_html_inyectado(self):
        html = (DEMO / "web" / "index.html").read_text(encoding="utf-8")
        js = (DEMO / "web" / "app.js").read_text(encoding="utf-8")
        css = (DEMO / "web" / "estilo.css").read_text(encoding="utf-8")
        for t in (html, css):
            self.assertNotIn("http://", t)
            self.assertNotIn("https://", t)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("eval(", js)
        self.assertIn("No es un traductor validado y no sustituye a intérpretes humanos", " ".join(html.split()))
        for ident in ("btn-iniciar", "btn-siguiente", "btn-anterior", "btn-reiniciar", "btn-detalles",
                      "btn-modo-real", "btn-modo-sim", "btn-pantalla", "btn-aprobar", "btn-rechazar", "btn-plan-b"):
            self.assertIn(f'id="{ident}"', html)
            self.assertIn(f'$("{ident}").addEventListener', js)


if __name__ == "__main__":
    unittest.main()
