"""
Pruebas del instrumento evidencia/registrar_pruebas.py (D2b). No prueban el sistema LESCO-Agent.

Cada prueba crea un repositorio git sintético en una carpeta temporal y reemplaza, solo durante la prueba,
las rutas y las suites del módulo. Los datos "sensibles" son sintéticos y se arman en ejecución, para que
este archivo no contenga ninguno literal. Ninguna prueba usa la red ni la API.

    python -m unittest discover -s evidencia -p "test_*.py" -v
"""

import argparse
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registrar_pruebas as rp  # noqa: E402

SUITES_REALES = dict(rp.SUITES)          # copia tomada antes de cualquier reemplazo

# Datos sensibles sintéticos, armados en ejecución (este archivo no contiene ninguno literal).
CLAVE = "sk-" + "ant-" + "x" * 24
CORREO = "persona" + "@" + "ejemplo.invalid"
WORKSPACE = "wrkspc" + "_" + "a" * 16
AUTORIZACION = "Autorizado por el autor (prueba sintética)"

SUITES_SINTETICAS = {
    "ok": ["-c", "import sys; print('Ran 1 test in 0.001s'); sys.stderr.write('OK\\n')"],
    "falla": ["-c", "import sys; sys.stderr.write('Ran 1 test in 0.001s\\nFAILED (failures=1)\\n'); sys.exit(1)"],
    "lenta": ["-c", "import time; print('parcial', flush=True); time.sleep(30)"],
    "sensible": ["-c", "import pathlib; print(pathlib.Path.home()); "
                       f"print({CLAVE!r}); print({CORREO!r}); print({WORKSPACE!r})"],
    "binaria": ["-c", "import sys; sys.stdout.buffer.write(bytes([0, 255]) + b'abc')"],
    "modifica_codigo": ["-c", "open('agente/a.py', 'a').write('y = 2\\n')"],
    "modifica_protegido": ["-c", "open('trazas/t.jsonl', 'a').write('{}\\n')"],
}
ARCHIVOS_BASE = {
    "agente/a.py": "x = 1\n",
    "tests/test_x.py": "# prueba sintética\n",
    "eval/casos.jsonl": '{"caso_id": "s1", "texto": "texto sintético"}\n',
    "eval/anotaciones/x.tsv": "caso_id\tetiqueta\n",
    "trazas/t.jsonl": "{}\n",
    "resultados/r.json": "{}\n",
    "data/d.tsv": "idw\tglosa\n",
}


def _borrar(ruta: Path) -> None:
    def quitar_solo_lectura(funcion, p, _info):          # los objetos de .git son de solo lectura en Windows
        os.chmod(p, stat.S_IWRITE)
        funcion(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(ruta, onexc=quitar_solo_lectura)
    else:
        shutil.rmtree(ruta, onerror=quitar_solo_lectura)


def _sha(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


class BaseRegistro(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lesco_registrador_"))
        self.addCleanup(_borrar, self.tmp)
        self.repo = self.tmp / "repo"
        for rel, texto in ARCHIVOS_BASE.items():
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(texto, encoding="utf-8", newline="\n")
        (self.tmp / "gitconfig").write_text("", encoding="utf-8")   # aísla la configuración global de git
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.name=prueba", "-c", "user.email=" + "prueba" + "@" + "ejemplo.invalid",
                 "commit", "-q", "-m", "base sintética")
        ev = self.repo / "evidencia"
        for nombre, valor in {"RAIZ": self.repo, "DIR_PRIVADO": ev / "privado", "DIR_PUBLICO": ev / "pruebas",
                              "INDICE": ev / "INDICE.md", "APROBACIONES": ev / "APROBACIONES.md"}.items():
            parche = mock.patch.object(rp, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)
        parche = mock.patch.dict(rp.SUITES, SUITES_SINTETICAS, clear=True)
        parche.start()
        self.addCleanup(parche.stop)

    def git(self, *args):
        env = {**os.environ, "GIT_CONFIG_GLOBAL": str(self.tmp / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1"}
        subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=self.repo, env=env,
                       check=True, capture_output=True)

    def registrar(self, suite, etiqueta, verifica=None, tiempo_max=30):
        args = argparse.Namespace(suite=suite, etiqueta=etiqueta, tipo="ejecucion", verifica=verifica,
                                  tiempo_max=tiempo_max)
        with redirect_stdout(io.StringIO()):
            codigo = rp.registrar(args)
        (registro,) = [p for p in rp.DIR_PRIVADO.iterdir() if p.is_dir() and p.name.endswith("_" + etiqueta)]
        return codigo, registro

    def verificar(self, carpeta, con_codigo=False):
        salida = io.StringIO()
        with redirect_stdout(salida):
            r = rp.verificar(carpeta, con_codigo)
        return r, salida.getvalue()

    def aprobar(self, nombre, texto=AUTORIZACION):
        with redirect_stdout(io.StringIO()):
            return rp.aprobar(nombre, texto)

    def celdas(self, archivo: Path, nombre: str) -> list[str]:
        filas = [l for l in archivo.read_text(encoding="utf-8").splitlines() if l.startswith(f"| {nombre} |")]
        self.assertEqual(len(filas), 1)
        return [c.strip() for c in filas[0].strip().strip("|").split("|")]

    def main_cli(self, *argv):
        with mock.patch.object(sys, "argv", ["registrar_pruebas.py", *argv]), \
                redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as e:
                rp.main()
        return e.exception.code


# ---------------------------------------------------------------- 1. registro íntegro
class TestRegistroIntegro(BaseRegistro):
    def test_salidas_fechas_codigo_y_sha256(self):
        codigo, reg = self.registrar("ok", "ok")
        self.assertEqual(codigo, 0)
        original = reg / "original"
        ctx = rp.cargar_json(original, "contexto.json")
        salida, error = (original / "stdout.txt").read_bytes(), (original / "stderr.txt").read_bytes()
        self.assertIn(b"Ran 1 test in 0.001s", salida)
        self.assertEqual(error.strip(), b"OK")
        self.assertEqual(ctx["sha256"]["stdout.txt"], _sha(salida))
        self.assertEqual(ctx["sha256"]["stderr.txt"], _sha(error))
        self.assertEqual(ctx["codigo_salida"], 0)
        inicio, fin = datetime.fromisoformat(ctx["fecha_inicio"]), datetime.fromisoformat(ctx["fecha_fin"])
        self.assertIsNotNone(inicio.tzinfo)
        self.assertLessEqual(inicio, fin)
        self.assertGreaterEqual(ctx["duracion_s"], 0)
        self.assertEqual(ctx["resumen_literal"], ["Ran 1 test in 0.001s", "OK"])
        for linea in (original / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            esperado, _, rel = linea.partition("  ")
            self.assertEqual(_sha((original / rel).read_bytes()), esperado, rel)
        self.assertEqual(self.verificar(original)[0], 0)
        self.assertEqual(self.verificar(reg / "candidata")[0], 0)

    def test_registro_limpio_sin_rutas_absolutas(self):
        # La carpeta temporal suele estar dentro del directorio personal: si el registro filtrara rutas
        # absolutas, la candidata saldría redactada.
        _, reg = self.registrar("ok", "limpio")
        pub = rp.cargar_json(reg / "candidata", "PUBLICACION.json")
        self.assertFalse(pub["contiene_redacciones"], pub["archivos_redactados"])
        self.assertFalse(pub["contiene_exclusiones"], pub["archivos_excluidos"])


# ---------------------------------------------------------------- 2. estados separados
class TestEstadosSeparados(BaseRegistro):
    def test_cuatro_estados_en_contexto_indice_publicacion_y_verificar(self):
        _, reg = self.registrar("ok", "estados")
        ctx = rp.cargar_json(reg / "original", "contexto.json")
        self.assertEqual(ctx["resultado_suite"], "OK")
        self.assertEqual(ctx["integridad_operativa"], "CONFORME")
        self.assertEqual(ctx["estado_publicacion"], rp.ESTADO_PUBLICACION)
        self.assertNotIn("VERIFICADA", json.dumps(ctx, ensure_ascii=False))   # no se certifica a sí mismo
        celdas = self.celdas(rp.INDICE, reg.name)
        self.assertEqual(celdas[4:8], ["OK", "CONFORME", "no", rp.ESTADO_PUBLICACION])
        pub = rp.cargar_json(reg / "candidata", "PUBLICACION.json")
        self.assertEqual(pub["estado_publicacion"], rp.ESTADO_PUBLICACION)
        r, texto = self.verificar(reg / "candidata")
        self.assertEqual(r, 0)
        for esperado in ("Integridad criptográfica: VERIFICADA", "Integridad operativa:     CONFORME",
                         "Resultado de la suite:    OK", f"Publicación:              {rp.ESTADO_PUBLICACION}"):
            self.assertIn(esperado, texto)


# ---------------------------------------------------------------- 3. suite fallida
class TestSuiteFallida(BaseRegistro):
    def test_suite_fallida_es_evidencia_integra_y_publicable(self):
        codigo, reg = self.registrar("falla", "falla")
        self.assertEqual(codigo, 1)                              # la suite falló; la evidencia es válida
        ctx = rp.cargar_json(reg / "original", "contexto.json")
        self.assertEqual((ctx["resultado_suite"], ctx["integridad_operativa"], ctx["codigo_salida"]),
                         ("FALLÓ", "CONFORME", 1))
        self.assertEqual(ctx["resumen_literal"], ["Ran 1 test in 0.001s", "FAILED (failures=1)"])
        r, texto = self.verificar(reg / "candidata")
        self.assertEqual(r, 0)
        self.assertIn("EVIDENCIA ÍNTEGRA", texto)
        self.assertEqual(self.verificar(reg / "original")[0], 0)
        self.assertEqual(self.aprobar(reg.name), 0)
        self.assertIn("FALLÓ", self.celdas(rp.APROBACIONES, reg.name))

    def test_tiempo_agotado_conserva_salida_parcial(self):
        codigo, reg = self.registrar("lenta", "lenta", tiempo_max=2)
        ctx = rp.cargar_json(reg / "original", "contexto.json")
        self.assertEqual((ctx["resultado_suite"], ctx["integridad_operativa"]), ("TIEMPO_AGOTADO", "CONFORME"))
        self.assertIn(b"parcial", (reg / "original" / "stdout.txt").read_bytes())
        self.assertEqual(codigo, 1)
        self.assertEqual(self.verificar(reg / "original")[0], 0)


# ---------------------------------------------------------------- 4. sobrescritura y comandos
class TestSobrescrituraYComandos(BaseRegistro):
    def test_no_sobrescribe_un_registro_existente(self):
        class Fija(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 1, 2, 3, 4, 5)

        with mock.patch.object(rp, "datetime", Fija):
            _, reg = self.registrar("ok", "fija")
            antes = {p: p.read_bytes() for p in reg.rglob("*") if p.is_file()}
            with self.assertRaises(SystemExit):
                self.registrar("ok", "fija")
        self.assertEqual({p: p.read_bytes() for p in reg.rglob("*") if p.is_file()}, antes)
        self.assertEqual(len(self.celdas(rp.INDICE, reg.name)), 10)           # una sola fila

    def test_crear_nunca_sobrescribe(self):
        ruta = self.tmp / "a.txt"
        rp.crear(ruta, b"1")
        with self.assertRaises(FileExistsError):
            rp.crear(ruta, b"2")
        self.assertEqual(ruta.read_bytes(), b"1")

    def test_cli_rechaza_suite_no_autorizada_y_argumentos_extra(self):
        base = ["registrar", "--etiqueta", "x", "--tipo", "ejecucion"]
        for argv in (base + ["--suite", "otra"], base + ["--suite", "ok", "--", "curl", "http://203.0.113.1"]):
            with self.subTest(argv=argv):
                self.assertEqual(self.main_cli(*argv), 2)
        self.assertFalse(rp.DIR_PRIVADO.exists())                # no se ejecutó nada

    def test_suites_reales_solo_unittest_local(self):
        self.assertEqual(sorted(SUITES_REALES), ["completa", "registrador", "servidor"])
        for nombre, args in SUITES_REALES.items():
            self.assertEqual(args[:2], ["-m", "unittest"], nombre)

    def test_entorno_minimo_sin_credenciales(self):
        falso = {"PATH": "x", "SYSTEMROOT": "y", "ANTHROPIC_API_KEY": CLAVE,
                 "ANTHROPIC_WORKSPACE_ID": WORKSPACE, "OTRA_VARIABLE": "z"}
        with mock.patch.dict(os.environ, falso, clear=True):
            env = rp.entorno_minimo("guardia")
        for ausente in ("ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID", "OTRA_VARIABLE"):
            self.assertNotIn(ausente, env)
        self.assertEqual((env["PATH"], env["PYTHONPATH"], env["PYTHONIOENCODING"]), ("x", "guardia", "utf-8"))

    def test_guardia_parcial_de_red_en_proceso_hijo(self):
        guardia = self.tmp / "guardia"
        guardia.mkdir()
        (guardia / "sitecustomize.py").write_text(rp.GUARDIA_RED, encoding="utf-8")
        # La aserción va primero: si la guardia no estuviera activa, no se intentaría ninguna conexión.
        codigo = ("import socket, sys\n"
                  "assert socket.getaddrinfo.__name__ == '_bloqueado'\n"
                  "try:\n"
                  "    socket.create_connection(('203.0.113.1', 9), timeout=1)\n"
                  "except PermissionError:\n"
                  "    sys.exit(0)\n"
                  "sys.exit(1)\n")
        r = subprocess.run([sys.executable, "-c", codigo], env=rp.entorno_minimo(str(guardia)),
                           capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)


# ---------------------------------------------------------------- 5. datos sensibles
class TestDatosSensibles(BaseRegistro):
    def test_detecta_y_redacta_en_todos_los_archivos(self):
        hogar = str(Path.home())
        (self.repo / "agente" / "a.py").write_text(f"x = 1\nCLAVE = {CLAVE!r}\n", encoding="utf-8",
                                                  newline="\n")                      # → cambios.patch
        (self.repo / "agente" / "nuevo.py").write_text(f"RUTA = {hogar!r}\n", encoding="utf-8",
                                                      newline="\n")                  # → fuentes/
        _, reg = self.registrar("sensible", "sensible", verifica=f"contacto {CORREO}")  # → inicio/contexto
        original, candidata = reg / "original", reg / "candidata"
        pub = rp.cargar_json(candidata, "PUBLICACION.json")
        esperados = {"stdout.txt", "cambios.patch", "fuentes/agente/nuevo.py", "inicio.json", "contexto.json"}
        self.assertTrue(esperados <= set(pub["archivos_redactados"]), pub["archivos_redactados"])
        self.assertTrue(pub["contiene_redacciones"])
        pats = rp.patrones_sensibles()
        for p in candidata.rglob("*"):
            if p.is_file():
                self.assertEqual(rp.revisar(p.read_bytes(), pats)[1], {}, p.name)
        for rel in esperados:
            d = pub["archivos"][rel]
            self.assertEqual(d["publicado_como"], rel + ".redactado")
            self.assertFalse((candidata / rel).exists())                 # nunca con el nombre del original
            self.assertNotEqual(d["sha256_original"], d["sha256_publicado"])
            self.assertEqual(_sha((original / rel).read_bytes()), d["sha256_original"])
        self.assertIn(CLAVE.encode(), (original / "stdout.txt").read_bytes())   # el original no se altera
        self.assertEqual(self.verificar(candidata)[0], 0)

    def test_terminos_privados_del_autor(self):
        rp.DIR_PRIVADO.mkdir(parents=True)
        (rp.DIR_PRIVADO / "terminos_privados.txt").write_text("Ran 1 test\n", encoding="utf-8")
        _, reg = self.registrar("ok", "terminos")
        pub = rp.cargar_json(reg / "candidata", "PUBLICACION.json")
        self.assertIn("stdout.txt", pub["archivos_redactados"])
        self.assertEqual(pub["archivos"]["stdout.txt"]["redacciones"], {"termino_privado": 1})


# ---------------------------------------------------------------- 6. publicación
class TestPublicacion(BaseRegistro):
    def test_registrar_no_publica_nada(self):
        self.registrar("ok", "nopublica")
        self.assertFalse(rp.DIR_PUBLICO.exists())
        self.assertFalse(rp.APROBACIONES.exists())

    def test_cli_aprobar_sin_autorizacion(self):
        _, reg = self.registrar("ok", "cli")
        self.assertEqual(self.main_cli("aprobar", reg.name), 2)
        self.assertFalse(rp.DIR_PUBLICO.exists())

    def test_aprobar_rechaza_autorizacion_vacia(self):
        _, reg = self.registrar("ok", "vacia")
        with self.assertRaises(SystemExit):
            self.aprobar(reg.name, "   ")
        self.assertFalse(rp.DIR_PUBLICO.exists())

    def test_aprobar_rechaza_autorizacion_con_datos_sensibles(self):
        _, reg = self.registrar("ok", "autsensible")
        self.assertEqual(self.aprobar(reg.name, f"aprobado por {CORREO}"), 1)
        self.assertFalse((rp.DIR_PUBLICO / reg.name).exists())

    def test_aprobar_rechaza_restos_sensibles_en_la_candidata(self):
        _, reg = self.registrar("ok", "restos")
        (rp.DIR_PRIVADO / "terminos_privados.txt").write_text("Ran 1 test\n", encoding="utf-8")  # término nuevo
        self.assertEqual(self.aprobar(reg.name), 1)
        self.assertFalse((rp.DIR_PUBLICO / reg.name).exists())

    def test_aprobado_solo_por_aprobaciones_y_sin_republicar(self):
        _, reg = self.registrar("ok", "aprobado")
        self.assertEqual(self.aprobar(reg.name), 0)
        publicado = rp.DIR_PUBLICO / reg.name
        self.assertEqual(rp.cargar_json(publicado, "PUBLICACION.json")["estado_publicacion"],
                         rp.ESTADO_PUBLICACION)                                  # el registro no cambia
        r, texto = self.verificar(publicado)
        self.assertEqual(r, 0)
        self.assertIn("Publicación:              APROBADO", texto)               # solo por APROBACIONES.md
        with self.assertRaises(SystemExit):
            self.aprobar(reg.name)


# ---------------------------------------------------------------- 7. manipulación (V4 sintética)
class TestManipulacion(BaseRegistro):
    def copia(self, reg: Path, sub: str, n: int) -> Path:
        destino = self.tmp / "copias" / str(n) / reg.name / sub
        shutil.copytree(reg / sub, destino)
        return destino

    def test_detecta_manipulacion_de_la_candidata(self):
        _, reg = self.registrar("ok", "manipulacion")
        originales = {p: p.read_bytes() for p in reg.rglob("*") if p.is_file()}

        def regenerar_sumas(c):
            (c / "stdout.txt").write_bytes(b"otro")
            (c / "SHA256SUMS").unlink()
            rp.escribir_sumas(c)

        alteraciones = {
            "byte cambiado": lambda c: (c / "stdout.txt").write_bytes(b"X" + (c / "stdout.txt").read_bytes()[1:]),
            "archivo extra": lambda c: (c / "extra.txt").write_bytes(b"x"),
            "archivo borrado": lambda c: (c / "stderr.txt").unlink(),
            "sumas regeneradas": regenerar_sumas,
        }
        for n, (nombre, alterar) in enumerate(alteraciones.items()):
            with self.subTest(nombre):
                c = self.copia(reg, "candidata", n)
                alterar(c)
                r, texto = self.verificar(c)
                self.assertEqual(r, 1)
                self.assertIn("NO VERIFICADA", texto)
        self.assertEqual({p: p.read_bytes() for p in reg.rglob("*") if p.is_file()}, originales)

    def test_detecta_manipulacion_del_original(self):
        _, reg = self.registrar("ok", "maniporiginal")
        c = self.copia(reg, "original", 0)
        shutil.copytree(reg / "candidata", c.parent / "candidata")
        (c / "stderr.txt").write_bytes(b"alterado")
        r, texto = self.verificar(c)
        self.assertEqual(r, 1)
        self.assertIn("NO VERIFICADA", texto)


# ---------------------------------------------------------------- 8. el proyecto no se modifica
class TestIntegridadDelProyecto(BaseRegistro):
    def test_suite_que_modifica_codigo_es_no_conforme(self):
        codigo, reg = self.registrar("modifica_codigo", "modcodigo")
        self.assertEqual(codigo, 4)
        ctx = rp.cargar_json(reg / "original", "contexto.json")
        self.assertEqual(ctx["integridad_operativa"], "NO_CONFORME")
        self.assertIn("agente/a.py", ctx["integridad"]["codigo_cambiado"])
        r, texto = self.verificar(reg / "candidata")
        self.assertEqual(r, 1)
        self.assertIn("Integridad criptográfica: VERIFICADA", texto)   # los hashes están bien...
        self.assertIn("EVIDENCIA NO ÍNTEGRA", texto)                   # ...pero la ejecución no es válida

    def test_suite_que_modifica_un_archivo_protegido_es_no_conforme(self):
        codigo, reg = self.registrar("modifica_protegido", "modprotegido")
        self.assertEqual(codigo, 4)
        ctx = rp.cargar_json(reg / "original", "contexto.json")
        self.assertIn("trazas/t.jsonl", ctx["integridad"]["protegidos_cambiados"])

    def test_el_registrador_solo_escribe_en_sus_rutas(self):
        def huella():
            return {p.relative_to(self.repo).as_posix(): _sha(p.read_bytes()) for p in self.repo.rglob("*")
                    if p.is_file() and ".git" not in p.relative_to(self.repo).parts
                    and not p.relative_to(self.repo).as_posix().startswith("evidencia/")}
        antes = huella()
        self.registrar("ok", "huella")
        self.assertEqual(huella(), antes)
        nuevos = {p.relative_to(self.repo).as_posix() for p in (self.repo / "evidencia").rglob("*") if p.is_file()}
        self.assertTrue(all(n.startswith(("evidencia/privado/", "evidencia/INDICE.md")) for n in nuevos), nuevos)

    def test_no_escribe_el_indice_de_git(self):
        indice = self.repo / ".git" / "index"
        antes = indice.read_bytes()
        self.registrar("ok", "indicegit")
        self.assertEqual(indice.read_bytes(), antes)


# ---------------------------------------------------------------- 9. original sin candidata
class TestCandidataFallida(BaseRegistro):
    def test_original_verificable_si_falla_la_candidata(self):
        with mock.patch.object(rp, "preparar_candidata", side_effect=RuntimeError("fallo sintético")):
            codigo, reg = self.registrar("ok", "sincandidata")
        self.assertEqual(codigo, 5)
        self.assertFalse((reg / "candidata").exists())
        celdas = self.celdas(rp.INDICE, reg.name)
        self.assertEqual(celdas[-1], "—")
        self.assertTrue(celdas[-2].startswith("`"))
        r, texto = self.verificar(reg / "original")
        self.assertEqual(r, 0)
        self.assertIn("EVIDENCIA ÍNTEGRA", texto)
        self.assertNotEqual(self.aprobar(reg.name), 0)
        self.assertFalse(rp.DIR_PUBLICO.exists())


# ---------------------------------------------------------------- 10. contenido no inspeccionable
class TestContenidoNoInspeccionable(BaseRegistro):
    def test_inspeccionable(self):
        self.assertTrue(rp.inspeccionable("texto con tildes: inválido\n".encode("utf-8")))
        self.assertFalse(rp.inspeccionable(b"a\x00b"))
        self.assertFalse(rp.inspeccionable(b"\xff\xfe"))
        self.assertFalse(rp.inspeccionable(b"diff --git a/x b/x\nGIT binary patch\nliteral 3\n"))

    def test_salida_binaria_se_excluye_y_la_evidencia_sigue_integra(self):
        codigo, reg = self.registrar("binaria", "binaria")
        self.assertEqual(codigo, 0)
        self.assertEqual((reg / "original" / "stdout.txt").read_bytes(), b"\x00\xffabc")
        pub = rp.cargar_json(reg / "candidata", "PUBLICACION.json")
        d = pub["archivos"]["stdout.txt"]
        self.assertTrue(d["excluido"])
        self.assertIsNone(d["publicado_como"])
        self.assertEqual(d["sha256_original"], _sha(b"\x00\xffabc"))
        self.assertTrue(pub["contiene_exclusiones"])
        self.assertFalse((reg / "candidata" / "stdout.txt").exists())
        self.assertFalse((reg / "candidata" / "stdout.txt.redactado").exists())
        r, texto = self.verificar(reg / "candidata")
        self.assertEqual(r, 0)                                  # una exclusión no es corrupción
        self.assertIn("EXCLUIDO", texto)

    def test_patch_y_fuente_binarios_se_excluyen(self):
        (self.repo / "agente" / "a.py").write_bytes(b"x = 1\n\x00binario\n")   # git lo trata como binario
        (self.repo / "agente" / "nuevo.bin").write_bytes(b"\x00\x01")
        _, reg = self.registrar("ok", "patchbinario")
        pub = rp.cargar_json(reg / "candidata", "PUBLICACION.json")
        self.assertIn("cambios.patch", pub["archivos_excluidos"])
        self.assertIn("fuentes/agente/nuevo.bin", pub["archivos_excluidos"])
        self.assertEqual(self.verificar(reg / "candidata")[0], 0)


# ---------------------------------------------------------------- 11. regresión v1.2.1: marcador de parche binario
class TestRegresionMarcadorBinario(BaseRegistro):
    """V3 (v1.2.0) excluyó las fuentes del registrador porque contienen el texto del marcador."""

    def test_python_que_menciona_el_marcador_es_inspeccionable(self):
        fuente = ('MARCA = "GIT binary patch"\n'
                  '"""\n'
                  'GIT binary patch\n'
                  'Esta línea no es un tamaño: el texto anterior no es un parche.\n'
                  '"""\n')
        for fin in ("\n", "\r\n"):
            with self.subTest(fin=repr(fin)):
                self.assertTrue(rp.inspeccionable(fuente.replace("\n", fin).encode("utf-8")))

    def test_parche_binario_real_sigue_excluido(self):
        (self.repo / "agente" / "a.py").write_bytes(b"x = 1\n\x00binario\n")
        env = {**os.environ, "GIT_CONFIG_GLOBAL": str(self.tmp / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1"}
        parche = subprocess.run(["git", "-c", "core.autocrlf=false", "diff", "HEAD", "--binary"], cwd=self.repo,
                                env=env, check=True, capture_output=True).stdout
        self.assertIn(b"GIT binary patch", parche)                     # git generó un parche binario real
        sin_nulos = parche.replace(b"\x00", b"")                       # aun sin bytes nulos se reconoce
        for datos in (parche, sin_nulos, sin_nulos.replace(b"\n", b"\r\n"),
                      b"GIT binary patch\ndelta 12\nabc\n"):
            with self.subTest(datos=datos[:40]):
                self.assertFalse(rp.inspeccionable(datos))

    def test_fuentes_del_registrador_no_se_excluyen(self):
        fuentes = {"evidencia/registrar_pruebas.py": Path(rp.__file__).read_bytes(),
                   "evidencia/test_registrar_pruebas.py": Path(__file__).read_bytes()}
        for rel, datos in fuentes.items():
            self.assertTrue(rp.inspeccionable(datos), rel)
            destino = self.repo / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(datos)                                  # código sin seguimiento → fuentes/
        _, reg = self.registrar("ok", "fuentesregistrador")
        pub = rp.cargar_json(reg / "candidata", "PUBLICACION.json")
        self.assertFalse(pub["contiene_exclusiones"], pub["archivos_excluidos"])
        for rel in fuentes:
            d = pub["archivos"][f"fuentes/{rel}"]
            self.assertFalse(d["excluido"])
            self.assertTrue(d["identico_al_original"])
            self.assertEqual(d["redacciones"], {})                      # tampoco hay falsas redacciones
            self.assertEqual(d["publicado_como"], f"fuentes/{rel}")
        self.assertEqual(self.verificar(reg / "candidata")[0], 0)


if __name__ == "__main__":
    unittest.main()
