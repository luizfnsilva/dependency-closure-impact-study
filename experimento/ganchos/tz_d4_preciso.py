"""Gancho d4-preciso do tz (PROTOCOLO_V_2026-10-02 §5, braco A0+d4-preciso; usado no A_full).

Poda a aresta R->Z so se o FROM de TODAS as linhas alteradas de R (lados p e c)
for > ano do UNTIL + 1 em TODO intervalo de uso de R por Z. Em particular:
  - nunca poda Rule anterior ao inicio da linha de Zone: a regra em vigor antes do
    inicio fixa o deslocamento inicial e a abreviatura
    (tz@bec4d95a:zic.c:3656-3665; zic.8:693-702);
  - nunca poda Rule no ano do UNTIL nem no seguinte (PROTOCOLO_V §5;
    tz@bec4d95a:zic.c:3645-3653: a regra que cai no UNTIL ou depois dele ainda e
    lida para a abreviatura de partida).
Intervalo sem UNTIL (fim = +inf) nunca e podado. Predicado diferente do detector
T1a: INDEPENDENTE (§4.5). Nao importa detectores; nao chama o fecho.

Leitura declarada: R sem nenhuma linha Rule alterada nao e podada.

dados = {"intervalos": {(R, Z): [(ini, fim)]}, "alteradas": {R: [(lado, FROM, TO)]}}
"""
from __future__ import annotations


def _par_podavel(de: float, ate: float, ini: float, fim: float) -> bool:
    # Com FROM <= TO (o zic recusa o contrario, zic.8:389-406), "de > fim + 1" ja implica
    # "ate >= de > fim >= ini": a Rule anterior ao inicio da linha (zic.c:3656-3665) nunca
    # e podada. A guarda explicita abaixo so age em dado malformado (TO < FROM, hipotetico)
    # e e testada com um par assim em adaptadores/test_tz.py.
    if ate < ini:
        return False
    return de > fim + 1      # so FROM > UNTIL + 1 (zic.c:3645-3653 cobre UNTIL e o ano seguinte)


def podavel(alteradas: list, intervalos: list) -> bool:
    return bool(alteradas) and bool(intervalos) and all(
        _par_podavel(de, ate, ini, fim) for (_, de, ate) in alteradas for (ini, fim) in intervalos)


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
