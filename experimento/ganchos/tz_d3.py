"""Gancho d3 do tz: checksum insensivel a anotacao (PROTOCOLO_V_2026-10-02 §4.3 d3, §5).

Tira da semente o no cujo checksum d3 (porta d3 do adaptador tz: lexico de
zic(8), tz@bec4d95a:zic.8:336-345) e igual nos dois lados. Grafo inalterado.
Nao importa detectores (§4.5) nem chama o fecho (INTERFACES §2.4).

dados = {"ap": arvore p, "ac": arvore c, "d3_checksum": callable(no, arvore) -> str}
"""
from __future__ import annotations


def aplicar(G, S: dict, dados: dict):
    ck, ap, ac = dados["d3_checksum"], dados["ap"], dados["ac"]
    return G, {n: e for n, e in S.items() if ck(n, ap) != ck(n, ac)}
