"""Adaptador npm (PROTOCOLO_V_2026-10-02 §2.3, §3.3, §4.3, §4.5 T1b; INTERFACES §2.2).

Estudo DESCRITIVO e condicional (§2.3), nao confirmatorio. Porta propria: d5,
resolucao temporal da ligacao (so npm, §4.3). O adaptador so LE: o tarball do quadro
(tarfile) e lockfiles ja produzidos pelo oraculo (json). Nao invoca nem reimplementa o
resolvedor (§4.3 iv): nada de subprocess, npm, semver ou escolha de versao. Os nomes de
pacote vem do quadro, nunca do codigo (§4.3 ii); todo literal fica em decl_npm.json.

Arvore de um lado = o lockfile v3 que o resolvedor gravou para (manifesto, data)
(package-lock-json.md:124-167). Nos (d1): "" (o manifesto-base) e um no por
NOME de pacote; o conteudo do no sao as versoes resolvidas daquele nome. Aresta u -> v =
"v consome u" (§4.1): dependencia -> dependente, por nome (d2). Elemento = nome.

Desenho do par (decl_npm.json:manifesto): o manifesto-base e o mesmo texto em toda janela e
declara so a raiz pela dist-tag; o manifesto EFETIVO e o package.json da versao da raiz
resolvida em t. O par (t, t+1) conta so se essa versao e igual nos dois lados
(`manifesto_igual`); senao a semente nao e vazia e o par sai do denominador de T1b.
"""
from __future__ import annotations

import calendar
import hashlib
import io
import json
import random
import re
import tarfile
from pathlib import Path

import networkx as nx

_DECL = json.loads(Path(__file__).with_name("decl_npm.json").read_text(encoding="utf-8"))
_LK = _DECL["campos_lockfile"]
_NPM = "npm@10.9.4:docs/content"

ESPEC: dict[str, str] = {
    "quadro": _DECL["quadro"]["cita"],
    "raizes": _DECL["raizes"]["cita"],
    "janelas": _DECL["janelas"]["cita"],
    "manifesto": _DECL["manifesto"]["cita"],
    "lockfile.packages": f"{_NPM}/configuring-npm/package-lock-json.md:124-130 (mapa local -> "
                         "pacote; raiz com chave ''; demais pelo caminho relativo)",
    "lockfile.version": f"{_NPM}/configuring-npm/package-lock-json.md:134",
    "lockfile.link": f"{_NPM}/configuring-npm/package-lock-json.md:147-149 (link: o alvo "
                     "tambem esta no lockfile)",
    "lockfile.name": "@npmcli/arborist@8.0.1:lib/shrinkwrap.js:86 (name so para apelido)",
    "lockfile.arestas": f"{_NPM}/configuring-npm/package-lock-json.md:166-167; "
                        "@npmcli/arborist@8.0.1:lib/shrinkwrap.js:85-104 (peerDependencies)",
    "spec.formas": f"{_NPM}/configuring-npm/package-json.md:593-624 (versao exata, faixas, "
                   "tag, URL, git, user/repo, caminho local, apelido npm:)",
    "spec.apelido": f"{_NPM}/configuring-npm/package-json.md:624; "
                    f"{_NPM}/using-npm/package-spec.md:35-43 (Aliases)",
    "d5.before": f"{_NPM}/using-npm/config.md:215-229 (so versoes publicadas ate o instante, "
                 "inclusivo; dist-tag que nao passa o filtro cai na maior versao <= tag)",
    "d5.packument": "pacote@19.0.1:lib/fetcher.js:79 (com before o packument e o completo, "
                    "com o campo time)",
}

# d5 (§4.3): a ligacao de um nome declarado por faixa ou tag e resolvida no instante
# --before; por versao exata, nao; URL/git/caminho, fora do registry.
D5: dict = {"resolucao": "por_data", "instante": "--before inclusivo",
            "tipos": {"data": "faixa ou dist-tag", "fixa": "versao exata",
                      "fora": "URL, git, user/repo, caminho local"},
            "espec": ESPEC["d5.before"] + "; " + ESPEC["spec.formas"]}
D7 = "fecho_sobre_ciclo_e_conta"       # d7 (§4.5, §4.7)

# Gramatica de versao exata do semver (package-json.md:605 'version Must match version
# exactly'), com o '=' e o 'v' que o modo frouxo aceita.
_EXATA = re.compile(r"^\s*=?\s*v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?\s*$")
_FORA = re.compile(r"^(?:git\+|git:|github:|gitlab:|bitbucket:|gist:|https?:|file:|link:"
                   r"|workspace:|\.{0,2}/|~/)")
_USUARIO_REPO = re.compile(r"^[^@\s/:]+/[^\s/:]+$")      # package-json.md:620 'user/repo'
_STR_JS = re.compile(r"""'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)\"""")
_ESC = {"\\": "\\", "'": "'", '"': '"', "/": "/"}


# ------------------------------------------------------------- quadro e sorteio
def hashes(caminho: str | Path) -> dict:
    b = Path(caminho).read_bytes()
    return {"sha1": hashlib.sha1(b).hexdigest(), "sha256": hashlib.sha256(b).hexdigest(),
            "bytes": len(b)}


def _js_str(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c != "\\":
            out.append(c)
            i += 1
        elif s[i + 1] in _ESC:
            out.append(_ESC[s[i + 1]])
            i += 2
        elif s[i + 1] == "u" and re.fullmatch(r"[0-9A-Fa-f]{4}", s[i + 2:i + 6]):
            out.append(chr(int(s[i + 2:i + 6], 16)))
            i += 6
        else:
            raise ValueError(f"escape nao previsto no quadro: {s!r}")
    return "".join(out)


def quadro(tgz: str | Path) -> list[str]:
    """Nomes do quadro, na ordem do arquivo. Recusa tarball com shasum diferente do
    declarado (§12.1) e qualquer coisa alem de literais de string no array."""
    q = _DECL["quadro"]
    h = hashes(tgz)
    if h["sha1"] != q["shasum"]:
        raise ValueError(f"shasum {h['sha1']} != {q['shasum']} ({q['pacote']}@{q['versao']})")
    with tarfile.open(tgz, "r:gz") as t:
        texto = t.extractfile(q["membro"]).read().decode("utf-8")
    ini, fim = texto.index("["), texto.rindex("]")
    corpo = texto[ini + 1:fim]
    nomes = [_js_str(a if a is not None else b) for a, b in _STR_JS.findall(corpo)]
    if _STR_JS.sub("", corpo).replace(",", "").strip():
        raise ValueError("array do quadro tem algo alem de literais de string")
    if len(set(nomes)) != len(nomes):
        raise ValueError("quadro com nome repetido")
    return nomes


def sortear_raizes(nomes: list[str], principal: int | str, n: int | None = None) -> list[str]:
    """§2.5 e INTERFACES §3: random.Random(f'{principal}:npm_raizes').sample sobre a
    populacao ordenada por nome. Devolve as raizes em ordem de nome."""
    r = _DECL["raizes"]
    pop = sorted(set(nomes))
    return sorted(random.Random(f"{principal}:{r['uso']}").sample(pop, n or r["n"]))


def janelas() -> list[str]:
    """Instantes --before das janelas mensais (decl_npm.json:janelas): ultimo ms do mes."""
    j = _DECL["janelas"]
    a0, m0 = map(int, j["inicio"].split("-"))
    a1, m1 = map(int, j["fim"].split("-"))
    out = []
    for a in range(a0, a1 + 1):
        for m in range(1, 13):
            if (a, m) < (a0, m0) or (a, m) > (a1, m1):
                continue
            out.append(f"{a:04d}-{m:02d}-{calendar.monthrange(a, m)[1]:02d}T23:59:59.999Z")
    return out


def pares_janelas() -> list[tuple[str, str]]:
    js = janelas()
    return list(zip(js, js[1:]))


def manifesto(raiz: str) -> bytes:
    """Manifesto-base fixo (o mesmo texto em toda janela) que declara so a raiz pela dist-tag."""
    m = dict(_DECL["manifesto"]["manifesto_base"])
    m["dependencies"] = {raiz: _DECL["manifesto"]["spec_raiz"]}
    return (json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n").encode("utf-8")


# ------------------------------------------------------------- leitura do lado
def ler_lock(fonte: str | Path | bytes | dict) -> dict:
    if isinstance(fonte, dict):
        return fonte
    b = fonte if isinstance(fonte, bytes) else Path(fonte).read_bytes()
    lock = json.loads(b)
    if not isinstance(lock.get(_LK["pacotes"]), dict):
        raise ValueError("lockfile sem 'packages' (exige lockfileVersion >= 2)")
    return lock


def _nome_de(chave: str, ent: dict) -> str:
    """Nome real do pacote num local do lockfile: 'name' (apelido) ou o trecho apos o
    ultimo node_modules/ (package-lock-json.md:129-130; shrinkwrap.js:86)."""
    if ent.get("name"):
        return ent["name"]
    p = _LK["prefixo_caminho"]
    i = chave.rfind(p)
    return chave[i + len(p):] if i >= 0 else chave


def _entradas(lock: dict):
    for chave, ent in sorted(ler_lock(lock)[_LK["pacotes"]].items()):
        if chave != _LK["raiz"] and not ent.get("link"):
            yield chave, ent


def ler_resolvido(caminho: str | Path) -> dict[str, tuple[str, ...]]:
    """resolvido.tsv do oraculo (nome<TAB>versoes separadas por virgula)."""
    out = {}
    for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
        if linha:
            nome, vs = linha.split("\t")
            out[nome] = tuple(vs.split(",")) if vs else ()
    return out


def versoes(lock: dict) -> dict[str, tuple[str, ...]]:
    """nome -> versoes distintas resolvidas (mesma regra do resolvido.tsv do oraculo)."""
    v: dict[str, set[str]] = {}
    for chave, ent in _entradas(lock):
        v.setdefault(_nome_de(chave, ent), set()).add(ent.get("version", ""))
    return {n: tuple(sorted(s)) for n, s in sorted(v.items())}


# ------------------------------------------------------------- d1
def d1_nos(lock: dict) -> dict[str, bytes]:
    """No -> bytes atribuidos: versoes do nome; o manifesto-base "" leva as suas arestas."""
    raiz = ler_lock(lock)[_LK["pacotes"]].get(_LK["raiz"], {})
    nos = {_LK["raiz"]: json.dumps({c: raiz.get(c, {}) for c in _LK["arestas"]},
                                   sort_keys=True).encode()}
    for n, vs in versoes(lock).items():
        nos[n] = ",".join(vs).encode()
    return nos


def d1_tipo(no: str) -> str:
    return "raiz" if no == _LK["raiz"] else "pacote"


def d1_elemento(no: str) -> str | None:
    return None if no == _LK["raiz"] else no


def d1_universo(lp: dict, lc: dict) -> set[str]:
    """Nomes resolvidos nos dois lados; o resto e MUDANCA_DE_IDENTIDADE (§4.7)."""
    return set(versoes(lp)) & set(versoes(lc))


def identidade(lp: dict, lc: dict) -> set[str]:
    return set(versoes(lp)) ^ set(versoes(lc))


def versao_raiz(lock: dict, raiz: str) -> str | None:
    ent = ler_lock(lock)[_LK["pacotes"]].get(_LK["prefixo_caminho"] + raiz)
    return None if ent is None else ent.get("version")


def manifesto_igual(lp: dict, lc: dict, raiz: str) -> bool:
    """§2.3: o manifesto efetivo (package.json da versao da raiz) e o mesmo em t e t+1."""
    vp = versao_raiz(lp, raiz)
    return vp is not None and vp == versao_raiz(lc, raiz)


def semente(lp: dict, lc: dict, raiz: str) -> dict[str, str]:
    """Nos cujo conteudo DECLARADO muda: o manifesto-base e fixo; a raiz entra (M) se a sua
    versao, logo o seu package.json, muda. Com manifesto igual, S = vazio."""
    return {} if manifesto_igual(lp, lc, raiz) else {raiz: "M"}


def b_sem(S: dict, U: set[str]) -> set[str]:
    return {s for s in S if s in U}


# ------------------------------------------------------------- d2
def _alvo(dep: str, spec: str) -> str:
    """Nome real do alvo de uma aresta: 'npm:<nome>@<faixa>' aponta para <nome>."""
    if isinstance(spec, str) and spec.startswith("npm:"):
        resto = spec[4:]
        i = resto.rfind("@")
        return resto[:i] if i > 0 else resto
    return dep


def arestas(lock: dict):
    """(dependencia, dependente, campo, spec) de todo local nao-link e do manifesto-base."""
    lock = ler_lock(lock)
    raiz = lock[_LK["pacotes"]].get(_LK["raiz"], {})
    locais = [(_LK["raiz"], _LK["raiz"], raiz)]
    locais += [(c, _nome_de(c, e), e) for c, e in _entradas(lock)]
    for _, quem, ent in locais:
        for campo in _LK["arestas"]:
            for dep, spec in sorted((ent.get(campo) or {}).items()):
                yield _alvo(dep, spec), quem, campo, spec


def d2_declarado(lock: dict) -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_nodes_from(d1_nos(lock))
    for u, v, campo, spec in arestas(lock):
        if u != v:
            G.add_edge(u, v, origem="declarada", campo=campo, spec=spec)
    return G


def d2_extraido(lock: dict) -> None:
    return None                         # sem segunda fonte de grafo no npm (§3.4)


def pendentes(lock: dict) -> set[str]:
    """Nomes declarados por dependencies que nao aparecem resolvidos (§4.7 PENDENTE).
    Pares opcionais e peer nao resolvidos sao permitidos pelo npm e ficam de fora."""
    tem = set(versoes(lock))
    return {u for u, _, campo, _ in arestas(lock) if campo == _LK["arestas"][0] and u not in tem}


# ------------------------------------------------------------- d3, d4, d5, d6, d8
d3_checksum = None                      # lockfile nao tem anotacao (§4.5 T2 nao se aplica)
d4_intervalos = None                    # d4 so tz (§5)


def d4_alteradas(R, ap, ac) -> list:
    return []


def d5_tipo_spec(spec: str) -> str:
    """'data' | 'fixa' | 'fora' (ESPEC spec.formas). So classifica o TEXTO da declaracao;
    nao compara versoes nem escolhe nenhuma."""
    if not isinstance(spec, str):
        return "fora"
    if spec.startswith("npm:"):
        resto = spec[4:]
        i = resto.rfind("@")
        return d5_tipo_spec(resto[i + 1:]) if i > 0 else "data"
    if _FORA.match(spec) or _USUARIO_REPO.match(spec):
        return "fora"
    return "fixa" if _EXATA.match(spec) else "data"


def d5_ligacoes(lock: dict) -> dict[tuple[str, str], str]:
    """(dependencia, dependente) -> tipo da ligacao; 'data' vence se houver varias."""
    out: dict[tuple[str, str], str] = {}
    for u, v, _, spec in arestas(lock):
        t = d5_tipo_spec(spec)
        if out.get((u, v)) != "data":
            out[(u, v)] = t
    return out


def d5_semente(lock: dict) -> set[str]:
    """Nos com ao menos uma ligacao de entrada resolvida por data: a declaracao d5 diz que
    eles podem mudar entre t e t+1 com o manifesto igual (T1b, §4.5)."""
    return {u for (u, _), t in d5_ligacoes(lock).items() if t == "data"}


def d6_globais(lock: dict) -> set[str]:
    return set(_DECL["d6_globais"]["valor"])


def d8_nao_det(lock: dict) -> set[str]:
    return set(_DECL["d8_nao_det"]["valor"])


def b_make(ac, S) -> None:
    return None                         # B-make so zlib/Lua (§5)
