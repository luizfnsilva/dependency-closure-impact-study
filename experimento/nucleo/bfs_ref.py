"""BFS iterativa de referencia (PROTOCOLO_V_2026-10-02 §4.1), so biblioteca padrao.

adj[u] = conjunto dos v com aresta u -> v ("v consome u"). Devolve S mais todo
no alcancavel a partir de S. Semente ausente de adj contribui so ela mesma.
Roda ao lado de networkx em todo par e todo braco; divergencia aborta (§4.1).
Limite do protocolo: este arquivo tem <= 40 linhas.
"""
from collections import deque
from collections.abc import Iterable


def bfs_ref(adj: dict[str, set[str]], S: Iterable[str]) -> frozenset[str]:
    vistos = set(S)
    fila = deque(vistos)
    while fila:
        u = fila.popleft()
        for v in adj.get(u, ()):
            if v not in vistos:
                vistos.add(v)
                fila.append(v)
    return frozenset(vistos)
