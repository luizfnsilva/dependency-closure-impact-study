"""Gancho d2-extraido em C (PROTOCOLO_V_2026-10-02 §4.4, §4.5 T3, §5 braco A0+d2-extraido).

Troca as arestas de conteudo de G_decl (origem "declarada", banco de make -p -n) pelas de
G_obs (origem "extraida", gcc -MM dos dois lados; G_obs ja traz as de configuracao) e mantem
as de configuracao ("config") e as de outros ganchos ("d6"); logo reach(G', S) contem
reach(G_obs, S). Semente inalterada. PARTILHADO com o detector de T3 (mesma ferramenta,
gcc -MM; declarado no §4.5). Nao importa detectores nem chama o fecho.

dados = {"G_obs": nx.DiGraph (porta d2_extraido, G_p uniao G_c)}
"""
from __future__ import annotations


def aplicar(G, S: dict, dados: dict):
    H = G.copy()
    H.remove_edges_from([(u, v) for u, v, d in G.edges(data=True)
                         if d.get("origem") == "declarada"])
    H.add_nodes_from(dados["G_obs"].nodes)
    for u, v, d in dados["G_obs"].edges(data=True):   # extraidas e config (G_obs inteiro)
        if not H.has_edge(u, v):
            H.add_edge(u, v, origem=d.get("origem", "extraida"))
    return H, dict(S)
