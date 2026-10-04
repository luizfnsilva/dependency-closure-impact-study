"""Gancho d4-ingenuo do tz (PROTOCOLO_V_2026-10-02 §4.4 d4, §5; braco de teste da H4).

Poda a aresta R->Z quando TODA linha alterada de R (multiconjunto p (-) c e
c (-) p, com [FROM, TO]) e disjunta de TODO intervalo de uso de R por Z
([ano do UNTIL da linha anterior, ano do UNTIL da linha]). E o predicado do
detector T1a (PARTILHADO, §4.5), escrito aqui de novo: ganchos nao importam
detectores. Nao chama o fecho.

Previsao escrita (H4, §7): este gancho cria FN, porque a Rule anterior ao inicio
da linha de Zone fixa o deslocamento inicial e a abreviatura
(tz@bec4d95a:zic.c:3656-3665; zic.8:693-702).

Leitura declarada: R sem nenhuma linha Rule alterada (so comentario mudou) nao e
podada; o predicado exige >= 1 linha alterada (igual ao detector).

dados = {"intervalos": {(R, Z): [(ini, fim)]}, "alteradas": {R: [(lado, FROM, TO)]}}
(porta d4 do adaptador; intervalos de p e de c).
"""
from __future__ import annotations


def podavel(alteradas: list, intervalos: list) -> bool:
    return bool(alteradas) and bool(intervalos) and all(
        ate < ini or de > fim for (_, de, ate) in alteradas for (ini, fim) in intervalos)


def aplicar(G, S: dict, dados: dict):
    G2 = G.copy()
    for R in S:
        if R not in G2 or not R.startswith("R:"):
            continue
        alt = dados["alteradas"].get(R, [])
        for Z in list(G2.successors(R)):
            if podavel(alt, dados["intervalos"].get((R, Z), [])):
                G2.remove_edge(R, Z)
    return G2, dict(S)
