"""Adaptador tz (PROTOCOLO_V_2026-10-02 §4.3-§4.4; INTERFACES §2.2).

Le os arquivos de dados de um commit do tz e declara as portas d1-d8. Ferramentas (§4.3 iv):
so `git` (via git_arvore) e `make -pn` (expansao de TDATA pelo proprio make). Todo campo lido
cita zic(8) de tz@bec4d95a (ESPEC e comentarios `zic.8:`); nenhum nome de zona, regra ou
arquivo e literal aqui (§4.3 ii): os nomes de arquivo vem de decl_tz.json.
Nos (§4.4 d1): R:<NOME> = linhas Rule do NOME (todos os arquivos); Z:<nome> = Zone +
continuacoes; L:<nome> = Link; F:<arquivo> = sobra do arquivo, sem aresta nem elemento.
Aresta u -> v = "v consome u" (§4.1). G = G_p uniao G_c (`grafo`).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import networkx as nx

_DECL = json.loads(Path(__file__).with_name("decl_tz.json").read_text(encoding="utf-8"))

ESPEC: dict[str, str] = {
    "lexico": "tz@bec4d95a:zic.8:336-345 (separadores espaco \\f \\n \\r \\t \\v; '#' fora de aspas = "
              "comentario; aspas; linha branca ignorada); zic.c:4041-4076",
    "linha.tipo": "tz@bec4d95a:zic.8:346-359 (Rule/Zone/Link sem caixa, abreviavel); zic.c:459-463,3986-4039",
    "linha.n_campos": "tz@bec4d95a:zic.c:343-395 (Rule 10; Zone 5-9; continuacao 3-7; Link 3)",
    "campo.hifen": "tz@bec4d95a:zic.c:4073 (campo '-' sozinho vale vazio)",
    "Rule.NAME": "tz@bec4d95a:zic.8:366,376-387 (nao comeca por digito, '-' ou '+')",
    "Rule.FROM": "tz@bec4d95a:zic.8:389-395; 'minimum' obsoleto: zic.c:509-512,2473-2486",
    "Rule.TO": "tz@bec4d95a:zic.8:397-406 (maximum, only = FROM); zic.c:514-518,2487-2501",
    "Zone.NAME": "tz@bec4d95a:zic.8:571,581-605",
    "Zone.RULES": "tz@bec4d95a:zic.8:571,617-628 (nome ou quantia SAVE; '-' nenhuma); zic.c:1942-1954",
    "Zone.UNTIL": "tz@bec4d95a:zic.8:571,666-675 (ano = primeiro campo de UNTIL)",
    "Zone.continuacao": "tz@bec4d95a:zic.8:677-689; zic.c:2039-2040",
    "Link.TARGET/LINK-NAME": "tz@bec4d95a:zic.8:745-778 (Link TARGET LINK-NAME; link de link)",
    "arquivos.dados": "PROTOCOLO_V §2.5; tz@bec4d95a:Makefile:653-658; GNU Make manual (-p -n -r -R -f; info)",
}

D5 = None                              # d5: so npm
D7 = "fecho_sobre_ciclo_e_conta"       # d7 (§4.5, §4.7)
_TIPOS = ("Rule", "Zone", "Link")      # zic.c:459-463
_INICIO = ("minimum",)                 # zic.c:509-512
_FIM = ("maximum", "only")             # zic.c:514-518
_ESP = frozenset(b" \f\n\r\t\v")       # zic.8:338-339
_HASH, _ASPA = 0x23, 0x22              # zic.8:341-344
_INT = re.compile(rb"[+-]?[0-9]+")
_TIPO_NO = {"R": "Rule", "Z": "Zone", "L": "Link", "F": "F"}
_CACHE: dict = {}


# ------------------------------------------------------------ lexico zic(8)
def campos(linha: bytes) -> list[bytes] | None:
    """Campos pelo lexico zic.8:336-345, sem aspas; [] = branca/comentario; None = aspas impares."""
    out, i, n = [], 0, len(linha)
    while True:
        while i < n and linha[i] in _ESP:
            i += 1
        if i >= n or linha[i] == _HASH:
            return out
        f = bytearray()
        while i < n and linha[i] != _HASH and linha[i] not in _ESP:
            if linha[i] == _ASPA:
                j = linha.find(b'"', i + 1)
                if j < 0:
                    return None
                f += linha[i + 1:j]
                i = j + 1
            else:
                f.append(linha[i])
                i += 1
        out.append(bytes(f))


def _linhas(dados: bytes) -> list[bytes]:
    """Linhas terminadas em LF (zic.8:323-325), com o LF."""
    partes = dados.split(b"\n")
    return [p + b"\n" for p in partes[:-1]] + ([partes[-1]] if partes[-1] else [])


def _palavra(f: bytes, tabela: tuple[str, ...]) -> str | None:
    """Palavra-chave: sem caixa; prefixo inicial sem ambiguidade (zic.8:349-359)."""
    w = f.decode("latin-1").lower()
    for t in tabela:
        if w == t.lower():
            return t
    achados = [t for t in tabela if t.lower().startswith(w)]
    return achados[0] if len(achados) == 1 else None


def _v(f: bytes) -> bytes:
    return b"" if f == b"-" else f     # zic.c:4073


_nome = lambda f: f.decode("utf-8", "backslashreplace")  # noqa: E731


def _inteiro(f: bytes) -> float | None:
    return float(int(f)) if _INT.fullmatch(f) else None


def _ano(f: bytes) -> float | None:
    """FROM e ano de UNTIL: inteiro ou 'minimum' = -inf (zic.8:389-395; zic.c:2473-2486)."""
    return -math.inf if _palavra(f, _INICIO) else _inteiro(f)


def _ate(f: bytes, de: float | None) -> float | None:
    """TO: maximum = +inf; only = FROM (zic.8:397-406)."""
    p = _palavra(f, _FIM)
    return math.inf if p == "maximum" else de if p == "only" else _inteiro(f)


def _regra_ref(z: list[bytes]) -> str | None:
    """RULES de [STDOFF, RULES, ...]: nome de regras, ou None se vazio, '-' ou SAVE (zic.8:378-382,617-628)."""
    if len(z) < 2:
        return None
    r = _v(z[1])
    return _nome(r) if r and r[:1] not in b"0123456789+-" else None


# ------------------------------------------------------------ arquivos de dados
_DIN = re.compile(rb"[$][({][ \t\r\f\v]*(shell|wildcard|eval|file)[ \t\r\f\v]"
                  rb"|^[ \t\r\f\v]*-?(include|sinclude)[ \t\r\f\v]|!=", re.M)


def _expandir(mk: bytes, var: str) -> list[str] | None:
    """Valor de `var` expandido pelo GNU make (`make -pn`) sobre o Makefile sozinho num diretorio
    vazio (como no oraculo); None se falhar, estourar o tempo ou nao imprimir o valor."""
    nome_mk = _DECL["makefile"]["valor"]
    with tempfile.TemporaryDirectory() as d:
        Path(d, nome_mk).write_bytes(mk)
        try:
            r = subprocess.run(["make", "-pn", "-r", "-R", "-f", nome_mk, "-f", "-", "__v_alvo"],
                               input=f"$(info __V_VAL__=$({var}))\n__v_alvo: ;\n".encode(),
                               cwd=d, capture_output=True, timeout=60,
                               env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"})
        except (subprocess.TimeoutExpired, OSError):
            return None
    for ln in r.stdout.splitlines():
        if ln.startswith(b"__V_VAL__="):
            return ln[len(b"__V_VAL__="):].decode("utf-8", "backslashreplace").split()
    return None


def _dados(a) -> tuple[list[str], list[str], str]:
    """(presentes, faltantes, fonte) (§2.5): TDATA do Makefile do PROPRIO lado, ou a lista fixa
    (reserva_sem_makefile|_sem_tdata|_make_falhou|_dinamico: Makefile com shell, wildcard, eval,
    file, include ou != nao e executado). Espelha faltantes.txt e tdata_fonte.txt do oraculo."""
    chave = ("dados", getattr(a, "repo", None), a.sha)
    if chave not in _CACHE:
        mk = a.ler(_DECL["makefile"]["valor"])
        fonte, nomes = "reserva_sem_makefile", []
        if mk is not None:
            din = _DIN.search(mk)
            nomes = [] if din else _expandir(mk, _DECL["variavel_dados"]["valor"])
            fonte = ("reserva_dinamico" if din else "reserva_make_falhou" if nomes is None
                     else "makefile" if nomes else "reserva_sem_tdata")
        nomes = [n for n in dict.fromkeys(nomes or _DECL["tdata_reserva"]["valor"])
                 if n not in _DECL["excluir_dados"]["valor"]]
        pres = set(a.listar())
        _CACHE[chave] = ([n for n in nomes if n in pres], sorted(set(nomes) - pres), fonte)
    return _CACHE[chave]


def arquivos_dados(a) -> list[str]:
    return list(_dados(a)[0])


def dados_status(a) -> dict:
    return {"fonte": _dados(a)[2], "faltantes": list(_dados(a)[1])}


# ------------------------------------------------------------ modelo de um lado
def _anexa(m: dict, no: str, ln: bytes, f) -> None:
    m["bytes"].setdefault(no, []).append(ln)
    if f != []:                        # linha nao-branca: entra no checksum d3
        m["lex"].setdefault(no, []).append(f if f is not None else [ln])


def _zona_linha(m: dict, no: str, f: list[bytes], base: int) -> bool:
    """Guarda [STDOFF, RULES, FORMAT, UNTIL...] (zic.8:677-689); True se ha UNTIL (continua)."""
    m["zonas"][no][-1].append(f[base:])
    return len(f) - base > 3


def _ler_arquivo(m: dict, arq: str, dados: bytes, atrib: str) -> None:
    sobra = "F:" + arq
    pend: list[bytes] = []
    ant, cont, zona = None, False, None
    for ln in _linhas(dados):
        f = campos(ln)
        if f == []:                    # zic.8:345: branca ou so comentario
            if atrib == "proxima":     # §4.4: pertence a PROXIMA estrofe do arquivo
                pend.append(ln)
            else:                      # sensibilidade §6.4: estrofe anterior
                _anexa(m, ant or sobra, ln, [])
            continue
        no = sobra
        if f is None:                  # aspas impares: o zic recusa; vai para F
            cont = False
        elif cont:                     # continuacao: 3-7 campos (zic.8:677-689), senao F
            cont = False
            if 3 <= len(f) <= 7:
                no = zona
                cont = _zona_linha(m, zona, f, 0)
        else:
            t = _palavra(f[0], _TIPOS)                     # zic.8:346-347,349-359
            if t == "Rule" and len(f) == 10:               # Rule NAME FROM TO - ... (zic.8:366)
                no = "R:" + _nome(f[1])
                m["regras"].setdefault(no, []).append(ln)
            elif t == "Zone" and 5 <= len(f) <= 9:         # Zone NAME STDOFF RULES FORMAT [UNTIL]
                no = zona = "Z:" + _nome(f[1])
                m["zonas"].setdefault(no, []).append([])
                cont = _zona_linha(m, no, f, 2)
            elif t == "Link" and len(f) == 3:              # Link TARGET LINK-NAME (zic.8:750)
                no = "L:" + _nome(f[2])
                m["links"].append((_nome(f[1]), _nome(f[2])))
        for p in pend:
            _anexa(m, no, p, [])
        pend = []
        _anexa(m, no, ln, f)
        ant = no
    for p in pend:
        _anexa(m, sobra, p, [])


def _modelo(a, atrib: str = "proxima") -> dict:
    if atrib not in ("proxima", "anterior"):
        raise ValueError(atrib)
    chave = (getattr(a, "repo", None), a.sha, atrib)
    if chave not in _CACHE:
        m = {"bytes": {}, "lex": {}, "regras": {}, "zonas": {}, "links": [],
             "arquivos": arquivos_dados(a)}
        for arq in sorted(m["arquivos"]):
            _ler_arquivo(m, arq, a.ler(arq) or b"", atrib)
        m["nos"] = {n: b"".join(v) for n, v in m["bytes"].items()}
        while len(_CACHE) >= 32:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[chave] = m
    return _CACHE[chave]


# ------------------------------------------------------------ d1
def d1_nos(a, atribuicao: str = "proxima") -> dict[str, bytes]:
    """No -> bytes das linhas atribuidas (§4.4 d1)."""
    return dict(_modelo(a, atribuicao)["nos"])


def d1_tipo(no: str) -> str:
    return _TIPO_NO[no[:1]]


def d1_elemento(no: str) -> str | None:
    """Elemento = nome de saida da Zone ou do Link (§2.2); R e F nao tem elemento."""
    return no[2:] if no[:2] in ("Z:", "L:") else None


def _especies(a) -> dict[str, frozenset[str]]:
    esp: dict[str, set[str]] = {}
    for n in _modelo(a)["nos"]:
        if (e := d1_elemento(n)) is not None:
            esp.setdefault(e, set()).add(d1_tipo(n))
    return {e: frozenset(k) for e, k in esp.items()}


def d1_universo(ap, ac) -> set[str]:
    """Nomes declarados nos dois lados com a mesma especie (§3.1)."""
    ep, ec = _especies(ap), _especies(ac)
    return {e for e in ep.keys() & ec.keys() if ep[e] == ec[e]}


def identidade(ap, ac) -> list[str]:
    """MUDANCA_DE_IDENTIDADE declarada (§3.1, §4.7): nome em um so lado ou Zone<->Link."""
    ep, ec = _especies(ap), _especies(ac)
    return sorted((ep.keys() ^ ec.keys()) | {e for e in ep.keys() & ec.keys() if ep[e] != ec[e]})


def semente(ap, ac, atribuicao: str = "proxima") -> dict[str, str]:
    """Nos com bytes atribuidos diferentes (M) ou presentes em um so lado (A/D) (§4.4)."""
    np_, nc_ = d1_nos(ap, atribuicao), d1_nos(ac, atribuicao)
    estado = {n: "D" if n not in nc_ else "A" if n not in np_ else "M"
              for n in np_.keys() | nc_.keys()}
    return {n: e for n, e in sorted(estado.items()) if e != "M" or np_[n] != nc_[n]}


def b_sem(S, U) -> set[str]:
    """B-sem (§5): as Zones e Links da semente."""
    return {e for e in map(d1_elemento, S) if e is not None} & set(U)


# ------------------------------------------------------------ d2
def d2_declarado(a) -> nx.DiGraph:
    """R->Z: linha de Z nomeia R em RULES (zic.8:617-628; zic.c:1942-1954); Z->L, L->L': TARGET."""
    m = _modelo(a)
    G = nx.DiGraph()
    for n in m["nos"]:
        G.add_node(n, tipo=d1_tipo(n))
    for z, segs in m["zonas"].items():
        for seg in segs:
            for lz in seg:
                r = _regra_ref(lz)
                if r is not None and "R:" + r in m["regras"]:
                    G.add_edge("R:" + r, z, origem="declarada")
    nomes_link = {nome for _, nome in m["links"]}
    for alvo, nome in m["links"]:
        if "Z:" + alvo in m["zonas"]:
            G.add_edge("Z:" + alvo, "L:" + nome, origem="declarada")
        if alvo in nomes_link:
            G.add_edge("L:" + alvo, "L:" + nome, origem="declarada")
    return G


def grafo(ap, ac) -> nx.DiGraph:
    """G = G_p uniao G_c (§4.4)."""
    return nx.compose(d2_declarado(ap), d2_declarado(ac))


def d2_extraido(a) -> None:          # tz: sem segundo grafo (§2.2)
    return None


def pendentes(a) -> set[str]:
    """Referencia a nome nao definido no lado (§4.7 PENDENTE)."""
    m = _modelo(a)
    out = {"R:" + r for segs in m["zonas"].values() for seg in segs for lz in seg
           if (r := _regra_ref(lz)) is not None and "R:" + r not in m["regras"]}
    nomes_link = {nome for _, nome in m["links"]}
    out |= {"Z|L:" + alvo for alvo, _ in m["links"]
            if "Z:" + alvo not in m["zonas"] and alvo not in nomes_link}
    return out


# ------------------------------------------------------------ d3
def d3_checksum(no: str, a) -> str:
    """sha256 dos campos (zic.8:336-345) das linhas nao-brancas do no (ausente = vazio)."""
    return hashlib.sha256(repr(_modelo(a)["lex"].get(no, [])).encode()).hexdigest()


# ------------------------------------------------------------ d4
def d4_intervalos(a) -> dict[tuple[str, str], list[tuple[float, float]]]:
    """(R, Z) -> [(ini, fim)] por linha de Z que nomeia R: UNTIL da linha anterior (ou -inf) e
    UNTIL da linha (ou +inf) (§4.4 d4; zic.8:666-689). UNTIL ilegivel alarga."""
    out: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for z, segs in _modelo(a)["zonas"].items():
        for seg in segs:
            ini = -math.inf
            for lz in seg:
                fim = _ano(_v(lz[3])) if len(lz) > 3 else math.inf
                r = _regra_ref(lz)
                if r is not None:
                    out.setdefault(("R:" + r, z), []).append(
                        (ini, math.inf if fim is None else fim))
                ini = -math.inf if fim is None else fim
    return out


def d4_alteradas(R: str, ap, ac) -> list[tuple[str, float, float]]:
    """Multiconjunto p (-) c e c (-) p das linhas Rule de R: (lado, FROM, TO) (§4.5; zic.8:389-406)."""
    lp = Counter(_modelo(ap)["regras"].get(R, []))
    lc = Counter(_modelo(ac)["regras"].get(R, []))
    out = []
    for lado, dif in (("p", lp - lc), ("c", lc - lp)):
        for ln in sorted(dif.elements()):
            f = campos(ln)             # Rule NAME FROM TO ...: f[2] FROM, f[3] TO
            de = _ano(_v(f[2]))
            ate = _ate(_v(f[3]), de)
            out.append((lado, -math.inf if de is None else de,
                        math.inf if ate is None else ate))
    return out


def d4_dados(S, ap, ac) -> dict:
    """Entrada dos ganchos d4 e do T1a: intervalos (p uniao c) e linhas alteradas das Rules de S."""
    iv: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for lado in (ap, ac):
        for k, v in d4_intervalos(lado).items():
            iv[k] = sorted(set(iv.get(k, [])) | set(v))
    return {"intervalos": iv,
            "alteradas": {R: d4_alteradas(R, ap, ac) for R in S if d1_tipo(R) == "Rule"}}


# ------------------------------------------------------------ d6, d8, B-make
def d6_globais(a) -> set[str]:
    return set(_DECL["d6_globais"]["valor"])


def d8_nao_det(a) -> set[str]:
    return set(_DECL["d8_nao_det"]["valor"])


def b_make(ac, S) -> None:            # B-make so em zlib/Lua (§5)
    return None


def placebo_globs() -> list[str]:
    return list(_DECL["placebo_globs"]["valor"])
