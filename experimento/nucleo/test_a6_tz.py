"""Bateria A6 (PROTOCOLO_V_2026-10-02 §4.2): fixture de tz escrita a mao.

Aceita o pipeline do tz (oraculo real, adaptador, detectores, ganchos, nucleo).
NUNCA e evidencia. A fixture fica em nucleo/fixtures/a6_tz/{p,c}/ e contem:
  - uma Rule (Xr, 1950) ANTERIOR ao inicio (1980) da linha de Zone que a usa, cuja
    LETTER/S muda de P para Q em c: muda a abreviatura de partida da linha
    (tz@bec4d95a:zic.c:3656-3665; zic.8:693-702) -> o d4-ingenuo poda e cria FN (H4);
  - uma Rule (Yr, 2000) posterior a UNTIL+1 (1990+1) do unico intervalo de uso:
    FP de A0 rotulado T1a; o d4-preciso poda sem FN;
  - uma edicao so de comentario antes de Fixa/Gama: FP rotulado T2; o d3 a remove;
  - um Link novo so em c (Fixa/Epsilon): MUDANCA_DE_IDENTIDADE, fora de U;
  - um arquivo fora de TDATA (dados_fora), alterado, que ninguem le.
Os ESPERADOS abaixo sao literais escritos a mao ANTES da primeira execucao
(sha256 deste arquivo antes de rodar: no relato do V-0a). Nenhum esperado e
calculado pelo codigo sob teste. O oraculo real so roda aqui, sobre a fixture.

Rodar de experimento/:
  V_TZ_BIN=<dir com zic/zdump de tz_ferramentas.sh> <venv>/bin/python -m unittest -v nucleo.test_a6_tz
Sem V_TZ_BIN, os testes que rodam o oraculo sao pulados (os demais rodam).
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptadores import tz  # noqa: E402
from adaptadores.git_arvore import Arvore, ArvoreDir  # noqa: E402
from detectores import tz_classes as det  # noqa: E402
from ganchos import tz_d3, tz_d4_ingenuo, tz_d4_preciso  # noqa: E402
from nucleo.reach import eis, reach_diferencial  # noqa: E402

EXP = Path(__file__).resolve().parents[1]
FIX = EXP / "nucleo" / "fixtures" / "a6_tz"
ORACULO = EXP / "oraculo" / "tz_zdump.sh"
INF = math.inf
A, B, D, G_, E = "Fixa/Alfa", "Fixa/Beta", "Fixa/Delta", "Fixa/Gama", "Fixa/Epsilon"

# ------------------------------------------------------------------ ESPERADOS (a mao)
ESP_ARQUIVOS = ["dados_a", "dados_b"]
ESP_S_PROXIMA = {"F:dados_b": "M", "L:Fixa/Epsilon": "A", "R:Xr": "M", "R:Yr": "M",
                 "Z:Fixa/Gama": "M"}
ESP_S_ANTERIOR = {"L:Fixa/Epsilon": "A", "R:Xr": "M", "R:Yr": "M", "Z:Fixa/Beta": "M",
                  "Z:Fixa/Gama": "M"}
ESP_ARESTAS = sorted([("R:Xr", "Z:Fixa/Alfa"), ("R:Yr", "Z:Fixa/Beta"),
                      ("Z:Fixa/Alfa", "L:Fixa/Delta"), ("Z:Fixa/Alfa", "L:Fixa/Epsilon")])
ESP_U = [A, B, D, G_]
ESP_IDENTIDADE = [E]
ESP_INTERVALOS_P = {("R:Xr", "Z:Fixa/Alfa"): [(1980.0, INF)],
                    ("R:Yr", "Z:Fixa/Beta"): [(-INF, 1990.0)]}
ESP_ALTERADAS = {"R:Xr": [("p", 1950.0, 1950.0), ("c", 1950.0, 1950.0)],
                 "R:Yr": [("p", 2000.0, 2000.0), ("c", 2000.0, 2000.0)]}
ESP_COMPARACAO = {A: "AIS", B: "IGUAL", D: "AIS", E: "MUDANCA_DE_IDENTIDADE", G_: "IGUAL"}
ESP_AIS = [A, D]
# braco -> (EIS, FN, FP)
ESP_BRACOS = {
    "A0": ([A, B, D, G_], [], [B, G_]),
    "A0+d3": ([A, B, D], [], [B]),
    "A0+d4-ingenuo": ([G_], [A, D], [G_]),
    "A0+d4-preciso": ([A, D, G_], [], [G_]),
    "A_full": ([A, D], [], []),
    "B-ret": ([A, B, D, G_], [], [B, G_]),
    "B-sem": ([G_], [A, D], [G_]),
}
ESP_MULTI = {B: ["T1a"], G_: ["T2"]}
ESP_NC = False
ESP_EIS_A0_ANTERIOR = [A, B, D, G_]
# Partida da 2a linha de Fixa/Alfa (1980-01-01 00:00 local). CORRECAO de esperado,
# 2026-10-02, depois da 1a execucao (sha antes cdb81732...): a versao anterior exigia
# "FPT" ausente da saida de c, o que e falso, pois as Rules Xr de 1990+ (LETTER/S P)
# tambem dao FPT; o esperado passa a ser a linha da transicao de 1980 e "FQT" ausente
# de p. Nenhum outro esperado mudou; o codigo sob teste nao mudou.
ESP_ABREVIATURA = {"p": "Tue Jan  1 00:00:00 1980 FPT", "c": "Tue Jan  1 00:00:00 1980 FQT"}


# ------------------------------------------------------------------ utilitarios
def _ap_ac():
    return ArvoreDir(FIX / "p"), ArvoreDir(FIX / "c")


def _bracos(ap, ac, ais):
    S = tz.semente(ap, ac)
    G = tz.grafo(ap, ac)
    U = tz.d1_universo(ap, ac)
    d4 = tz.d4_dados(S, ap, ac)
    d3 = {"ap": ap, "ac": ac, "d3_checksum": tz.d3_checksum}

    def b(eis_):
        eis_ = sorted(eis_)
        return (eis_, sorted(set(ais) - set(eis_)), sorted(set(eis_) - set(ais)))

    out = {"A0": b(eis(G, S, U, tz.d1_elemento))}
    G3, S3 = tz_d3.aplicar(G, S, d3)
    out["A0+d3"] = b(eis(G3, S3, U, tz.d1_elemento))
    Gi, Si = tz_d4_ingenuo.aplicar(G, S, d4)
    out["A0+d4-ingenuo"] = b(eis(Gi, Si, U, tz.d1_elemento))
    Gp, Sp = tz_d4_preciso.aplicar(G, S, d4)
    out["A0+d4-preciso"] = b(eis(Gp, Sp, U, tz.d1_elemento))
    Gf, Sf = tz_d4_preciso.aplicar(*tz_d3.aplicar(G, S, d3), d4)
    out["A_full"] = b(eis(Gf, Sf, U, tz.d1_elemento))
    out["B-ret"] = b(U)
    out["B-sem"] = b(tz.b_sem(S, U))
    return out, {"G": G, "S": S, "nos_p": tz.d1_nos(ap), "nos_c": tz.d1_nos(ac), **d4}


def _oraculo(*args, env=None):
    return subprocess.run(["bash", str(ORACULO), *map(str, args)], capture_output=True,
                          text=True, env={**os.environ, **(env or {})}, timeout=600)


def _comparacao(saida: Path) -> dict:
    return dict(ln.split("\t") for ln in (saida / "comparacao.tsv").read_text().splitlines())


BIN = os.environ.get("V_TZ_BIN")


# ------------------------------------------------------------------ testes
class A6Adaptador(unittest.TestCase):
    def test_arquivos_semente_grafo(self):
        ap, ac = _ap_ac()
        self.assertEqual(tz.arquivos_dados(ap), ESP_ARQUIVOS)
        self.assertEqual(tz.arquivos_dados(ac), ESP_ARQUIVOS)
        self.assertEqual(tz.semente(ap, ac), ESP_S_PROXIMA)
        self.assertEqual(tz.semente(ap, ac, "anterior"), ESP_S_ANTERIOR)
        self.assertEqual(sorted(tz.grafo(ap, ac).edges()), ESP_ARESTAS)
        self.assertEqual(sorted(tz.d1_universo(ap, ac)), ESP_U)
        self.assertEqual(tz.identidade(ap, ac), ESP_IDENTIDADE)
        self.assertEqual(tz.pendentes(ap) | tz.pendentes(ac), set())
        self.assertEqual(tz.d4_intervalos(ap), ESP_INTERVALOS_P)
        self.assertEqual(tz.d4_dados(tz.semente(ap, ac), ap, ac)["alteradas"], ESP_ALTERADAS)

    def test_bracos_rotulos_nc_com_ais_escrito(self):
        ap, ac = _ap_ac()
        bracos, ctx = _bracos(ap, ac, ESP_AIS)
        self.assertEqual(bracos, ESP_BRACOS)
        inst = [(e, "FN") for e in bracos["A0"][1]] + [(e, "FP") for e in bracos["A0"][2]]
        self.assertEqual(det.rotular_tz(inst, ctx), ESP_MULTI)
        self.assertEqual(det.nc_tz(ctx), ESP_NC)
        # sensibilidade: comentario atribuido a estrofe anterior (§4.4, §6.4)
        S_ant = tz.semente(ap, ac, "anterior")
        G = tz.grafo(ap, ac)
        self.assertEqual(sorted(eis(G, S_ant, tz.d1_universo(ap, ac), tz.d1_elemento)),
                         ESP_EIS_A0_ANTERIOR)
        reach_diferencial(G, S_ant)


@unittest.skipUnless(BIN, "V_TZ_BIN ausente: oraculo real nao roda")
class A6Oraculo(unittest.TestCase):
    def test_oraculo_real_diretorio_e_bracos(self):
        with tempfile.TemporaryDirectory() as t:
            r = _oraculo("--par", FIX, "p", "c", BIN, Path(t) / "par")
            self.assertEqual(r.returncode, 0, r.stderr)
            comp = _comparacao(Path(t) / "par")
            self.assertEqual(comp, ESP_COMPARACAO)
            for lado in ("p1", "p2", "c1", "c2"):
                self.assertEqual((Path(t) / "par" / lado / "dados.txt").read_text().split(),
                                 ESP_ARQUIVOS)
            for lado in ("p", "c"):
                z = (Path(t) / "par" / f"{lado}1" / "zdump" / f"{A}.zdump").read_text()
                self.assertIn(ESP_ABREVIATURA[lado], z)
            z = (Path(t) / "par" / "p1" / "zdump" / f"{A}.zdump").read_text()
            self.assertNotIn("FQT", z)
            ais = sorted(n for n, c in comp.items() if c == "AIS")
            self.assertEqual(ais, ESP_AIS)
            ap, ac = _ap_ac()
            bracos, ctx = _bracos(ap, ac, ais)
            self.assertEqual(bracos, ESP_BRACOS)
            # registro da aceitacao (nunca evidencia) em saidas/fixtures/a6_tz.json
            inst = [(e, "FN") for e in bracos["A0"][1]] + [(e, "FP") for e in bracos["A0"][2]]
            multi = det.rotular_tz(inst, ctx)
            par = Path(t) / "par"
            reg = {"fixture": "a6_tz", "janela": "fixture", "oraculo": {"modo": "real",
                   "comparacao": comp, "manifestos": {k: (par / k / "manifesto.tsv").read_text()
                                                      for k in ("p1", "p2", "c1", "c2")},
                   "zic_stderr": (par / "p1" / "zic.stderr").read_text()
                   + (par / "c1" / "zic.stderr").read_text()},
                   "S": tz.semente(ap, ac), "U": sorted(tz.d1_universo(ap, ac)), "AIS": ais,
                   "identidade": tz.identidade(ap, ac),
                   "bracos": {k: {"EIS": v[0], "FN": v[1], "FP": v[2], "seguro": not v[1]}
                              for k, v in bracos.items()},
                   "instancias": [{"e": e, "lado": l, "multi": multi[e]} for e, l in inst],
                   "nc": det.nc_tz(ctx)}
            destino = EXP / "saidas" / "fixtures" / "a6_tz.json"
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps(reg, ensure_ascii=False, indent=1, sort_keys=True) + "\n")

    def test_oraculo_real_caminho_git_igual_ao_diretorio(self):
        repo = FIX / f"_git_tmp_{os.getpid()}"
        try:
            repo.mkdir()
            git = ["git", "-C", str(repo), "-c", "user.name=fixture", "-c",
                   "user.email=fixture@invalid", "-c", "commit.gpgsign=false"]
            subprocess.run(git[:3] + ["init", "-q"], check=True)
            shas = {}
            for lado in ("p", "c"):
                for f in repo.iterdir():
                    if f.name != ".git":
                        f.unlink()
                for f in (FIX / lado).iterdir():
                    shutil.copy(f, repo / f.name)
                subprocess.run(git + ["add", "-A"], check=True)
                subprocess.run(git + ["commit", "-q", "-m", lado], check=True,
                               env={**os.environ, "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
                                    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"})
                shas[lado] = subprocess.run(git[:3] + ["rev-parse", "HEAD"], check=True,
                                            capture_output=True, text=True).stdout.strip()
            gp, gc = Arvore(repo, shas["p"]), Arvore(repo, shas["c"])
            self.assertEqual(tz.semente(gp, gc), ESP_S_PROXIMA)
            with tempfile.TemporaryDirectory() as t:
                r = _oraculo("--par", repo, shas["p"], shas["c"], BIN, Path(t) / "par")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(_comparacao(Path(t) / "par"), ESP_COMPARACAO)
        finally:
            shutil.rmtree(repo, ignore_errors=True)

    def test_guarda_fora_de_fixture_sai_9(self):
        with tempfile.TemporaryDirectory() as t:
            shutil.copytree(FIX / "p", Path(t) / "p")
            for env in ({}, {"V_MODO": "confirmatorio"}):
                r = _oraculo(t, "p", BIN, Path(t) / "saida", env=env)
                self.assertEqual(r.returncode, 9, r.stderr)
                self.assertFalse((Path(t) / "saida").exists())
                r = _oraculo("--par", t, "p", "p", BIN, Path(t) / "saida", env=env)
                self.assertEqual(r.returncode, 9, r.stderr)
                self.assertFalse((Path(t) / "saida").exists())

    def test_par_nulo_sem_ais(self):
        with tempfile.TemporaryDirectory() as t:
            r = _oraculo("--par", FIX, "p", "p", BIN, Path(t) / "par")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(set(_comparacao(Path(t) / "par").values()), {"IGUAL"})
            ap = ArvoreDir(FIX / "p")
            self.assertEqual(tz.semente(ap, ap), {})


if __name__ == "__main__":
    unittest.main()
