import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "eval"))
sys.path.insert(0, str(RAIZ / "agente"))
sys.path.insert(0, str(RAIZ))

import agente  # noqa: E402
import puntuar  # noqa: E402
import reproducir  # noqa: E402
from construir_referencia import adjudicar, motivos_de, secuencia  # noqa: E402
from puntuar import ErrorVinculacion, agregar, diferencia_pareada, evaluar, puntuar_caso  # noqa: E402


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


class TestValidezDeEjecuciones(unittest.TestCase):
    """E2-5: solo se puntúan ejecuciones esperadas, existentes y documentalmente consistentes.
    Trazas y resultados sintéticos en una carpeta temporal, con la estructura real de evaluar():
    trazas/<exp>/<config>/<rep>/<config>_<caso>_*.jsonl y resultados/<exp>/<config>/<rep>/<caso>.json."""

    REF = {"s1": {"dificultad": "normal", "secuencia": ["CENAREC-1"]}}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lesco_validez_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    @staticmethod
    def vinculado(caso="s1"):
        return [{"nombre": "lesco", "version": "0.2.0", "caso_vinculado": caso}]

    def traza(self, caso="s1", servidores="vinculado", guardados=(), con_inicio=True, config="A", rep="rep1",
              motivo="el modelo terminó (end_turn)", con_fin=True, fecha="20260101_000000_000000"):
        carpeta = self.tmp / "trazas" / "x" / config / rep
        carpeta.mkdir(parents=True, exist_ok=True)
        eventos = []
        if con_inicio:
            inicio = {"tipo": "inicio", "caso_id": caso, "modelo": "simulado", "configuracion": config,
                      "repeticion": int(rep[3:])}
            if servidores == "vinculado":
                inicio["servidores"] = self.vinculado(caso)
            elif servidores is not None:                    # None = traza histórica, sin el campo
                inicio["servidores"] = servidores
            eventos.append(inicio)
        for paso, destino in enumerate(guardados, start=1):
            eventos.append({"tipo": "herramienta", "paso": paso, "nombre": "lesco__guardar_resultado",
                            "argumentos": {"caso_id": destino}, "decision": "permitir", "razon": "",
                            "es_error": False, "salida": "{}"})
        if con_fin:
            eventos.append({"tipo": "fin", "motivo": motivo, "pasos": 1,
                            "tokens_entrada": 0, "tokens_salida": 0, "duracion_s": 0, "llamadas": [],
                            "respuesta_final": ""})
        (carpeta / f"{config}_{caso}_{fecha}.jsonl").write_text(
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in eventos), encoding="utf-8")

    def resultado(self, caso="s1", declarado=None, config="A", rep="rep1"):
        carpeta = self.tmp / "resultados" / "x" / config / rep
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / f"{caso}.json").write_text(
            json.dumps({"caso_id": declarado or caso, "secuencia": ["CENAREC-1"]}), encoding="utf-8")

    def anexar_a_traza(self, texto, caso="s1", config="A", rep="rep1"):
        """Añade una línea cruda al final de la traza sintética del caso."""
        ruta = self.tmp / "trazas" / "x" / config / rep / f"{config}_{caso}_20260101_000000_000000.jsonl"
        with ruta.open("a", encoding="utf-8") as fh:
            fh.write(texto + "\n")

    def resultado_crudo(self, texto, caso="s1", config="A", rep="rep1"):
        carpeta = self.tmp / "resultados" / "x" / config / rep
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / f"{caso}.json").write_text(texto, encoding="utf-8")

    def protocolo(self, configs, reps, casos=("s1",)):
        """Ejecuciones válidas y vinculadas para cada configuración × repetición × caso."""
        for config in configs:
            for rep in reps:
                for caso in casos:
                    self.traza(caso, guardados=(caso,), config=config, rep=rep)
                    self.resultado(caso, config=config, rep=rep)

    def rechaza(self, fragmento, referencia=None):
        with self.assertRaises(ErrorVinculacion) as e:
            evaluar("x", referencia or self.REF, raiz=self.tmp)
        self.assertIn(fragmento, "; ".join(e.exception.args[0]))

    def rechaza_con(self, fragmentos, **kw):
        with self.assertRaises(ErrorVinculacion) as e:
            evaluar("x", self.REF, raiz=self.tmp, **kw)
        texto = "; ".join(e.exception.args[0])
        for f in fragmentos:
            self.assertIn(f, texto)

    # ---- consistencia documental de cada ejecución
    def test_valida_con_resultado_se_puntua_igual(self):
        self.traza(guardados=("s1",)); self.resultado()
        (fila,) = evaluar("x", self.REF, raiz=self.tmp)
        self.assertEqual((fila["guardado"], fila["exacta"], fila["f1"]), (1.0, 1.0, 1.0))

    def test_valida_sin_resultado_cuenta_como_no_guardado(self):
        self.traza()
        (fila,) = evaluar("x", self.REF, raiz=self.tmp)
        self.assertEqual((fila["guardado"], fila["f1"]), (0.0, 0.0))      # mismo criterio que antes

    def test_rechaza_traza_historica_sin_servidores(self):
        self.traza(servidores=None, guardados=("s1",)); self.resultado()
        self.rechaza("sin evidencia de --caso")

    def test_rechaza_servidor_vinculado_a_otro_caso(self):
        self.traza(servidores=self.vinculado("s2"), guardados=("s1",)); self.resultado()
        self.rechaza("servidor sin vinculación declarada")

    def test_rechaza_resultado_sin_guardado_en_la_traza(self):
        self.traza(); self.resultado()
        self.rechaza("registra 0 guardados")

    def test_rechaza_guardados_exitosos_duplicados(self):
        self.traza(guardados=("s1", "s1")); self.resultado()
        self.rechaza("registra 2 guardados")

    def test_rechaza_guardado_sin_resultado(self):
        self.traza(guardados=("s1",))
        self.rechaza("no existe s1.json")

    def test_rechaza_guardado_de_otro_caso(self):
        self.traza(guardados=("s2",))
        self.rechaza("guardado exitoso de otro caso")

    def test_rechaza_resultado_que_declara_otro_caso(self):
        self.traza(guardados=("s1",)); self.resultado(declarado="s2")
        self.rechaza("declara caso_id 's2'")

    def test_rechaza_traza_sin_inicio(self):
        self.traza(con_inicio=False)
        self.rechaza("no tiene evento 'inicio'")

    def test_rechaza_ejecucion_esperada_sin_traza(self):
        self.traza("s1", guardados=("s1",)); self.resultado("s1")          # s2 no tiene traza
        ref = {**self.REF, "s2": {"dificultad": "normal", "secuencia": ["CENAREC-1"]}}
        self.rechaza("A/rep1/s2: no hay traza de la ejecución esperada", referencia=ref)

    def test_rechaza_repeticion_ausente_en_una_configuracion(self):
        for config, reps in (("A", ("rep1", "rep2")), ("B", ("rep1",))):   # falta B/rep2
            for rep in reps:
                self.traza(config=config, rep=rep)
        self.rechaza("B/rep2: falta la carpeta de la repetición")

    def test_no_devuelve_puntuaciones_parciales(self):
        self.traza("s1", guardados=("s1",)); self.resultado("s1")      # válida
        self.traza("s2", servidores=None)                               # inválida
        ref = {**self.REF, "s2": {"dificultad": "normal", "secuencia": ["CENAREC-1"]}}
        self.rechaza("A/rep1/s2", referencia=ref)

    def test_reproducir_sale_con_3_y_no_escribe_tablas(self):
        self.traza(servidores=None, guardados=("s1",)); self.resultado()
        ref = self.tmp / "referencia.jsonl"
        ref.write_text(json.dumps({"caso_id": "s1", **self.REF["s1"]}) + "\n", encoding="utf-8")
        tablas = self.tmp / "tablas"
        argv = ["reproducir.py", "--experimento", "x", "--referencia", str(ref), "--salida", str(tablas),
                "--configs", "A", "--repeticiones", "1"]
        original = puntuar.evaluar
        with mock.patch.object(sys, "argv", argv), mock.patch.object(reproducir, "RAIZ", self.tmp), \
                mock.patch.object(reproducir, "evaluar",
                                  lambda exp, referencia, **kw: original(exp, referencia, raiz=self.tmp, **kw)), \
                redirect_stdout(io.StringIO()) as salida:
            codigo = reproducir.main()
        self.assertEqual(codigo, 3)
        self.assertFalse(tablas.exists())                               # ninguna tabla ni carpeta
        self.assertIn("No se generan tablas", salida.getvalue())
        self.assertIn("A/rep1/s1", salida.getvalue())

    # ---- conjunto esperado de configuraciones y repeticiones
    def test_protocolo_completo_valido(self):
        self.protocolo(("A", "B"), ("rep1", "rep2"))
        filas = evaluar("x", self.REF, raiz=self.tmp, configuraciones=["A", "B"], repeticiones=2)
        self.assertEqual(len(filas), 4)                       # 2 configuraciones × 2 repeticiones × 1 caso

    def test_rechaza_configuracion_esperada_ausente(self):
        self.protocolo(("A",), ("rep1",))                     # falta B por completo
        self.rechaza_con(["B: falta la configuración esperada"], configuraciones=["A", "B"], repeticiones=1)

    def test_rechaza_configuracion_no_esperada(self):
        self.protocolo(("A", "B", "C"), ("rep1",))
        self.rechaza_con(["C: configuración no esperada"], configuraciones=["A", "B"], repeticiones=1)

    def test_rechaza_repeticiones_insuficientes(self):
        self.protocolo(("A", "B"), ("rep1",))                 # el protocolo indicado pide 3
        self.rechaza_con(["A/rep2: falta", "A/rep3: falta", "B/rep2: falta", "B/rep3: falta"],
                         configuraciones=["A", "B"], repeticiones=3)

    def test_rechaza_repeticion_no_esperada(self):
        self.protocolo(("A", "B"), ("rep1", "rep2"))
        self.rechaza_con(["A/rep2: repetición no esperada", "B/rep2: repetición no esperada"],
                         configuraciones=["A", "B"], repeticiones=1)

    def test_rechaza_experimento_sin_trazas(self):
        self.rechaza_con(["no existe trazas/x"])              # la carpeta trazas/x no existe

    def test_rechaza_experimento_sin_configuraciones(self):
        (self.tmp / "trazas" / "x").mkdir(parents=True)
        self.rechaza_con(["no contiene configuraciones"])

    def test_rechaza_configuraciones_sin_repeticiones(self):
        for config in ("A", "B"):
            (self.tmp / "trazas" / "x" / config).mkdir(parents=True)
        self.rechaza_con(["ninguna configuración contiene repeticiones"])
        self.rechaza_con(["A/rep1: falta", "B/rep1: falta"], configuraciones=["A", "B"], repeticiones=1)

    def test_rechaza_referencia_vacia(self):
        self.protocolo(("A",), ("rep1",))
        with self.assertRaises(ErrorVinculacion) as e:
            evaluar("x", {}, raiz=self.tmp)
        self.assertIn("referencia está vacía", e.exception.args[0][0])

    def test_protocolo_de_reproducir_coincide_con_ejecutar_casos(self):
        """Los valores por defecto de reproducir.py y de ejecutar_casos.py no deben divergir (lectura estática)."""
        import ast
        arbol = ast.parse((RAIZ / "agente" / "ejecutar_casos.py").read_text(encoding="utf-8"))
        defaults = {}
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument" and nodo.args:
                opcion = getattr(nodo.args[0], "value", None)
                for kw in nodo.keywords:
                    if kw.arg == "default" and opcion in ("--configs", "--repeticiones"):
                        defaults[opcion] = ast.literal_eval(kw.value)
        self.assertEqual(defaults["--configs"], reproducir.CONFIGURACIONES_PROTOCOLO)
        self.assertEqual(defaults["--repeticiones"], reproducir.REPETICIONES_PROTOCOLO)

    # ---- JSON mal formado o con forma inesperada (falla cerrado, sin volcar contenido)
    def test_rechaza_traza_con_json_mal_formado(self):
        self.traza(guardados=("s1",)); self.resultado()
        self.anexar_a_traza('{"tipo": "herramienta", "nombre": ')
        self.rechaza("JSON mal formado en la línea")

    def test_rechaza_linea_de_traza_que_no_es_objeto(self):
        self.traza(guardados=("s1",)); self.resultado()
        self.anexar_a_traza("42")
        self.rechaza("no es un objeto JSON")

    def test_rechaza_evento_sin_tipo(self):
        self.traza(guardados=("s1",)); self.resultado()
        self.anexar_a_traza('{"x": 1}')
        self.rechaza("no tiene 'tipo'")

    def test_rechaza_herramienta_sin_campos_esperados(self):
        self.traza(guardados=("s1",)); self.resultado()
        for linea in ('{"tipo": "herramienta"}',
                      '{"tipo": "herramienta", "nombre": "x", "decision": "permitir", "argumentos": [], "es_error": false}',
                      '{"tipo": "herramienta", "nombre": "x", "decision": "permitir", "argumentos": {}, "es_error": false, "salida": 3}'):
            with self.subTest(linea=linea):
                self.traza(guardados=("s1",))                 # reescribe la traza limpia
                self.anexar_a_traza(linea)
                self.rechaza("no tiene los campos esperados")

    def test_rechaza_resultado_con_json_mal_formado(self):
        self.traza(guardados=("s1",)); self.resultado_crudo('{"caso_id": "s1", "secuencia": [')
        self.rechaza("s1.json no se pudo leer como JSON")

    def test_rechaza_resultado_que_no_es_objeto(self):
        self.traza(guardados=("s1",)); self.resultado_crudo('["CENAREC-1"]')
        self.rechaza("s1.json no es un objeto JSON")

    def test_rechaza_resultado_sin_secuencia(self):
        self.traza(guardados=("s1",)); self.resultado_crudo('{"caso_id": "s1"}')
        self.rechaza("s1.json no contiene 'secuencia'")

    def test_rechaza_secuencia_que_no_es_lista_de_textos(self):
        for valor in ('"CENAREC-1"', "[1, 2]", '["CENAREC-1", null]', "{}"):
            with self.subTest(secuencia=valor):
                self.traza(guardados=("s1",))
                self.resultado_crudo('{"caso_id": "s1", "secuencia": ' + valor + "}")
                self.rechaza("'secuencia' no es una lista de textos")

    def test_mensajes_no_vuelcan_contenido(self):
        marca = "CONTENIDO-PRIVADO-" + "x" * 60
        self.traza(guardados=("s1",))
        self.anexar_a_traza('{"tipo": "inicio", "dato": "' + marca)                      # traza mal formada
        self.traza("s2", guardados=("s2",)); self.resultado("s2", declarado=marca)     # caso_id inválido
        self.resultado_crudo('{"secuencia": "' + marca, caso="s1")                      # resultado mal formado
        ref = {**self.REF, "s2": {"dificultad": "normal", "secuencia": ["CENAREC-1"]}}
        with self.assertRaises(ErrorVinculacion) as e:
            evaluar("x", ref, raiz=self.tmp)
        texto = "; ".join(e.exception.args[0])
        self.assertNotIn(marca, texto)                                  # ni el contenido completo...
        self.assertNotIn("CONTENIDO-PRIVADO-", texto)                   # ...ni su prefijo
        self.assertIn("JSON mal formado", texto)
        self.assertIn("s2.json declara caso_id 'identificador inválido'", texto)

    def test_reproducir_sale_con_3_ante_traza_mal_formada(self):
        self.traza(guardados=("s1",)); self.resultado()
        self.anexar_a_traza("{no es json")
        ref = self.tmp / "referencia.jsonl"
        ref.write_text(json.dumps({"caso_id": "s1", **self.REF["s1"]}) + "\n", encoding="utf-8")
        tablas = self.tmp / "tablas"
        argv = ["reproducir.py", "--experimento", "x", "--referencia", str(ref), "--salida", str(tablas),
                "--configs", "A", "--repeticiones", "1"]
        original = puntuar.evaluar
        with mock.patch.object(sys, "argv", argv), mock.patch.object(reproducir, "RAIZ", self.tmp), \
                mock.patch.object(reproducir, "evaluar",
                                  lambda exp, referencia, **kw: original(exp, referencia, raiz=self.tmp, **kw)), \
                redirect_stdout(io.StringIO()) as salida:
            codigo = reproducir.main()
        self.assertEqual(codigo, 3)
        self.assertFalse(tablas.exists())
        self.assertIn("JSON mal formado en la línea", salida.getvalue())

    # ---- D19 (2026-11-14): fallos técnicos y cierre de la ejecución
    def test_http_401_es_invalida_y_no_expone_el_motivo(self):
        self.traza(motivo='error del modelo: Error de la API (401): {"type":"error",'
                          '"error":{"type":"authentication_error","message":"invalid x-api-key"},'
                          '"request_id":"req_sintetico"}')
        with self.assertRaises(ErrorVinculacion) as e:
            evaluar("x", self.REF, raiz=self.tmp)
        msg = "; ".join(e.exception.args[0])
        self.assertIn("fallo técnico", msg)
        for privado in ("invalid x-api-key", "req_sintetico", "401"):
            self.assertNotIn(privado, msg)

    def test_error_de_conexion_es_invalida(self):
        for motivo in ("error del modelo: No se pudo conectar con la API: sintético",
                       "error del modelo: reintentos agotados",
                       "error al conectar: servidor MCP sin vincular al caso: sintético"):
            with self.subTest(motivo=motivo):
                self.traza(motivo=motivo)
                self.rechaza("fallo técnico")

    def test_ejecucion_valida_incorrecta_se_puntua(self):
        self.traza(guardados=("s1",))
        self.resultado_crudo(json.dumps({"caso_id": "s1", "secuencia": ["CENAREC-2"]}))
        (fila,) = evaluar("x", self.REF, raiz=self.tmp)
        self.assertEqual((fila["exacta"], fila["f1"], fila["guardado"]), (0.0, 0.0, 1.0))

    def test_ejecucion_valida_correcta_se_puntua(self):
        self.traza(guardados=("s1",))
        self.resultado()
        (fila,) = evaluar("x", self.REF, raiz=self.tmp)
        self.assertEqual((fila["exacta"], fila["f1"], fila["guardado"]), (1.0, 1.0, 1.0))

    def test_http_401_seguido_de_ejecucion_valida_puntua_la_valida(self):
        # Reproduce A/c001: primero un 401 sin guardado; después, el reintento válido.
        self.traza(motivo="error del modelo: Error de la API (401): sintético",
                   fecha="20260101_000000_000000")
        self.traza(guardados=("s1",), fecha="20260101_000500_000000")
        self.resultado()
        (fila,) = evaluar("x", self.REF, raiz=self.tmp)
        self.assertEqual((fila["exacta"], fila["guardado"]), (1.0, 1.0))

    def test_rechaza_traza_sin_evento_fin(self):
        self.traza(guardados=("s1",), con_fin=False)
        self.resultado()
        self.rechaza("no tiene evento 'fin'")

    def test_rechaza_evento_fin_malformado(self):
        for motivo in (None, 42, "", "   "):
            with self.subTest(motivo=motivo):
                self.traza(motivo=motivo)
                self.rechaza("no tiene un 'motivo' de texto")
        self.traza(guardados=("s1",)); self.resultado()
        self.anexar_a_traza('{"tipo": "aviso"}')
        self.rechaza("no es el último")
        self.traza(guardados=("s1",))
        self.anexar_a_traza('{"tipo": "fin", "motivo": "el modelo terminó (end_turn)"}')
        self.rechaza("2 eventos 'fin'")

    def test_limite_de_pasos_sin_guardado_sigue_siendo_puntuable(self):
        # Un fallo del agente (no técnico) se puntúa como tal: no se excluye.
        self.traza(motivo="límite de pasos alcanzado")
        (fila,) = evaluar("x", self.REF, raiz=self.tmp)
        self.assertEqual((fila["exacta"], fila["guardado"]), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
