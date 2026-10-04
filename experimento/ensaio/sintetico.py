"""Oraculo SINTETICO da janela de ensaio (PROTOCOLO_V_2026-10-02 §11.3; INTERFACES §2.5).

AIS sorteado por Bernoulli(q) sobre o universo REAL U do par, com
random.Random(f"{semente}:{p}:{c}"). So o oraculo e trocado; o resto do pipeline roda igual.
Nunca e resultado. Para o par nulo (p, p) o oraculo sintetico devolve vazio (builds identicos).
"""
from __future__ import annotations

import random


def ais_sintetico(U, semente, p, c, q: float = 0.1) -> set[str]:
    if p == c:
        return set()
    r = random.Random(f"{semente}:{p}:{c}")
    return {e for e in sorted(U) if r.random() < q}
