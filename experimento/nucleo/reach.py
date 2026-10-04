"""Fecho por alcance (PROTOCOLO_V_2026-10-02 §4.1), identico em todo corpus e braco.

Convencao de aresta: u -> v significa "v consome u".

    reach(G, S) = S  uniao  U_{s em S} networkx.descendants(G, s)

Semente fora de V(G) contribui so ela mesma; grafo sem nos devolve S (nunca
"nada impactado", §4.1). O nucleo nao emite rotulo de situacao: ciclo e grafo
sem arestas sao descritores contados (§4.7), devolvidos por `descritores`.

`reach_diferencial` roda networkx e a BFS de referencia (bfs_ref.py) e levanta
DivergenciaNucleo se discordarem; o runner usa essa funcao em todo par e todo
braco, e a excecao aborta a corrida inteira (§4.1, §8).

Sem import de adaptadores, detectores ou ganchos (§4.3; INTERFACES §2.1).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable

import networkx as nx

from .bfs_ref import bfs_ref


class DivergenciaNucleo(RuntimeError):
    """networkx e bfs_ref discordam; a corrida inteira aborta (§4.1)."""


def _semente(S: Iterable[str]) -> frozenset[str]:
    """Materializa S. str/bytes seriam decompostos em caracteres/inteiros sem erro: rejeitados."""
    if isinstance(S, (str, bytes)):
        raise TypeError("S deve ser colecao de nos, nao str/bytes")
    return frozenset(S)


def _reach_nx(G: nx.DiGraph, S: frozenset[str]) -> frozenset[str]:
    alcance = set(S)
    for s in S:
        if s in G:
            alcance |= nx.descendants(G, s)
    return frozenset(alcance)


def adjacencia(G: nx.DiGraph) -> dict[str, set[str]]:
    """Lista de adjacencia de saida, para a BFS de referencia."""
    adj: dict[str, set[str]] = {u: set() for u in G.nodes}
    for u, v in G.edges():
        adj[u].add(v)
    return adj


def reach(G: nx.DiGraph, S: Iterable[str]) -> frozenset[str]:
    """Fecho por alcance, SEMPRE diferencial (§4.1): networkx e bfs_ref rodam em toda chamada e
    divergencia levanta DivergenciaNucleo. S pode ser dict (usa as chaves). Unico ponto de
    entrada do fecho; `nx.descendants` fora deste arquivo e proibido (teste de AST)."""
    sementes = _semente(S)  # materializa: um gerador seria esgotado pela 1a implementacao
    r_nx = _reach_nx(G, sementes)
    r_bfs = bfs_ref(adjacencia(G), sementes)
    if r_nx != r_bfs:
        so_nx = sorted(r_nx - r_bfs)[:20]
        so_bfs = sorted(r_bfs - r_nx)[:20]
        raise DivergenciaNucleo(
            f"networkx x bfs_ref: |so_nx|={len(r_nx - r_bfs)} {so_nx}; "
            f"|so_bfs|={len(r_bfs - r_nx)} {so_bfs}"
        )
    return r_nx


reach_diferencial = reach  # nome explicito do §4.1; mesma funcao


def eis(G: nx.DiGraph, S: Iterable[str], U: Iterable[str],
        elemento: Callable[[str], str | None]) -> frozenset[str]:
    """EIS = U intersecao d1(reach(G, S)) (§4.1). `elemento` e o mapa d1 no -> elemento|None,
    recebido como funcao para que o nucleo nao importe o adaptador."""
    universo = _semente(U)
    mapeados = {elemento(n) for n in reach_diferencial(G, S)}
    return frozenset(e for e in mapeados if e is not None and e in universo)


def descritores(G: nx.DiGraph, S: Iterable[str] = ()) -> dict:
    """Descritores de grafo do §4.7, so contados.

    CICLO: componentes fortemente conexos com mais de um no (pela letra do §4.7,
    autolaco isolado nao entra), cada um como lista ordenada, e a lista ordenada.
    AUTOLACO: nos com aresta u->u, contados a parte (nao sao CICLO pela letra do §4.7).
    GRAFO_VAZIO: |E| = 0 (INTERFACES §2.1; Emenda 1).
    Calculados sobre o grafo inteiro do par (G = G_p uniao G_c); S faz parte da
    assinatura fixada em INTERFACES §2.1 e nao altera o resultado.
    """
    ciclos = sorted(sorted(c) for c in nx.strongly_connected_components(G) if len(c) > 1)
    return {"CICLO": ciclos, "AUTOLACO": sorted(n for n in G.nodes if G.has_edge(n, n)),
            "GRAFO_VAZIO": G.number_of_edges() == 0}


def pendentes(G: nx.DiGraph, definidos: Iterable[str]) -> list[str]:
    """PENDENTE (§4.1, §4.7): nos de G referenciados e sem definicao em `definidos`. No pipeline,
    `definidos` vem do adaptador (d1_nos); o runner grava o resultado de adaptador.pendentes(a)."""
    return sorted(set(G.nodes) - _semente(definidos))
