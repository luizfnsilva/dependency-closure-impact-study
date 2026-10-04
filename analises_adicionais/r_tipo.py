"""EXPLORATÓRIA, PÓS-DADOS (DESVIO 6, 2026-10-04). Família R_tipo da H7 (PROTOCOLO_V §7), escrita depois de ver as
saídas porque o módulo `ganchos/r_tipo.py` nunca foi implementado. Implementa EXATAMENTE a família do protocolo:

  tipos de nó: tz {Rule, Zone, Link}; C {fonte, cabecalho, cabecalho_gerado, configuracao, objeto}
  estado do diff de um nó da semente: {M, A, D, R}
  poda   rho = (tipo origem, tipo destino, estado): a mudança de estado `estado` num nó da semente do tipo origem
               NÃO propaga aos nós do tipo destino (as arestas u->v com tipo(u)=origem, tipo(v)=destino, S[u]=estado
               saem do grafo);
  aditiva alfa = (tipo origem -> todos do tipo destino): todo nó da semente do tipo origem ganha aresta para todo nó
               do grafo do tipo destino.

Busca exaustiva de regras ISOLADAS (uma por vez). Interface igual à esperada por `corre.r_tipo_efeitos`:
regras(tipos) -> lista de chaves `rho:<orig>><dest>:<estado>` e `alfa:<orig>><dest>`; aplicar_regra(G, S, regra,
d1tipo) -> (G2, S2). Não lê conteúdo de arquivo: só tipo e estado (é o que torna a regra "tipada", §7 H7).
"""
from __future__ import annotations

ESTADOS = ("M", "A", "D", "R")


def regras(tipos) -> list[str]:
    out = []
    for o in tipos:
        for d in tipos:
            for st in ESTADOS:
                out.append(f"rho:{o}>{d}:{st}")
            out.append(f"alfa:{o}>{d}")
    return out


def aplicar_regra(G, S: dict, regra: str, d1tipo):
    G2 = G.copy()
    tipo, corpo = regra.split(":", 1)
    if tipo == "rho":
        par, st = corpo.rsplit(":", 1)
        o, d = par.split(">")
        corta = [(u, v) for u, v in G2.edges() if S.get(u) == st and d1tipo(u) == o and d1tipo(v) == d]
        G2.remove_edges_from(corta)
    elif tipo == "alfa":
        o, d = corpo.split(">")
        destinos = [v for v in G2.nodes() if d1tipo(v) == d]
        for u in [u for u in S if d1tipo(u) == o]:
            for v in destinos:
                if u != v:
                    G2.add_edge(u, v)
    else:
        raise ValueError(regra)
    return G2, S
