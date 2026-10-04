"""Bateria de aceitacao A1-A5 do nucleo (PROTOCOLO_V_2026-10-02 §4.2).

Todos os resultados ESPERADOS deste arquivo sao literais escritos a mao ANTES da
primeira execucao (sha256 deste arquivo antes de rodar: registrado no relato do
V-0a). Nenhum esperado e calculado pelo codigo sob teste.

Topologias: especificadas pela fonte citada no §4.2 do protocolo (linhas
97-100, 138-156, 354-357, 395-413), lida so como texto; nenhum codigo foi lido,
copiado ou adaptado. A fonte da os NOMES das topologias; os grafos concretos e
as sementes abaixo sao escolha deste arquivo.

Convencao (§4.1): aresta u -> v = "v consome u". A fonte de A3 escreve em
notacao de dependencia ("x -> y" = "x depende de y"); a traducao para §4.1 e
y -> x, escrita a mao e checada em A3.

A2 tambem roda sobre os adaptadores reais (tz e cbuild) em fixtures minimas, sem oraculo.
A6-A7 (oraculo real, so sobre fixtures) ficam em nucleo/test_a6_tz.py e
nucleo/fixtures/a7_c/test_a7.py (layout §11.1 a aprovar na Emenda 1; shas em config.modulos).

Rodar, de experimento/:   <v_venv>/bin/python -m unittest -v nucleo.test_aceitacao
"""
from __future__ import annotations

import ast
import hashlib
import itertools
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import networkx as nx  # noqa: E402

from adaptadores import cbuild, tz  # noqa: E402
from adaptadores.git_arvore import ArvoreDir  # noqa: E402
from nucleo import reach as R  # noqa: E402
from nucleo.bfs_ref import bfs_ref  # noqa: E402

AQUI = Path(__file__).resolve().parent


# ---------------------------------------------------------------- utilitarios
def grafo(arestas, nos=()):
    G = nx.DiGraph()
    G.add_nodes_from(nos)
    G.add_edges_from(arestas)
    return G


def adj_direto(arestas, nos=()):
    """Adjacencia montada da lista de arestas, sem passar pelo networkx."""
    adj = {n: set() for n in nos}
    for u, v in arestas:
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set())
    return adj


# Formato de cada caso: (nome, nos_isolados, arestas, [(S, esperado), ...],
#                        CICLO esperado, GRAFO_VAZIO esperado)

# ---------------------------------------------------------------- A1: 9 topologias
TOPOLOGIAS_A1 = [
    ("cadeia", (), [("a", "b"), ("b", "c"), ("c", "d")],
     [({"a"}, {"a", "b", "c", "d"}),
      ({"b"}, {"b", "c", "d"}),
      ({"d"}, {"d"}),
      (set(), set())],
     [], False),
    ("diamante", (), [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
     [({"a"}, {"a", "b", "c", "d"}),
      ({"b"}, {"b", "d"}),
      ({"c"}, {"c", "d"}),
      ({"b", "c"}, {"b", "c", "d"}),
      ({"d"}, {"d"})],
     [], False),
    ("desconexo", ("e",), [("a", "b"), ("c", "d")],
     [({"a"}, {"a", "b"}),
      ({"c"}, {"c", "d"}),
      ({"e"}, {"e"}),
      ({"a", "c"}, {"a", "b", "c", "d"})],
     [], False),
    # p e referido por c e nao tem definicao; o e no isolado. O nucleo nao sabe
    # que p nao tem definicao: PENDENTE e contado pelo adaptador (pendentes(a)).
    ("orfao_pendurado", ("o",), [("a", "b"), ("p", "c"), ("c", "d")],
     [({"a"}, {"a", "b"}),
      ({"p"}, {"p", "c", "d"}),
      ({"c"}, {"c", "d"}),
      ({"o"}, {"o"})],
     [], False),
    ("no_externo", (), [("a", "b")],
     [({"x"}, {"x"}),
      ({"a", "x"}, {"a", "b", "x"}),
      ({"b"}, {"b"})],
     [], False),
    ("ciclo_de_2", (), [("a", "b"), ("b", "a"), ("b", "c")],
     [({"a"}, {"a", "b", "c"}),
      ({"b"}, {"a", "b", "c"}),
      ({"c"}, {"c"})],
     [["a", "b"]], False),
    ("ciclo_ao_lado", (), [("a", "b"), ("c", "d"), ("d", "c"), ("d", "e")],
     [({"a"}, {"a", "b"}),
      ({"c"}, {"c", "d", "e"}),
      ({"e"}, {"e"})],
     [["c", "d"]], False),
    # autolaco: CFC de 1 no; pela letra do §4.7 (CFC com mais de um no) nao e CICLO, e e
    # contado a parte em AUTOLACO (Emenda 1), para o descritor nao ficar mudo.
    ("autolaco", (), [("a", "a"), ("a", "b")],
     [({"a"}, {"a", "b"}),
      ({"b"}, {"b"})],
     [], False),
    # grafo vazio: EIS = semente mapeada, nunca "nada impactado" (§4.1).
    ("grafo_vazio", (), [],
     [(set(), set()),
      ({"a"}, {"a"})],
     [], True),
]

# ---------------------------------------------------------------- A4: bateria patologica
TOPOLOGIAS_A4 = [
    ("ciclo_3_com_entrada_e_cauda", (),
     [("e", "a"), ("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")],
     [({"b"}, {"a", "b", "c", "d"}),
      ({"e"}, {"a", "b", "c", "d", "e"}),
      ({"d"}, {"d"})],
     [["a", "b", "c"]], False),
    ("dois_ciclos_encadeados", (),
     [("a", "b"), ("b", "a"), ("b", "c"), ("c", "d"), ("d", "c")],
     [({"c"}, {"c", "d"}),
      ({"a"}, {"a", "b", "c", "d"})],
     [["a", "b"], ["c", "d"]], False),
    ("ciclos_que_se_fundem", (),
     [("a", "b"), ("b", "a"), ("b", "c"), ("c", "b")],
     [({"c"}, {"a", "b", "c"})],
     [["a", "b", "c"]], False),
    ("autolaco_isolado", (), [("a", "a")],
     [({"a"}, {"a"}),
      ({"b"}, {"b"})],
     [], False),
    ("autolacos_em_cadeia", (), [("a", "a"), ("a", "b"), ("b", "b"), ("b", "c")],
     [({"b"}, {"b", "c"}),
      ({"a"}, {"a", "b", "c"})],
     [], False),
    ("desconexo_semente_vazia", ("e", "f"), [("a", "b"), ("c", "d")],
     [(set(), set()),
      ({"e", "c"}, {"c", "d", "e"})],
     [], False),
    # q: fornecedor referido sem definicao; z: consumidor sem definicao.
    ("pendente_dos_dois_lados", (), [("q", "r"), ("r", "s"), ("a", "z")],
     [({"r"}, {"r", "s"}),
      ({"q"}, {"q", "r", "s"}),
      ({"a"}, {"a", "z"})],
     [], False),
    ("semente_toda_externa", (), [("a", "b")],
     [({"x", "y"}, {"x", "y"}),
      ({"b", "x"}, {"b", "x"})],
     [], False),
    ("nos_sem_arestas", ("a", "b"), [],
     [({"a"}, {"a"}),
      ({"a", "b"}, {"a", "b"})],
     [], True),
]


# AUTOLACO esperado (escrito a mao) por topologia; ausente = [].
AUTOLACOS = {"autolaco": ["a"], "autolaco_isolado": ["a"], "autolacos_em_cadeia": ["a", "b"]}


def desc_esperado(nome, ciclo, vazio):
    return {"CICLO": ciclo, "AUTOLACO": AUTOLACOS.get(nome, []), "GRAFO_VAZIO": vazio}


class BaseCasos(unittest.TestCase):
    def checar_caso(self, nome, nos, arestas, casos, ciclo, vazio):
        G = grafo(arestas, nos)
        adj = adj_direto(arestas, nos)
        self.assertEqual(R.adjacencia(G), adj, nome)
        for S, esperado in casos:
            with self.subTest(topologia=nome, S=sorted(S)):
                esperado = frozenset(esperado)
                self.assertEqual(R.reach(G, S), esperado)
                self.assertEqual(bfs_ref(adj, S), esperado)
                self.assertEqual(R.reach_diferencial(G, S), esperado)
        with self.subTest(topologia=nome, descritores=True):
            self.assertEqual(R.descritores(G, set()), desc_esperado(nome, ciclo, vazio))


class A1Topologias(BaseCasos):
    def test_a1_nove_topologias(self):
        self.assertEqual(len(TOPOLOGIAS_A1), 9)
        for caso in TOPOLOGIAS_A1:
            self.checar_caso(*caso)


# ---------------------------------------------------------------- A2: religacao sem mudanca de conteudo
class A2Religacao(unittest.TestCase):
    """b passa a consumir x em vez de a; nem a nem x mudam de conteudo.
    O nucleo da a mesma resposta com G_p, G_c ou G_p uniao G_c para a mesma semente;
    quem decide e a regra d1 de semente (§4.4): se o conteudo de b inclui a sua
    especificacao de dependencia (linha de Zone com o campo RULES; #include em C),
    S = {b}; se nao inclui, S = vazio."""

    NOS = ("a", "x", "b", "y")
    G_P = [("a", "b"), ("b", "y")]
    G_C = [("x", "b"), ("b", "y")]
    COM_DEP_P = {"a": b"A", "x": b"X", "b": b"B usa a", "y": b"Y usa b"}
    COM_DEP_C = {"a": b"A", "x": b"X", "b": b"B usa x", "y": b"Y usa b"}
    SEM_DEP_P = {"a": b"A", "x": b"X", "b": b"B", "y": b"Y"}
    SEM_DEP_C = {"a": b"A", "x": b"X", "b": b"B", "y": b"Y"}

    @staticmethod
    def semente(cp, cc):
        # §4.4: no cujo conteudo difere entre p e c, ou que existe em um so lado
        return {n for n in set(cp) | set(cc) if cp.get(n) != cc.get(n)}

    def test_a2_semente_decide(self):
        self.assertEqual(self.semente(self.COM_DEP_P, self.COM_DEP_C), {"b"})
        self.assertEqual(self.semente(self.SEM_DEP_P, self.SEM_DEP_C), set())

    def test_a2_nucleo_indiferente(self):
        grafos = {
            "G_p": grafo(self.G_P, self.NOS),
            "G_c": grafo(self.G_C, self.NOS),
            "G_p|G_c": grafo(self.G_P + self.G_C, self.NOS),
        }
        for nome, G in grafos.items():
            with self.subTest(grafo=nome):
                self.assertEqual(R.reach_diferencial(G, {"b"}), frozenset({"b", "y"}))
                self.assertEqual(R.reach_diferencial(G, set()), frozenset())

    def test_a2_regra_de_uniao(self):
        # Se a mudasse de conteudo no mesmo par, a regra G = G_p uniao G_c (§4.4),
        # e nao o nucleo, decide se b e alcancado.
        self.assertEqual(R.reach_diferencial(grafo(self.G_P + self.G_C, self.NOS), {"a"}),
                         frozenset({"a", "b", "y"}))
        self.assertEqual(R.reach_diferencial(grafo(self.G_P, self.NOS), {"a"}),
                         frozenset({"a", "b", "y"}))
        self.assertEqual(R.reach_diferencial(grafo(self.G_C, self.NOS), {"a"}),
                         frozenset({"a"}))


# ---------------------------------------------------------------- A2 sobre os adaptadores reais
class A2AdaptadoresReais(unittest.TestCase):
    """A religacao a -> x de b, com a regra d1 REAL dos adaptadores (nao reimplementada aqui).
    So adaptador + nucleo sobre fixtures minimas escritas a mao em diretorio temporario; nenhum
    oraculo, nenhum corpus. Esperados a mao, escritos antes da 1a execucao."""

    def _dir(self, arquivos):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        for nome, txt in arquivos.items():
            (Path(d.name) / nome).write_text(txt, encoding="utf-8")
        return ArvoreDir(d.name)

    # ---- tz: Zone b consome o conjunto de regras a (p) ou x (c); Link y consome b.
    @staticmethod
    def _tz(regra_de_b):
        return {
            "Makefile": "TDATA=\tdados\n",
            "dados": ("Rule\tA\t1950\tmax\t-\tJan\t1\t0:00\t1:00\tS\n"
                      "Rule\tX\t1950\tmax\t-\tJan\t1\t0:00\t0\t-\n"
                      f"Zone\tB\t1:00\t{regra_de_b}\tF%sT\n"
                      "Link\tB\tY\n"),
        }

    def test_a2_tz_regra_d1_real(self):
        ap, ac = self._dir(self._tz("A")), self._dir(self._tz("X"))
        S = tz.semente(ap, ac)
        self.assertEqual(S, {"Z:B": "M"})              # a linha da Zone entra nos bytes de b; R:A e R:X nao mudam
        G = tz.grafo(ap, ac)
        self.assertTrue(G.has_edge("R:A", "Z:B") and G.has_edge("R:X", "Z:B"))
        self.assertEqual(R.reach(G, S), frozenset({"Z:B", "L:Y"}))
        U = tz.d1_universo(ap, ac)
        self.assertEqual(U, {"B", "Y"})
        self.assertEqual(R.eis(G, S, U, tz.d1_elemento), frozenset({"B", "Y"}))
        # mesma resposta em G_p, G_c e G_p uniao G_c (o nucleo e indiferente a uniao)
        for Gx in (tz.d2_declarado(ap), tz.d2_declarado(ac)):
            self.assertEqual(R.reach(Gx, S), frozenset({"Z:B", "L:Y"}))

    def test_a2_tz_sem_dependencia_nos_bytes(self):
        ap, ac = self._dir(self._tz("A")), self._dir(self._tz("A"))
        self.assertEqual(tz.semente(ap, ac), {})
        self.assertEqual(R.eis(tz.grafo(ap, ac), tz.semente(ap, ac), tz.d1_universo(ap, ac),
                               tz.d1_elemento), frozenset())

    # ---- C (estilo makefile do Lua): a.o passa de depender de a.h para depender de u.h.
    _MK = ("CC= gcc\nCORE_O= a.o b.o\nALL_O= $(CORE_O)\n\no:\t$(ALL_O)\n\n"
           "$(ALL_O): makefile\n\na.o: a.c {dep}\nb.o: b.c b.h\n")
    _FONTES = {"a.c": '#include "a.h"\nint fa(void) { return 1; }\n', "a.h": "int fa(void);\n",
               "u.h": "#define U 1\n", "b.c": '#include "b.h"\nint fb(void) { return 2; }\n',
               "b.h": "int fb(void);\n"}

    def _c(self, dep):
        return self._dir({**self._FONTES, "makefile": self._MK.format(dep=dep)})

    def test_a2_c_religacao_no_makefile(self):
        A = cbuild.para("lua")
        ap, ac = self._c("a.h"), self._c("u.h")
        S = A.semente(ap, ac)
        self.assertEqual(S, {"makefile": "M"})       # so a linha de dependencia mudou: o no e o makefile
        G = A.grafo(ap, ac)
        self.assertTrue(G.has_edge("a.h", "a.o") and G.has_edge("u.h", "a.o"))
        U = A.d1_universo(ap, ac)
        self.assertEqual(U, {"a.o", "b.o"})
        # makefile e configuracao: alcanca todo objeto (arestas "config"), a.h e u.h nao entram em S
        self.assertEqual(R.eis(G, S, U, A.d1_elemento), frozenset({"a.o", "b.o"}))
        self.assertEqual(R.eis(G, {"u.h"}, U, A.d1_elemento), frozenset({"a.o"}))
        self.assertEqual(R.eis(G, {"a.h"}, U, A.d1_elemento), frozenset({"a.o"}))

    def test_a2_c_include_trocado_no_fonte(self):
        A = cbuild.para("lua")
        ap = self._dir({**self._FONTES, "makefile": self._MK.format(dep="a.h")})
        ac = self._dir({**self._FONTES, "a.c": '#include "u.h"\nint fa(void) { return 1; }\n',
                        "makefile": self._MK.format(dep="a.h")})
        S = A.semente(ap, ac)
        self.assertEqual(S, {"a.c": "M"})
        self.assertEqual(R.eis(A.grafo(ap, ac), S, A.d1_universo(ap, ac), A.d1_elemento),
                         frozenset({"a.o"}))


# ---------------------------------------------------------------- A3: ciclo de 2, 24 permutacoes
class A3CicloPermutado(unittest.TestCase):
    # Fonte, em notacao de dependencia: a -> b, b -> a, c -> a, d isolado ("x -> y" = x depende de y).
    FONTE_DEPENDENCIA = {"a": ["b"], "b": ["a"], "c": ["a"], "d": []}
    # Traducao a mao para §4.1 (u -> v = v consome u):
    ARESTAS_41 = {("b", "a"), ("a", "b"), ("a", "c")}
    SEMENTE = {"a"}
    ESPERADO = frozenset({"a", "b", "c"})

    def test_a3_traducao(self):
        traduzidas = {(y, x) for x, ys in self.FONTE_DEPENDENCIA.items() for y in ys}
        self.assertEqual(traduzidas, self.ARESTAS_41)

    def test_a3_24_permutacoes_um_resultado(self):
        perms = list(itertools.permutations(["a", "b", "c", "d"]))
        self.assertEqual(len(perms), 24)
        resultados = set()
        for perm in perms:
            G = nx.DiGraph()
            G.add_nodes_from(perm)
            adj = {x: [] for x in perm}
            for x in perm:
                for y in self.FONTE_DEPENDENCIA[x]:
                    G.add_edge(y, x)
                    adj[y].append(x)
            r_nx = R.reach(G, self.SEMENTE)
            r_bfs = bfs_ref(adj, self.SEMENTE)
            resultados.add(r_nx)
            resultados.add(r_bfs)
            self.assertEqual(R.reach_diferencial(G, self.SEMENTE), self.ESPERADO, perm)
            self.assertEqual(R.descritores(G, self.SEMENTE),
                             {"CICLO": [["a", "b"]], "AUTOLACO": [], "GRAFO_VAZIO": False}, perm)
        self.assertEqual(resultados, {self.ESPERADO})  # 1 resultado distinto nas 24

    def test_a3_leitura_literal_da_aresta_com_semente_c(self):
        # Leitura alternativa, sem traducao: aresta c -> a lida direto no §4.1 ("a consome c")
        # e semente {c}. Esperado a mao: {a, b, c}, nas 24 permutacoes.
        resultados = set()
        for perm in itertools.permutations(["a", "b", "c", "d"]):
            G = nx.DiGraph()
            G.add_nodes_from(perm)
            for u, v in (("a", "b"), ("b", "a"), ("c", "a")):
                G.add_edge(u, v)
            resultados.add(R.reach(G, {"c"}))
        self.assertEqual(resultados, {frozenset({"a", "b", "c"})})

    def test_a3_notacao_literal(self):
        # Se "c -> a" fosse lido na convencao do §4.1 (a consome c), c nao seria alcancado.
        G = grafo([("a", "b"), ("b", "a"), ("c", "a")], ("d",))
        self.assertEqual(R.reach_diferencial(G, self.SEMENTE), frozenset({"a", "b"}))


# ---------------------------------------------------------------- A4: bateria patologica
class A4Patologica(BaseCasos):
    def test_a4_topologias(self):
        for caso in TOPOLOGIAS_A4:
            self.checar_caso(*caso)

    def test_a4_universo_vazio(self):
        ident = lambda n: n  # noqa: E731
        self.assertEqual(R.eis(grafo([("a", "b")]), {"a"}, set(), ident), frozenset())
        self.assertEqual(R.eis(grafo([]), {"a"}, {"a"}, ident), frozenset({"a"}))
        self.assertEqual(R.eis(grafo([]), set(), set(), ident), frozenset())
        mapa = {"h": None, "a": "a.o", "b": "b.o"}
        G = grafo([("h", "a"), ("a", "b")])
        self.assertEqual(R.eis(G, {"h"}, {"a.o", "b.o", "c.o"}, mapa.get), frozenset({"a.o", "b.o"}))
        self.assertEqual(R.eis(G, {"h"}, {"b.o"}, mapa.get), frozenset({"b.o"}))
        self.assertEqual(R.eis(G, {"h"}, set(), mapa.get), frozenset())
        self.assertEqual(R.eis(G, {"b"}, {"a.o", "b.o", "c.o"}, mapa.get), frozenset({"b.o"}))
        self.assertEqual(R.eis(G, {"x"}, {"a.o"}, mapa.get), frozenset())

    def test_a4_permutacao_da_entrada(self):
        rng = random.Random(4202)
        for nome, nos, arestas, casos, ciclo, vazio in TOPOLOGIAS_A1 + TOPOLOGIAS_A4:
            todos_nos = list(dict.fromkeys(list(nos) + [n for e in arestas for n in e]))
            for S, esperado in casos:
                distintos = set()
                for _ in range(30):
                    ordem_nos = rng.sample(todos_nos, len(todos_nos))
                    ordem_arestas = rng.sample(arestas, len(arestas))
                    ordem_S = rng.sample(sorted(S), len(S))
                    G = nx.DiGraph()
                    G.add_nodes_from(ordem_nos)
                    G.add_edges_from(ordem_arestas)
                    adj = {n: [] for n in ordem_nos}
                    for u, v in ordem_arestas:
                        adj[u].append(v)
                    distintos.add(R.reach(G, ordem_S))
                    distintos.add(bfs_ref(adj, ordem_S))
                    distintos.add(R.reach_diferencial(G, iter(ordem_S)))
                    self.assertEqual(R.descritores(G, ordem_S),
                                     desc_esperado(nome, ciclo, vazio), nome)
                self.assertEqual(distintos, {frozenset(esperado)}, (nome, sorted(S)))

    def test_a4_pendente(self):
        # (arestas, definidos, PENDENTE esperado), escritos a mao.
        casos = [
            ([("a", "b"), ("p", "c"), ("c", "d")], {"a", "b", "c", "d"}, ["p"]),
            ([("q", "r"), ("r", "s"), ("a", "z")], {"r", "s", "a"}, ["q", "z"]),
            ([("a", "b")], {"a", "b"}, []),
            ([("a", "b")], set(), ["a", "b"]),
            ([], set(), []),
        ]
        for arestas, definidos, esperado in casos:
            with self.subTest(arestas=arestas):
                self.assertEqual(R.pendentes(grafo(arestas), definidos), esperado)
        with self.assertRaises(TypeError):
            R.pendentes(grafo([("a", "b")]), "ab")

    def test_a4_autolaco_contado_a_parte(self):
        d = R.descritores(grafo([("a", "a"), ("a", "b"), ("b", "c"), ("c", "b")]))
        self.assertEqual(d, {"CICLO": [["b", "c"]], "AUTOLACO": ["a"], "GRAFO_VAZIO": False})

    def test_a4_semente_string_rejeitada(self):
        G = grafo([("a", "b")])
        for S in ("ab", b"ab"):
            with self.assertRaises(TypeError):
                R.reach(G, S)
            with self.assertRaises(TypeError):
                R.eis(G, S, {"a"}, lambda n: n)
        with self.assertRaises(TypeError):
            R.eis(G, {"a"}, "ab", lambda n: n)
        self.assertEqual(R.reach(G, ["ab"]), frozenset({"ab"}))   # no chamado "ab", fora de V(G)
        self.assertEqual(R.reach(G, {"a", "zz"}), frozenset({"a", "b", "zz"}))  # parte dentro, parte fora

    def test_a4_semente_gerador_e_dict(self):
        G = grafo([("a", "b"), ("b", "c"), ("c", "d")])
        self.assertEqual(R.reach_diferencial(G, (s for s in ["b"])), frozenset({"b", "c", "d"}))
        self.assertEqual(R.reach_diferencial(G, {"b": "M"}), frozenset({"b", "c", "d"}))
        self.assertEqual(R.reach(G, {"b": "M"}), frozenset({"b", "c", "d"}))
        self.assertEqual(R.reach(G, (s for s in ["b"])), frozenset({"b", "c", "d"}))

    def test_a4_divergencia_aborta(self):
        G = grafo([("a", "b"), ("b", "c"), ("c", "d")])
        with mock.patch.object(R, "bfs_ref", lambda adj, S: frozenset()):
            with self.assertRaises(R.DivergenciaNucleo):
                R.reach_diferencial(G, {"a"})
            with self.assertRaises(R.DivergenciaNucleo):   # reach() tambem e diferencial
                R.reach(G, {"a"})
            with self.assertRaises(R.DivergenciaNucleo):
                R.eis(G, {"a"}, {"a"}, lambda n: n)
        with mock.patch.object(R, "bfs_ref", lambda adj, S: frozenset({"a", "b", "c", "d", "z"})):
            with self.assertRaises(R.DivergenciaNucleo):
                R.reach_diferencial(G, {"a"})
        self.assertEqual(R.reach_diferencial(G, {"a"}), frozenset({"a", "b", "c", "d"}))


# ---------------------------------------------------------------- A5: aleatorios, semente fixa
SEMENTE_A5 = 20261002
N_DAG = 10_000
N_CICLICO = 1_000


def _sementes(rng, nos, i):
    S = set(rng.sample(nos, rng.randint(0, min(len(nos), 4))))
    if rng.random() < 0.2:
        S.add(f"externo{i}")
    return S


def gerar_a5(semente):
    rng = random.Random(semente)
    for i in range(N_DAG):
        n = rng.randint(0, 24)
        nos = [f"n{j}" for j in range(n)]
        ordem = rng.sample(nos, n)
        p = rng.random() * 0.4
        arestas = [(ordem[a], ordem[b]) for a in range(n) for b in range(a + 1, n)
                   if rng.random() < p]
        yield "dag", nos, arestas, _sementes(rng, nos, i)
    for i in range(N_CICLICO):
        n = rng.randint(2, 24)   # >= 2 nos: o ciclo plantado e CFC com mais de 1 no
        nos = [f"n{j}" for j in range(n)]
        p = rng.random() * 0.2
        arestas = [(u, v) for u in nos for v in nos if u != v and rng.random() < p]
        k = rng.randint(2, min(n, 6))
        ciclo = rng.sample(nos, k)
        arestas += [(ciclo[j], ciclo[(j + 1) % k]) for j in range(k)]
        yield "ciclico", nos, arestas, _sementes(rng, nos, i)


def _digest(semente):
    h = hashlib.sha256()
    for tipo, nos, arestas, S in gerar_a5(semente):
        h.update(repr((tipo, nos, sorted(arestas), sorted(S))).encode())
    return h.hexdigest()


DIGEST_A5 = "85ef73c10811079666b106e2883606ba091c2ca709dac576a0c377a782fd91d4"   # pino de regressao do gerador (calculado uma vez e fixado); a semente vai ao config.json


class A5Aleatorios(unittest.TestCase):
    def test_a5_networkx_igual_bfs(self):
        n = {"dag": 0, "ciclico": 0}
        com_cfc = 0
        divergencias = []
        soma_alcance = 0
        for tipo, nos, arestas, S in gerar_a5(SEMENTE_A5):
            G = grafo(arestas, nos)
            if tipo == "dag":
                self.assertTrue(nx.is_directed_acyclic_graph(G))
            else:
                self.assertFalse(nx.is_directed_acyclic_graph(G))
                self.assertTrue(R.descritores(G, S)["CICLO"])   # todo "ciclico" tem CFC > 1
                com_cfc += 1
            n[tipo] += 1
            r_nx = R._reach_nx(G, frozenset(S))                 # implementacao networkx isolada
            r_bfs = bfs_ref(adj_direto(arestas, nos), S)        # BFS sobre adjacencia sem networkx
            if r_nx != r_bfs:
                divergencias.append((tipo, n[tipo], sorted(S)))
            self.assertEqual(R.reach_diferencial(G, S), r_bfs)  # em TODA instancia
            soma_alcance += len(r_nx)
        self.assertEqual(n, {"dag": N_DAG, "ciclico": N_CICLICO})
        self.assertEqual(com_cfc, N_CICLICO)
        self.assertEqual(divergencias, [])
        sys.stderr.write(f"\n[A5] semente={SEMENTE_A5} dag={n['dag']} ciclico={n['ciclico']} "
                         f"ciclico_com_CFC>1={com_cfc} divergencias={len(divergencias)} "
                         f"soma|reach|={soma_alcance} digest={_digest(SEMENTE_A5)}\n")

    def test_a5_digest_literal(self):
        self.assertEqual(_digest(SEMENTE_A5), DIGEST_A5)


# ---------------------------------------------------------------- restricoes do §4.1
class Restricoes(unittest.TestCase):
    def test_bfs_ref_ate_40_linhas_so_stdlib(self):
        fonte = (AQUI / "bfs_ref.py").read_text(encoding="utf-8")
        self.assertLessEqual(len(fonte.splitlines()), 40)
        mods = set()
        for no in ast.walk(ast.parse(fonte)):
            if isinstance(no, ast.Import):
                mods |= {a.name.split(".")[0] for a in no.names}
            elif isinstance(no, ast.ImportFrom):
                mods.add((no.module or "").split(".")[0])
        self.assertTrue(mods <= set(sys.stdlib_module_names), mods)

    def test_fecho_so_no_nucleo(self):
        """nx.descendants / bfs_ref fora de nucleo/reach.py (e dos testes) e proibido: o fecho tem
        um so ponto de entrada diferencial (§4.1)."""
        exp = AQUI.parent
        achados = []
        for arq in sorted(exp.rglob("*.py")):
            rel = arq.relative_to(exp)
            if "__pycache__" in rel.parts or "fixtures" in rel.parts or rel.name.startswith("test_") \
                    or rel.parts[:2] == ("nucleo", "reach.py") or rel.parts[:2] == ("nucleo", "bfs_ref.py") \
                    or rel.parts[0] == "auditoria":
                continue
            for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
                nome = no.attr if isinstance(no, ast.Attribute) else no.id if isinstance(no, ast.Name) else None
                if nome in {"descendants", "bfs_ref", "_reach_nx", "descendants_at_distance"}:
                    achados.append(f"{rel}:{no.lineno}:{nome}")
        self.assertEqual(achados, [])

    def test_nucleo_nao_importa_outros_modulos_do_pipeline(self):
        proibidos = {"adaptadores", "detectores", "ganchos", "oraculo", "ensaio", "analise"}
        for arq in ("reach.py", "bfs_ref.py", "__init__.py"):
            arvore = ast.parse((AQUI / arq).read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                nomes = []
                if isinstance(no, ast.Import):
                    nomes = [a.name for a in no.names]
                elif isinstance(no, ast.ImportFrom):
                    nomes = [no.module or ""]
                for nome in nomes:
                    self.assertFalse(set(nome.split(".")) & proibidos, (arq, nome))


if __name__ == "__main__":
    unittest.main(verbosity=2)
