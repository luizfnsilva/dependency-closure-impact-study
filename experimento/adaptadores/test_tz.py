"""Testes do lado tz: adaptador, detector, ganchos e oraculo, sem par real.

Esperados escritos a mao. Nada aqui roda o oraculo, nem calcula EIS, detector ou
gancho sobre commit real. O unico contato com historico real e LER nomes no
ultimo commit da janela de ensaio (tz@7550cb98, §2.5) para a auditoria (ii) de
"zero identificador literal"; so roda com V_TZ_REPO.

Rodar de experimento/:  [V_TZ_REPO=<clone de eggert/tz>] <venv>/bin/python -m unittest -v adaptadores.test_tz
"""
from __future__ import annotations

import ast
import json
import math
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptadores import tz  # noqa: E402
from adaptadores.git_arvore import Arvore, ArvoreDir  # noqa: E402
from detectores import tz_classes as det  # noqa: E402
from ganchos import tz_d4_ingenuo, tz_d4_preciso  # noqa: E402

EXP = Path(__file__).resolve().parents[1]
INF = math.inf
ENSAIO_ULTIMO = "7550cb98da5f42e9e551f10caa725ce0b6b571b8"   # §2.5, INTERFACES §0
MODULOS_TZ = ["adaptadores/tz.py", "adaptadores/git_arvore.py", "detectores/tz_classes.py",
              "ganchos/tz_d3.py", "ganchos/tz_d4_ingenuo.py", "ganchos/tz_d4_preciso.py"]

LINHAS = [  # (linha, campos esperados pelo lexico de zic.8:336-345)
    (b"Rule\tQr\t1967\t1973\t-\tApr\tlastSun\t2:00\t1:00\tD\n",
     [b"Rule", b"Qr", b"1967", b"1973", b"-", b"Apr", b"lastSun", b"2:00", b"1:00", b"D"]),
    (b'Zone\t"Q b"\t1:00\t-\t"X#Y"\t# coment\n', [b"Zone", b"Q b", b"1:00", b"-", b"X#Y"]),
    (b"  # so comentario\n", []),
    (b"\n", []),
    (b"", []),
    (b"a#b c\n", [b"a"]),
    (b'a"b"c d\n', [b"abc", b"d"]),
    (b'""\tx\n', [b"", b"x"]),
    (b"x\vy\fz\rw\n", [b"x", b"y", b"z", b"w"]),
    (b"sem_fim_de_linha", [b"sem_fim_de_linha"]),
]

DADOS = (b"# cabecalho\n"
         b"Z\tQa/Um\t1:00\tQr\tQT\t1990 Mar\n"
         b"# comentario entre linhas da mesma Zone\n"
         b"\t\t2:00\t-\tQT2\t2000\n"
         b"\t\t3:00\tQr\tQ%sT\n"
         b"R\tQr\tmin\t1985\t-\tJan\t1\t0:00\t1:00\tS\n"
         b"ru\tQr\t1999\tmax\t-\tJul\t1\t0:00\t0\t-\n"
         b"Zone\tQa/Quatro\t1:00\tQn\tQT\n"
         b"Zone\tQa/Cinco\t1:00\t1:00\tQT\n"
         b"li\tQa/Um\tQa/Dois\n"
         b"LINK\tQa/Dois\tQa/Tres\n"
         b"Link\tQa/Nada\tQa/Seis\n"
         b"Xyz\tlinha de tipo desconhecido\n"
         b"# sobra\n")


def _arvore(tmp: str, dados: dict[str, bytes]) -> ArvoreDir:
    for nome, conteudo in dados.items():
        Path(tmp, nome).write_bytes(conteudo)
    return ArvoreDir(tmp)


class Lexico(unittest.TestCase):
    def test_campos_e_detector_concordam(self):
        for linha, esperado in LINHAS:
            self.assertEqual(tz.campos(linha), esperado, linha)
            self.assertEqual(list(det._tokens(linha)), esperado, linha)
        self.assertIsNone(tz.campos(b'aspas "impares\n'))
        self.assertEqual(det._tokens(b'aspas "impares\n'), (b'aspas "impares\n',))

    def test_palavras_chave(self):
        P = tz._palavra
        self.assertEqual(P(b"Z", tz._TIPOS), "Zone")
        self.assertEqual(P(b"li", tz._TIPOS), "Link")
        self.assertEqual(P(b"RULE", tz._TIPOS), "Rule")
        self.assertIsNone(P(b"", tz._TIPOS))
        self.assertIsNone(P(b"Zx", tz._TIPOS))
        self.assertEqual(tz._ano(b"mi"), -INF)
        self.assertEqual(tz._ano(b"1970"), 1970.0)
        self.assertIsNone(tz._ano(b"1970x"))
        self.assertEqual(tz._ate(b"o", 1950.0), 1950.0)
        self.assertEqual(tz._ate(b"ma", 1950.0), INF)
        self.assertEqual(tz._ate(b"1960", 1950.0), 1960.0)


class Modelo(unittest.TestCase):
    def test_modelo_continuacao_links_pendentes(self):
        with tempfile.TemporaryDirectory() as t:
            dados = tz._DECL["tdata_reserva"]["valor"][0]     # sem Makefile: lista fixa
            a = _arvore(t, {dados: DADOS})
            self.assertEqual(tz.arquivos_dados(a), [dados])
            nos = tz.d1_nos(a)
            self.assertEqual(sorted(nos), sorted([
                "F:" + dados, "L:Qa/Dois", "L:Qa/Seis", "L:Qa/Tres", "R:Qr",
                "Z:Qa/Cinco", "Z:Qa/Quatro", "Z:Qa/Um"]))
            self.assertEqual(nos["Z:Qa/Um"], b"".join(DADOS.splitlines(True)[0:5]))
            self.assertEqual(nos["F:" + dados], b"".join(DADOS.splitlines(True)[12:14]))
            G = tz.d2_declarado(a)
            self.assertEqual(sorted(G.edges()), [("L:Qa/Dois", "L:Qa/Tres"),
                                                 ("R:Qr", "Z:Qa/Um"), ("Z:Qa/Um", "L:Qa/Dois")])
            self.assertEqual(tz.pendentes(a), {"R:Qn", "Z|L:Qa/Nada"})
            self.assertEqual(tz.d4_intervalos(a), {("R:Qr", "Z:Qa/Um"): [(-INF, 1990.0), (2000.0, INF)],
                                                   ("R:Qn", "Z:Qa/Quatro"): [(-INF, INF)]})
            self.assertEqual(tz.d1_tipo("R:Qr"), "Rule")
            self.assertEqual(tz.d1_elemento("L:Qa/Dois"), "Qa/Dois")
            self.assertIsNone(tz.d1_elemento("F:" + dados))
            # anterior: cabecalho -> F; comentario entre linhas da Zone -> a propria Zone
            nos_ant = tz.d1_nos(a, "anterior")
            self.assertEqual(nos_ant["Z:Qa/Um"], nos["Z:Qa/Um"][len(b"# cabecalho\n"):])

    def test_alteradas_multiconjunto(self):
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            dados = tz._DECL["tdata_reserva"]["valor"][0]
            rp = b"Rule\tQr\t1950\tonly\t-\tJan\t1\t0:00\t1:00\tS\n"
            rq = b"Rule\tQr\tmin\tmax\t-\tJul\t1\t0:00\t0\t-\n"
            ap = _arvore(t1, {dados: rp + rp + rq})
            ac = _arvore(t2, {dados: rp + rq + b"Rule\tQr\t1960\t1965\t-\tJan\t1\t0:00\t1:00\tS # c\n"})
            self.assertEqual(tz.d4_alteradas("R:Qr", ap, ac),
                             [("p", 1950.0, 1950.0), ("c", 1960.0, 1965.0)])
            self.assertEqual(tz.semente(ap, ac), {"R:Qr": "M"})


class Ganchos(unittest.TestCase):
    """Predicados de poda: esperados a mao, por par (linha alterada, intervalo)."""

    def test_ingenuo_e_preciso(self):
        casos = [  # (alteradas, intervalos, ingenuo, preciso)
            ([("p", 1950.0, 1950.0)], [(1980.0, INF)], True, False),      # anterior ao inicio
            ([("p", 2000.0, 2000.0)], [(-INF, 1990.0)], True, True),      # > UNTIL + 1
            ([("p", 1991.0, 1991.0)], [(-INF, 1990.0)], True, False),     # ano seguinte ao UNTIL
            ([("p", 1990.0, 1990.0)], [(-INF, 1990.0)], False, False),    # ano do UNTIL
            ([("p", 1992.0, INF)], [(-INF, 1990.0)], True, True),
            ([("p", 1992.0, INF)], [(-INF, 1990.0), (2000.0, INF)], False, False),
            ([], [(-INF, 1990.0)], False, False),                          # sem linha alterada
            ([("p", 2000.0, 2000.0)], [], False, False),                   # sem intervalo
        ]
        for alt, ivs, ing, pre in casos:
            self.assertEqual(tz_d4_ingenuo.podavel(alt, ivs), ing, (alt, ivs))
            self.assertEqual(tz_d4_preciso.podavel(alt, ivs), pre, (alt, ivs))
            self.assertEqual(det._disjunta(alt, ivs), ing, (alt, ivs))   # T1a = ingenuo


class Auditoria(unittest.TestCase):
    def test_tamanho_do_adaptador(self):
        n = len((EXP / "adaptadores" / "tz.py").read_text().splitlines())
        self.assertLessEqual(n, 400)

    def test_lista_fixa_igual_no_oraculo(self):
        sh = (EXP / "oraculo" / "tz_zdump.sh").read_text()
        reserva = re.search(r'^RESERVA="([^"]*)"', sh, re.M).group(1).split()
        excluir = re.search(r'^EXCLUIR="([^"]*)"', sh, re.M).group(1).split()
        self.assertEqual(reserva, tz._DECL["tdata_reserva"]["valor"])
        self.assertEqual(excluir, tz._DECL["excluir_dados"]["valor"])

    def test_espec_cita_zic8(self):
        for campo, cita in tz.ESPEC.items():
            self.assertRegex(cita, r"zic\.(8|c):\d|PROTOCOLO_V", campo)

    def test_ferramentas_permitidas(self):
        """§4.3 iv: so git e make -pn; nenhum literal de executavel do oraculo."""
        proibidos = {"zic", "zdump", "gcc", "cc1", "ld", "npm"}
        for rel in ("adaptadores/tz.py", "adaptadores/git_arvore.py"):
            arv = ast.parse((EXP / rel).read_text())
            for no in ast.walk(arv):
                if isinstance(no, ast.Constant) and isinstance(no.value, str):
                    self.assertNotIn(no.value, proibidos, rel)
                if isinstance(no, ast.Call) and getattr(no.func, "attr", "") in (
                        "run", "Popen", "call", "check_output", "check_call", "system"):
                    argv = no.args[0]
                    self.assertIsInstance(argv, ast.List, rel)
                    self.assertIn(argv.elts[0].value, ("git", "make"), rel)
                    if argv.elts[0].value == "make":
                        self.assertEqual(argv.elts[1].value, "-pn", rel)

    def test_ganchos_nao_importam_detectores_nem_fecho(self):
        for rel in ("ganchos/tz_d3.py", "ganchos/tz_d4_ingenuo.py", "ganchos/tz_d4_preciso.py"):
            for no in ast.walk(ast.parse((EXP / rel).read_text())):
                if isinstance(no, (ast.Import, ast.ImportFrom)):
                    nomes = [a.name for a in no.names] + [getattr(no, "module", "") or ""]
                    self.assertFalse(any("detectores" in n or "nucleo" in n for n in nomes), rel)

    def test_detector_nao_importa_ganchos(self):
        for no in ast.walk(ast.parse((EXP / "detectores" / "tz_classes.py").read_text())):
            if isinstance(no, (ast.Import, ast.ImportFrom)):
                nomes = [a.name for a in no.names] + [getattr(no, "module", "") or ""]
                self.assertFalse(any("ganchos" in n or "adaptadores" in n for n in nomes))

    @unittest.skipUnless(os.environ.get("V_TZ_REPO"), "V_TZ_REPO ausente")
    def test_zero_identificador_literal(self):
        """§4.3 ii: nenhum nome de zona, link, conjunto de regras ou arquivo de dados
        (de tz@7550cb98, ultimo commit da janela de ensaio, e da lista fixa) aparece
        como palavra nos modulos do tz."""
        a = Arvore(os.environ["V_TZ_REPO"], ENSAIO_ULTIMO)
        ids = set(tz._DECL["tdata_reserva"]["valor"]) | set(tz._DECL["excluir_dados"]["valor"])
        ids |= set(tz.arquivos_dados(a))
        for n in tz.d1_nos(a):
            ids.add(n[2:])
            ids.update(n[2:].split("/"))
        ids = {i for i in ids if len(i) >= 2}
        for rel in MODULOS_TZ:
            s = (EXP / rel).read_text()
            hits = sorted(i for i in ids if re.search(
                r"(?<![A-Za-z0-9_/-])" + re.escape(i) + r"(?![A-Za-z0-9_/-])", s))
            self.assertEqual(hits, [], rel)


if __name__ == "__main__":
    unittest.main()
