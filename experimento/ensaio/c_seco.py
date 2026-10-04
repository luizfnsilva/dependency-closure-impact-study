"""Corrida seca do lado C (zlib, Lua) na JANELA DE ENSAIO (PROTOCOLO_V_2026-10-02 §2.5,
§4.4 diferencial do parser, §11.3 V-0b). Nunca e resultado.

Janela (INTERFACES §0), conferida por git em TODO par antes de qualquer calculo; violacao
aborta a corrida inteira (codigo 2):
  zlib: bcf78a20 ⊑ p e c ⊑ 9712272 (commits de importacao de 2011-09-09);
  Lua:  datas de autor e de commit de p e de c < 2010-01-01.
Oraculo SINTETICO: AIS sorteado por Bernoulli(q) sobre U real com
random.Random(f"{semente}:{p}:{c}") (INTERFACES §2.5); nenhum objeto e compilado.

Por par exercita adaptador (cbuild), nucleo (networkx x BFS, aborta se divergir), ganchos
(c_d3, c_d2x, c_d6), detectores (c_classes) e faz as checagens de engenharia:
  - diferencial do parser (§4.4), lados p e c: make -n depois de tocar S == U ∩ reach(G_decl, S);
  - par nulo (p, p): S vazio, EIS vazio em todo braco que parte da semente, B-make vazio;
  - EIS(A0+d3) ⊆ EIS(A0) ⊆ EIS(A0+d6);
  - PARTILHADO (§4.5): FP com T3-FP sai do EIS de d2-extraido; FN com T3-FN entra nele.
Concordancia T2 (gcc) x d3 (pygments), INDEPENDENTES, so contada.

Uso (de experimento/):
  <venv>/bin/python -m ensaio.c_seco <zlib|lua> <repo> <saida.jsonl> [--desde AAAA-MM-DD]
         [--amostra N] [--semente S] [--q Q]
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

from adaptadores import cbuild  # noqa: E402
from adaptadores.git_arvore import Arvore  # noqa: E402
from detectores import c_classes as det  # noqa: E402
from ganchos import c_d2x, c_d3, c_d6  # noqa: E402
from nucleo.reach import descritores, eis, reach  # noqa: E402

ZLIB_PRIMEIRO = "bcf78a20978d76f64b7cd46d1a4d7a79a578c77b"
ZLIB_ULTIMO = "9712272c78b9d9c93746d9c8e156a3728c65ca72"
LUA_LIMITE = 1262304000            # 2010-01-01T00:00:00Z

try:
    from ensaio.sintetico import ais_sintetico  # noqa: E402
except ImportError:                              # mesma especificacao (INTERFACES §2.5)
    def ais_sintetico(U, semente, p, c, q=0.1):
        r = random.Random(f"{semente}:{p}:{c}")
        return {e for e in sorted(U) if r.random() < q}


class ForaDaJanela(SystemExit):
    pass


def _git(repo, *a, ok=False):
    p = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)
    if ok:
        return p.returncode == 0
    p.check_returncode()
    return p.stdout


def na_janela(corpus: str, repo: str, sha: str) -> bool:
    if corpus == "zlib":
        return (_git(repo, "merge-base", "--is-ancestor", ZLIB_PRIMEIRO, sha, ok=True)
                and _git(repo, "merge-base", "--is-ancestor", sha, ZLIB_ULTIMO, ok=True))
    datas = _git(repo, "log", "-1", "--format=%at %ct", sha).split()
    return all(int(d) < LUA_LIMITE for d in datas)


def pares_ensaio(corpus: str, repo: str, desde: str | None) -> list[tuple[str, str]]:
    A = cbuild.para(corpus)
    sufs = tuple(A.suf_fonte + A.suf_cab)
    if corpus == "zlib":
        linhas = _git(repo, "rev-list", "--parents", ZLIB_ULTIMO).splitlines()
    else:
        args = ["rev-list", "--parents", "--all", "--before=2009-12-31T23:59:59Z"]
        linhas = _git(repo, *args, *([f"--since={desde}"] if desde else [])).splitlines()
    out = []
    for ln in reversed(linhas):
        c, *pais = ln.split()
        if not pais:
            continue
        mud = _git(repo, "diff", "--name-only", pais[0], c).split("\n")
        if corpus == "lua" and not any("/" not in m and (m.endswith(sufs) or m in A.makefiles)
                                       for m in mud if m):
            continue                    # filtro do quadro (§2.5) transposto para o ensaio
        out.append((c, pais[0]))
    return out


def _b(eis_, ais):
    fn, fp = sorted(set(ais) - set(eis_)), sorted(set(eis_) - set(ais))
    return {"EIS": sorted(eis_), "FN": fn, "FP": fp, "seguro": not fn}


def um_par(corpus, repo, c, p, semente, q):
    for x in (p, c):
        if not na_janela(corpus, repo, x):
            raise ForaDaJanela(f"{corpus}:{x} fora da janela de ensaio: corrida abortada")
    A = cbuild.para(corpus)
    ap, ac = Arvore(repo, p), Arvore(repo, c)
    U, S = A.d1_universo(ap, ac), A.semente(ap, ac)
    G, (G_obs, cob) = A.grafo(ap, ac), A.grafo_obs(ap, ac)
    ais = ais_sintetico(U, semente, p, c, q)
    E = lambda G_, S_: set(eis(G_, S_, U, A.d1_elemento))  # noqa: E731
    d3 = {"ap": ap, "ac": ac, "d3_checksum": A.d3_checksum}
    tem_d6 = bool(A.decl["d6_globais"]["valor"])
    d6 = {"globais": A.d6_globais(ap) | A.d6_globais(ac), "objetos": U}
    e0, e3 = E(G, S), E(*c_d3.aplicar(G, S, d3))
    ex = E(*c_d2x.aplicar(G, S, {"G_obs": G_obs}))
    e6 = E(*c_d6.aplicar(G, S, d6)) if tem_d6 else None
    Gf, Sf = c_d2x.aplicar(*c_d3.aplicar(G, S, d3), {"G_obs": G_obs})
    ef = E(*(c_d6.aplicar(Gf, Sf, d6) if tem_d6 else (Gf, Sf)))
    assert e3 <= e0 and (e6 is None or e0 <= e6), "poda criou alcance ou acrescimo tirou alcance"
    bm = A.b_make(ac, S)
    dif = {lado: cbuild.diferencial_parser(A, a, S, reach) for lado, a in (("p", ap), ("c", ac))}
    Sn = A.semente(ap, ap)                                   # par nulo (p, p)
    assert Sn == {} and E(A.grafo(ap, ap), Sn) == set() and A.b_make(ap, Sn) == set(), "par nulo"
    bracos = {"A0": _b(e0, ais), "A0+d3": _b(e3, ais), "A0+d2-extraido": _b(ex, ais),
              "A0+d6": _b(e6, ais) if tem_d6 else None, "A_full": _b(ef, ais),
              "A0+d4-ingenuo": None, "A0+d4-preciso": None, "B-ret": _b(U, ais),
              "B-sem": _b(A.b_sem(S, U), ais), "B-make": _b(bm & U, ais)}
    ctx = {"reach": reach, "G": G, "G_obs": G_obs, "S": S, "nos_p": A.d1_nos(ap), "nos_c": A.d1_nos(ac),
           "tipo": A.d1_tipo}
    inst = [(e, "FN") for e in bracos["A0"]["FN"]] + [(e, "FP") for e in bracos["A0"]["FP"]]
    multi = det.rotular_c(inst, ctx)
    t2_d3 = Counter()
    for e, m in multi.items():         # checagem de manipulacao (PARTILHADO, §4.5)
        assert "T3-FP" not in m or e not in ex, ("T3-FP sem remocao pelo d2-extraido", e)
        assert "T3-FN" not in m or e in ex, ("T3-FN sem entrada pelo d2-extraido", e)
        if "T2" in m:
            t2_d3["T2_removido_por_d3" if e not in e3 else "T2_mantido_por_d3"] += 1
    meta = ac.meta()
    return {"v": 1, "corpus": corpus, "janela": "ensaio", "controle": None, "p": p, "c": c,
            "data_c": meta["data_autor"], "ano": int(meta["data_autor"][:4]),
            "semente_sorteio": semente, "oraculo": {"modo": "sintetico", "dig": None},
            "U": sorted(U), "S": S, "AIS": sorted(ais), "bracos": bracos,
            "instancias": [{"e": e, "lado": l, "multi": multi[e]} for e, l in inst],
            "nc": det.nc_c(ctx), "cobertura": cob, "diferencial_parser": dif,
            "t2_x_d3": dict(t2_d3), "sens": None, "r_tipo": None,
            "descritores": {**descritores(G, S),
                            "PENDENTE": sorted(A.pendentes(ap) | A.pendentes(ac)),
                            "MUDANCA_DE_IDENTIDADE": sorted(set(A._modelo(ap)["U"])
                                                           ^ set(A._modelo(ac)["U"]))}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", choices=["zlib", "lua"])
    ap.add_argument("repo")
    ap.add_argument("saida")
    ap.add_argument("--desde", default=None)
    ap.add_argument("--amostra", type=int, default=0)
    ap.add_argument("--semente", type=int, default=0)
    ap.add_argument("--q", type=float, default=0.1)
    a = ap.parse_args(argv)
    pares = pares_ensaio(a.corpus, a.repo, a.desde)
    if a.amostra and a.amostra < len(pares):
        pares = sorted(random.Random(f"{a.semente}:{a.corpus}_seco").sample(pares, a.amostra),
                       key=pares.index)
    t0, cont = time.time(), Counter()
    Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
    with open(a.saida, "w", encoding="utf-8") as f:
        for i, (c, p) in enumerate(pares):
            if (i + 1) % 50 == 0:
                print(f"{i + 1}/{len(pares)} {time.time() - t0:.0f}s", file=sys.stderr)
            try:
                reg = um_par(a.corpus, a.repo, c, p, a.semente, a.q)
            except ForaDaJanela as e:
                print(e, file=sys.stderr)
                sys.exit(2)
            f.write(json.dumps(reg, sort_keys=True, ensure_ascii=False) + "\n")
            cont["pares"] += 1
            cont["U_vazio"] += not reg["U"]
            cont["nc"] += reg["nc"]
            for lado, d in reg["diferencial_parser"].items():
                cont[f"diferencial_{lado}:{'igual' if d['igual'] else 'DIVERGE'}"] += 1
            cont["cobertura_falha"] += any(v["c_ok"] < v["c_total"] for v in reg["cobertura"].values())
            for b, v in reg["bracos"].items():
                if v is not None:
                    cont[f"inseguro:{b}"] += not v["seguro"]
            for inst in reg["instancias"]:
                for r in inst["multi"]:
                    cont[f"rotulo:{r}"] += 1
            cont.update(reg["t2_x_d3"])
            cont["ciclo"] += bool(reg["descritores"]["CICLO"])
            cont["pendente"] += bool(reg["descritores"]["PENDENTE"])
            cont["identidade"] += bool(reg["descritores"]["MUDANCA_DE_IDENTIDADE"])
    print(json.dumps({"ENSAIO": True, "corpus": a.corpus, "pares_lidos": len(pares),
                      "segundos": round(time.time() - t0), **dict(sorted(cont.items()))},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
