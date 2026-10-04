"""Gancho d6 em C: entradas globais fora do grafo (PROTOCOLO_V_2026-10-02 §4.3 d6, §4.4, §5).

Acrescenta a aresta g -> o de cada entrada global declarada g (porta d6_globais do
adaptador, lados p e c; zlib: configure, Makefile.in, zconf.h.in) para todo objeto o.
Semente inalterada. Lista do autor conferida contra a documentacao do projeto: PARCIAL (§4.5).
Nao importa detectores nem chama o fecho.

dados = {"globais": set[str], "objetos": iterable[str] (nos objeto: U do par)}
"""
from __future__ import annotations


def aplicar(G, S: dict, dados: dict):
    H = G.copy()
    for g in sorted(dados["globais"]):
        for o in sorted(dados["objetos"]):
            H.add_edge(g, o, origem="d6")
    return H, dict(S)
