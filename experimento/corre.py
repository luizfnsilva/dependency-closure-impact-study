#!/usr/bin/env python3
"""Runner do experimento V (PROTOCOLO_V_2026-10-02 §2.5, §3, §3.5, §5, §6.6, §11.3).

Por par: adaptador -> nucleo (networkx x BFS, aborta se divergir) -> ganchos -> oraculo ->
detectores -> um registro JSONL encadeado por hash (integridade.py). Tres modos:

  fixture       so as fixtures A6/A7 (nucleo/fixtures/); unico modo pre-DOI com oraculo REAL.
  ensaio        so pares com p E c na janela de ensaio (§2.5); oraculo SINTETICO forcado; grava so
                em saidas/ensaio/; nunca e resultado. Nao tem caminho de codigo para o oraculo real.
  confirmatorio RECUSA (codigo 2) antes de ler qualquer par se config.json nao tiver `doi` e todo
                sha256 conferindo (§6.6), ou se nao estiver em GitHub Actions sem ci.local_autorizado
                (D4). Oraculo real, c obrigatoriamente na janela de quadro.

Subcomandos:  rodar (padrao) | portao | pares | reexecutar     (ver --help)
O que NAO e feito aqui: nenhum EIS, detector ou gancho roda fora da janela de ensaio sem o portao
do modo confirmatorio, e o oraculo real so roda em fixture ou, depois do portao, em quadro.

Codigos: 0 ok; 2 recusa/guarda/janela; 3 cadeia quebrada; 4 defeito de pipeline (divergencia
networkx x BFS, par nulo violado, poda que cria alcance, adaptador); 5 oraculo fora de contrato.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import quadro  # noqa: E402
from integridade import (CONFIG, RAIZ, Cadeia, Recusa, canonico, carregar_config,  # noqa: E402
                         guarda_confirmatoria, verificar_cadeia)

FIXTURES = RAIZ / "nucleo" / "fixtures"
ENSAIO_DIR = RAIZ / "saidas" / "ensaio"
BRACOS = ("A0", "A0+d3", "A0+d4-ingenuo", "A0+d4-preciso", "A0+d2-extraido", "A0+d6", "A_full",
          "B-ret", "B-sem", "B-make")
PRECEDENCIA = {"FN": ("T4", "T3-FN", "T1b", "INCLASSIFICADO-FN"),     # §4.6
               "FP": ("T3-FP", "T2", "T1a", "T5")}
TIPOS_H7 = {"tz": ("Rule", "Zone", "Link"),                              # §7 H7
            "c": ("fonte", "cabecalho", "cabecalho_gerado", "configuracao", "objeto")}
CAUSAS_ORACULO = {"tz": ("zic_recusa", 3), "zlib": ("nao_constroi", 4), "lua": ("nao_constroi", 4)}
RE_TMP = re.compile(r"/(?:tmp|var/folders)/\S+")
RE_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def defeito(msg: str):
    raise Recusa(4, msg)


class NaoExecutado(Exception):
    def __init__(self, causa: str, detalhe: str, man_p: dict | None = None):
        super().__init__(causa)
        self.causa, self.detalhe, self.man_p = causa, detalhe, man_p


# ============================================================ contexto
class Contexto:
    def __init__(self, modo: str, corpus: str, repo: str, cfg: dict, sha_cfg: str,
                 semente, q: float = 0.1, tz_bin: str | None = None, fixture: str | None = None):
        self.modo, self.corpus, self.repo, self.cfg, self.sha_cfg = modo, corpus, repo, cfg, sha_cfg
        self.semente, self.q, self.tz_bin, self.fixture = semente, q, tz_bin, fixture
        self._J = None
        self.janela_reg = {"fixture": "fixture", "ensaio": "ensaio", "confirmatorio": "quadro"}[modo]
        self._ult: dict | None = None            # ultimo oraculo real, para o par nulo (reuso p1/p2)

    @property
    def J(self):
        """Janelas do clone (so fora de fixture); criado na primeira consulta."""
        if self._J is None and self.modo != "fixture":
            self._J = quadro.Janela(self.corpus, self.repo, self.cfg)
        return self._J

    # arvores
    def arvore(self, ref: str):
        from adaptadores.git_arvore import Arvore, ArvoreDir
        return ArvoreDir(Path(self.repo) / ref) if self.modo == "fixture" else Arvore(self.repo, ref)

    def meta(self, a) -> dict:
        return a.meta()


# ============================================================ oraculo
def _normaliza(txt: str) -> str:
    return RE_TMP.sub("<tmp>", txt)[:300].strip()


def _ler_tsv(caminho: Path) -> list[list[str]]:
    if not caminho.is_file():
        return []
    return [ln.split("\t") for ln in caminho.read_text(encoding="utf-8", errors="replace").splitlines() if ln]


def _manifesto(caminho: Path, corpus: str) -> dict[str, str]:
    """nome -> sha256 valido (tz: coluna 3, 'AUSENTE' fora; C: coluna 2)."""
    col = 2 if corpus == "tz" else 1
    return {r[0]: r[col] for r in _ler_tsv(caminho) if len(r) > col and RE_HEX64.match(r[col])}


def oraculo_real(ctx: Contexto, p: str, c: str, destino: Path) -> dict:
    """Roda o script de oraculo (cada lado duas vezes). Devolve classes por elemento e digests.
    Levanta NaoExecutado (zic recusa / nao constroi) ou Recusa 5 (fora de contrato)."""
    if ctx.modo not in ("fixture", "confirmatorio"):
        raise Recusa(2, f"oraculo real proibido no modo {ctx.modo} (§0, regra 1)")
    if ctx.modo == "confirmatorio" and ctx.J.classe(c) != "quadro" and p != c:
        raise Recusa(2, f"confirmatorio: c={c[:12]} fora do quadro")
    env = {k: v for k, v in os.environ.items() if k != "V_MODO"}
    if ctx.modo == "confirmatorio":
        env["V_MODO"] = "confirmatorio"
    if ctx.corpus == "tz":
        cmd = ["bash", str(RAIZ / "oraculo" / "tz_zdump.sh"), "--par", ctx.repo, p, c,
               str(ctx.tz_bin), str(destino), ctx.cfg["corpora"]["tz"]["janela_zdump"]]
    else:
        cmd = ["bash", str(RAIZ / "oraculo" / "c_build.sh"), "--par", ctx.corpus, ctx.repo, p, c, str(destino)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=4 * 3600)
    prefixo, codigo_recusa = CAUSAS_ORACULO[ctx.corpus]
    if r.returncode == codigo_recusa:
        ne = _ler_tsv(destino / "nao_executado.tsv")
        causa = ne[0][0] if ne and ne[0] else f"{prefixo}_p"
        if causa not in {f"{prefixo}_p", f"{prefixo}_c"}:
            raise Recusa(5, f"causa de NAO_EXECUTADO inesperada: {causa!r}")
        det = ""
        if ne and len(ne[0]) > 1 and Path(ne[0][1]).is_file():
            linhas = Path(ne[0][1]).read_text(encoding="utf-8", errors="replace").strip().splitlines()
            det = _normaliza(" | ".join(linhas[-3:]))
        man = {k: (destino / k / "manifesto.tsv").read_bytes() for k in ("p1", "p2")
               if (destino / k / "manifesto.tsv").is_file()}
        raise NaoExecutado(causa, det, man if len(man) == 2 and causa.endswith("_c") else None)
    if r.returncode != 0:
        raise Recusa(5, f"oraculo saiu com {r.returncode}: {_normaliza(r.stderr[-400:])}")
    comp = {a: b for a, b in (ln.split("\t", 1) for ln in
                              (destino / "comparacao.tsv").read_text(encoding="utf-8").splitlines() if ln)}
    return {"comp": comp,
            "dig": {k: _sha_arq(destino / k / "manifesto.tsv") for k in ("p1", "p2", "c1", "c2")},
            "_man": {k: (destino / k / "manifesto.tsv").read_bytes() for k in ("p1", "p2")}}


def _sha_arq(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sens_w_linha(ctx: Contexto, p: str, c: str, U: set[str], nd: set[str], tmp: Path) -> list[str] | None:
    """tz, §6.4: janela W' do zdump, uma execucao por lado; AIS' = nomes de U (fora do
    NAO_DETERMINISTICO) cujo sha difere. Oraculo real: so fora do ensaio."""
    if ctx.corpus != "tz" or ctx.modo == "ensaio":
        return None
    env = {k: v for k, v in os.environ.items() if k != "V_MODO"}
    if ctx.modo == "confirmatorio":
        env["V_MODO"] = "confirmatorio"
    man = {}
    for lado, ref in (("p", p), ("c", c)):
        saida = tmp / f"w_{lado}"
        r = subprocess.run(["bash", str(RAIZ / "oraculo" / "tz_zdump.sh"), ctx.repo, ref, str(ctx.tz_bin),
                            str(saida), ctx.cfg["corpora"]["tz"]["janela_zdump_sens"]],
                           capture_output=True, text=True, env=env, timeout=3600)
        if r.returncode != 0:
            raise Recusa(5, f"zdump W' ({lado}) saiu com {r.returncode}: {_normaliza(r.stderr[-300:])}")
        man[lado] = _manifesto(saida / "manifesto.tsv", "tz")
    return sorted(n for n in U if n not in nd and n in man["p"] and n in man["c"] and man["p"][n] != man["c"][n])


# ============================================================ nucleo + bracos
def _E(U, elem):
    from nucleo.reach import eis
    return lambda G, S: set(eis(G, S, U, elem))


def _b(E, AIS) -> dict:
    E, AIS = set(E), set(AIS)
    fn, fp = sorted(AIS - E), sorted(E - AIS)
    return {"EIS": sorted(E), "FN": fn, "FP": fp, "seguro": not fn}


def bracos_tz(ap, ac, G, S: dict, U: set[str], AIS: set[str], A) -> tuple[dict, dict]:
    from ganchos import tz_d3, tz_d4_ingenuo, tz_d4_preciso
    E = _E(U, A.d1_elemento)
    d4 = A.d4_dados(S, ap, ac)
    d3 = {"ap": ap, "ac": ac, "d3_checksum": A.d3_checksum}
    e0, e3 = E(G, S), E(*tz_d3.aplicar(G, S, d3))
    ei, ep = E(*tz_d4_ingenuo.aplicar(G, S, d4)), E(*tz_d4_preciso.aplicar(G, S, d4))
    ef = E(*tz_d4_preciso.aplicar(*tz_d3.aplicar(G, S, d3), d4))
    if not (ei <= ep <= e0 and e3 <= e0 and ef <= (e3 & ep)):
        defeito("poda criou alcance (EIS de gancho nao esta contido no de A0)")
    br = {"A0": _b(e0, AIS), "A0+d3": _b(e3, AIS), "A0+d4-ingenuo": _b(ei, AIS),
          "A0+d4-preciso": _b(ep, AIS), "A0+d2-extraido": None, "A0+d6": None,
          "A_full": _b(ef, AIS), "B-ret": _b(U, AIS), "B-sem": _b(A.b_sem(S, U), AIS), "B-make": None}
    return br, {"d4": d4, "e0": e0}


def bracos_c(ap, ac, G, G_obs, S: dict, U: set[str], AIS: set[str], A) -> tuple[dict, dict]:
    from ganchos import c_d2x, c_d3, c_d6
    E = _E(U, A.d1_elemento)
    d3 = {"ap": ap, "ac": ac, "d3_checksum": A.d3_checksum}
    tem_d6 = bool(A.decl["d6_globais"]["valor"])
    d6 = {"globais": A.d6_globais(ap) | A.d6_globais(ac), "objetos": U}
    e0, e3 = E(G, S), E(*c_d3.aplicar(G, S, d3))
    ex = E(*c_d2x.aplicar(G, S, {"G_obs": G_obs}))
    e6 = E(*c_d6.aplicar(G, S, d6)) if tem_d6 else None
    Gf, Sf = c_d2x.aplicar(*c_d3.aplicar(G, S, d3), {"G_obs": G_obs})
    ef = E(*(c_d6.aplicar(Gf, Sf, d6) if tem_d6 else (Gf, Sf)))
    if not (e3 <= e0 and (e6 is None or e0 <= e6)):
        defeito("poda criou alcance ou acrescimo tirou alcance")
    bm = A.b_make(ac, S)
    br = {"A0": _b(e0, AIS), "A0+d3": _b(e3, AIS), "A0+d4-ingenuo": None, "A0+d4-preciso": None,
          "A0+d2-extraido": _b(ex, AIS), "A0+d6": _b(e6, AIS) if tem_d6 else None, "A_full": _b(ef, AIS),
          "B-ret": _b(U, AIS), "B-sem": _b(A.b_sem(S, U), AIS), "B-make": _b(set(bm) & U, AIS)}
    return br, {"e0": e0, "ex": ex}


def r_tipo_efeitos(chave: str, G, S, U, elem, d1tipo, e0: set, AIS: set, fn0: set, fp0: set):
    """H7 (§7): busca exaustiva das regras tipadas isoladas; guarda so as com efeito."""
    try:
        from ganchos import r_tipo
    except ImportError:
        return None
    out = {}
    for regra in r_tipo.regras(TIPOS_H7[chave]):
        G2, S2 = r_tipo.aplicar_regra(G, S, regra, d1tipo)
        e2 = _E(U, elem)(G2, S2)
        fn_novo = sorted((AIS & e0) - e2)
        rem = sorted(((e0 - e2) & fp0) | ((e2 - e0) & fn0))
        if fn_novo or rem:
            out[regra] = {"fn_novo": fn_novo, "removidas": rem}
    return out


def primario(lado: str, multi: list[str]) -> str:
    for k in PRECEDENCIA[lado]:
        if k in multi:
            return k
    defeito(f"rotulo sem precedencia: {lado} {multi}")


# ============================================================ registro
def esqueleto(ctx: Contexto, par: dict, ap, ac) -> dict:
    mp, mc = ap.meta(), ac.meta()
    data_c = par.get("data_c") or mc.get("data_autor")
    return {"v": 1, "corpus": ctx.corpus, "janela": par.get("janela") or ctx.janela_reg,
            "controle": par["controle"], "p": par["p"], "c": par["c"],
            "data_p": mp.get("data_autor"), "data_c": data_c,
            "ano": int(data_c[:4]) if data_c else None,
            "semente_sorteio": ctx.semente, "sha_config": ctx.sha_cfg}


def registro_nao_executado(ctx: Contexto, par: dict, ap, ac, ne: NaoExecutado) -> dict:
    return {**esqueleto(ctx, par, ap, ac), "nao_executado": {"causa": ne.causa, "detalhe": ne.detalhe},
            "oraculo": {"modo": "real" if ctx.modo != "ensaio" else "sintetico", "dig": None},
            "U": [], "S": {}, "AIS": [], "bracos": {}, "instancias": [], "nc": None, "r_tipo": None,
            "sens": None, "descritores": {"NAO_DETERMINISTICO": {"p": [], "c": []},
                                          "MUDANCA_DE_IDENTIDADE": [], "CICLO": [], "PENDENTE": [],
                                          "GRAFO_VAZIO": False}}


def universo_e_ais(ctx: Contexto, A, ap, ac, par: dict, orc: dict | None, ident_decl: set[str]):
    """U, AIS, descritores do oraculo. Real: U = declarado nos dois lados & produzido (AIS, IGUAL ou
    NAO_DETERMINISTICO); resto em MUDANCA_DE_IDENTIDADE (INTERFACES §1). Sintetico: AIS por semente."""
    Ud = set(A.d1_universo(ap, ac))
    if orc is None:                                         # ensaio
        from ensaio.sintetico import ais_sintetico
        # placebo: nenhum arquivo do universo muda; o oraculo esperado e vazio (§5), como no nulo
        ais = set() if par["controle"] == "placebo" else ais_sintetico(Ud, ctx.semente, par["p"],
                                                                       par["c"], ctx.q)
        return Ud, ais, {"p": [], "c": []}, sorted(ident_decl), {"modo": "sintetico", "dig": None}
    comp = orc["comp"]
    nd_p = {n for n, k in comp.items() if "NAO_DETERMINISTICO_p" in k}
    nd_c = {n for n, k in comp.items() if "NAO_DETERMINISTICO_c" in k}
    produzidos = {n for n, k in comp.items() if k in ("AIS", "IGUAL")} | nd_p | nd_c
    U = Ud & produzidos
    ais = {n for n, k in comp.items() if k == "AIS"} & U
    mud = set(ident_decl) | {n for n, k in comp.items() if k == "MUDANCA_DE_IDENTIDADE"} | (Ud - U)
    fora = sorted(produzidos - Ud)
    return U, ais, {"p": sorted(nd_p), "c": sorted(nd_c)}, sorted(mud), \
        {"modo": "real", "dig": orc["dig"], "fora_universo": fora}


def par_tz(ctx: Contexto, par: dict, ap, ac, orc: dict | None, tmp: Path) -> dict:
    from adaptadores import tz as A
    from detectores import tz_classes as det
    from nucleo.reach import descritores
    S, G = A.semente(ap, ac), A.grafo(ap, ac)
    U, AIS, nd, ident, orc_reg = universo_e_ais(ctx, A, ap, ac, par, orc, set(A.identidade(ap, ac)))
    br, aux = bracos_tz(ap, ac, G, S, U, AIS, A)
    ctrl = par["controle"]
    reg = {**esqueleto(ctx, par, ap, ac), "nao_executado": None, "oraculo": orc_reg, "U": sorted(U),
           "S": S, "AIS": sorted(AIS), "bracos": br}
    d4 = aux["d4"]
    dctx = {"G": G, "S": S, "nos_p": A.d1_nos(ap), "nos_c": A.d1_nos(ac), **d4}
    inst = [(e, "FN") for e in br["A0"]["FN"]] + [(e, "FP") for e in br["A0"]["FP"]]
    multi = det.rotular_tz(inst, dctx)
    reg["instancias"] = [{"e": e, "lado": l, "multi": multi[e], "primario": primario(l, multi[e])}
                         for e, l in inst]
    reg["nc"] = det.nc_tz(dctx) if ctrl in (None, "tag") else None
    reg["r_tipo"] = r_tipo_efeitos("tz", G, S, U, A.d1_elemento, A.d1_tipo, aux["e0"], AIS,
                                   set(br["A0"]["FN"]), set(br["A0"]["FP"]))
    S_ant = A.semente(ap, ac, "anterior")
    sens_b = {"A0": _b(_E(U, A.d1_elemento)(G, S_ant), AIS)}
    reg["sens"] = {"AIS_1970_2037": (sens_w_linha(ctx, par["p"], par["c"], U, set(nd["p"]) | set(nd["c"]), tmp)
                                     if orc is not None and par["p"] != par["c"] else None),
                   "d1_anterior": sens_b}
    reg["descritores"] = {**descritores(G, S), "NAO_DETERMINISTICO": nd, "MUDANCA_DE_IDENTIDADE": ident,
                          "PENDENTE": sorted(A.pendentes(ap) | A.pendentes(ac))}
    return reg


def par_c(ctx: Contexto, par: dict, ap, ac, orc: dict | None, tmp: Path) -> dict:
    from adaptadores import cbuild
    from detectores import c_classes as det
    from nucleo.reach import descritores, reach
    A = cbuild.para(ctx.corpus)
    S, G = A.semente(ap, ac), A.grafo(ap, ac)
    G_obs, cob = A.grafo_obs(ap, ac)
    ident_decl = set(A._modelo(ap)["U"]) ^ set(A._modelo(ac)["U"])
    U, AIS, nd, ident, orc_reg = universo_e_ais(ctx, A, ap, ac, par, orc, ident_decl)
    br, aux = bracos_c(ap, ac, G, G_obs, S, U, AIS, A)
    reg = {**esqueleto(ctx, par, ap, ac), "nao_executado": None, "oraculo": orc_reg, "U": sorted(U),
           "S": S, "AIS": sorted(AIS), "bracos": br, "cobertura": cob}
    dctx = {"reach": reach, "G": G, "G_obs": G_obs, "S": S, "nos_p": A.d1_nos(ap), "nos_c": A.d1_nos(ac), "tipo": A.d1_tipo}
    inst = [(e, "FN") for e in br["A0"]["FN"]] + [(e, "FP") for e in br["A0"]["FP"]]
    multi = det.rotular_c(inst, dctx)
    reg["instancias"] = [{"e": e, "lado": l, "multi": multi[e], "primario": primario(l, multi[e])}
                         for e, l in inst]
    reg["nc"] = det.nc_c(dctx) if par["controle"] in (None, "tag") else None
    reg["r_tipo"] = r_tipo_efeitos("c", G, S, U, A.d1_elemento, A.d1_tipo, aux["e0"], AIS,
                                   set(br["A0"]["FN"]), set(br["A0"]["FP"]))
    reg["sens"] = None
    reg["descritores"] = {**descritores(G, S), "NAO_DETERMINISTICO": nd, "MUDANCA_DE_IDENTIDADE": ident,
                          "PENDENTE": sorted(A.pendentes(ap) | A.pendentes(ac))}
    if ctx.modo in ("ensaio", "fixture") and par["p"] != par["c"]:      # §4.4: so antes do DOI
        reg["diferencial_parser"] = {lado: cbuild.diferencial_parser(A, a, S, reach)
                                     for lado, a in (("p", ap), ("c", ac))}
    return reg


def checa_nulo(reg: dict) -> None:
    """§5: par nulo exige EIS = AIS = vazio (B-ret fica fora: EIS = U por definicao)."""
    if reg["AIS"] or any(B is not None and B["EIS"] for b, B in reg["bracos"].items() if b != "B-ret"):
        defeito(f"par nulo {reg['p'][:12]} com EIS ou AIS nao vazio (§5)")


def checa_janela(ctx: Contexto, par: dict) -> None:
    p, c, ctrl = par["p"], par["c"], par["controle"]
    if ctx.modo == "fixture":
        return
    cp, cc = ctx.J.classe(p), ctx.J.classe(c)
    if ctx.modo == "ensaio":
        if cp != "ensaio" or cc != "ensaio":
            raise Recusa(2, f"ensaio: par ({c[:12]}, {p[:12]}) fora da janela de ensaio "
                            f"({cc}, {cp}); corrida inteira abortada (§0)")
    else:
        # EMENDA 3 (2026-10-04): o par e definido por c (§2.5: c do quadro, p o seu primeiro pai, de QUALQUER janela).
        # A guarda antiga exigia p em quadro/ensaio e abortava o zlib no 1o par (p = 10daf0d, fronteira "fora").
        # Nulo (p, p): exige que o c de onde veio ("de") seja do quadro.
        if ctrl == "nulo":
            ok = cc == cp and bool(par.get("de")) and ctx.J.classe(par["de"]) == "quadro"
        else:
            ok = cc == "quadro"
        if not ok:
            raise Recusa(2, f"confirmatorio: par ({c[:12]}, {p[:12]}) com janela ({cc}, {cp}) invalida")


def executar_par(ctx: Contexto, par: dict) -> dict:
    """Um par -> um registro (sem `h`). Nao escreve nada. Defeito de pipeline levanta Recusa 4."""
    checa_janela(ctx, par)
    p, c, ctrl = par["p"], par["c"], par["controle"]
    ap, ac = ctx.arvore(p), ctx.arvore(c)
    corp = par_tz if ctx.corpus == "tz" else par_c
    with tempfile.TemporaryDirectory(prefix="v_corre_") as td:
        tmp = Path(td)
        orc = None
        if ctx.modo != "ensaio":
            try:
                if ctrl == "nulo":
                    orc = nulo_do_par(ctx, par)
                else:
                    orc = oraculo_real(ctx, p, c, tmp / "orc")
                    ctx._ult = {"de": c, "orc": orc, "ne": None}
            except NaoExecutado as ne:
                if ctrl != "nulo":
                    ctx._ult = {"de": c, "orc": None, "ne": ne}
                return registro_nao_executado(ctx, par, ap, ac, ne)
        try:
            reg = corp(ctx, par, ap, ac, orc, tmp)
        except Recusa:
            raise
        except subprocess.TimeoutExpired as e:
            raise Recusa(4, f"tempo esgotado em {e.cmd[:3]} no par {c[:12]}") from None
        except Exception as e:                                    # defeito de adaptador/detector
            raise Recusa(4, f"{type(e).__name__} no par ({c[:12]}, {p[:12]}): {e}") from e
    if ctrl == "nulo":
        checa_nulo(reg)
    return reg


def nulo_do_par(ctx: Contexto, par: dict) -> dict:
    """Par nulo (p, p) pelo reuso de p1 e p2 do par principal (config.controles.nulo_oraculo): p vs p.
    AIS = vazio por definicao; elementos instaveis entre p1 e p2 vao para NAO_DETERMINISTICO.
    Se p nao construiu no principal, o nulo e NAO_EXECUTADO com a mesma causa."""
    u = ctx._ult
    if u is None or u.get("de") != par.get("de"):
        raise Recusa(4, f"par nulo de {str(par.get('de'))[:12]} sem o oraculo do principal em memoria")
    if u["orc"] is None:
        ne = u["ne"]
        if ne.man_p is None:
            raise NaoExecutado(ne.causa, ne.detalhe)
        orc = {"_man": ne.man_p, "dig": {k: _sha_bytes(v) for k, v in ne.man_p.items()}}
    else:
        orc = u["orc"]
    col = 2 if ctx.corpus == "tz" else 1

    def ler(b: bytes) -> dict[str, str]:
        out = {}
        for ln in b.decode("utf-8", "replace").splitlines():
            r = ln.split("\t")
            if len(r) > col and RE_HEX64.match(r[col]):
                out[r[0]] = r[col]
        return out
    m1, m2 = ler(orc["_man"]["p1"]), ler(orc["_man"]["p2"])
    comp = {n: ("IGUAL" if m1.get(n) == m2.get(n) else "NAO_DETERMINISTICO_p,NAO_DETERMINISTICO_c")
            for n in set(m1) | set(m2)}
    return {"comp": comp, "dig": {"p1": orc["dig"]["p1"], "p2": orc["dig"]["p2"],
                                  "c1": orc["dig"]["p1"], "c2": orc["dig"]["p2"]}}


def _sha_bytes(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()


# ============================================================ execucao da lista
def executar_lista(ctx: Contexto, lista: list[dict], cadeia: Cadeia | None, vistos: set,
                   limite: int | None = None, publicar=None, a_cada: int = 0) -> list[dict]:
    regs, t0, novos = [], time.time(), 0
    for i, par in enumerate(lista):
        chave = (par["p"], par["c"], par["controle"])
        if chave in vistos:
            continue
        if par["controle"] == "nulo" and ctx.modo != "ensaio" and (
                ctx._ult is None or ctx._ult.get("de") != par.get("de")):
            principal = next(d for d in lista if d["c"] == par["de"] and d["controle"] is None)
            executar_par(ctx, principal)                  # so para recuperar p1/p2 em memoria (retomada)
        reg = executar_par(ctx, par)
        regs.append(reg)
        if cadeia is not None:
            cadeia.anexar(reg)
        vistos.add(chave)
        novos += 1
        if (i + 1) % 25 == 0:
            print(f"[corre] {i + 1}/{len(lista)} {time.time() - t0:.0f}s", file=sys.stderr)
        if publicar and a_cada and novos % a_cada == 0:
            publicar(f"{ctx.corpus}: {novos} registros novos")
        if limite and novos >= limite:
            break
    return regs


# ============================================================ publicacao (CI)
def publicar_git(caminhos: list[Path], msg: str) -> None:
    """Commit e push dos JSONL pelo proprio runner (§3.5). So em GitHub Actions."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    g = lambda *a, ok=False: subprocess.run(["git", *a], capture_output=True, text=True, check=not ok,  # noqa: E731
                                            cwd=RAIZ)
    g("config", "user.name", "v-runner")
    g("config", "user.email", "v-runner@users.noreply.github.com")
    g("add", "--", *map(str, caminhos))
    if g("diff", "--cached", "--quiet", ok=True).returncode == 0:
        return
    g("commit", "-m", f"runner: {msg}")
    for _ in range(5):
        g("pull", "--rebase", "--autostash", ok=True)
        if g("push", ok=True).returncode == 0:
            return
        time.sleep(5)
    raise Recusa(5, "push do runner falhou apos 5 tentativas")


# ============================================================ CLI
def _ctx_de_args(a, cfg: dict, sha_cfg: str) -> Contexto:
    modo = a.modo
    repo = a.repo
    fixture = None
    if modo == "fixture":
        nomes = {"a6_tz": ("tz", FIXTURES / "a6_tz"), "a7_zlib": ("zlib", FIXTURES / "a7_c" / "zlib"),
                 "a7_lua": ("lua", FIXTURES / "a7_c" / "lua")}
        if a.fixture not in nomes:
            raise Recusa(2, f"fixture invalida: {a.fixture!r} (use {sorted(nomes)})")
        a.corpus, repo = nomes[a.fixture][0], str(nomes[a.fixture][1])
        fixture = a.fixture
    elif not repo:
        raise Recusa(2, "--repo e obrigatorio fora do modo fixture")
    semente = cfg["sementes"]["principal"] if modo == "confirmatorio" else (
        a.semente if a.semente is not None else cfg["sementes"].get("ensaio", 0))
    tz_bin = a.tz_bin or os.environ.get("V_TZ_BIN")
    if a.corpus == "tz" and modo != "ensaio" and not tz_bin:
        raise Recusa(2, "tz com oraculo real exige --tz-bin (zic/zdump de tz_ferramentas.sh)")
    return Contexto(modo, a.corpus, repo, cfg, sha_cfg, semente, a.q, tz_bin, fixture)


def lista_fixture(ctx: Contexto) -> list[dict]:
    d = Path(ctx.repo)
    if ctx.fixture == "a6_tz":
        base = [("p", "c")]
    else:
        vs = sorted((x.name for x in d.iterdir() if x.is_dir()), key=lambda n: int(n[1:]))
        base = list(zip(vs, vs[1:]))
    lista, vistos = [], set()
    for p, c in base:
        lista.append({"c": c, "p": p, "data_c": None, "janela": "fixture", "controle": None})
        if p not in vistos:
            vistos.add(p)
            lista.append({"c": p, "p": p, "data_c": None, "janela": "fixture", "controle": "nulo", "de": c})
    return lista


def cmd_rodar(a) -> int:
    cfg, sha_cfg = carregar_config(a.config)
    if a.modo == "confirmatorio":
        guarda_confirmatoria(a.config, RAIZ, a.tz_bin or os.environ.get("V_TZ_BIN"))     # recusa antes de tudo
    elif a.modo == "ensaio" and os.environ.get("V_MODO") == "confirmatorio":
        raise Recusa(2, "V_MODO=confirmatorio no ambiente de um ensaio")
    ctx = _ctx_de_args(a, cfg, sha_cfg)
    # arquivo de saida por modo (nunca fora das pastas previstas)
    if a.modo == "ensaio":
        saida = Path(a.saida) if a.saida else ENSAIO_DIR / f"{ctx.corpus}_corre.jsonl"
        if saida.resolve().parent != ENSAIO_DIR.resolve():
            raise Recusa(2, f"ensaio grava so em {ENSAIO_DIR}")
    elif a.modo == "fixture":
        saida = Path(a.saida) if a.saida else RAIZ / "saidas" / "fixtures" / f"corre_{ctx.fixture}.jsonl"
    else:
        saida = RAIZ / "saidas" / f"{ctx.corpus}.jsonl"
        c0 = cfg["corpora"][ctx.corpus]["congelamento"]
    parte = _parte(a)
    if parte and a.modo != "fixture":       # EMENDA 4: arquivo proprio por parte, cadeia propria
        saida = saida.with_name(f"{ctx.corpus}.parte-{parte[0]}-de-{parte[1]}.jsonl")
    if a.modo == "confirmatorio":
        if quadro.git(ctx.repo, "rev-parse", "--verify", "-q", f"{c0}^{{commit}}", ok=True) is False:
            raise Recusa(2, f"clone sem o commit de congelamento {c0[:12]}")
    cadeia = Cadeia(saida, sha_cfg, retomar=a.retomar)
    if a.modo == "fixture":
        lista = lista_fixture(ctx)
    else:
        lista = quadro.montar_lista(a.modo, ctx.corpus, ctx.repo, cfg,
                                    a.amostra if a.modo == "ensaio" else None)
        if parte:
            lista = filtra_parte(lista, *parte)
    vistos = {(r["p"], r["c"], r["controle"]) for r in cadeia.registros()}
    pub = (lambda m: publicar_git([saida], m)) if a.publicar_cada else None
    regs = executar_lista(ctx, lista, cadeia, vistos, a.limite if a.modo != "confirmatorio" else None,
                          pub, a.publicar_cada)
    if pub:
        publicar_git([saida], f"{ctx.corpus}: fim ({cadeia.n} registros)")
    cont = Counter()
    for r in regs:
        cont[f"controle:{r['controle']}"] += 1
        if r["nao_executado"]:
            cont[f"NAO_EXECUTADO:{r['nao_executado']['causa']}"] += 1
    print(json.dumps({"modo": a.modo, "corpus": ctx.corpus, "saida": str(saida), "linhas": cadeia.n,
                      "novos": len(regs), **dict(sorted(cont.items())),
                      **({"ENSAIO": True} if a.modo == "ensaio" else {})}, ensure_ascii=False))
    return 0


# ============================================================ EMENDA 4: partes (so engenharia de execucao)
def _parte(a) -> tuple[int, int] | None:
    """--parte K/N -> (K, N), 0 <= K < N. Sem a opcao: None (execucao inteira, como antes)."""
    v = getattr(a, "parte", None)
    if not v:
        return None
    m = re.fullmatch(r"(\d+)/(\d+)", v)
    if not m or not 0 <= int(m.group(1)) < int(m.group(2)):
        raise Recusa(2, f"--parte invalida: {v!r} (esperado K/N com 0 <= K < N)")
    return int(m.group(1)), int(m.group(2))


def grupos_da_lista(lista: list[dict]) -> list[list[dict]]:
    """Cada par nulo fica no grupo do par principal logo antes dele (montar_lista o poe ali, e o nulo reusa as
    execucoes p1/p2 desse principal). Placebo e tag sao grupos de um par."""
    grupos: list[list[dict]] = []
    for d in lista:
        if d.get("controle") == "nulo" and grupos:
            grupos[-1].append(d)
        else:
            grupos.append([d])
    return grupos


def filtra_parte(lista: list[dict], k: int, n: int) -> list[dict]:
    """Os grupos de indice i com i % n == k, na ordem da lista. Nenhum par muda; so quem o executa."""
    return [d for i, g in enumerate(grupos_da_lista(lista)) if i % n == k for d in g]


def cmd_juntar(a) -> int:
    """Junta as N partes de um corpus num unico <corpus>.jsonl, na ORDEM da lista do protocolo, com cadeia nova a
    partir do sha256 do config. Cada parte tem a cadeia conferida inteira; todo par da lista tem de aparecer
    exatamente uma vez; o corpo de cada registro (sem `h`) e copiado byte a byte. Recusa 3 se faltar ou sobrar par."""
    cfg, sha_cfg = carregar_config(a.config)
    if a.modo == "confirmatorio":
        guarda_confirmatoria(a.config, RAIZ, a.tz_bin or os.environ.get("V_TZ_BIN"))
    ctx = _ctx_de_args(a, cfg, sha_cfg)
    base = (ENSAIO_DIR / f"{ctx.corpus}_corre.jsonl") if a.modo == "ensaio" else RAIZ / "saidas" / f"{ctx.corpus}.jsonl"
    regs: dict = {}
    for k in range(a.partes):
        arq = base.with_name(f"{ctx.corpus}.parte-{k}-de-{a.partes}.jsonl")
        if not arq.exists():
            raise Recusa(3, f"parte ausente: {arq.name}")
        verificar_cadeia(arq, sha_cfg)
        for L in arq.read_bytes().split(b"\n"):
            if not L:
                continue
            r = json.loads(L)
            x = (r["p"], r["c"], r["controle"])
            if x in regs:
                raise Recusa(3, f"par repetido entre partes: {x}")
            regs[x] = {k_: v for k_, v in r.items() if k_ != "h"}
    lista = quadro.montar_lista(a.modo, ctx.corpus, ctx.repo, cfg, a.amostra if a.modo == "ensaio" else None)
    chaves = [(d["p"], d["c"], d["controle"]) for d in lista]
    faltam, sobram = [x for x in chaves if x not in regs], set(regs) - set(chaves)
    if faltam or sobram:
        raise Recusa(3, f"juntar: faltam {len(faltam)} e sobram {len(sobram)} pares (ex.: {(faltam or list(sobram))[:2]})")
    cadeia = Cadeia(base, sha_cfg, retomar=False)
    for x in chaves:
        cadeia.anexar(regs[x])
    if a.publicar:
        publicar_git([base], f"{ctx.corpus}: juntado de {a.partes} partes ({cadeia.n} registros)")
    print(json.dumps({"corpus": ctx.corpus, "partes": a.partes, "registros": cadeia.n, "saida": str(base)}))
    return 0


def cmd_portao(a) -> int:
    cfg, sha = guarda_confirmatoria(a.config, RAIZ, a.tz_bin or os.environ.get("V_TZ_BIN"))
    print(f"portao aberto: doi={cfg['doi']} sha_config={sha}")
    return 0


def cmd_pares(a) -> int:
    """Lista de pares (so enumeracao git). A lista confirmatoria exige a semente do deposito."""
    try:
        return quadro.main(["pares", a.corpus, a.repo, "--modo", a.modo] + (["--saida", a.saida] if a.saida else []))
    except ValueError as e:
        raise Recusa(2, str(e)) from None


def cmd_reexecutar(a) -> int:
    """§3.5: reexecuta 10% dos registros (semente do §2.5) e compara byte a byte (sem `h`)."""
    cfg, sha_cfg = carregar_config(a.config)
    if a.modo == "confirmatorio":
        guarda_confirmatoria(a.config, RAIZ, a.tz_bin or os.environ.get("V_TZ_BIN"))
    ctx = _ctx_de_args(a, cfg, sha_cfg)
    orig = Path(a.original)
    verificar_cadeia(orig, sha_cfg)
    regs = [json.loads(L) for L in orig.read_bytes().split(b"\n") if L]
    chave = lambda r: (r["p"], r["c"], r["controle"])  # noqa: E731
    pop = sorted(regs, key=lambda r: (r["c"], r["p"], str(r["controle"])))
    k = max(1, math.ceil(cfg["controles"]["reexecucao_fracao"] * len(pop))) if pop else 0
    import random
    base = cfg["sementes"]["principal"] if a.modo == "confirmatorio" else cfg["sementes"].get("ensaio", 0)
    esc = random.Random(f"{base}:reexec_10pct").sample(range(len(pop)), min(k, len(pop)))
    alvo = {chave(pop[i]) for i in esc}
    por_chave = {chave(r): r for r in regs}
    if a.modo == "fixture":
        lista = lista_fixture(ctx)
    else:
        lista = quadro.montar_lista(a.modo, ctx.corpus, ctx.repo, cfg,
                                    a.amostra if a.modo == "ensaio" else None)
    # o nulo selecionado exige o principal logo antes dele na lista
    idx = {(d["p"], d["c"], d["controle"]): i for i, d in enumerate(lista)}
    ordem = sorted({i for x in alvo if x in idx for i in ([idx[x]] + ([idx[x] - 1] if x[2] == "nulo" else []))})
    sub = [lista[i] for i in ordem]
    parte = _parte(a)
    if parte:   # EMENDA 4: a MESMA amostra de 10%, dividida em grupos (nulo junto do seu principal)
        sub = filtra_parte(sub, *parte)
        alvo = {x for x in alvo if x in {(d["p"], d["c"], d["controle"]) for d in sub}}
    novos = executar_lista(ctx, sub, None, set())
    novos_por = {chave(r): r for r in novos}
    dif, ok = [], 0
    for x in sorted(alvo, key=str):
        a_, b_ = por_chave.get(x), novos_por.get(x)
        if a_ is None or b_ is None:
            dif.append({"par": list(x), "motivo": "ausente"})
            continue
        ca, cb = canonico({k_: v for k_, v in a_.items() if k_ != "h"}), canonico(b_)
        if ca == cb:
            ok += 1
        else:
            dif.append({"par": list(x), "motivo": "bytes diferentes"})
    rel = {"corpus": ctx.corpus, "modo": a.modo, "parte": a.parte if getattr(a, "parte", None) else None,
           "populacao": len(pop), "amostra": len(alvo), "iguais": ok,
           "diferentes": dif, "maquina": os.environ.get("RUNNER_NAME", "local")}
    destino = Path(a.relatorio) if a.relatorio else RAIZ / "saidas" / f"reexec_{ctx.corpus}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(rel, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(rel, ensure_ascii=False))
    return 0 if not dif else 4


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")

    def comum(p):
        p.add_argument("--modo", choices=["fixture", "ensaio", "confirmatorio"], required=True)
        p.add_argument("--corpus", choices=["tz", "zlib", "lua"])
        p.add_argument("--fixture", choices=["a6_tz", "a7_zlib", "a7_lua"])
        p.add_argument("--repo")
        p.add_argument("--config", default=str(CONFIG))
        p.add_argument("--tz-bin")
        p.add_argument("--amostra", type=int)
        p.add_argument("--semente", type=int)
        p.add_argument("--q", type=float, default=0.1)
    r = sub.add_parser("rodar")
    comum(r)
    r.add_argument("--saida")
    r.add_argument("--retomar", action="store_true")
    r.add_argument("--limite", type=int)
    r.add_argument("--publicar-cada", type=int, default=0)
    r.add_argument("--parte", help="K/N (EMENDA 4): so os grupos i com i %% N == K, em arquivo proprio")
    j = sub.add_parser("juntar")
    comum(j)
    j.add_argument("--partes", type=int, required=True)
    j.add_argument("--publicar", action="store_true")
    x = sub.add_parser("reexecutar")
    comum(x)
    x.add_argument("--original", required=True)
    x.add_argument("--relatorio")
    x.add_argument("--parte", help="K/N (EMENDA 4): so os grupos i com i %% N == K da amostra de 10%%")
    s = sub.add_parser("portao")
    s.add_argument("--config", default=str(CONFIG))
    s.add_argument("--tz-bin")
    p = sub.add_parser("pares")
    p.add_argument("corpus", choices=["tz", "zlib", "lua"])
    p.add_argument("repo")
    p.add_argument("--modo", choices=["ensaio", "confirmatorio"], default="confirmatorio")
    p.add_argument("--saida")
    p.add_argument("--config", default=str(CONFIG))
    return ap


def main(argv: list[str] | None = None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    if a and a[0].startswith("--modo"):
        a = ["rodar", *a]
    args = parser().parse_args(a)
    try:
        return {"rodar": cmd_rodar, "portao": cmd_portao, "pares": cmd_pares,
                "reexecutar": cmd_reexecutar, "juntar": cmd_juntar}.get(args.cmd, lambda _: (parser().print_help(), 2)[1])(args)
    except Recusa as e:
        return e.codigo


if __name__ == "__main__":
    sys.exit(main())
