"""Pruebas del ejecutor supervisado (agente/ejecutar_supervisado.py) y de las exclusiones del análisis.

Todo es sintético y en carpetas temporales: agente.ejecutar se sustituye por una función que escribe trazas
y resultados de prueba, y urlopen por dobles que fallan. Ninguna prueba llama a la API ni toca trazas/ ni
resultados/ del repositorio.
"""

import io
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "agente"))
sys.path.insert(0, str(RAIZ / "eval"))
sys.path.insert(0, str(RAIZ))

import agente  # noqa: E402
import ejecutar_supervisado as sup  # noqa: E402
import puntuar  # noqa: E402

MODELO = "claude-sonnet-5-5"


def restaurar_agente():
    """Restaura lo que sin_reintentos() cambia en el proceso (clase y urlopen)."""
    return (mock.patch.object(agente.ModeloClaude, "REINTENTOS", agente.ModeloClaude.REINTENTOS),
            mock.patch.object(agente.ModeloClaude, "responder", agente.ModeloClaude.responder),
            mock.patch.object(agente.urllib.request, "urlopen", agente.urllib.request.urlopen))


class TestSinReintentos(unittest.TestCase):
    """Problema 1: ModeloClaude reintentaba 4 veces 429/529/5xx y fallos de red."""

    def setUp(self):
        for p in restaurar_agente():
            p.start()
            self.addCleanup(p.stop)
        self.modelo = agente.ModeloClaude.__new__(agente.ModeloClaude)
        self.modelo.modelo, self.modelo.max_tokens, self.modelo.esfuerzo, self.modelo.clave = MODELO, 100, None, "x"

    def contar_llamadas(self, error):
        llamadas = []

        def falla(req, *a, **k):
            llamadas.append(k.get("timeout"))
            raise error
        agente.urllib.request.urlopen = falla
        sup.sin_reintentos(t_http=150)
        with mock.patch.object(agente.time, "sleep", side_effect=AssertionError("no debía esperar para reintentar")):
            with self.assertRaises(agente.ErrorModelo):
                self.modelo.responder("s", [], [])
        return llamadas

    def test_http_transitorio_sin_reintento(self):
        for codigo in (429, 529, 500, 503):
            with self.subTest(codigo=codigo):
                err = urllib.error.HTTPError(agente.ModeloClaude.URL, codigo, "x", {}, io.BytesIO(b"{}"))
                self.assertEqual(self.contar_llamadas(err), [150])     # una sola llamada, con tiempo máximo

    def test_fallo_de_red_sin_reintento(self):
        self.assertEqual(len(self.contar_llamadas(urllib.error.URLError("sin red"))), 1)

    def test_modelo_declarado_distinto_es_fallo(self):
        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        agente.urllib.request.urlopen = lambda req, *a, **k: Resp(json.dumps({"model": MODELO + "-otro"}).encode())
        sup.sin_reintentos(t_http=150)
        with self.assertRaises(agente.ErrorModelo):
            self.modelo.responder("s", [], [])


class TestEjecutorSupervisado(unittest.TestCase):
    """Problemas 2–4: reanudación sin repetir, parada ante fallos, umbral de gasto y de tiempo."""

    def setUp(self):
        for p in restaurar_agente():
            p.start()
            self.addCleanup(p.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="lesco_sup_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "eval").mkdir()
        (self.tmp / "agente").mkdir()
        self.casos = self.tmp / "eval" / "casos.jsonl"
        self.casos.write_text("".join(json.dumps({"caso_id": c, "texto": "x"}) + "\n" for c in ("s1", "s2")),
                              encoding="utf-8")
        for f in ("agente/instrucciones_genericas.md", "skill/SKILL.md"):   # para el SHA-256 de instrucciones
            (self.tmp / f).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / f).write_text("x", encoding="utf-8")
        self.excl = self.tmp / "eval" / "exclusiones.json"
        self.llamadas = []
        self.resultado_fake = {}           # caso -> "ok" | "tecnico"
        self.n = 0

    # --- doble de agente.ejecutar: escribe una traza y un resultado como los reales ---
    def escribir_traza(self, carpeta: Path, config: str, caso: str, rep: int, motivo: str, guardar: bool,
                       entrada=20000, salida=700):
        self.n += 1
        carpeta.mkdir(parents=True, exist_ok=True)
        ev = [{"tipo": "inicio", "caso_id": caso, "modelo": MODELO, "configuracion": config, "repeticion": rep,
               "servidores": [{"nombre": "lesco", "version": "0.2.0", "caso_vinculado": caso}]}]
        if guardar:
            ev.append({"tipo": "herramienta", "paso": 1, "nombre": "lesco__guardar_resultado",
                       "argumentos": {"caso_id": caso}, "decision": "permitir", "razon": "", "es_error": False,
                       "salida": "{}"})
        ev.append({"tipo": "fin", "motivo": motivo, "pasos": 1, "tokens_entrada": entrada, "tokens_salida": salida,
                   "duracion_s": 1, "llamadas": [], "respuesta_final": ""})
        ruta = carpeta / f"{config}_{caso}_20260101_0000{self.n:02d}_000000.jsonl"
        ruta.write_text("".join(json.dumps(e) + "\n" for e in ev), encoding="utf-8")
        return ruta

    def ejecutar_fake(self, args):
        config, caso, rep = Path(args.config).stem, args.caso, args.repeticion
        self.llamadas.append((config, caso, rep))
        tecnico = self.resultado_fake.get(caso) == "tecnico"
        traza = self.escribir_traza(Path(args.trazas), config, caso, rep,
                                    "error del modelo: Error de la API (529): x" if tecnico
                                    else "el modelo terminó (end_turn)", guardar=not tecnico)
        if not tecnico:
            Path(args.salidas).mkdir(parents=True, exist_ok=True)
            (Path(args.salidas) / f"{caso}.json").write_text(json.dumps({"caso_id": caso, "secuencia": ["CENAREC-1"]}),
                                                            encoding="utf-8")
        return {"codigo": 2 if tecnico else 0, "traza": str(traza), "motivo": "x"}

    def correr(self, *extra, ejecutar=None):
        argv = ["--casos", str(self.casos), "--exclusiones", str(self.excl), "--repeticiones", "1", *extra]
        with mock.patch.object(agente, "ejecutar", ejecutar or self.ejecutar_fake), \
                redirect_stdout(io.StringIO()) as out:
            codigo = sup.main(argv, raiz=self.tmp)
        return codigo, out.getvalue()

    def manifiesto(self):
        ruta = self.tmp / "resultados" / "experimento" / "supervisor.jsonl"
        return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines()] if ruta.exists() else []

    def test_plan_mismo_orden_que_ejecutar_casos(self):
        self.assertEqual(sup.plan(["s1", "s2"], ["A", "B"], 2),
                         [("A", "s1", 1), ("B", "s1", 1), ("A", "s2", 1), ("B", "s2", 1),
                          ("A", "s1", 2), ("B", "s1", 2), ("A", "s2", 2), ("B", "s2", 2)])

    def test_tramos_y_reanudacion_sin_repetir(self):
        codigo, _ = self.correr("--tope-usd", "10", "--max-corridas", "3")
        self.assertEqual(codigo, 10)
        self.assertEqual(self.llamadas, [("A", "s1", 1), ("B", "s1", 1), ("A", "s2", 1)])
        codigo, _ = self.correr("--tope-usd", "10", "--max-corridas", "3")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.llamadas[3:], [("B", "s2", 1)])                     # no repite las hechas
        m = self.manifiesto()
        self.assertEqual([x["id_corrida"] for x in m], ["experimento/A/rep1/s1", "experimento/B/rep1/s1",
                                                        "experimento/A/rep1/s2", "experimento/B/rep1/s2"])
        self.assertTrue(all(x["valida_D19"] and x["modelo_traza"] == MODELO for x in m))
        self.assertEqual(len({x["sha256_instrucciones"] for x in m}), 2)          # A y B difieren (Skill)
        self.assertAlmostEqual(m[0]["costo_estimado_usd"], 20000 * 2e-6 + 700 * 10e-6)
        codigo, out = self.correr("--tope-usd", "10", "--max-corridas", "3")
        self.assertEqual((codigo, len(self.llamadas)), (0, 4))                    # nada pendiente

    def test_fallo_tecnico_detiene_y_no_se_repite(self):
        self.resultado_fake["s1"] = "tecnico"
        codigo, out = self.correr("--tope-usd", "10", "--max-corridas", "10")
        self.assertEqual(codigo, 5)
        self.assertEqual(self.llamadas, [("A", "s1", 1)])                         # se detiene en la primera
        self.assertFalse(self.manifiesto()[0]["valida_D19"])
        self.resultado_fake.clear()
        codigo, out = self.correr("--tope-usd", "10", "--max-corridas", "10")
        self.assertEqual(codigo, 4)                                               # fallida previa: decisión humana
        self.assertEqual(len(self.llamadas), 1)
        self.assertIn("A/rep1/s1", out)

    def test_umbral_de_gasto_antes_de_cada_corrida(self):
        # Gasto previo de una corrida hecha (0,047) + reserva 0,15 > tope 0,10: no se inicia ninguna nueva.
        self.escribir_traza(self.tmp / "trazas/experimento/A/rep1", "A", "s1", 1, "el modelo terminó (end_turn)", True)
        (self.tmp / "resultados/experimento/A/rep1").mkdir(parents=True)
        (self.tmp / "resultados/experimento/A/rep1/s1.json").write_text(
            json.dumps({"caso_id": "s1", "secuencia": ["CENAREC-1"]}), encoding="utf-8")
        codigo, out = self.correr("--tope-usd", "0.10", "--max-corridas", "5")
        self.assertEqual(codigo, 8)
        self.assertEqual(self.llamadas, [])
        # 0,047 + 0,15 = 0,197 ≤ 0,22 → corre 1; luego 0,094 + 0,15 = 0,244 > 0,22 → se detiene antes de la 2.ª
        codigo, _ = self.correr("--tope-usd", "0.22", "--max-corridas", "5")
        self.assertEqual(codigo, 8)
        self.assertEqual(len(self.llamadas), 1)

    def test_limite_de_tiempo_antes_de_cada_corrida(self):
        tiempos = iter([0, 0, 500, 500, 500, 500])
        with mock.patch.object(sup.time, "monotonic", side_effect=lambda: next(tiempos)):
            codigo, _ = self.correr("--tope-usd", "10", "--max-corridas", "5", "--t-nueva", "420")
        self.assertEqual(codigo, 9)
        self.assertEqual(len(self.llamadas), 1)

    def test_traza_excluida_no_cuenta_y_otra_valida_la_sustituye(self):
        excluida = self.escribir_traza(self.tmp / "trazas/experimento/A/rep1", "A", "s1", 1,
                                       "error del modelo: Error de la API (401): x", False)
        import hashlib
        self.excl.write_text(json.dumps({"trazas_excluidas": [{
            "ruta": excluida.relative_to(self.tmp).as_posix(),
            "sha256": hashlib.sha256(excluida.read_bytes()).hexdigest(), "motivo": "401"}]}), encoding="utf-8")
        codigo, _ = self.correr("--tope-usd", "10", "--max-corridas", "1")
        self.assertEqual(codigo, 10)
        self.assertEqual(self.llamadas, [("A", "s1", 1)])                         # sin exclusión sería "fallida"
        self.assertTrue(excluida.exists())                                        # se conserva intacta
        # El análisis ignora la excluida y usa la corrida válida
        excl = puntuar.cargar_exclusiones(self.excl, self.tmp)
        ultima = puntuar.ultima_traza(self.tmp / "trazas/experimento/A/rep1", "A", "s1", excl)
        self.assertNotEqual(ultima, excluida)

    def test_exclusion_con_sha_distinto_falla_cerrado(self):
        excluida = self.escribir_traza(self.tmp / "trazas/experimento/A/rep1", "A", "s1", 1,
                                       "error del modelo: Error de la API (401): x", False)
        self.excl.write_text(json.dumps({"trazas_excluidas": [{
            "ruta": excluida.relative_to(self.tmp).as_posix(), "sha256": "0" * 64}]}), encoding="utf-8")
        codigo, out = self.correr("--tope-usd", "10", "--max-corridas", "1")
        self.assertEqual(codigo, 3)
        self.assertEqual(self.llamadas, [])
        with self.assertRaises(puntuar.ErrorVinculacion):
            puntuar.cargar_exclusiones(self.excl, self.tmp)

    def test_solo_plan_no_ejecuta(self):
        codigo, out = self.correr("--tope-usd", "10", "--max-corridas", "2", "--solo-plan")
        self.assertEqual(codigo, 10)
        self.assertEqual(self.llamadas, [])
        self.assertIn("pendientes 4", out)


class TestExclusionesDelRepositorio(unittest.TestCase):
    """El archivo versionado de exclusiones es coherente con la traza del 401 conservada."""

    def test_exclusion_del_401_valida_si_la_traza_esta_presente(self):
        ruta = RAIZ / "eval" / "exclusiones_experimento.json"
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(len(datos["trazas_excluidas"]), 1)
        e = datos["trazas_excluidas"][0]
        self.assertTrue(e["ruta"].startswith("trazas/experimento/A/rep1/A_c001_"))
        # Si la traza existe en este clon, su SHA-256 debe coincidir (si no existe, no hay nada que excluir)
        puntuar.cargar_exclusiones(ruta, RAIZ)


if __name__ == "__main__":
    unittest.main()
