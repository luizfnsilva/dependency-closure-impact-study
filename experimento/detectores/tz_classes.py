"""Detectores das classes T1a e T2 no tz (PROTOCOLO_V_2026-10-02 §4.5, §4.6, §5).

Modulo separado, congelado antes dos ganchos (§4.5); nao importa ganchos nem o
nucleo de fecho. Alimentado pelo runner com `ctx` (INTERFACES §2.3):
    ctx["G"]          grafo do braco A0 (G_p uniao G_c), aresta u->v = "v consome u"
    ctx["S"]          semente {no: M|A|D|R}
    ctx["nos_p"]      {no: bytes atribuidos} do lado p (porta d1 do adaptador)
    ctx["nos_c"]      idem, lado c
    ctx["intervalos"] {(R, Z): [(ini, fim)]} de p e c (porta d4 do adaptador)
    ctx["alteradas"]  {R: [(lado, FROM, TO)]} (porta d4 do adaptador)
Nos do tz: R:<NOME>, Z:<nome>, L:<nome>, F:<arquivo> (INTERFACES §1).

T2 usa um lexico proprio deste modulo, escrito a partir de zic(8) (tz@bec4d95a:
zic.8:336-345): mesmo predicado do gancho d3 do tz, logo PARTILHADO (§4.5).
T1a usa o predicado de disjuncao do §4.5 = o do gancho d4-ingenuo (PARTILHADO);
o d4-preciso usa outro predicado (INDEPENDENTE).

Decisao de leitura (declarada): uma Rule da semente sem nenhuma LINHA Rule
alterada (so comentario/linha branca mudou) nao e "disjunta": o predicado exige
>= 1 linha alterada; sem ela, nao ha ano a comparar.
"""
from __future__ import annotations

import networkx as nx

_BRANCO = frozenset(b" \t\n\r\f\v")     # zic.8:338-339
_SUSTENIDO, _ASPAS = ord("#"), ord('"')  # zic.8:341-344


def _tokens(linha: bytes) -> tuple[bytes, ...]:
    """Campos de uma linha: comentario = '#' fora de aspas ate o fim; espaco separa;
    aspas agrupam e somem (zic.8:336-345). Aspas impares: a linha crua."""
    toks: list[bytes] = []
    atual, em_aspas, aberto = bytearray(), False, False
    for b in linha:
        if em_aspas:
            if b == _ASPAS:
                em_aspas = False
            else:
                atual.append(b)
        elif b == _ASPAS:
            em_aspas = aberto = True
        elif b == _SUSTENIDO:
            break
        elif b in _BRANCO:
            if aberto:
                toks.append(bytes(atual))
                atual, aberto = bytearray(), False
        else:
            atual.append(b)
            aberto = True
    if em_aspas:
        return (linha,)
    if aberto:
        toks.append(bytes(atual))
    return tuple(toks)


def sem_anotacao(conteudo: bytes) -> tuple[tuple[bytes, ...], ...]:
    """Conteudo de um no sem comentario, sem espaco e sem linha branca."""
    return tuple(t for t in map(_tokens, conteudo.split(b"\n")) if t)


def _origem(z: str, ctx: dict) -> tuple[set[str], list[str]]:
    """Nos que alcancam o elemento z em G (com os nos de z) e as sementes entre eles."""
    G = ctx["G"]
    nos = [n for n in ("Z:" + z, "L:" + z) if n in G]
    anc = set(nos)
    for n in nos:
        anc |= nx.ancestors(G, n)
    return anc, sorted(s for s in ctx["S"] if s in anc)


def _disjunta(alteradas: list, intervalos: list) -> bool:
    """§4.5 T1a: toda linha alterada [FROM, TO] e disjunta de todo intervalo [ini, fim]."""
    return bool(alteradas) and bool(intervalos) and all(
        ate < ini or de > fim for (_, de, ate) in alteradas for (ini, fim) in intervalos)


def t2(z: str, ctx: dict) -> bool:
    """§4.5 T2: toda semente que alcanca z tem conteudo igual sem anotacao em p e c."""
    _, sementes = _origem(z, ctx)
    return bool(sementes) and all(
        sem_anotacao(ctx["nos_p"].get(s, b"")) == sem_anotacao(ctx["nos_c"].get(s, b""))
        for s in sementes)


def t1a(z: str, ctx: dict) -> bool:
    """§4.5 T1a: todo caminho semente->z passa por uma Rule R da semente cujas linhas
    alteradas sao disjuntas de todo intervalo de uso de R pela Zone do caminho."""
    anc, sementes = _origem(z, ctx)
    if not sementes or any(not s.startswith("R:") for s in sementes):
        return False
    for R in sementes:
        zonas = [Z for Z in ctx["G"].successors(R) if Z in anc]
        if not zonas or not all(_disjunta(ctx["alteradas"].get(R, []),
                                          ctx["intervalos"].get((R, Z), [])) for Z in zonas):
            return False
    return True


def rotular_tz(inst: list[tuple[str, str]], ctx: dict) -> dict[str, list[str]]:
    """Rotulos multiplos (§4.6 a) das instancias (elemento, FN|FP) do braco A0 no tz.
    FP: T2, T1a (T3-FP nao se aplica ao tz); sem rotulo -> T5 (exclusivo, §4.5).
    FN: T4, T3-FN e T1b nao se aplicam ao tz -> INCLASSIFICADO-FN."""
    out: dict[str, list[str]] = {}
    for e, lado in inst:
        if lado == "FP":
            r = [k for k, f in (("T1a", t1a), ("T2", t2)) if f(e, ctx)]
            out[e] = r or ["T5"]
        elif lado == "FN":
            out[e] = ["INCLASSIFICADO-FN"]
        else:
            raise ValueError(lado)
    return out


def nc_tz(ctx: dict, com_F: bool = True) -> bool:
    """§5 subconjunto sem disparo de detector, no tz: todo no da semente muda o conteudo
    sem anotacao (sem T2) e nenhuma Rule da semente e disjunta de algum intervalo de
    uso (sem T1a). Leitura declarada: pseudo-nos F: contam (letra do §5, "todo no da
    semente"), logo uma semente so de comentario final de arquivo tira o par do NC;
    com_F=False (sensibilidade §6.4, registrada em sens.nc_sem_F) ignora os F:. Semente
    vazia: NC vacuamente (nao ha no que dispare detector)."""
    for s in ctx["S"]:
        if not com_F and s.startswith("F:"):
            continue
        if sem_anotacao(ctx["nos_p"].get(s, b"")) == sem_anotacao(ctx["nos_c"].get(s, b"")):
            return False
    G = ctx["G"]
    for R in (s for s in ctx["S"] if s.startswith("R:") and s in G):
        for Z in G.successors(R):
            if _disjunta(ctx["alteradas"].get(R, []), ctx["intervalos"].get((R, Z), [])):
                return False
    return True
