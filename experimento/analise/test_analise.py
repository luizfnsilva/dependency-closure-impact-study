"""Testes de analise.py (PROTOCOLO_V_2026-10-02 §6, §7, §8) sobre entradas SINTETICAS do
gerador_teste.py. Cada hipotese tem um par de cenarios escritos a mao que vira o ramo
(refutada / nao refutada / nao testavel). Nenhum dado real e lido.

Uso (de experimento/):  <venv>/bin/python -m unittest analise.test_analise -v
"""
from __future__ import annotations

import ast
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from analise import analise as an            # noqa: E402
from analise import gerador_teste as g       # noqa: E402

U_TZ = [f"Z{i:02d}" for i in range(12)]
U_C = ["a.o", "b.o", "c.o", "d.o", "e.o"]
U_GRANDE = [f"o{i:02d}.o" for i in range(40)]


def rodar(por_corpus: dict, B: int = 200) -> dict:
    """Confere cada registro como o carregador faria e roda a analise (modo teste)."""
    for k, regs in por_corpus.items():
        for i, r in enumerate(regs):
            an.conferir_registro(r, k, f"{k}:{i}")
    return an.analisar(por_corpus, "teste", {"sementes": {"ensaio": 0}}, B=B)


def tz_seguro(i, **kw):        # FP Z01 (T5), seguro
    return g.par("tz", i, U_TZ, {"Z00"}, {"A0": {"Z00", "Z01"}}, **kw)


def tz_fn(i, **kw):            # FN Z02, inseguro
    return g.par("tz", i, U_TZ, {"Z00", "Z02"}, {"A0": {"Z00"}}, **kw)


def c_seguro(corpus, i, **kw):  # FP b.o (T5), seguro
    return g.par(corpus, i, U_C, {"a.o"}, {"A0": {"a.o", "b.o"}}, **kw)


# ------------------------------------------------------------------------- estatistica

class TestEstatistica(unittest.TestCase):
    def test_wilson(self):
        lo, hi = an.wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.27753, places=4)
        lo, hi = an.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.23659, places=4)
        self.assertAlmostEqual(hi, 0.76341, places=4)
        self.assertEqual(an.wilson(0, 0), (None, None))

    def test_binomial_exato(self):
        self.assertAlmostEqual(an.binom_cauda_inferior(0, 150, an.P0_H1), 0.98 ** 150, places=12)
        esperado = sum(math.comb(300, k) * 0.02 ** k * 0.98 ** (300 - k) for k in range(11))
        self.assertAlmostEqual(an.binom_cauda_inferior(10, 300, an.P0_H1), esperado, places=10)
        self.assertAlmostEqual(an.binom_cauda_inferior(5, 5, an.P0_H1), 1.0)

    def test_fisher(self):
        self.assertAlmostEqual(an.fisher_bilateral(((3, 1), (1, 3))), 0.4857142857, places=9)
        self.assertAlmostEqual(an.fisher_bilateral(((1, 9), (11, 3))), 0.002759456, places=8)
        self.assertAlmostEqual(an.fisher_bilateral(((5, 5), (5, 5))), 1.0)

    def test_mcnemar(self):
        self.assertAlmostEqual(an.mcnemar_exato(0, 6), 2 / 64)
        self.assertEqual(an.mcnemar_exato(0, 0), 1.0)
        self.assertEqual(an.mcnemar_exato(3, 3), 1.0)

    def test_holm(self):
        aj, rej = an.holm({"A": 0.01, "B": 0.04, "C": 0.03})
        self.assertAlmostEqual(aj["A"], 0.03)
        self.assertAlmostEqual(aj["C"], 0.06)
        self.assertAlmostEqual(aj["B"], 0.06)
        self.assertEqual(rej, {"A": True, "B": False, "C": False})
        aj, rej = an.holm({"A": 0.001, "B": None, "C": None})
        self.assertAlmostEqual(aj["A"], 0.003)
        self.assertEqual(rej, {"A": True, "B": False, "C": False})

    def test_regra_de_tres(self):
        self.assertEqual(an.regra_de_tres(300), 0.01)
        self.assertIsNone(an.regra_de_tres(0))

    def test_bootstrap_deterministico(self):
        nums = {"k": [1, 0, 2, 0, 1, 3]}
        dens = {"FP": [2, 1, 2, 1, 1, 3]}
        a = an.bootstrap_fracoes(nums, {"k": "FP"}, dens, "s:bootstrap:tz", 2000)
        b = an.bootstrap_fracoes(nums, {"k": "FP"}, dens, "s:bootstrap:tz", 2000)
        c = an.bootstrap_fracoes(nums, {"k": "FP"}, dens, "outra", 2000)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        lo, hi, _ = a["k"]
        self.assertLessEqual(lo, 7 / 10)
        self.assertGreaterEqual(hi, 7 / 10)


# --------------------------------------------------------------------------- hipoteses

class TestH1(unittest.TestCase):
    def test_h1a_nao_refutada_com_zero_pares(self):
        H = rodar({"tz": [tz_seguro(i) for i in range(300)]})["hipoteses"]
        self.assertEqual(H["H1a"]["pares_com_evento"], 0)
        self.assertAlmostEqual(H["H1a"]["p"], 0.98 ** 300, places=12)
        self.assertAlmostEqual(H["H1a"]["p_holm"], 3 * 0.98 ** 300, places=12)
        self.assertIs(H["H1a"]["refutada"], False)
        self.assertEqual(H["H1b"]["status"], "nao_testavel")
        self.assertIsNone(H["H1b"]["refutada"])

    def test_h1a_refutada_com_muitos_pares(self):
        regs = [tz_seguro(i) for i in range(290)] + [tz_fn(1000 + i) for i in range(10)]
        H = rodar({"tz": regs})["hipoteses"]
        self.assertEqual(H["H1a"]["pares_com_evento"], 10)
        self.assertIs(H["H1a"]["refutada"], True)
        self.assertEqual(len(H["H1a"]["exemplos"]), 10)
        self.assertEqual(H["H1a"]["exemplos"][0]["elementos"], ["Z02"])

    def test_h1a_holm_vira_o_ramo(self):
        # p bruto 0,98^150 = 0,048 < 0,05, mas Holm (x3) = 0,145: H0 nao rejeitada
        H = rodar({"tz": [tz_seguro(i) for i in range(150)]})["hipoteses"]
        self.assertLess(H["H1a"]["p"], 0.05)
        self.assertGreater(H["H1a"]["p_holm"], 0.05)
        self.assertIs(H["H1a"]["refutada"], True)

    def test_h1b(self):
        lua = [c_seguro("lua", i) for i in range(300)]
        H = rodar({"lua": lua})["hipoteses"]
        self.assertIs(H["H1b"]["refutada"], False)
        t4 = [g.par("lua", 900 + i, U_C, {"a.o", "d.o"}, {"A0": {"a.o"}}, {"d.o": ["T4"]})
              for i in range(10)]
        H = rodar({"lua": lua[:290] + t4})["hipoteses"]
        self.assertEqual(H["H1b"]["pares_com_evento"], 10)
        self.assertIs(H["H1b"]["refutada"], True)
        # FN sem rotulo T4 nao conta para H1b
        inc = [g.par("lua", 950 + i, U_C, {"a.o", "d.o"}, {"A0": {"a.o"}}) for i in range(10)]
        H = rodar({"lua": lua[:290] + inc})["hipoteses"]
        self.assertEqual(H["H1b"]["pares_com_evento"], 0)


class TestH2(unittest.TestCase):
    def test_nc_sem_fn(self):
        regs = [tz_seguro(i, nc=True) for i in range(100)] + [tz_fn(500)]   # FN fora do NC
        H = rodar({"tz": regs})["hipoteses"]
        self.assertIs(H["H2"]["tz"]["refutada"], False)
        self.assertEqual(H["H2"]["tz"]["n_nc"], 100)
        self.assertAlmostEqual(H["H2"]["tz"]["limite_regra_de_tres"], 0.03)

    def test_um_fn_no_nc_refuta(self):
        regs = [tz_seguro(i, nc=True) for i in range(100)] + [tz_fn(500, nc=True)]
        H = rodar({"tz": regs})["hipoteses"]
        self.assertIs(H["H2"]["tz"]["refutada"], True)
        self.assertEqual(H["H2"]["tz"]["contraexemplos"][0]["elementos"], ["Z02"])
        self.assertIsNone(H["H2"]["tz"]["limite_regra_de_tres"])

    def test_sem_nc_nao_testavel_e_checagem(self):
        H = rodar({"tz": [tz_seguro(i) for i in range(10)]})["hipoteses"]
        self.assertIsNone(H["H2"]["tz"]["refutada"])
        r = g.par("tz", 1, U_TZ, {"Z00"}, {"A0": {"Z00", "Z01"}, "A_full": {"Z00"}}, nc=True)
        H = rodar({"tz": [r]})["hipoteses"]
        self.assertEqual(H["H2"]["tz"]["checagem_manipulacao_EIS_A0_difere_A_full"]["n"], 1)


class TestH3H4(unittest.TestCase):
    def test_h3_fn_novo_refuta_gancho_e_corpus(self):
        bom = [c_seguro("zlib", i) for i in range(20)]
        ruim = g.par("zlib", 99, U_C, {"a.o"}, {"A0": {"a.o", "b.o"}, "A0+d3": {"b.o"}})
        H = rodar({"zlib": bom + [ruim]})["hipoteses"]
        self.assertIs(H["H3"]["zlib"]["A0+d3"]["refutada"], True)
        self.assertIs(H["H3"]["zlib"]["A0+d3"]["subclasse_exploratoria"], True)
        self.assertEqual(H["H3"]["zlib"]["A0+d3"]["contraexemplos"][0]["elementos"], ["a.o"])
        self.assertIs(H["H3"]["zlib"]["A0+d2-extraido"]["refutada"], False)
        self.assertIsNone(H["H3"]["tz"]["A0+d3"]["refutada"])
        H = rodar({"zlib": bom})["hipoteses"]
        self.assertIs(H["H3"]["zlib"]["A0+d3"]["refutada"], False)

    def test_h4_ingenuo(self):
        base = [tz_seguro(i) for i in range(20)]
        H = rodar({"tz": base})["hipoteses"]
        self.assertIs(H["H4"]["refutada"], True)        # 0 FN novo no quadro
        poda = g.par("tz", 77, U_TZ, {"Z00"}, {"A0": {"Z00", "Z01"}, "A0+d4-ingenuo": {"Z01"}})
        H = rodar({"tz": base + [poda]})["hipoteses"]
        self.assertIs(H["H4"]["refutada"], False)
        self.assertEqual(H["H4"]["exemplos_FN_novo"][0]["elementos"], ["Z00"])
        # o mesmo FN novo no d4-preciso refuta a H3 (tz, d4-preciso)
        p2 = g.par("tz", 78, U_TZ, {"Z00"}, {"A0": {"Z00", "Z01"}, "A0+d4-preciso": {"Z01"}})
        H = rodar({"tz": base + [p2]})["hipoteses"]
        self.assertIs(H["H3"]["tz"]["A0+d4-preciso"]["refutada"], True)


def _zlib_fn(i, n_inc, n_t3=5, corpus="zlib"):
    """Par com 5 FN: n_inc INCLASSIFICADO-FN e o resto T3-FN."""
    ais = set(U_GRANDE[i * 5 % 35: i * 5 % 35 + 5])
    els = sorted(ais)
    rot = {e: (["INCLASSIFICADO-FN"] if j < n_inc else ["T3-FN"]) for j, e in enumerate(els)}
    return g.par(corpus, i, U_GRANDE, ais, {"A0": set()}, rot)


class TestH5(unittest.TestCase):
    def test_incompleta_acima_de_10pc(self):
        regs = [_zlib_fn(i, n) for i, n in enumerate([1, 1, 1, 1, 0, 0])]  # 4/30
        H = rodar({"zlib": regs})["hipoteses"]
        self.assertEqual(H["H5"]["zlib"]["instancias_FN"], 30)
        self.assertIs(H["H5"]["zlib"]["refutada"], True)
        self.assertEqual(H["H5"]["zlib"]["taxonomia"], "incompleta")

    def test_completa_em_10pc_exatos(self):
        regs = [_zlib_fn(i, n) for i, n in enumerate([1, 1, 1, 0, 0, 0])]  # 3/30
        H = rodar({"zlib": regs})["hipoteses"]
        self.assertIs(H["H5"]["zlib"]["refutada"], False)

    def test_menos_de_30_fn(self):
        regs = [_zlib_fn(i, n) for i, n in enumerate([5, 5, 5, 5, 5])]       # 25 FN
        H = rodar({"zlib": regs})["hipoteses"]
        self.assertIsNone(H["H5"]["zlib"]["refutada"])
        self.assertTrue(H["H5"]["zlib"]["status"].startswith("nao_aplicavel"))


class TestH6(unittest.TestCase):
    def test_b_sem_seguro_em_todo_par_refuta_e_suspende(self):
        regs = [g.par("zlib", i, U_C, {"a.o"}, {"A0": {"a.o"}, "B-sem": {"a.o"}})
                for i in range(10)]
        H = rodar({"zlib": regs})["hipoteses"]
        self.assertIs(H["H6"]["zlib"]["refutada"], True)
        self.assertEqual(H["interpretacao_suspensa_por_H6"], ["zlib"])

    def test_b_sem_inseguro(self):
        H = rodar({"zlib": [c_seguro("zlib", i) for i in range(10)]})["hipoteses"]
        self.assertIs(H["H6"]["zlib"]["refutada"], False)
        self.assertEqual(H["interpretacao_suspensa_por_H6"], [])


class TestH7(unittest.TestCase):
    RHO = "rho:cabecalho>objeto:M"
    ALFA = "alfa:configuracao>objeto"

    def _t2(self, i, rt):
        return g.par("zlib", i, U_C, {"a.o"}, {"A0": {"a.o", "b.o", "c.o"}},
                     {"b.o": ["T2"]}, r_tipo=rt)

    def test_a_rho_segura_refuta(self):
        regs = [self._t2(0, {self.RHO: {"fn_novo": [], "removidas": ["b.o"]}}),
                self._t2(1, {})]
        H = rodar({"zlib": regs})["hipoteses"]
        a = H["H7"]["a"]["zlib"]["T2"]
        self.assertIs(a["refutada"], True)
        self.assertEqual(a["rho_seguras_que_removem"], [self.RHO])

    def test_a_rho_com_fn_nao_refuta(self):
        regs = [self._t2(0, {self.RHO: {"fn_novo": [], "removidas": ["b.o"]}}),
                self._t2(1, {self.RHO: {"fn_novo": ["a.o"], "removidas": []}})]
        H = rodar({"zlib": regs})["hipoteses"]
        a = H["H7"]["a"]["zlib"]["T2"]
        self.assertIs(a["refutada"], False)
        self.assertEqual(a["rho_que_removem"][self.RHO]["fn_novo"], 1)

    def test_a_r_tipo_ausente_incompleta(self):
        regs = [self._t2(0, {self.RHO: {"fn_novo": [], "removidas": ["b.o"]}}),
                self._t2(1, None)]
        H = rodar({"zlib": regs})["hipoteses"]
        self.assertTrue(H["H7"]["a"]["zlib"]["T2"]["status"].startswith("incompleta"))
        self.assertIsNone(H["H7"]["a"]["zlib"]["T2"]["refutada"])

    def _t4(self, i, rt):
        return g.par("zlib", i, U_C, {"a.o", "d.o"}, {"A0": {"a.o"}}, {"d.o": ["T4"]},
                     r_tipo=rt)

    def test_b_alfa_remove_todas(self):
        ef = {self.ALFA: {"fn_novo": [], "removidas": ["d.o"]}}
        H = rodar({"zlib": [self._t4(0, ef), self._t4(1, ef)]})["hipoteses"]
        b = H["H7"]["b"]["zlib"]
        self.assertIs(b["refutada"], False)
        self.assertEqual(b["alfa_que_removem_todas"], [self.ALFA])

    def test_b_alfa_remove_parte_refuta(self):
        ef = {self.ALFA: {"fn_novo": [], "removidas": ["d.o"]}}
        H = rodar({"zlib": [self._t4(0, ef), self._t4(1, {})]})["hipoteses"]
        self.assertIs(H["H7"]["b"]["zlib"]["refutada"], True)

    def test_b_sem_t4_nao_testavel(self):
        H = rodar({"zlib": [self._t2(0, {})]})["hipoteses"]
        self.assertIsNone(H["H7"]["b"]["zlib"]["refutada"])


class TestH8(unittest.TestCase):
    def _zlib_t2(self, i):
        return g.par("zlib", i, U_C, {"a.o"}, {"A0": {"a.o", "b.o"}}, {"b.o": ["T2"]})

    def test_misturas_diferentes(self):
        tz = [tz_seguro(i) for i in range(20)]                      # FP todas T5
        zl = [self._zlib_t2(i) for i in range(20)]                   # FP todas T2
        H = rodar({"tz": tz, "zlib": zl})["hipoteses"]
        self.assertEqual(H["H8"]["tabela"], {"tz": [20, 0], "zlib": [0, 20]})
        self.assertLess(H["H8"]["p_holm"], 0.05)
        self.assertIs(H["H8"]["refutada"], False)

    def test_misturas_iguais_refuta(self):
        tz = [tz_seguro(i) for i in range(20)]
        zl = [c_seguro("zlib", i) for i in range(20)]
        H = rodar({"tz": tz, "zlib": zl})["hipoteses"]
        self.assertAlmostEqual(H["H8"]["p"], 1.0)
        self.assertIs(H["H8"]["refutada"], True)

    def test_sem_zlib_nao_testavel(self):
        H = rodar({"tz": [tz_seguro(i) for i in range(5)]})["hipoteses"]
        self.assertIsNone(H["H8"]["refutada"])
        self.assertEqual(H["H8"]["status"], "nao_testavel")


class TestSecao8(unittest.TestCase):
    def _exato(self, corpus, i, U):
        return g.par(corpus, i, U, {U[0]}, {"A0": {U[0]}})

    def test_resultado_negativo_nos_dois_dominios(self):
        d = {"tz": [self._exato("tz", i, U_TZ) for i in range(10)],
             "zlib": [self._exato("zlib", i, U_C) for i in range(10)],
             "lua": [self._exato("lua", i, U_C) for i in range(10)]}
        s8 = rodar(d)["hipoteses"]["secao_8"]
        self.assertIs(s8["tz"]["tese_rejeitada_no_dominio"], True)
        self.assertIs(s8["build_C"]["tese_rejeitada_no_dominio"], True)
        self.assertIs(s8["resultado_negativo_nos_dois_dominios"], True)

    def test_precisao_mediana_baixa_mantem_tese(self):
        regs = ([self._exato("tz", i, U_TZ) for i in range(4)]
                + [tz_seguro(100 + i) for i in range(6)])            # precisao 0,5
        s8 = rodar({"tz": regs})["hipoteses"]["secao_8"]
        self.assertAlmostEqual(s8["tz"]["corpora"]["tz"]["mediana_precisao_teto"], 0.5)
        self.assertIs(s8["tz"]["tese_rejeitada_no_dominio"], False)

    def test_um_par_inseguro_mantem_tese_e_lua_ausente(self):
        regs = [self._exato("tz", i, U_TZ) for i in range(10)] + [tz_fn(99)]
        s8 = rodar({"tz": regs, "zlib": [self._exato("zlib", i, U_C) for i in range(5)]})[
            "hipoteses"]["secao_8"]
        self.assertIs(s8["tz"]["tese_rejeitada_no_dominio"], False)
        self.assertEqual(s8["build_C"]["status"], "nao_decidivel")      # Lua ausente
        self.assertIs(s8["build_C_so_zlib_descritivo"]["tese_rejeitada_no_dominio"], True)
        self.assertIsNone(s8["resultado_negativo_nos_dois_dominios"])


# ---------------------------------------------------------------------- classes §6.2

def _linha(tab, atrib, lado, cat):
    return next(x for x in tab if x["atribuicao"] == atrib and x["lado"] == lado
                and x["categoria"] == cat)


class TestClasses(unittest.TestCase):
    def test_nao_exercida_abaixo_de_5(self):
        def t2(i):
            return g.par("zlib", i, U_C, {"a.o"}, {"A0": {"a.o", "b.o"}}, {"b.o": ["T2"]})
        tab = rodar({"zlib": [t2(i) for i in range(4)]})["por_corpus"]["zlib"]["classes"]
        self.assertEqual(_linha(tab, "primario", "FP", "T2")["status"], "nao_exercida")
        self.assertEqual(_linha(tab, "primario", "FP", "T1a")["status"], "nao_se_aplica")
        tab = rodar({"zlib": [t2(i) for i in range(5)]})["por_corpus"]["zlib"]["classes"]
        x = _linha(tab, "primario", "FP", "T2")
        self.assertEqual(x["status"], "exercida")
        self.assertEqual((x["n_instancias"], x["elementos_distintos"], x["pares_com_instancia"]),
                         (5, 1, 5))

    def test_precedencias_e_multirrotulo(self):
        r = g.par("zlib", 1, U_C, {"a.o"}, {"A0": {"a.o", "b.o", "c.o"}},
                  {"b.o": ["T3-FP", "T2"], "c.o": ["T2"]})
        tab = rodar({"zlib": [r]})["por_corpus"]["zlib"]["classes"]
        self.assertEqual(_linha(tab, "primario", "FP", "T3m-FP")["n_instancias"], 1)
        self.assertEqual(_linha(tab, "primario", "FP", "T2")["n_instancias"], 1)
        self.assertEqual(_linha(tab, "alt_c", "FP", "T3m-FP")["n_instancias"], 0)
        self.assertEqual(_linha(tab, "alt_c", "FP", "T2")["n_instancias"], 2)
        self.assertEqual(_linha(tab, "multirrotulo", "FP", "T2")["n_instancias"], 2)
        self.assertEqual(_linha(tab, "multirrotulo", "FP", "T3m-FP")["n_instancias"], 1)
        self.assertAlmostEqual(_linha(tab, "primario", "FP", "T2")["frac_lado"], 0.5)
        r = g.par("lua", 1, U_C, {"a.o", "d.o"}, {"A0": {"a.o"}}, {"d.o": ["T3-FN"]})
        tab = rodar({"lua": [r]})["por_corpus"]["lua"]["classes"]
        self.assertEqual(_linha(tab, "primario", "FN", "T3g-FN")["n_instancias"], 1)

    def test_ablacao(self):
        e0 = {"a.o", "b.o", "c.o", "d.o"}          # AIS = {a.o, e.o}; FP b, c, d; FN e
        r = g.par("zlib", 1, U_C, {"a.o", "e.o"},
                  {"A0": e0,
                   "A0+d3": {"a.o", "c.o", "d.o"},            # remove b
                   "A0+d2-extraido": {"a.o", "b.o", "d.o"},   # remove c
                   "A0+d6": e0 | {"e.o"},                     # remove FN e
                   "A_full": {"a.o", "e.o"}},                 # remove b, c, d, e
                  {"b.o": ["T2"], "c.o": ["T3-FP"], "e.o": ["T4"]})
        r2 = g.par("zlib", 2, U_C, {"a.o"},
                   {"A0": {"a.o", "b.o"}, "A0+d3": {"a.o"}, "A0+d2-extraido": {"a.o"},
                    "A_full": {"a.o"}})                        # b removido por 2 isolados
        tab = rodar({"zlib": [r, r2]})["por_corpus"]["zlib"]["classes"]
        n = {x["categoria"]: x["n_instancias"] for x in tab
             if x["atribuicao"] == "ablacao" and x["lado"] == "FP"}
        self.assertEqual(n, {"d3": 1, "d2-extraido": 1, "d6": 0, "SOBREPOSTA": 1,
                             "COMPOSTA": 1, "NAO_REMOVIDA": 0})
        fn = _linha(tab, "ablacao", "FN", "d6")
        self.assertEqual((fn["n_instancias"], fn["classe_do_gancho"]), (1, "T4"))
        self.assertEqual(_linha(tab, "ablacao", "FP", "d2-extraido")["classe_do_gancho"], "T3m-FP")

    def test_bootstrap_na_tabela_e_deterministico(self):
        regs = [tz_seguro(i) for i in range(30)] + [
            g.par("tz", 100 + i, U_TZ, {"Z00"}, {"A0": {"Z00", "Z03"}}, {"Z03": ["T2"]})
            for i in range(10)]
        a = rodar({"tz": regs}, B=500)["por_corpus"]["tz"]["classes"]
        b = rodar({"tz": regs}, B=500)["por_corpus"]["tz"]["classes"]
        self.assertEqual(a, b)
        x = _linha(a, "primario", "FP", "T2")
        self.assertAlmostEqual(x["frac_lado"], 0.25)
        self.assertLessEqual(x["boot_lo"], 0.25)
        self.assertGreaterEqual(x["boot_hi"], 0.25)
        self.assertLess(x["boot_hi"] - x["boot_lo"], 0.5)


# ------------------------------------------------- controles, sensibilidades, corpora

class TestControles(unittest.TestCase):
    def test_nulo_violado_aborta(self):
        ok = g.par("zlib", 1, U_C, set(), {"A0": set()}, controle="nulo")
        rodar({"zlib": [c_seguro("zlib", 0), ok]})
        ruim = g.par("zlib", 2, U_C, set(), {"A0": {"a.o"}}, controle="nulo")
        with self.assertRaises(an.Recusa) as cm:
            rodar({"zlib": [c_seguro("zlib", 0), ruim]})
        self.assertEqual(cm.exception.codigo, 3)

    def test_placebo_com_ais_e_t4_e_fora_do_quadro(self):
        pl = g.par("zlib", 5, U_C, {"a.o"}, {"A0": set()}, controle="placebo")
        A = rodar({"zlib": [c_seguro("zlib", i) for i in range(3)] + [pl]})
        c = A["controles"]["zlib"]["placebo"]
        self.assertEqual((c["AIS_nao_vazio"], c["instancias_T4"]), (1, 1))
        self.assertEqual(A["por_corpus"]["zlib"]["n_primarios"], 3)
        self.assertEqual(A["hipoteses"]["H1a"]["status"], "nao_testavel")

    def test_nao_executado_contado_e_fora(self):
        regs = [tz_seguro(i) for i in range(5)] + [g.nao_executado("tz", 9, "zic_recusa_c", 2013)]
        A = rodar({"tz": regs})
        d = {x["ano"]: x for x in A["por_corpus"]["tz"]["descritores"]}
        self.assertEqual(d[2013]["nao_executado_zic_recusa_c"], 1)
        self.assertEqual(d["todos"]["executados"], 5)
        self.assertEqual(A["hipoteses"]["H1a"]["n_pares"], 5)


class TestSensibilidades(unittest.TestCase):
    def test_exclusao_nao_deterministico(self):
        regs = [tz_seguro(i) for i in range(10)] + [tz_fn(50, nd=2)]
        A = rodar({"tz": regs})
        self.assertEqual(A["hipoteses"]["H1a"]["pares_com_evento"], 1)
        s = A["sensibilidades"]["exclusao_nao_deterministico"]
        self.assertEqual(s["pares_excluidos"]["tz"], 1)
        self.assertEqual(s["hipoteses"]["H1a"]["pares_com_evento"], 0)

    def test_janela_w_e_atribuicao_anterior(self):
        def r(i):
            return tz_seguro(i, sens={"AIS_1970_2037": ["Z00", "Z05"], "d1_anterior": {
                "A0": {"EIS": ["Z00"], "FN": [], "FP": [], "seguro": True}}})
        A = rodar({"tz": [r(i) for i in range(4)]})
        w = A["sensibilidades"]["janela_W_1970_2037"]
        self.assertEqual(w["status"], "calculada")
        self.assertEqual(w["hipoteses"]["H1a"]["pares_com_evento"], 4)   # Z05 vira FN
        self.assertEqual(w["hipoteses"]["H5"]["tz"]["status"], "nao_recalculada")
        self.assertEqual(A["hipoteses"]["H1a"]["pares_com_evento"], 0)   # principal intacta
        d1 = A["sensibilidades"]["atribuicao_comentario_anterior"]
        self.assertEqual(d1["status"], "calculada")
        self.assertEqual(d1["bracos"][0]["mediana_precisao_teto"], 1.0)
        self.assertEqual(d1["hipoteses"]["H3"]["tz"]["A0+d3"]["status"], "nao_testavel")
        A = rodar({"tz": [tz_seguro(0)]})
        self.assertTrue(A["sensibilidades"]["janela_W_1970_2037"]["status"].startswith("ausente"))

    def test_pares_de_tags_fora_da_unidade_primaria(self):
        regs = [tz_seguro(i) for i in range(5)] + [tz_fn(70 + i, controle="tag") for i in range(3)]
        A = rodar({"tz": regs})
        self.assertEqual(A["hipoteses"]["H1a"]["pares_com_evento"], 0)
        t = A["sensibilidades"]["pares_de_tags_tz"]
        self.assertEqual(t["hipoteses"]["H1a"]["pares_com_evento"], 3)


class TestOrdemENews(unittest.TestCase):
    def test_ordem_do_arquivo_nao_muda_nada(self):
        regs = [tz_seguro(i) for i in range(30)] + [
            g.par("tz", 100 + i, U_TZ, {"Z00"}, {"A0": {"Z00", "Z03"}}, {"Z03": ["T2"]})
            for i in range(10)] + [tz_fn(200 + i) for i in range(3)]
        a = rodar({"tz": regs}, B=300)
        b = rodar({"tz": list(reversed(regs))}, B=300)
        self.assertEqual(a["por_corpus"]["tz"]["classes"], b["por_corpus"]["tz"]["classes"])
        self.assertEqual(a["hipoteses"], b["hipoteses"])

    def test_concordancia_news_nos_tags(self):
        t_ok = g.par("tz", 1, U_TZ, set(), {"A0": {"Z01"}}, controle="tag",
                     extra={"news_so_comentario": True})
        t_disc = tz_fn(2, controle="tag", extra={"news_so_comentario": True})
        A = rodar({"tz": [tz_seguro(9), t_ok, t_disc]})
        n = A["sensibilidades"]["pares_de_tags_tz"]["concordancia_NEWS_nao_confirmatoria"]
        self.assertEqual((n["tags_so_comentario"], n["com_AIS_vazio"]), (2, 1))
        self.assertEqual(n["discordantes"], [{"p": t_disc["p"], "c": t_disc["c"]}])


class TestNadaSomado(unittest.TestCase):
    def test_zlib_nao_muda_com_lua(self):
        zl = [c_seguro("zlib", i) for i in range(10)] + [
            g.par("zlib", 50, U_C, {"a.o", "d.o"}, {"A0": {"a.o"}}, {"d.o": ["T4"]})]
        lua = [g.par("lua", i, U_C, {"a.o", "e.o"}, {"A0": {"a.o"}}) for i in range(10)]
        so = rodar({"zlib": zl}, B=300)
        com = rodar({"zlib": zl, "lua": lua}, B=300)
        for k in ("bracos", "classes", "descritores", "mcnemar"):
            self.assertEqual(so["por_corpus"]["zlib"][k], com["por_corpus"]["zlib"][k])
        for h in ("H2", "H3", "H5", "H6"):
            self.assertEqual(so["hipoteses"][h]["zlib"], com["hipoteses"][h]["zlib"])
        self.assertEqual(com["por_corpus"]["lua"]["bracos"][0]["inseguros"], 10)
        self.assertEqual(com["por_corpus"]["zlib"]["bracos"][0]["inseguros"], 1)


# ------------------------------------------------------- integridade e guardas (arquivo)

class TestIntegridade(unittest.TestCase):
    def _recusa(self, r, corpus="zlib"):
        with self.assertRaises(an.Recusa) as cm:
            an.conferir_registro(r, corpus, "t")
        self.assertEqual(cm.exception.codigo, 3)

    def test_fn_inconsistente(self):
        r = c_seguro("zlib", 1)
        r["bracos"]["A0"]["FN"] = ["c.o"]
        self._recusa(r)

    def test_instancia_faltando(self):
        r = c_seguro("zlib", 1)
        r["instancias"] = []
        self._recusa(r)

    def test_primario_contra_precedencia(self):
        r = g.par("zlib", 1, U_C, {"a.o"}, {"A0": {"a.o", "b.o"}}, {"b.o": ["T3-FP", "T2"]},
                  primarios={"b.o": "T2"})
        self._recusa(r)
        r = g.par("zlib", 1, U_C, {"a.o"}, {"A0": {"a.o", "b.o"}}, {"b.o": ["T3-FP", "T2"]},
                  primarios={"b.o": "T3-FP"})
        an.conferir_registro(r, "zlib", "t")

    def test_braco_indevido_e_rotulo_indevido(self):
        r = c_seguro("zlib", 1)
        r["bracos"]["A0+d4-preciso"] = r["bracos"]["A0"]
        self._recusa(r)
        r = g.par("zlib", 1, U_C, {"a.o"}, {"A0": {"a.o", "b.o"}}, {"b.o": ["T1a"]})
        self._recusa(r)
        r = g.par("tz", 1, U_TZ, {"Z00"}, {"A0": {"Z00", "Z01"}}, {"Z01": ["T5", "T2"]})
        self._recusa(r, "tz")


class TestArquivos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v_analise_teste_")
        self.d = Path(self.tmp.name)
        self.cfg, self.sha = g.config_teste(self.d)
        self.tz = g.gravar(self.d / "tz.jsonl", [tz_seguro(i, nc=True) for i in range(30)]
                           + [tz_fn(99)], self.sha)
        self.zl = g.gravar(self.d / "zlib.jsonl", [c_seguro("zlib", i) for i in range(20)],
                           self.sha)
        self.lua = g.gravar(self.d / "lua.jsonl", [c_seguro("lua", i) for i in range(20)],
                            self.sha)

    def tearDown(self):
        self.tmp.cleanup()

    def _sub(self, nome):
        p = self.d / nome
        p.mkdir()
        return p

    def _main(self, *args):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return an.main([str(a) for a in args])

    def test_ponta_a_ponta_marcado_e_deterministico(self):
        s1, s2 = self.d / "s1", self.d / "s2"
        for s in (s1, s2):
            self.assertEqual(self._main("--teste", "--config", self.cfg, "--saida", s,
                                        self.tz, self.zl, self.lua), 0)
        nomes = sorted(p.name for p in s1.iterdir())
        for k in ("tz", "zlib", "lua"):
            for pre in ("por_par", "resumo_bracos", "por_classe"):
                self.assertIn(f"{pre}_{k}.csv", nomes)
        for p in s1.iterdir():
            self.assertEqual(p.read_bytes(), (s2 / p.name).read_bytes(), p.name)
            txt = p.read_text(encoding="utf-8")
            if p.suffix == ".csv":
                linhas = txt.splitlines()
                self.assertTrue(all(L.startswith("TESTE,") for L in linhas[1:]), p.name)
            elif p.suffix == ".json":
                self.assertEqual(json.loads(txt)["marca"], "TESTE")
            else:
                self.assertIn("TESTE: nao e resultado", txt)
        H = json.loads((s1 / "hipoteses.json").read_text())["hipoteses"]
        self.assertIs(H["H2"]["tz"]["refutada"], False)
        self.assertEqual(H["H1a"]["pares_com_evento"], 1)

    def test_cadeia_adulterada(self):
        linhas = self.zl.read_bytes().split(b"\n")
        for mexe in (lambda L: [L[1], L[0]] + L[2:],                          # troca ordem
                     lambda L: L[1:],                                         # apaga a 1a
                     lambda L: [L[0].replace(b'"a.o"', b'"c.o"', 1)] + L[1:],  # muda conteudo
                     lambda L: [L[0].replace(b'":', b'": ', 1)] + L[1:]):      # nao canonica
            ruim = self.d / "ruim.jsonl"
            ruim.write_bytes(b"\n".join(mexe(linhas[:-1])) + b"\n")
            self.assertEqual(self._main("--teste", "--config", self.cfg, "--saida",
                                        self.d / "x", ruim), 3)
        outro, _ = g.config_teste(self._sub("outro"), uso="OUTRO")          # sha diferente
        self.assertEqual(self._main("--teste", "--config", outro, "--saida", self.d / "x",
                                    self.zl), 3)

    def test_registro_de_teste_recusado_no_ensaio(self):
        self.assertEqual(self._main("--ensaio", "--config", self.cfg, "--saida", self.d / "x",
                                    self.zl), 3)

    def test_guardas_confirmatorias(self):
        import hashlib
        self.assertEqual(self._main("--config", self.cfg, "--saida", self.d / "x", self.zl), 2)
        dep = hashlib.sha256(b"deposito ficticio de teste").hexdigest()
        base = {"doi": "10.0000/teste", "protocolo": {"sha256_deposito": dep},
                "modulos": {an.CHAVE_MODULO: an.sha256_arquivo(an.ESTE_ARQUIVO)}}
        ruim, _ = g.config_teste(self._sub("c1"), **base,
                                 sementes={"principal": 1, "bootstrap": 10000})
        self.assertEqual(self._main("--config", ruim, "--saida", self.d / "x", self.zl), 2)
        princ = int.from_bytes(bytes.fromhex(dep)[:8], "big")
        b, _ = g.config_teste(self._sub("c2"), **base,
                              sementes={"principal": princ, "bootstrap": 100})
        self.assertEqual(self._main("--config", b, "--saida", self.d / "x", self.zl), 2)
        cfg_ok, sha_ok = g.config_teste(self._sub("c3"), **base,
                                        sementes={"principal": princ, "bootstrap": 10000})
        zl = g.gravar(self.d / "zlib2.jsonl", [c_seguro("zlib", i) for i in range(3)], sha_ok)
        # guarda de config satisfeita; registro sintetico continua proibido no confirmatorio
        self.assertEqual(self._main("--config", cfg_ok, "--saida", self.d / "x", zl), 3)
        m = dict(base["modulos"])
        m[an.CHAVE_MODULO] = "0" * 64
        c2, _ = g.config_teste(self._sub("c4"), **{**base, "modulos": m},
                               sementes={"principal": princ, "bootstrap": 10000})
        self.assertEqual(self._main("--config", c2, "--saida", self.d / "x", zl), 2)

    def test_gerador_nao_grava_em_saidas(self):
        with self.assertRaises(RuntimeError):
            g.gravar(AQUI.parent / "saidas" / "nao_deve_existir.jsonl", [], self.sha)
        self.assertFalse((AQUI.parent / "saidas" / "nao_deve_existir.jsonl").exists())

    def test_corpus_repetido(self):
        z2 = g.gravar(self.d / "zlib_b.jsonl", [c_seguro("zlib", 50)], self.sha)
        self.assertEqual(self._main("--teste", "--config", self.cfg, "--saida", self.d / "x",
                                    self.zl, z2), 2)


# ---------------------------------------------------------------- auditoria do proprio

class TestAuditoria(unittest.TestCase):
    PERMITIDOS = {"__future__", "argparse", "csv", "hashlib", "io", "json", "math", "random",
                  "statistics", "sys", "collections", "fractions", "operator", "pathlib"}

    def _imports(self, arq):
        mods = set()
        for n in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or "").split(".")[0] if n.level == 0 else "<relativo>")
        return mods

    def test_analise_so_biblioteca_padrao(self):
        self.assertLessEqual(self._imports(AQUI / "analise.py"), self.PERMITIDOS)

    def test_gerador_nao_importa_analise_nem_experimento(self):
        self.assertLessEqual(self._imports(AQUI / "gerador_teste.py"),
                             {"__future__", "hashlib", "json", "pathlib"})

    def test_vocabulario_vetado(self):
        # §10.3. Termos gravados INVERTIDOS para que a varredura por grep do repositorio
        # nao acuse este arquivo de teste; a lista e desinvertida abaixo.
        inv = ["otnemelpmoc", "noititrap", "oaçitrap", "oacitrap", "acifitrecer",
               "dacifitrec", "otiderev", "DETCEFFA", "TNAIRAVNI", "ELBASSESSA_NON", "iránret",
               "iranret", "leváilava oãn", "levailava oan", "ssessa", "yalper", "megahnil",
               "egaenil", "noissesrepus", "azilamron", "dlrow desolc", "enonâc", "enonac",
               "adneme", "ecnarelot", "aicnêgiv", "aicnegiv", "ytidilav laropmet",
               "egatniv", "otnemurtsni", "deretsiger-erp", "elkrem", "tniopkcehc",
               "epolevne", "pag noitagaporp", "gnidnib-fles", "etats citsinimreted",
               "gninraelnu", "repmat", "tfird_erusolc", "sodnum ed oelcún", "oirótarobal",
               "oirotarobal", "rodirefnoc", "ahlof", "ahcif", "osnec", "adamac", "zirtam"]
        palavra_inteira = ["enoc", "laes", "oles"]
        rx = re.compile("|".join([r"\b" + re.escape(t[::-1]) for t in inv]
                                 + [r"\b" + t[::-1] + r"\b" for t in palavra_inteira]),
                        re.IGNORECASE)
        caixa = "|".join(t[::-1] for t in ("EGNAHC", "NREVOG", "ETATS"))
        rx_caixa = re.compile(r"\b(?:" + caixa + r")\b|\bP(?:1[0-2]|[1-9])\b")
        for nome in ("analise.py", "gerador_teste.py", "__init__.py"):
            txt = (AQUI / nome).read_text(encoding="utf-8")
            self.assertIsNone(rx.search(txt), (nome, rx.search(txt)))
            self.assertIsNone(rx_caixa.search(txt), (nome, rx_caixa.search(txt)))

    def test_nada_de_u_artefato(self):
        alvo = "/".join(["artigos", "U", "artefato"])     # join: nao vira literal no .pyc
        for nome in ("analise.py", "gerador_teste.py"):
            self.assertNotIn(alvo, (AQUI / nome).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
