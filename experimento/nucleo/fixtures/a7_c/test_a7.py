"""A7 (PROTOCOLO_V_2026-10-02 §4.2): aceitacao do pipeline C sobre a fixture escrita a mao.

Roda o ORACULO REAL (oraculo/c_build.sh --par, cada lado duas vezes) so nesta fixture
(INTERFACES §0: unico uso pre-DOI do oraculo real), o adaptador C (adaptadores/cbuild.py),
os detectores (detectores/c_classes.py) e os ganchos (ganchos/c_d3, c_d2x, c_d6), e compara
com esperado.json, escrito a mao ANTES da primeira execucao (sha256 bb382f60bbeb7f8d...
registrado em 2026-10-02T18:56:11Z). Nunca e evidencia.

Dois sabores: lua/ (makefile no formato do Lua: TESTS, ALL_O, alvo o, $(ALL_O): makefile) e
zlib/ (configure + Makefile.in + zconf.h.in, como o zlib). Par i = (v{i-1}, v{i}).

Rodar, de experimento/:   <v_venv>/bin/python -m unittest -v nucleo.fixtures.a7_c.test_a7
                     ou:  <v_venv>/bin/python nucleo/fixtures/a7_c/test_a7.py
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EXP = AQUI.parents[2]
if str(EXP) not in sys.path:
    sys.path.insert(0, str(EXP))

from adaptadores import cbuild  # noqa: E402
from adaptadores.git_arvore import Arvore, ArvoreDir  # noqa: E402
from detectores import c_classes  # noqa: E402
from ganchos import c_d2x, c_d3, c_d6  # noqa: E402
from nucleo.reach import descritores, eis, reach  # noqa: E402

ESP = json.loads((AQUI / "esperado.json").read_text(encoding="utf-8"))
ORACULO = EXP / "oraculo" / "c_build.sh"
SAIDAS = EXP / "saidas" / "fixtures"
PREC = {"FN": ["T4", "T3-FN", "T1b", "INCLASSIFICADO-FN"], "FP": ["T3-FP", "T2", "T1a", "T5"]}


def primario(lado: str, multi: list[str]) -> str:
    """Precedencia padrao do §4.6, escrita a mao aqui (o modulo generico e de outro componente)."""
    return next(r for r in PREC[lado] if r in multi)


def braco(EIS: set, AIS: set) -> dict:
    FN, FP = sorted(AIS - EIS), sorted(EIS - AIS)
    return {"EIS": sorted(EIS), "FN": FN, "FP": FP, "seguro": not FN}


def oraculo_par(corpus: str, p: str, c: str, saida: Path) -> dict[str, str]:
    r = subprocess.run(["bash", str(ORACULO), "--par", corpus, str(AQUI / corpus), p, c,
                        str(saida)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise AssertionError(f"oraculo {corpus} {p}->{c}: rc={r.returncode} {r.stderr}")
    return dict(ln.split("\t") for ln in (saida / "comparacao.tsv").read_text().splitlines())


def corre_par(corpus: str, ap, ac, comp: dict[str, str]) -> dict:
    """Mini-runner do par: so para aceitar o pipeline (o runner do estudo e executar.py)."""
    A = cbuild.para(corpus)
    produzidos = {o for o, k in comp.items() if k in ("AIS", "IGUAL")}
    U = A.d1_universo(ap, ac) & produzidos
    ident = sorted(set(A._modelo(ap)["U"]) ^ set(A._modelo(ac)["U"])
                   | {o for o, k in comp.items() if k == "MUDANCA_DE_IDENTIDADE"})
    AIS = {o for o, k in comp.items() if k == "AIS"} & U
    S = A.semente(ap, ac)
    G = A.grafo(ap, ac)
    G_obs, cob = A.grafo_obs(ap, ac)

    def E(Gx, Sx):
        return set(eis(Gx, Sx, U, A.d1_elemento))

    d3 = {"ap": ap, "ac": ac, "d3_checksum": A.d3_checksum}
    tem_d6 = bool(A.decl["d6_globais"]["valor"])            # §5: A0+d6 so zlib
    d6 = {"globais": A.d6_globais(ap) | A.d6_globais(ac), "objetos": U}
    b = {"A0": braco(E(G, S), AIS),
         "A0+d3": braco(E(*c_d3.aplicar(G, S, d3)), AIS),
         "A0+d2-extraido": braco(E(*c_d2x.aplicar(G, S, {"G_obs": G_obs})), AIS),
         "A0+d6": braco(E(*c_d6.aplicar(G, S, d6)), AIS) if tem_d6 else None}
    Gf, Sf = c_d2x.aplicar(*c_d3.aplicar(G, S, d3), {"G_obs": G_obs})
    if tem_d6:
        Gf, Sf = c_d6.aplicar(Gf, Sf, d6)
    b["A_full"] = braco(E(Gf, Sf), AIS)
    b["B-ret"] = braco(set(U), AIS)
    b["B-sem"] = braco(A.b_sem(S, U), AIS)
    b["B-make"] = braco(A.b_make(ac, S) & U, AIS)
    inst = [(o, "FN") for o in b["A0"]["FN"]] + [(o, "FP") for o in b["A0"]["FP"]]
    ctx = {"reach": reach, "G": G, "G_obs": G_obs, "S": S, "nos_p": A.d1_nos(ap), "nos_c": A.d1_nos(ac),
           "tipo": A.d1_tipo}
    multi = c_classes.rotular_c(inst, ctx)
    return {"S": S, "U": sorted(U), "AIS": sorted(AIS), "identidade": ident, "bracos": b,
            "instancias": sorted(({"e": o, "lado": l, "primario": primario(l, multi[o]),
                                   "multi": multi[o]} for o, l in inst),
                                  key=lambda d: (d["lado"], d["e"])),
            "nc": c_classes.nc_c(ctx), "cobertura": cob,
            "descritores": {**descritores(G), "PENDENTE": sorted(A.pendentes(ap) | A.pendentes(ac)),
                            "NAO_DETERMINISTICO": sorted(o for o, k in comp.items()
                                                         if k.startswith("NAO_DET"))}}


def monta_git(sabor: str, destino: Path) -> list[str]:
    """Repositorio git com v0..vN como commits (datas fixas); devolve os shas."""
    env = {**os.environ, "GIT_AUTHOR_NAME": "a7", "GIT_AUTHOR_EMAIL": "a7@fixture",
           "GIT_COMMITTER_NAME": "a7", "GIT_COMMITTER_EMAIL": "a7@fixture",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    g = lambda *a: subprocess.run(["git", "-C", str(destino), *a], env=env, check=True,  # noqa: E731
                                  capture_output=True, text=True).stdout.strip()
    destino.mkdir(parents=True)
    g("init", "-q")
    shas = []
    for k, v in enumerate(sorted((AQUI / sabor).iterdir(), key=lambda d: int(d.name[1:]))):
        for f in destino.iterdir():
            if f.name != ".git":
                shutil.rmtree(f) if f.is_dir() else f.unlink()
        shutil.copytree(v, destino, dirs_exist_ok=True, copy_function=shutil.copy)
        (destino / ".git" / "index").unlink(missing_ok=True)   # indice refeito do conteudo
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"2000-01-0{k + 1}T00:00:00Z"
        g("add", "-A")
        g("commit", "-q", "-m", v.name, "--allow-empty")
        shas.append(g("rev-parse", "HEAD"))
    return shas


class A7(unittest.TestCase):
    maxDiff = None

    def _sabor(self, sabor: str):
        SAIDAS.mkdir(parents=True, exist_ok=True)
        obtidos = []
        with tempfile.TemporaryDirectory(prefix="v_a7_") as tmp:
            for esp in ESP[sabor]["pares"]:
                i = esp["par"]
                p, c = f"v{i - 1}", f"v{i}"
                comp = oraculo_par(sabor, p, c, Path(tmp) / f"par{i}")
                r = corre_par(sabor, ArvoreDir(AQUI / sabor / p), ArvoreDir(AQUI / sabor / c), comp)
                obtidos.append({"par": i, **r, "oraculo": comp})
                with self.subTest(sabor=sabor, par=i):
                    for k in ("S", "U", "AIS", "identidade", "bracos", "instancias", "nc"):
                        self.assertEqual(r[k], esp[k], (sabor, i, k))
                    self.assertEqual(r["descritores"]["CICLO"], [])
                    self.assertFalse(r["descritores"]["GRAFO_VAZIO"])
                    self.assertEqual(r["descritores"]["PENDENTE"], [])
                    self.assertEqual(r["descritores"]["NAO_DETERMINISTICO"], [])
                    self.assertEqual(r["cobertura"]["p"]["c_ok"], r["cobertura"]["p"]["c_total"])
                    self.assertEqual(r["cobertura"]["c"]["c_ok"], r["cobertura"]["c"]["c_total"])
        (SAIDAS / f"a7_c_{sabor}.json").write_text(
            json.dumps(obtidos, sort_keys=True, ensure_ascii=False, indent=1, default=sorted),
            encoding="utf-8")

    def test_lua(self):
        self._sabor("lua")

    def test_zlib(self):
        self._sabor("zlib")

    def test_git_igual_a_diretorio(self):
        """A mesma fixture como repositorio git (git diff --name-status, git cat-file) da a
        mesma semente, universo, grafos, B-make e diferencial do parser que como diretorio."""
        with tempfile.TemporaryDirectory(prefix="v_a7_git_") as tmp:
            for sabor in ("lua", "zlib"):
                A = cbuild.para(sabor)
                shas = monta_git(sabor, Path(tmp) / sabor)
                for i in range(1, len(shas)):
                    gp, gc = Arvore(Path(tmp) / sabor, shas[i - 1]), Arvore(Path(tmp) / sabor, shas[i])
                    dp, dc = ArvoreDir(AQUI / sabor / f"v{i - 1}"), ArvoreDir(AQUI / sabor / f"v{i}")
                    with self.subTest(sabor=sabor, par=i):
                        self.assertEqual(A.semente(gp, gc), A.semente(dp, dc))
                        self.assertEqual(A.d1_nos(gc), A.d1_nos(dc))
                        self.assertEqual(A.d1_universo(gp, gc), A.d1_universo(dp, dc))
                        self.assertEqual(sorted(A.grafo(gp, gc).edges(data=True)),
                                         sorted(A.grafo(dp, dc).edges(data=True)))
                        self.assertEqual(sorted(A.grafo_obs(gp, gc)[0].edges(data=True)),
                                         sorted(A.grafo_obs(dp, dc)[0].edges(data=True)))
                        S = A.semente(gp, gc)
                        self.assertEqual(A.b_make(gc, S), A.b_make(dc, S))
                        for lado in (gp, gc):
                            dif = cbuild.diferencial_parser(A, lado, S, reach)
                            self.assertTrue(dif["igual"], dif)

    def test_guarda_do_oraculo(self):
        """Fora de nucleo/fixtures/ e sem V_MODO=confirmatorio + doi, c_build.sh sai com 9."""
        with tempfile.TemporaryDirectory(prefix="v_a7_guarda_") as tmp:
            shutil.copytree(AQUI / "lua", Path(tmp) / "lua")
            for args in (["lua", str(Path(tmp) / "lua"), "v0", str(Path(tmp) / "o1")],
                         ["--par", "lua", str(Path(tmp) / "lua"), "v0", "v1", str(Path(tmp) / "o2")]):
                r = subprocess.run(["bash", str(ORACULO), *args], capture_output=True, text=True,
                                   env={**os.environ, "V_MODO": "confirmatorio"})
                self.assertEqual(r.returncode, 9, r.stderr)
                self.assertFalse((Path(tmp) / "o1" / "manifesto.tsv").exists())

    def test_d3_pygments(self):
        """d3: comentario e espaco nao contam; diretiva e literal contam (leitura do §4.5)."""
        t = cbuild.tokens_d3
        self.assertEqual(t(b"/* a */\nint  x;\n"), t(b"/* b\n   c */ int x; // d\n"))
        self.assertNotEqual(t(b"#define X 1\n"), t(b"#define X 2\n"))
        self.assertNotEqual(t(b'#include "a.h"\n'), t(b'#include "b.h"\n'))
        self.assertNotEqual(t(b'char *s = " ";\n'), t(b'char *s = "";\n'))
        self.assertNotEqual(t(b"#define F(a) a\n"), t(b"#define F (a) a\n"))
        self.assertEqual(t(b"#define X 1 /* um */\n"), t(b"#  define   X 1\n"))

    def test_t2_gcc(self):
        """Detector T2: gcc -fpreprocessed -dD -E -P tira comentario e nada mais."""
        f = c_classes.sem_comentario
        self.assertEqual(f(b"/* a */\nint x;\n"), f(b"/* b\n   c */\nint x; // d\n"))
        self.assertNotEqual(f(b"#define X 1\n"), f(b"#define X 2\n"))
        self.assertNotEqual(f(b"int x = 1;\n"), f(b"int x = 2;\n"))

    def test_auditoria_cbuild(self):
        """§4.3 (ii)-(iv) no adaptador C: <= 400 linhas; nenhum valor de decl_*.json como
        literal no codigo; comandos externos so git, make e gcc -MM."""
        fonte = (EXP / "adaptadores" / "cbuild.py").read_text(encoding="utf-8")
        self.assertLessEqual(len(fonte.splitlines()), 400)
        nomes: set[str] = set()
        for corpus in ("zlib", "lua"):
            for k, v in json.loads((EXP / "adaptadores" / f"decl_{corpus}.json").read_text()).items():
                if isinstance(v, dict):
                    for x in [v.get("valor")] + [v.get(s) for s in ("fonte", "cabecalho", "objeto")]:
                        nomes |= {x} if isinstance(x, str) else set(x or [])
        consts = {n.value for n in ast.walk(ast.parse(fonte))
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        self.assertEqual(consts & nomes, set())
        cmds = {n.elts[0].value for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.List)
                and n.elts and isinstance(n.elts[0], ast.Constant) and isinstance(n.elts[0].value, str)
                and n.elts[0].value in ("git", "make", "gcc", "cc", "ld", "cc1", "zic", "zdump",
                                        "sh", "bash", "npm")}
        self.assertEqual(cmds, {"git", "make", "gcc"})
        for n in ast.walk(ast.parse(fonte)):
            if isinstance(n, ast.List) and n.elts and isinstance(n.elts[0], ast.Constant) \
                    and n.elts[0].value == "gcc":
                vals = [e.value for e in n.elts if isinstance(e, ast.Constant)]
                self.assertIn("-MM", vals)
                self.assertNotIn("-c", vals)


if __name__ == "__main__":
    unittest.main(verbosity=2)
