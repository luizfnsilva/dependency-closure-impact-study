"""Gancho d3 em C: checksum insensivel a anotacao (PROTOCOLO_V_2026-10-02 §4.3 d3, §4.5, §5).

Tira da semente o no cujo checksum d3 (porta d3 do adaptador C: tokens do lexer C do
pygments sem comentario e sem espaco; Gligoric et al. 2015, ccache modo pre-processador) e
igual nos dois lados. No ausente de um lado (A, D, R) tem checksum None e fica. Grafo
inalterado. Nao importa detectores (§4.5) nem chama o fecho (INTERFACES §2.4).

dados = {"ap": arvore p, "ac": arvore c, "d3_checksum": callable(no, arvore) -> str | None}
"""
from __future__ import annotations


def aplicar(G, S: dict, dados: dict):
    ck, ap, ac = dados["d3_checksum"], dados["ap"], dados["ac"]
    fica = {}
    for n, e in S.items():
        kp, kc = ck(n, ap), ck(n, ac)
        if kp is None or kc is None or kp != kc:
            fica[n] = e
    return G, fica
