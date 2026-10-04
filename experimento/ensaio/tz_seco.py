"""Corrida seca do lado tz na JANELA DE ENSAIO (PROTOCOLO_V_2026-10-02 §2.5, §11.3 V-0b).

So pares (c, primeiro pai p) com p e c na janela de ensaio (quadro.Janela: ancestral de
corpora.tz.ensaio_ultimo de config.json E data de autor e de commit < data_min;
INTERFACES §0); qualquer outro aborta ANTES de ler conteudo (exigir_ensaio). Oraculo SINTETICO: AIS
sorteado por Bernoulli(q) sobre U real com random.Random(f"{semente}:{p}:{c}")
(INTERFACES §2.5). Nunca e resultado. Exercita adaptador, nucleo (networkx x BFS),
ganchos, detectores e controles nulos, e confere invariantes de engenharia:
  - EIS(d4-ingenuo) <= EIS(d4-preciso) <= EIS(A0); EIS(A0+d3) <= EIS(A0);
    EIS(A_full) <= EIS(A0+d3) & EIS(d4-preciso)  (podas so removem);
  - par nulo (p, p): S vazio e EIS vazio em todo braco que parte da semente;
  - lexico do adaptador (d3) = lexico do detector (T2) em todo no dos dois lados;
  - FP com T1a sai do EIS do d4-ingenuo; FP com T2 sai do EIS do d3 (PARTILHADO).

Uso (de experimento/):
  <venv>/bin/python -m ensaio.tz_seco <repo_tz> <saida.jsonl> [--amostra N] [--semente S] [--q Q]
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import quadro  # noqa: E402
from adaptadores import tz  # noqa: E402
from adaptadores.git_arvore import Arvore  # noqa: E402
from detectores import tz_classes as det  # noqa: E402
from ensaio.sintetico import ais_sintetico  # noqa: E402
from ganchos import tz_d3, tz_d4_ingenuo, tz_d4_preciso  # noqa: E402
from nucleo.reach import descritores, eis  # noqa: E402

_JANELAS: dict = {}


def janela_tz(repo):
    """quadro.Janela do tz (limites de config.json); uma por repositorio."""
    if repo not in _JANELAS:
        _JANELAS[repo] = quadro.Janela("tz", repo, quadro.carregar_cfg())
    return _JANELAS[repo]


def exigir_ensaio(janela, *shas):
    """INTERFACES §0: p ou c com janela != "ensaio" aborta (nada e lido do commit)."""
    for sha in shas:
        if janela.classe(sha) != "ensaio":
            raise SystemExit(f"tz_seco: {sha} fora da janela de ensaio; aborta (INTERFACES §0)")


def _git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], check=True, capture_output=True,
                          text=True).stdout


def pares_ensaio(repo: str) -> list[tuple[str, str]]:
    ultimo = quadro.carregar_cfg()["corpora"]["tz"]["ensaio_ultimo"]
    out = []
    for ln in reversed([ln.split() for ln in _git(repo, "rev-list", "--parents", ultimo).splitlines()]):
        if len(ln) > 1:
            exigir_ensaio(janela_tz(repo), ln[0], ln[1])
            out.append((ln[0], ln[1]))
    return out


def _b(eis_, ais):
    eis_ = sorted(eis_)
    fn, fp = sorted(set(ais) - set(eis_)), sorted(set(eis_) - set(ais))
    return {"EIS": eis_, "FN": fn, "FP": fp, "seguro": not fn}


def um_par(repo, c, p, semente, q, janela=None):
    exigir_ensaio(janela or janela_tz(repo), p, c)        # antes de qualquer leitura de conteudo
    ap, ac = Arvore(repo, p), Arvore(repo, c)
    mudados = set(_git(repo, "diff", "--name-only", p, c).split("\n"))
    if not mudados & (set(tz.arquivos_dados(ap)) | set(tz.arquivos_dados(ac))):
        return None                                   # nao toca arquivo de dados
    S, G, U = tz.semente(ap, ac), tz.grafo(ap, ac), tz.d1_universo(ap, ac)
    ais = ais_sintetico(U, semente, p, c, q)
    d4 = tz.d4_dados(S, ap, ac)
    d3 = {"ap": ap, "ac": ac, "d3_checksum": tz.d3_checksum}
    E = lambda G_, S_: set(eis(G_, S_, U, tz.d1_elemento))  # noqa: E731
    e0 = E(G, S)
    e3 = E(*tz_d3.aplicar(G, S, d3))
    ei = E(*tz_d4_ingenuo.aplicar(G, S, d4))
    ep = E(*tz_d4_preciso.aplicar(G, S, d4))
    ef = E(*tz_d4_preciso.aplicar(*tz_d3.aplicar(G, S, d3), d4))
    assert ei <= ep <= e0 and e3 <= e0 and ef <= (e3 & ep), "poda criou alcance"
    for a in (ap, ac):                                 # lexico adaptador == detector
        lex = tz._modelo(a)["lex"]
        for n, b in tz.d1_nos(a).items():
            assert tuple(map(tuple, lex.get(n, []))) == det.sem_anotacao(b), (a.sha, n)
    Sn = tz.semente(ap, ap)
    assert Sn == {} and E(tz.grafo(ap, ap), Sn) == set(), "par nulo"
    bracos = {"A0": _b(e0, ais), "A0+d3": _b(e3, ais), "A0+d4-ingenuo": _b(ei, ais),
              "A0+d4-preciso": _b(ep, ais), "A_full": _b(ef, ais), "B-ret": _b(U, ais),
              "B-sem": _b(tz.b_sem(S, U), ais), "A0+d2-extraido": None, "A0+d6": None,
              "B-make": None}
    ctx = {"G": G, "S": S, "nos_p": tz.d1_nos(ap), "nos_c": tz.d1_nos(ac), **d4}
    inst = [(e, "FN") for e in bracos["A0"]["FN"]] + [(e, "FP") for e in bracos["A0"]["FP"]]
    multi = det.rotular_tz(inst, ctx)
    for e, m in multi.items():         # checagem de manipulacao (PARTILHADO, §4.5)
        assert "T1a" not in m or e not in ei, ("T1a sem poda do d4-ingenuo", e)
        assert "T2" not in m or e not in e3, ("T2 sem remocao pelo d3", e)
    S_ant = tz.semente(ap, ac, "anterior")
    meta = ac.meta()
    return {"v": 1, "corpus": "tz", "janela": "ensaio", "controle": None, "p": p, "c": c,
            "data_c": meta["data_autor"], "ano": int(meta["data_autor"][:4]),
            "semente_sorteio": semente, "oraculo": {"modo": "sintetico", "dig": None},
            "U": sorted(U), "S": S, "AIS": sorted(ais), "bracos": bracos,
            "instancias": [{"e": e, "lado": l, "multi": multi[e]} for e, l in inst],
            "nc": det.nc_tz(ctx),
            "sens": {"AIS_1970_2037": None, "nc_sem_F": det.nc_tz(ctx, com_F=False),
                     "d1_anterior": {"A0": _b(E(G, S_ant), ais)}},
            "descritores": {**descritores(G, S),
                            "PENDENTE": sorted(tz.pendentes(ap) | tz.pendentes(ac)),
                            "MUDANCA_DE_IDENTIDADE": tz.identidade(ap, ac),
                            "DADOS": {"p": tz.dados_status(ap), "c": tz.dados_status(ac)}}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("saida")
    ap.add_argument("--amostra", type=int, default=0)
    ap.add_argument("--semente", type=int, default=0)
    ap.add_argument("--q", type=float, default=0.1)
    a = ap.parse_args(argv)
    pares = pares_ensaio(a.repo)
    if a.amostra:
        pares = sorted(random.Random(f"{a.semente}:tz_seco").sample(pares, a.amostra),
                       key=pares.index)
    t0, n, cont = time.time(), 0, Counter()
    with open(a.saida, "w", encoding="utf-8") as f:
        for i, (c, p) in enumerate(pares):
            if (i + 1) % 200 == 0:
                print(f"{i + 1}/{len(pares)} {time.time() - t0:.0f}s", file=sys.stderr)
            reg = um_par(a.repo, c, p, a.semente, a.q)
            if reg is None:
                cont["nao_toca_dados"] += 1
                continue
            n += 1
            f.write(json.dumps(reg, sort_keys=True, ensure_ascii=False) + "\n")
            cont["nc"] += reg["nc"]
            cont["S_vazia"] += not reg["S"]
            for b, v in reg["bracos"].items():
                if v is not None:
                    cont[f"inseguro:{b}"] += not v["seguro"]
            for inst in reg["instancias"]:
                for r in inst["multi"]:
                    cont[f"rotulo:{r}"] += 1
            cont["ciclo"] += bool(reg["descritores"]["CICLO"])
            cont["pendente"] += bool(reg["descritores"]["PENDENTE"])
            cont["identidade"] += bool(reg["descritores"]["MUDANCA_DE_IDENTIDADE"])
            cont["nc_sem_F"] += reg["sens"]["nc_sem_F"]
            for lado in "pc":
                d = reg["descritores"]["DADOS"][lado]
                cont[f"tdata_fonte:{d['fonte']}"] += 1
                cont["arquivo_faltante"] += bool(d["faltantes"])
    print(json.dumps({"ENSAIO": True, "pares_lidos": len(pares), "pares_gravados": n,
                      "segundos": round(time.time() - t0), **dict(sorted(cont.items()))},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
