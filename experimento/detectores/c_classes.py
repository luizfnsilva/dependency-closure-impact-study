"""Detectores das classes T2, T3 (T3m zlib / T3g Lua), T4 e T5 em C (PROTOCOLO_V_2026-10-02
§4.5, §4.6, §5).

Modulo separado, congelado antes dos ganchos (§4.5); nao importa ganchos, adaptadores nem o
nucleo de fecho. Alimentado pelo runner com `ctx` (INTERFACES §2.3):
    ctx["G"]      G_decl do braco A0 (G_p uniao G_c), aresta u->v = "v consome u", atributo
                  origem em {declarada, config}
    ctx["reach"]  nucleo.reach (diferencial; injetado pelo runner, o detector nao importa o nucleo)
    ctx["G_obs"]  G_obs (gcc -MM dos dois lados, uniao; origem "extraida") MAIS as arestas
                  de configuracao de G_decl (§4.4; origem "config", as mesmas nos dois grafos,
                  logo nunca criam caminho so de um lado: nao contam para T3)
    ctx["S"]      semente {no: M|A|D|R}
    ctx["nos_p"]  {no: bytes} do lado p (porta d1); ctx["nos_c"] idem, lado c
    ctx["tipo"]   porta d1_tipo do adaptador (no -> fonte|cabecalho|cabecalho_gerado|
                  configuracao|objeto|outro)
Elemento = no objeto (x.o).

Regras (§4.5), lidas assim (declarado):
- T2 (FP): toda semente que alcanca o elemento em G tem saida igual nos dois lados por
  `gcc -x c -fpreprocessed -dD -E -P` (o lexer do proprio compilador: tira comentario, nao
  expande macro nem inclui). So semente C (fonte/cabecalho/cabecalho_gerado) presente nos dois
  lados pode ser so-anotacao. INDEPENDENTE do gancho d3 (pygments).
- T3-FN: o caminho semente -> o existe em G_obs e nao em G_decl; para o em FN (o fora de
  reach(G_decl, S)) isso e: o em reach(G_obs, S).
- T3-FP: o caminho existe so em G_decl, restrito a arestas fonte/cabecalho: o em
  reach(G_decl sem arestas config, S) e o fora de reach(G_obs, S) (G_obs com config). Leitura
  por conjunto, a mesma do criterio NC do §5 (reach(G_decl,S) = reach(G_obs ∪ config,S)).
- T4 (FN): a semente contem arquivo fora de V(G_decl) e o fora de reach(G_obs, S).
- T5 (FP): FP sem T1a, T2 nem T3-FP. INCLASSIFICADO-FN: FN sem T1b, T3-FN nem T4.
T1a e T1b nao se aplicam a C (§4.5).
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import networkx as nx

_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TZ": "UTC"}
_TIPOS_C = ("fonte", "cabecalho", "cabecalho_gerado")
_CACHE: dict[bytes, bytes | None] = {}


def sem_comentario(conteudo: bytes) -> bytes | None:
    """Saida de gcc -x c -fpreprocessed -dD -E -P (gcc 13 manual §3.13); None se o gcc falha."""
    if conteudo not in _CACHE:
        if len(_CACHE) >= 512:
            _CACHE.clear()
        with tempfile.TemporaryDirectory(prefix="v_det_c_") as d:
            arq = os.path.join(d, "entrada")
            with open(arq, "wb") as f:
                f.write(conteudo)
            p = subprocess.run(["gcc", "-x", "c", "-fpreprocessed", "-dD", "-E", "-P", arq],
                               cwd=d, env=_ENV, capture_output=True, timeout=300)
            _CACHE[conteudo] = p.stdout if p.returncode == 0 else None
    return _CACHE[conteudo]


def so_anotacao(s: str, ctx: dict) -> bool:
    """A semente s muda so comentario (T2): C, nos dois lados, saidas iguais e validas."""
    bp, bc = ctx["nos_p"].get(s), ctx["nos_c"].get(s)
    if ctx["tipo"](s) not in _TIPOS_C or bp is None or bc is None:
        return False
    sp = sem_comentario(bp)
    return sp is not None and sp == sem_comentario(bc)


def _alcance(G: nx.DiGraph, S, reach) -> set[str]:
    """Fecho vem do nucleo (ctx["reach"], diferencial, §4.1); o detector nao o reimplementa."""
    return set(reach(G, S))


def _so_conteudo(G: nx.DiGraph) -> nx.DiGraph:
    H = nx.DiGraph()
    H.add_nodes_from(G)
    H.add_edges_from((u, v) for u, v, d in G.edges(data=True) if d.get("origem") != "config")
    return H


def t2(o: str, ctx: dict) -> bool:
    G = ctx["G"]
    anc = nx.ancestors(G, o) | {o} if o in G else {o}
    origem = [s for s in ctx["S"] if s in anc]
    return bool(origem) and all(so_anotacao(s, ctx) for s in origem)


def rotular_c(inst: list[tuple[str, str]], ctx: dict) -> dict[str, list[str]]:
    """elemento -> multirrotulo (§4.6 a), so do braco A0."""
    S = list(ctx["S"])
    r_obs = _alcance(ctx["G_obs"], S, ctx["reach"])
    r_decl_cont = _alcance(_so_conteudo(ctx["G"]), S, ctx["reach"])
    fora = any(s not in ctx["G"] for s in S)
    out: dict[str, list[str]] = {}
    for o, lado in inst:
        rot: list[str] = []
        if lado == "FN":
            if fora and o not in r_obs:
                rot.append("T4")
            if o in r_obs:
                rot.append("T3-FN")
            out[o] = rot or ["INCLASSIFICADO-FN"]
        else:
            if o in r_decl_cont and o not in r_obs:
                rot.append("T3-FP")
            if t2(o, ctx):
                rot.append("T2")
            out[o] = rot or ["T5"]
    return out


def nc_c(ctx: dict) -> bool:
    """Par NC (§5): nenhuma semente so-anotacao; reach(G_decl,S) = reach(G_obs ∪ config,S);
    S contido em V(G_decl)."""
    S = list(ctx["S"])
    if any(so_anotacao(s, ctx) for s in S):
        return False
    if _alcance(ctx["G"], S, ctx["reach"]) != _alcance(ctx["G_obs"], S, ctx["reach"]):
        return False
    return all(s in ctx["G"] for s in S)
