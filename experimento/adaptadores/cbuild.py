"""Adaptador C para zlib e Lua (PROTOCOLO_V_2026-10-02 §4.3-§4.4, §5; INTERFACES §2.2).

Uso: A = cbuild.para("zlib" | "lua"); A.<porta>(arvore). A arvore e git_arvore.Arvore
(repo + commit) ou ArvoreDir (fixture); so se usa a.sha, a.repo, a.listar(), a.ler().
Nos (d1) = caminhos de arquivo relativos a raiz; elemento = objeto .o do universo.
Aresta u -> v = "v consome u" (§4.1); atributo `origem` em {declarada, config,
extraida, d6}. G = G_p uniao G_c (`grafo`, `grafo_obs`).

Ferramentas (§4.3 iv), e so estas: git (git_arvore e `git diff`/`cat-file`), make -p -n
(d2-declarado), make -t / make -n (so b_make e diferencial do parser), gcc -MM (so
d2_extraido) e o lexer C do pygments (d3). Nada de gcc -c, cc1 compilando, ld, configure,
zic, zdump. Nenhum nome de arquivo literal (§4.3 ii): vem todo de decl_<corpus>.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

import networkx as nx
from pygments.lexers.c_cpp import CLexer
from pygments.token import Comment, Text

AQUI = Path(__file__).resolve().parent

ESPEC: dict[str, str] = {
    "d1.nos": "git-ls-tree(1) -r; git-cat-file(1) --batch: no = caminho relativo, bytes do blob",
    "d1.elemento": "GNU Make manual 4.3 §10.2 (n.o feito de n.c); PROTOCOLO_V §3.2 "
                   "(zlib: OBJS de libz.a, zlib@767c4c94:Makefile.in:59-60,71,129; Lua: "
                   "ALL_O/alvo o, lua@0b29f408:makefile:110,116)",
    "semente": "git-diff(1) --name-status -M -z (estados M, A, D, R; T conta como M)",
    "d2.declarado": "GNU Make manual 4.3 §9.7 (-p --print-data-base; -n --just-print; -k; "
                    "-f), §10.8 'Implicit Rule Search Algorithm' (o pre-requisito da regra "
                    "implicita entra na lista do arquivo no banco), §4.3 'Types of "
                    "Prerequisites' (order-only, depois de '|', fora: nunca refaz o alvo), "
                    "§3.2 (-f -: makefile lido da entrada padrao, so na falta do alvo)",
    "d2.config": "PROTOCOLO_V §4.4: aresta cuja origem e arquivo de configuracao (decl) "
                 "e d6 e nunca conta para T3",
    "d2.extraido": "gcc 13 manual §3.13 'Options Controlling the Preprocessor': -MM "
                   "(cabecalhos de usuario), -MG (cabecalho ausente tratado como gerado), "
                   "-MT (nome do alvo), -I -D -U -include -imacros -iquote -isystem "
                   "-idirafter -std; bandeiras = as da linha de compilacao que o proprio "
                   "make imprime em make -p -n para aquele objeto",
    "d3": "pygments.lexers.c_cpp.CLexer (wheel fixado): tokens sem Comment.Single/"
          "Multiline/Special/Hashbang e sem Text de espaco; Comment.Preproc e "
          "Comment.PreprocFile (diretivas) mantidos com espaco colapsado. Nao-C: sha256 "
          "dos bytes. Leitura de 'sem Comment.*' (§4.5) a ratificar no V-0c, antes do DOI",
    "d6": "decl_<corpus>.json:d6_globais (PROTOCOLO_V §4.4)",
    "b_make": "GNU Make manual 4.3 §9.3 'Instead of Executing Recipes' (-t, -n), §9.7 "
              "(--debug=b: 'Must remake target'); mtimes por os.utime: arvore < alvos < semente",
    "pendentes": "GNU Make manual 4.3 §3.7/§10.8: 'No rule to make target' no stderr de "
                 "make -p -n; pre-requisito sem regra, ausente e nao declarado gerado",
}
D5 = None
D7 = "fecho_sobre_ciclo_e_conta"
_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TZ": "UTC"}
_ENV_GIT = {**_ENV, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "HOME": os.devnull}
_ALVO_AUX = "v-universo-declarado"   # alvo sintetico do -f - (nao e no do corpus)
_REGRA = re.compile(r"^([^\s#:=][^:=]*?)(::?)(?!=)\s*(.*)$")
_REFAZ = re.compile(r"Must remake target '([^']+)'")
_SEM_REGRA = re.compile(r"No rule to make target '([^']+)'")
_PP_ARG = ("-include", "-imacros", "-iquote", "-isystem", "-idirafter", "-I")
_PP_PREF = ("-I", "-D", "-U", "-std=", "-iquote", "-isystem", "-idirafter")
_PP_SOLO = ("-ansi", "-nostdinc")
_LEXER = CLexer(stripnl=False, ensurenl=True)
_INSTANCIAS: dict[str, "AdaptadorC"] = {}


def para(corpus: str) -> "AdaptadorC":
    if corpus not in _INSTANCIAS:
        _INSTANCIAS[corpus] = AdaptadorC(corpus)
    return _INSTANCIAS[corpus]


def _roda(cmd, cwd, entrada: bytes | None = None, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env or _ENV, input=entrada,
                          capture_output=True, timeout=900)


_txt = lambda b: b.decode("utf-8", "surrogateescape")  # noqa: E731


def _banco(saida: str) -> tuple[dict[str, list[str]], list[str]]:
    """Le a saida de make -p -n: (alvo -> pre-requisitos normais, comandos impressos)."""
    pedacos = saida.split("\n# Make data base, printed on", 1)
    cmds, db = pedacos if len(pedacos) == 2 else ("", saida)
    linhas = db.split("\n# Files\n", 1)[-1].split("\n# files hash-table stats", 1)[0]
    alvos: dict[str, list[str]] = {}
    nao_alvo = False
    for ln in linhas.split("\n"):
        if ln.startswith("# Not a target"):
            nao_alvo = True
        elif not ln.strip():
            nao_alvo = False
        elif not ln.startswith(("#", "\t")) and (m := _REGRA.match(ln)) and not nao_alvo:
            pre = alvos.setdefault(m.group(1).strip(), [])
            for q in m.group(3).split("|", 1)[0].split():
                if q not in pre:
                    pre.append(q)
    return alvos, cmds.replace("\\\n", " ").split("\n")


def _bandeiras(cmds: list[str], suf_fonte, suf_obj) -> dict[str, tuple[str, ...]]:
    """objeto -> opcoes de pre-processamento da linha `... -c ...` que o make imprimiu."""
    out: dict[str, tuple[str, ...]] = {}
    for ln in cmds:
        try:
            tk = shlex.split(ln)
        except ValueError:
            continue
        if "-c" not in tk:
            continue
        fontes = [t for t in tk if t.endswith(tuple(suf_fonte))]
        if not fontes:
            continue
        i = tk.index("-o") if "-o" in tk else -1
        obj = tk[i + 1] if 0 <= i < len(tk) - 1 else \
            os.path.splitext(os.path.basename(fontes[-1]))[0] + suf_obj[0]
        pp, j = [], 0
        while j < len(tk):
            t = tk[j]
            if t in _PP_ARG and j + 1 < len(tk):
                pp += [t, tk[j + 1]]
                j += 1
            elif t.startswith(_PP_PREF) or t in _PP_SOLO:
                pp.append(t)
            j += 1
        out[os.path.normpath(obj)] = tuple(pp)
    return out


class AdaptadorC:
    def __init__(self, corpus: str):
        self.corpus = corpus
        self.decl = json.loads((AQUI / f"decl_{corpus}.json").read_text(encoding="utf-8"))
        v = lambda k: self.decl[k]["valor"]  # noqa: E731
        suf = self.decl["sufixos"]
        self.suf_fonte, self.suf_cab, self.suf_obj = suf["fonte"], suf["cabecalho"], suf["objeto"]
        self.makefiles, self.alvo, self.var_u = v("makefiles"), v("alvo"), v("variavel_universo")
        self.make_args, self.config = list(v("make_args")), frozenset(v("configuracao"))
        self.gerados, self.globais = frozenset(v("cabecalho_gerado")), frozenset(v("d6_globais"))
        self.ESPEC, self.D5, self.D7 = ESPEC, D5, D7
        self._cache: dict = {}

    # ---------- d1 ----------
    def d1_nos(self, a) -> dict[str, bytes]:
        chave = ("nos", a.repo, a.sha)
        if chave not in self._cache:
            self._guarda(chave, self._ler_todos(a))
        return self._cache[chave]

    def _guarda(self, chave, valor):
        """Cache por arvore com teto (corridas longas de ensaio); o mais antigo sai primeiro."""
        while len(self._cache) >= 96:
            self._cache.pop(next(iter(self._cache)))
        self._cache[chave] = valor

    def _ler_todos(self, a) -> dict[str, bytes]:
        if not a.repo:
            return {p: a.ler(p) for p in a.listar()}
        ls = _roda(["git", "-C", a.repo, "ls-tree", "-r", "-z", a.sha], None, env=_ENV_GIT)
        ent = [r.split(b"\t", 1) for r in ls.stdout.split(b"\0") if r]
        ent = [(m.split()[2], _txt(p)) for m, p in ent if m.split()[1] == b"blob"]
        bat = _roda(["git", "-C", a.repo, "cat-file", "--batch"], None,
                    b"".join(o + b"\n" for o, _ in ent), env=_ENV_GIT).stdout
        out, k = {}, 0
        for _, p in ent:
            cab = bat.index(b"\n", k)
            n = int(bat[k:cab].split()[2])
            out[p] = bat[cab + 1:cab + 1 + n]
            k = cab + 2 + n
        return out

    def d1_tipo(self, no: str) -> str:
        if no in self.config:
            return "configuracao"
        if no in self.gerados:
            return "cabecalho_gerado"
        for tipo, suf in (("objeto", self.suf_obj), ("fonte", self.suf_fonte),
                          ("cabecalho", self.suf_cab)):
            if no.endswith(tuple(suf)):
                return tipo
        return "outro"

    def d1_elemento(self, no: str) -> str | None:
        return no if self.d1_tipo(no) == "objeto" else None

    def d1_universo(self, ap, ac) -> set[str]:
        return set(self._modelo(ap)["U"]) & set(self._modelo(ac)["U"])

    def semente(self, ap, ac) -> dict[str, str]:
        if ap.repo and ap.repo == ac.repo:
            out = _roda(["git", "-C", ap.repo, "diff", "--name-status", "-M", "-z",
                         "--no-ext-diff", ap.sha, ac.sha], None, env=_ENV_GIT).stdout
            campos, S, i = [_txt(c) for c in out.split(b"\0")], {}, 0
            while i < len(campos) and campos[i]:
                st = campos[i][0]
                n = 2 if st in "RC" else 1
                for p in campos[i + 1:i + 1 + n]:
                    S[p] = st if st in "MADR" else "M"
                i += 1 + n
            return S
        np_, nc_ = self.d1_nos(ap), self.d1_nos(ac)
        S = {p: "D" for p in np_.keys() - nc_.keys()} | {p: "A" for p in nc_.keys() - np_.keys()}
        S |= {p: "M" for p in np_.keys() & nc_.keys() if np_[p] != nc_[p]}
        return S

    def b_sem(self, S, U) -> set[str]:
        return {os.path.splitext(s)[0] + self.suf_obj[0] for s in S
                if self.d1_tipo(s) == "fonte"} & set(U)

    # ---------- d2 ----------
    def _materializa(self, a, d: str) -> None:
        for p, b in self.d1_nos(a).items():
            f = Path(d, p)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b)

    def _aux(self) -> bytes:
        return f"{_ALVO_AUX}: $({self.var_u})\n".encode()

    def _make_pn(self, a, d: str):
        """make -p -n -k no alvo declarado; sem ele, alvo sintetico com a variavel do universo
        (-f -). Devolve (rc, stdout, stderr, makefile, usou_aux) ou None sem makefile."""
        mf = next((m for m in self.makefiles if m in self.d1_nos(a)), None)
        if mf is None:
            return None
        base = ["make", "-p", "-n", "-k", "-f", mf]
        p, aux = _roda([*base, *self.make_args, self.alvo], d), False
        if self.var_u and self.alvo not in _banco(_txt(p.stdout))[0]:
            p, aux = _roda([*base, "-f", "-", *self.make_args, _ALVO_AUX], d, self._aux()), True
        return p.returncode, _txt(p.stdout), _txt(p.stderr), mf, aux

    def _modelo(self, a) -> dict:
        chave = ("modelo", a.repo, a.sha)
        if chave in self._cache:
            return self._cache[chave]
        with tempfile.TemporaryDirectory(prefix="v_cbuild_") as d:
            self._materializa(a, d)
            rc, out, err, mf, aux = self._make_pn(a, d) or (None, "", "", None, False)
            alvos, cmds = _banco(out)
            topo = _ALVO_AUX if aux else self.alvo
            U = sorted({q for q in alvos.get(topo, []) if self.d1_tipo(q) == "objeto"})
            G = nx.DiGraph()
            G.add_nodes_from(U)
            fila, vistos = list(U), set(U)
            while fila:
                t = fila.pop()
                for q in alvos.get(t, []):
                    orig = "config" if self.d1_tipo(q) == "configuracao" else "declarada"
                    G.add_edge(q, t, origem=orig)
                    if q not in vistos:
                        vistos.add(q)
                        fila.append(q)
            fontes = {o: [q for q in G.predecessors(o) if self.d1_tipo(q) == "fonte"] for o in U}
            m = {"U": U, "G": G, "fontes": fontes, "mf": mf, "aux": aux, "rc": rc,
                 "flags": _bandeiras(cmds, self.suf_fonte, self.suf_obj),
                 "sem_regra": sorted(set(_SEM_REGRA.findall(err)))}
        self._guarda(chave, m)
        return m

    def d2_declarado(self, a) -> nx.DiGraph:
        return self._modelo(a)["G"].copy()

    def d2_extraido(self, a) -> tuple[nx.DiGraph, dict]:
        chave = ("obs", a.repo, a.sha)
        if chave in self._cache:
            G, cob = self._cache[chave]
            return G.copy(), dict(cob)
        m = self._modelo(a)
        G = nx.DiGraph()
        G.add_nodes_from(m["U"])
        G.add_edges_from((u, v, d) for u, v, d in m["G"].edges(data=True)
                         if d["origem"] == "config")
        ok = 0
        with tempfile.TemporaryDirectory(prefix="v_cbuild_mm_") as d:
            self._materializa(a, d)
            for o in m["U"]:
                bons = 0
                for src in m["fontes"][o]:
                    p = _roda(["gcc", "-MM", "-MG", "-MT", o, *m["flags"].get(o, ()), src], d)
                    if p.returncode != 0:
                        continue
                    bons += 1
                    deps = _txt(p.stdout).replace("\\\n", " ").split(":", 1)[-1].split()
                    for q in (os.path.normpath(x) for x in deps):   # include real = conteudo
                        if not q.startswith(("/", "..")) and not G.has_edge(q, o):
                            G.add_edge(q, o, origem="extraida")
                ok += bool(m["fontes"][o]) and bons == len(m["fontes"][o])
        cob = {"c_total": len(m["U"]), "c_ok": int(ok)}
        self._guarda(chave, (G, cob))
        return G.copy(), dict(cob)

    def grafo(self, ap, ac) -> nx.DiGraph:
        return nx.compose(self.d2_declarado(ap), self.d2_declarado(ac))

    def grafo_obs(self, ap, ac) -> tuple[nx.DiGraph, dict]:
        (gp, cp), (gc, cc) = self.d2_extraido(ap), self.d2_extraido(ac)
        return nx.compose(gp, gc), {"p": cp, "c": cc}

    def pendentes(self, a) -> set[str]:
        m, nos = self._modelo(a), self.d1_nos(a)
        orfaos = {n for n in m["G"] if m["G"].in_degree(n) == 0 and n not in nos
                  and self.d1_tipo(n) not in ("cabecalho_gerado", "objeto")}
        return (orfaos | set(m["sem_regra"])) - self.gerados - {self.alvo}

    # ---------- d3, d4, d6, d8 ----------
    def d3_checksum(self, no: str, a) -> str | None:
        b = self.d1_nos(a).get(no)
        if b is None:
            return None
        if self.d1_tipo(no) not in ("fonte", "cabecalho", "cabecalho_gerado"):
            return hashlib.sha256(b).hexdigest()
        return hashlib.sha256(json.dumps(tokens_d3(b)).encode()).hexdigest()

    def d4_intervalos(self, a) -> None:      # d4: so tz (§5)
        return None

    d4_alteradas = staticmethod(lambda R, ap, ac: None)

    def d6_globais(self, a) -> set[str]:
        return {g for g in self.globais if g in self.d1_nos(a)}

    def d8_nao_det(self, a) -> set[str]:
        return set(self.decl["d8_nao_det"]["valor"])

    def placebo_globs(self) -> list[str]:
        return list(self.decl["placebo_globs"]["valor"])

    # ---------- B-make e diferencial do parser (§4.4, §5) ----------
    def b_make(self, ac, S) -> set[str]:
        """make -t; mtime da semente > alvos > arvore; make -n --debug=b; objetos do universo
        com regra (sem regra, make erra em vez de refazer: fica fora)."""
        m = self._modelo(ac)
        if m["mf"] is None:
            return set()
        opc_aux = (["-f", "-"], self._aux()) if m["aux"] else ([], None)
        alvo = _ALVO_AUX if m["aux"] else self.alvo
        with tempfile.TemporaryDirectory(prefix="v_cbuild_bm_") as d:
            self._materializa(ac, d)
            for n in m["G"]:            # make -t nao cria diretorio do alvo (ex.: objs/x.o)
                Path(d, n).parent.mkdir(parents=True, exist_ok=True)
            arvore = set(self.d1_nos(ac))
            for g in self.gerados - arvore:   # cabecalho gerado (decl): vazio, como arvore
                if g in m["G"]:
                    Path(d, g).write_bytes(b"")
                    arvore.add(g)
            base = ["make", "-k", "-f", m["mf"], *opc_aux[0], *self.make_args]
            _roda([*base[:1], "-t", *base[1:], alvo], d, opc_aux[1])
            for raiz, _, arqs in os.walk(d):
                for f in arqs:
                    rel = os.path.relpath(os.path.join(raiz, f), d)
                    t = 1_000_000_000 if rel in arvore else 1_000_000_100
                    os.utime(os.path.join(raiz, f), (t, t))
            for s in set(S) & set(self.d1_nos(ac)):   # so arquivo real do lado c
                os.utime(os.path.join(d, s), (1_000_000_200, 1_000_000_200))
            p = _roda([*base[:1], "-n", "--debug=b", *base[1:], alvo], d, opc_aux[1])
        return (set(_REFAZ.findall(_txt(p.stdout))) & set(m["U"])) - set(m["sem_regra"])


def tokens_d3(b: bytes) -> list[tuple[str, str]]:
    """Tokens do CLexer sem comentario nem espaco (porta d3, §4.5); diretivas mantidas."""
    out = []
    for t, v in _LEXER.get_tokens(b.decode("latin-1")):
        diretiva = t in Comment.Preproc or t in Comment.PreprocFile
        if t in Comment and not diretiva:
            continue
        if diretiva:
            v = " ".join(v.split()) or ("\n" if "\n" in v else "")
        elif t in Text and not v.strip():
            continue
        if v:
            out.append((str(t), v))
    return out


def diferencial_parser(A: AdaptadorC, a, S, reach) -> dict:
    """§4.4: make -n depois de tocar S == U ∩ reach(G_decl(a), S ∩ arquivos(a)). `reach` vem
    do runner (nucleo), para o adaptador nao importar o nucleo. Objeto inconstruivel (ele ou um
    ancestral em G_decl sem regra: 'No rule to make target') fica fora dos dois lados: make erra
    nele em vez de decidir por aresta."""
    S_a = {s for s in S if s in A.d1_nos(a)}
    m, falta = A._modelo(a), set(A._modelo(a)["sem_regra"])
    inviavel = {o for o in m["U"] if o in falta or falta & nx.ancestors(m["G"], o)}
    via_make = A.b_make(a, S_a) - inviavel
    via_reach = set(reach(m["G"], S_a)) & set(m["U"]) - inviavel
    return {"igual": via_make == via_reach, "so_make": sorted(via_make - via_reach),
            "so_reach": sorted(via_reach - via_make), "S": sorted(S_a), "aux": m["aux"],
            "sem_regra": m["sem_regra"], "inconstruiveis": sorted(inviavel)}
