"""Testes do lado npm (estudo descritivo, §2.3): adaptador d5 e oraculo npm_lock.sh.

Esperados escritos a mao. Nenhum teste aqui resolve pacote real do registry: o oraculo
so roda sobre a fixture nucleo/fixtures/npm_local (tarballs locais, zero bytes da rede);
as guardas e o teto sao testados sem rede. O quadro so e lido se V_NPM_QUADRO apontar
para o tarball npm-high-impact-1.13.0.tgz.

Rodar de experimento/:  [V_NPM_QUADRO=<tgz>] <venv>/bin/python -m unittest -v adaptadores.test_npm
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptadores import npm  # noqa: E402

EXP = Path(__file__).resolve().parents[1]
ORACULO = EXP / "oraculo" / "npm_lock.sh"
FIXTURE = EXP / "nucleo" / "fixtures" / "npm_local"
QUADRO = os.environ.get("V_NPM_QUADRO")


def _cadeia_ok() -> bool:
    try:
        nv = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
        mv = subprocess.run(["npm", "--version"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return False
    return (nv, mv) == (npm._DECL["cadeia"]["node"], npm._DECL["cadeia"]["npm"])


# Lockfile v3 escrito a mao: manifesto-base -> r (raiz) ; r -> a ^1 , b 2.0.0 (exata), c (apelido
# npm:k@^3), d git ; a -> b ^2 (b aninhado em a numa 2a versao) ; peer e opcional ausentes.
LOCK_P = {"lockfileVersion": 3, "packages": {
    "": {"name": "env", "version": "0.0.0", "dependencies": {"r": "latest"}},
    "node_modules/r": {"version": "1.0.0", "dependencies": {"a": "^1.0.0", "b": "2.0.0",
                       "c": "npm:k@^3.0.0", "d": "github:u/d"},
                       "peerDependencies": {"p": "*"}, "optionalDependencies": {"o": "~1"}},
    "node_modules/a": {"version": "1.2.0", "dependencies": {"b": "^2.1.0"}},
    "node_modules/a/node_modules/b": {"version": "2.1.5"},
    "node_modules/b": {"version": "2.0.0"},
    "node_modules/c": {"name": "k", "version": "3.4.0"},
    "node_modules/d": {"version": "0.1.0", "resolved": "git+ssh://git@github.com/u/d.git#0"},
    "node_modules/l": {"link": True, "resolved": "x"}}}
LOCK_C = json.loads(json.dumps(LOCK_P))
LOCK_C["packages"]["node_modules/a/node_modules/b"]["version"] = "2.1.6"
LOCK_C["packages"]["node_modules/z"] = {"version": "9.0.0"}


class TestAdaptador(unittest.TestCase):
    def test_janelas(self):
        js = npm.janelas()
        self.assertEqual(len(js), 84)                     # 2019-01 .. 2025-12
        self.assertEqual(js[0], "2019-01-31T23:59:59.999Z")
        self.assertEqual(js[13], "2020-02-29T23:59:59.999Z")
        self.assertEqual(js[-1], "2025-12-31T23:59:59.999Z")
        self.assertEqual(len(npm.pares_janelas()), 83)
        self.assertEqual(js, sorted(js))

    def test_manifesto_fixo(self):
        m = json.loads(npm.manifesto("q"))
        self.assertEqual(m["dependencies"], {"q": "latest"})
        self.assertTrue(m["private"])
        self.assertEqual(npm.manifesto("q"), npm.manifesto("q"))

    def test_sorteio(self):
        pop = [f"p{i:05d}" for i in range(1000)]
        a = npm.sortear_raizes(pop, 7)
        self.assertEqual(len(a), 200)
        self.assertEqual(len(set(a)), 200)
        self.assertEqual(a, npm.sortear_raizes(list(reversed(pop)), 7))   # nao depende da ordem
        self.assertEqual(a, npm.sortear_raizes(pop, "7"))
        self.assertNotEqual(a, npm.sortear_raizes(pop, 8))
        import random
        self.assertEqual(a, sorted(random.Random("7:npm_raizes").sample(sorted(pop), 200)))

    def test_tipo_spec(self):
        casos = {"^1.2.3": "data", "1.2.3": "fixa", "=v1.2.3": "fixa", " 1.2.3-b.1 ": "fixa",
                 "1.2.3+m": "fixa", "latest": "data", "next": "data", "*": "data", "": "data",
                 ">=1 <2": "data", "1.x": "data", "~1.2": "data", "1.2": "data",
                 "1.0.0 - 2.0.0": "data", "<1 || >=2": "data",
                 "npm:k@1.2.3": "fixa", "npm:@s/k@^1": "data", "npm:k": "data",
                 "git+https://h/r.git": "fora", "git://h/r": "fora", "github:u/r": "fora",
                 "u/r": "fora", "u/r#v1": "fora", "https://h/x.tgz": "fora",
                 "file:../x": "fora", "./x": "fora", "../x": "fora", "/abs": "fora",
                 "~/x": "fora", "link:../x": "fora", "workspace:*": "fora"}
        for s, t in casos.items():
            self.assertEqual(npm.d5_tipo_spec(s), t, s)

    def test_lockfile(self):
        v = npm.versoes(LOCK_P)
        self.assertEqual(v, {"a": ("1.2.0",), "b": ("2.0.0", "2.1.5"), "d": ("0.1.0",),
                             "k": ("3.4.0",), "r": ("1.0.0",)})        # sem "" e sem link
        self.assertEqual(npm.d1_universo(LOCK_P, LOCK_C), set(v))
        self.assertEqual(npm.identidade(LOCK_P, LOCK_C), {"z"})
        self.assertTrue(npm.manifesto_igual(LOCK_P, LOCK_C, "r"))
        self.assertEqual(npm.semente(LOCK_P, LOCK_C, "r"), {})
        self.assertEqual(npm.d1_nos(LOCK_P)["b"], b"2.0.0,2.1.5")
        self.assertNotEqual(npm.d1_nos(LOCK_P)["b"], npm.d1_nos(LOCK_C)["b"])
        self.assertEqual(npm.d1_tipo(""), "raiz")
        self.assertIsNone(npm.d1_elemento(""))
        self.assertEqual(npm.d1_elemento("b"), "b")
        G = npm.d2_declarado(LOCK_P)
        esperadas = {("r", ""), ("a", "r"), ("b", "r"), ("k", "r"), ("d", "r"), ("p", "r"),
                     ("o", "r"), ("b", "a")}                  # u -> v: v consome u
        self.assertEqual(set(G.edges), esperadas)
        self.assertEqual(npm.pendentes(LOCK_P), set())          # p e o: peer/opcional
        lig = npm.d5_ligacoes(LOCK_P)
        self.assertEqual(lig[("b", "r")], "fixa")
        self.assertEqual(lig[("b", "a")], "data")
        self.assertEqual(lig[("d", "r")], "fora")
        self.assertEqual(npm.d5_semente(LOCK_P), {"r", "a", "b", "k", "p", "o"})
        self.assertEqual(npm.b_sem({"r": "M", "zz": "A"}, set(v)), {"r"})

    def test_manifesto_muda(self):
        c = json.loads(json.dumps(LOCK_P))
        c["packages"]["node_modules/r"]["version"] = "1.0.1"
        self.assertFalse(npm.manifesto_igual(LOCK_P, c, "r"))
        self.assertEqual(npm.semente(LOCK_P, c, "r"), {"r": "M"})
        sem = json.loads(json.dumps(LOCK_P))
        del sem["packages"]["node_modules/r"]
        self.assertFalse(npm.manifesto_igual(sem, sem, "r"))

    def test_portas_nao_aplicaveis(self):
        self.assertIsNone(npm.d3_checksum)
        self.assertIsNone(npm.d4_intervalos)
        self.assertIsNone(npm.d2_extraido(LOCK_P))
        self.assertIsNone(npm.b_make(None, {}))
        self.assertEqual(npm.d6_globais(LOCK_P), set())
        self.assertEqual(npm.D7, "fecho_sobre_ciclo_e_conta")
        self.assertEqual(npm.D5["resolucao"], "por_data")

    @unittest.skipUnless(QUADRO, "V_NPM_QUADRO nao definido")
    def test_quadro(self):
        nomes = npm.quadro(QUADRO)
        self.assertEqual(len(nomes), 17338)
        self.assertEqual(npm.hashes(QUADRO)["sha1"], npm._DECL["quadro"]["shasum"])
        with tempfile.TemporaryDirectory() as t:
            ruim = Path(t) / "q.tgz"
            ruim.write_bytes(Path(QUADRO).read_bytes() + b"\0")
            with self.assertRaises(ValueError):
                npm.quadro(ruim)


class TestAuditoria(unittest.TestCase):
    def test_tamanho(self):
        n = len((EXP / "adaptadores" / "npm.py").read_text().splitlines())
        self.assertLessEqual(n, 400)                            # §4.3 iii

    def test_espec_cita(self):                                  # §4.3 i
        for campo, cita in npm.ESPEC.items():
            self.assertRegex(cita, r"(npm@10\.9\.4|arborist@|pacote@|PROTOCOLO_V|npm-high-impact@)",
                             campo)

    def test_sem_resolvedor_no_adaptador(self):                 # §4.3 iv
        arv = ast.parse((EXP / "adaptadores" / "npm.py").read_text())
        imps = set()
        for n in ast.walk(arv):
            if isinstance(n, ast.Import):
                imps |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                imps.add((n.module or "").split(".")[0])
        self.assertEqual(imps - {"__future__", "calendar", "hashlib", "io", "json", "random",
                                 "re", "tarfile", "pathlib", "networkx"}, set())
        nomes = {n.id for n in ast.walk(arv) if isinstance(n, ast.Name)}
        nomes |= {n.attr for n in ast.walk(arv) if isinstance(n, ast.Attribute)}
        self.assertEqual(nomes & {"subprocess", "system", "popen", "Popen", "spawn", "exec",
                                  "eval", "run", "check_output", "urlopen"}, set())

    def test_oraculo_nao_chama_python(self):
        s = ORACULO.read_text()
        self.assertNotRegex(s, r"\bpython")
        self.assertNotIn("adaptadores", s.replace("adaptadores/decl_npm.json", "")
                         .replace("nem os adaptadores", ""))

    def test_constantes_do_oraculo_iguais_a_decl(self):
        s = ORACULO.read_text()
        self.assertIn(f"TETO_PADRAO={npm._DECL['teto_bytes']['valor']}\n", s)
        self.assertIn(f"NPM_VERSAO={npm._DECL['cadeia']['npm']}\n", s)
        self.assertIn(f"V_NODE:-{npm._DECL['cadeia']['node']}}}", s)
        self.assertIn(f"REGISTRY={npm._DECL['registry']['valor']}\n", s)

    # Colisoes de vocabulario: palavras genericas que TAMBEM sao nomes registrados no
    # quadro, usadas no codigo como chave, evento ou modulo, nunca como no. Lista fechada.
    COLISOES = {
        "-": "separador de AAAA-MM (janelas)",
        "n": "chave de decl_npm.json:raizes",
        "bytes": "chave do dicionario de hashes",
        "pacote": "chave de decl_npm.json:quadro",
        "shasum": "chave de decl_npm.json:quadro (campo dist.shasum do registry)",
        "sha1": "nome do algoritmo de hash",
        "npm": "valor do campo corpus do relatorio",
        "connect": "evento de socket do node (net)",
        "error": "evento de socket do node (net)",
        "fs": "modulo embutido do node",
        "net": "modulo embutido do node",
        "utf8": "codificacao de leitura do lockfile",
    }

    @unittest.skipUnless(QUADRO, "V_NPM_QUADRO nao definido")
    def test_zero_identificador_literal(self):                  # §4.3 ii
        nomes = set(npm.quadro(QUADRO))
        for rel in ("adaptadores/npm.py", "ensaio/npm_orcamento.py"):
            arv = ast.parse((EXP / rel).read_text())
            consts = {n.value for n in ast.walk(arv)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str)}
            self.assertEqual(sorted((consts & nomes) - set(self.COLISOES)), [], rel)
        s = ORACULO.read_text()
        lits = set(re.findall(r'"([^"\s$]+)"', s)) | set(re.findall(r"'([^'\s$]+)'", s))
        self.assertEqual(sorted((lits & nomes) - set(self.COLISOES)), [], "npm_lock.sh")


def _roda(args, env_extra=None):
    env = dict(os.environ)
    env.pop("V_MODO", None)
    env.update(env_extra or {})
    return subprocess.run([str(ORACULO), *args], env=env, capture_output=True, text=True)


class TestOraculo(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.est = os.path.join(self.t, "estado")

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def test_guarda_fora_da_fixture(self):
        man = Path(self.t) / "package.json"
        man.write_bytes(npm.manifesto("q"))
        r = _roda([str(man), "2019-01-31", self.t + "/s"], {"V_NPM_ESTADO": self.est})
        self.assertEqual(r.returncode, 9, r.stderr)
        r = _roda([str(man), "2019-01-31", self.t + "/s"],
                  {"V_NPM_ESTADO": self.est, "V_MODO": "confirmatorio"})   # sem doi
        self.assertEqual(r.returncode, 9, r.stderr)
        self.assertFalse(os.path.exists(self.est))               # nada rodou

    def test_guarda_orcamento(self):
        r = _roda(["--orcamento", str(FIXTURE / "package.json"), "2019-01-31"],
                  {"V_NPM_ESTADO": self.est})
        self.assertEqual(r.returncode, 9, r.stderr)

    def test_uso_e_data(self):
        r = _roda([str(FIXTURE / "package.json"), "2019-13", self.t + "/s"],
                  {"V_NPM_ESTADO": self.est})
        self.assertEqual(r.returncode, 2)
        r = _roda([str(FIXTURE / "package.json"), "2019-01-31", self.t + "/s"])
        self.assertEqual(r.returncode, 2)                        # sem V_NPM_ESTADO

    @unittest.skipUnless(_cadeia_ok(), "node/npm diferentes da cadeia fixada")
    def test_teto_acumulado_sem_rede(self):
        os.makedirs(self.est)
        Path(self.est, "baixados").write_text("150\n")
        r = _roda([str(FIXTURE / "package.json"), "2019-01-31", self.t + "/s"],
                  {"V_NPM_ESTADO": self.est, "V_NPM_TETO": "100"})
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertFalse(Path(self.t, "s", "package-lock.json").exists())
        self.assertIn("codigo\t5\n", Path(self.t, "s", "execucao.tsv").read_text())

    @unittest.skipUnless(_cadeia_ok(), "node/npm diferentes da cadeia fixada")
    def test_fixture_duas_vezes(self):
        saidas = []
        for i in (1, 2):
            s = os.path.join(self.t, f"s{i}")
            r = _roda([str(FIXTURE / "package.json"), "2019-01-31T23:59:59.999Z", s],
                      {"V_NPM_ESTADO": self.est})
            self.assertEqual(r.returncode, 0, r.stderr)
            saidas.append(Path(s))
        esperado = "pa\t1.0.0\npb\t2.0.0,3.0.0\n"                 # LEIAME da fixture
        for s in saidas:
            self.assertEqual((s / "resolvido.tsv").read_text(), esperado)
            self.assertIn("bytes\t0\n", (s / "execucao.tsv").read_text())
            # a mesma regra no oraculo (node) e no adaptador (python)
            lock = npm.ler_lock(s / "package-lock.json")
            self.assertEqual(npm.versoes(lock), npm.ler_resolvido(s / "resolvido.tsv"))
        self.assertEqual((saidas[0] / "package-lock.json").read_bytes(),
                         (saidas[1] / "package-lock.json").read_bytes())
        self.assertEqual(Path(self.est, "baixados").read_text().strip(), "0")


if __name__ == "__main__":
    unittest.main()
