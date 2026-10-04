"""Quadro de pares e janelas do experimento V (PROTOCOLO_V_2026-10-02 §2.5, §12.2; INTERFACES §0).

So enumeracao: `git` (historico, datas, nomes de arquivo de cada diff) e, no tz, a leitura do
Makefile de cada commit pelo adaptador (`make -pn`, expansao de TDATA). Nenhum oraculo, nenhum EIS,
nenhum detector, nenhum gancho. Os limites (commits e datas) vem de config.json (corpora.*).

Janela de cada commit (decidida por ancestralidade git, SHA completo, e por data absoluta):
  tz   : ensaio  <=> sha e ancestral (ou igual) de corpora.tz.ensaio_ultimo
         quadro  <=> max(data de autor, data de commit) >= corpora.tz.data_min (00:00 UTC)
  zlib : ensaio  <=> ensaio[0] ancestral-ou-igual de sha E sha ancestral-ou-igual de ensaio[1]
         quadro  <=> corpora.zlib.apos e ancestral estrito de sha
  lua  : ensaio  <=> datas de autor e de commit < data_min; quadro <=> alguma >= data_min
  Um sha que seja os dois, ou nenhum dos dois, e "fora" (abortaria qualquer modo).

Uso:
  python quadro.py contagem tz|zlib|lua <repo>     # contagens do quadro (§12.2), sem tocar o oraculo
  python quadro.py tdata <repo_tz> [saida.json]    # contagem exata TDATA-por-commit (V-0c)
  python quadro.py pares tz|zlib|lua <repo> [--modo ensaio|confirmatorio] [--saida X.tsv]
"""
from __future__ import annotations

import fnmatch
import json
import random
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from integridade import CONFIG, RAIZ  # noqa: E402


def git(repo: str, *args: str, ok: bool = False):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if ok:
        return p.returncode == 0
    p.check_returncode()
    return p.stdout


def epoca(data: str) -> int:
    """AAAA-MM-DD -> segundos UTC 00:00."""
    return int(datetime.strptime(data, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def carregar_cfg(caminho: str | Path = CONFIG) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


class Janela:
    """Classifica commits de um clone em quadro / ensaio / fora (INTERFACES §0)."""

    def __init__(self, corpus: str, repo: str, cfg: dict):
        self.corpus, self.repo = corpus, repo
        self.c = cfg["corpora"][corpus]
        self._cache: dict[str, str] = {}
        self._datas: dict[str, tuple[int, int]] = {}
        self._ens: frozenset[str] | None = None
        if corpus == "tz":
            self._ens = frozenset(git(repo, "rev-list", self.c["ensaio_ultimo"]).split())

    def datas(self, sha: str) -> tuple[int, int]:
        if sha not in self._datas:
            a, c = git(self.repo, "log", "-1", "--format=%at %ct", sha).split()
            self._datas[sha] = (int(a), int(c))
        return self._datas[sha]

    def _anc(self, a: str, b: str) -> bool:        # a ancestral-ou-igual de b
        return git(self.repo, "merge-base", "--is-ancestor", a, b, ok=True)

    def _flags(self, sha: str) -> tuple[bool, bool]:
        c, lim = self.c, epoca(self.c.get("data_min", "1970-01-01"))
        if self.corpus == "tz":
            return (sha in self._ens), max(self.datas(sha)) >= lim
        if self.corpus == "zlib":
            ens = self._anc(c["ensaio"][0], sha) and self._anc(sha, c["ensaio"][1])
            return ens, (sha != c["apos"] and self._anc(c["apos"], sha))
        return max(self.datas(sha)) < lim, max(self.datas(sha)) >= lim

    def classe(self, sha: str) -> str:
        if sha not in self._cache:
            ens, quad = self._flags(sha)
            self._cache[sha] = "fora" if ens == quad else ("ensaio" if ens else "quadro")
        return self._cache[sha]


# ------------------------------------------------------------------ historico
def historico(repo: str, topo: str) -> list[dict]:
    """Todo commit alcancavel de `topo`: {c, pais, ta, tc}, ordenado por data de autor e sha."""
    out = []
    for ln in git(repo, "log", "--format=%H|%P|%at|%ct", topo).splitlines():
        h, pais, ta, tc = ln.split("|")
        out.append({"c": h, "pais": pais.split(), "ta": int(ta), "tc": int(tc)})
    return sorted(out, key=lambda d: (d["ta"], d["c"]))


def mudados(repo: str, p: str, c: str) -> list[str]:
    return [x for x in git(repo, "diff", "--name-only", "--no-renames", p, c).split("\n") if x]


def _casa(caminho: str, globs: list[str], raiz: bool) -> bool:
    if raiz and "/" in caminho:
        return False
    return any(fnmatch.fnmatchcase(caminho, g) for g in globs)


def _data_iso(repo: str, sha: str) -> str:
    return git(repo, "log", "-1", "--format=%aI", sha).strip()


# ------------------------------------------------------------------ tz: TDATA por commit
def dados_tz(repo: str, sha: str) -> list[str]:
    """Arquivos de dados do commit (TDATA do Makefile, sem backzone), pelo adaptador (make -pn)."""
    from adaptadores import tz
    from adaptadores.git_arvore import Arvore
    return tz.arquivos_dados(Arvore(repo, sha))


def tdata_por_commit(repo: str, cfg: dict) -> dict:
    """§12.2: contagem exata do quadro tz pela regra TDATA-por-commit. So enumeracao."""
    from adaptadores import tz
    from adaptadores.git_arvore import Arvore
    c = cfg["corpora"]["tz"]
    lim = epoca(c["data_min"])
    reserva = tz._DECL["tdata_reserva"]["valor"]
    cont: Counter = Counter()
    por_ano: Counter = Counter()
    sem_tdata_def: list[str] = []
    cache: dict[str, tuple[frozenset[str], bool]] = {}

    def conj(sha: str) -> tuple[frozenset[str], bool]:
        if sha not in cache:
            a = Arvore(repo, sha)
            mk = a.ler(tz._DECL["makefile"]["valor"])
            exp = tz._expandir(mk, tz._DECL["variavel_dados"]["valor"]) if mk is not None else None
            cache[sha] = (frozenset(tz.arquivos_dados(a)), bool(exp))
        return cache[sha]

    for h in historico(repo, c["congelamento"]):
        if not h["pais"]:
            cont["raiz_sem_pai"] += 1
            continue
        datas = {"autor": h["ta"], "commit": h["tc"]}
        em = {k: v >= lim for k, v in datas.items()}
        if not any(em.values()):
            continue
        cont["commits_com_data>=min(autor ou commit)"] += 1
        cont["commits_com_data>=min(autor)"] += em["autor"]
        cont["commits_com_data>=min(commit)"] += em["commit"]
        cont["commits_com_data>=min(autor e commit)"] += all(em.values())
        p, cc = h["pais"][0], h["c"]
        mud = set(mudados(repo, p, cc))
        (dp, tp), (dc, tc_) = conj(p), conj(cc)
        uniao = dp | dc
        toca = bool(mud & uniao)
        toca_fixa = bool(mud & set(reserva))
        toca_com_backzone = bool(mud & (uniao | {"backzone"}))
        toca_tdata_c = bool(mud & dc)
        toca_tdata_p = bool(mud & dp)
        cont["toca_TDATA(p uniao c)  [REGRA DO PROTOCOLO]"] += toca
        cont["toca_TDATA(c)"] += toca_tdata_c
        cont["toca_TDATA(p)"] += toca_tdata_p
        cont["toca_lista_fixa(reserva)"] += toca_fixa
        cont["toca_TDATA_com_backzone"] += toca_com_backzone
        cont["merge(2+ pais)"] += len(h["pais"]) > 1
        if toca:
            ano = datetime.fromtimestamp(h["ta"], timezone.utc).year
            por_ano[ano] += 1
            cont["quadro_sem_Makefile_TDATA_em_p_ou_c(usa lista fixa)"] += (not tp) or (not tc_)
            if toca != toca_fixa:
                cont["quadro_difere_da_lista_fixa"] += 1
                sem_tdata_def.append(cc)
    return {"regra": "commit com data (autor ou commit) >= data_min, primeiro pai p, "
                     "diff(p,c) toca arquivo de TDATA(p) uniao TDATA(c) sem backzone (§2.5)",
            "data_min": c["data_min"], "congelamento": c["congelamento"],
            "contagens": dict(sorted(cont.items())), "quadro_por_ano_de_autor": dict(sorted(por_ano.items())),
            "commits_onde_TDATA_difere_da_lista_fixa": sem_tdata_def[:50]}


# ------------------------------------------------------------------ quadro por corpus
def pares_quadro(corpus: str, repo: str, cfg: dict) -> list[dict]:
    """Pares (c, p primeiro pai) do QUADRO por regra mecanica (§2.5). So enumeracao."""
    c = cfg["corpora"][corpus]
    J = Janela(corpus, repo, cfg)
    out = []
    for h in historico(repo, c["congelamento"]):
        if not h["pais"] or J.classe(h["c"]) != "quadro":
            continue
        p = h["pais"][0]
        mud = mudados(repo, p, h["c"])
        if corpus == "tz":
            alvo = set(dados_tz(repo, p)) | set(dados_tz(repo, h["c"]))
            if not set(mud) & alvo:
                continue
        elif not any(_casa(m, c["quadro_globs"], c.get("quadro_so_raiz", True)) for m in mud):
            continue
        out.append({"c": h["c"], "p": p, "data_c": _data_iso(repo, h["c"]), "janela": "quadro",
                    "controle": None})
    return out


def pares_ensaio(corpus: str, repo: str, cfg: dict) -> list[dict]:
    """Pares (c, p) cuja AMBAS as pontas estao na janela de ensaio (§2.5). Mesmas regras do quadro."""
    c = cfg["corpora"][corpus]
    J = Janela(corpus, repo, cfg)
    topo = c["ensaio_ultimo"] if corpus == "tz" else c["ensaio"][1] if corpus == "zlib" else c["congelamento"]
    out = []
    for h in historico(repo, topo):
        if not h["pais"] or J.classe(h["c"]) != "ensaio" or J.classe(h["pais"][0]) != "ensaio":
            continue
        p = h["pais"][0]
        mud = mudados(repo, p, h["c"])
        if corpus == "tz":
            if not set(mud) & (set(dados_tz(repo, p)) | set(dados_tz(repo, h["c"]))):
                continue
        elif not any(_casa(m, c["quadro_globs"], c.get("quadro_so_raiz", True)) for m in mud):
            continue
        out.append({"c": h["c"], "p": p, "data_c": _data_iso(repo, h["c"]), "janela": "ensaio",
                    "controle": None})
    return out


def pares_placebo(corpus: str, repo: str, cfg: dict, janela: str, globs: list[str],
                  excluir: set[str], semente: str, maximo: int) -> list[dict]:
    """Commits da janela cujos arquivos mudados casam TODOS com os globs de placebo (fora de todo
    universo, §5), fora dos pares principais; amostra semeada de ate `maximo`."""
    c = cfg["corpora"][corpus]
    J = Janela(corpus, repo, cfg)
    topo = (c["ensaio_ultimo"] if corpus == "tz" else c["ensaio"][1] if corpus == "zlib"
            else c["congelamento"]) if janela == "ensaio" else c["congelamento"]
    pool = []
    for h in historico(repo, topo):
        if not h["pais"] or h["c"] in excluir or J.classe(h["c"]) != janela:
            continue
        p = h["pais"][0]
        if janela == "ensaio" and J.classe(p) != "ensaio":
            continue
        mud = mudados(repo, p, h["c"])
        if mud and all(any(fnmatch.fnmatchcase(m, g) for g in globs) for m in mud):
            pool.append({"c": h["c"], "p": p, "data_c": _data_iso(repo, h["c"]), "janela": janela,
                         "controle": "placebo"})
    pool.sort(key=lambda d: d["c"])
    if len(pool) > maximo:
        pool = sorted(random.Random(semente).sample(pool, maximo), key=lambda d: d["c"])
    return sorted(pool, key=lambda d: (d["data_c"], d["c"]))


def pares_tag_tz(repo: str, cfg: dict) -> list[dict]:
    """Sensibilidade §2.5: pares de tags consecutivas 2012e -> 2026e (c = tag posterior)."""
    c = cfg["corpora"]["tz"]
    J = Janela("tz", repo, cfg)
    tags = [t for t in git(repo, "tag", "--sort=creatordate").split() if len(t) == 5
            and t[:4].isdigit() and t[4].isalpha()]
    ini, fim = c["tags"]["primeira"], c["tags"]["ultima"]
    tags = tags[tags.index(ini): tags.index(fim) + 1]
    sha = {t: git(repo, "rev-list", "-n1", t).strip() for t in tags}
    return [{"c": sha[b], "p": sha[a], "data_c": _data_iso(repo, sha[b]),
             "janela": J.classe(sha[b]), "controle": "tag"} for a, b in zip(tags, tags[1:])]


def amostra_lua(pares: list[dict], principal: int | str, n: int) -> list[dict]:
    """Amostra uniforme sem reposicao, populacao ordenada pelo sha de c (INTERFACES §3)."""
    pop = sorted(pares, key=lambda d: d["c"])
    if len(pop) <= n:
        return pop
    return sorted(random.Random(f"{principal}:lua_amostra").sample(pop, n), key=lambda d: d["c"])


def montar_lista(modo: str, corpus: str, repo: str, cfg: dict, amostra: int | None = None) -> list[dict]:
    """Lista final de execucao: principais (ordem cronologica), cada um seguido do seu nulo
    (um por p distinto), mais placebo e tag. `modo` em {ensaio, confirmatorio}."""
    c = cfg["corpora"][corpus]
    sem = cfg["sementes"]
    from adaptadores import cbuild, tz as tz_ad
    globs = tz_ad.placebo_globs() if corpus == "tz" else cbuild.para(corpus).placebo_globs()
    if modo == "ensaio":
        base, semente = pares_ensaio(corpus, repo, cfg), sem.get("ensaio", 0)
    else:
        base, semente = pares_quadro(corpus, repo, cfg), sem.get("principal")
        if corpus == "lua" and semente is not None:
            base = amostra_lua(base, semente, c["amostra"])
    if semente is None:
        raise ValueError("lista confirmatoria exige sementes.principal (primeiros 64 bits do sha256 do deposito, §2.5)")
    base.sort(key=lambda d: (d["data_c"], d["c"]))
    if amostra and amostra < len(base):
        base = sorted(random.Random(f"{semente}:amostra_{corpus}").sample(base, amostra),
                      key=lambda d: (d["data_c"], d["c"]))
    plac = pares_placebo(corpus, repo, cfg, "ensaio" if modo == "ensaio" else "quadro", globs,
                         {d["c"] for d in base}, f"{semente}:placebo:{corpus}",
                         cfg["controles"]["placebo_max"])
    tags = pares_tag_tz(repo, cfg) if corpus == "tz" and modo == "confirmatorio" else []
    lista, nulos = [], set()
    for d in base:
        lista.append(d)
        if cfg["controles"]["nulo_por_commit"] and d["p"] not in nulos:
            nulos.add(d["p"])
            lista.append({"c": d["p"], "p": d["p"], "data_c": _data_iso(repo, d["p"]),
                          "janela": d["janela"], "controle": "nulo", "de": d["c"]})
    return lista + plac + tags


# ------------------------------------------------------------------ CLI
def _contagem(corpus: str, repo: str, cfg: dict) -> dict:
    pares = pares_quadro(corpus, repo, cfg)
    por_ano = Counter(p["data_c"][:4] for p in pares)
    return {"corpus": corpus, "quadro": len(pares), "por_ano": dict(sorted(por_ano.items()))}


def main(argv: list[str] | None = None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    cfg = carregar_cfg()
    if len(a) >= 3 and a[0] == "contagem":
        print(json.dumps(_contagem(a[1], a[2], cfg), indent=1))
    elif len(a) >= 2 and a[0] == "tdata":
        r = tdata_por_commit(a[1], cfg)
        txt = json.dumps(r, indent=1, ensure_ascii=False)
        if len(a) > 2:
            Path(a[2]).write_text(txt + "\n", encoding="utf-8")
        print(txt)
    elif len(a) >= 3 and a[0] == "pares":
        modo = a[a.index("--modo") + 1] if "--modo" in a else "confirmatorio"
        lista = montar_lista(modo, a[1], a[2], cfg)
        saida = Path(a[a.index("--saida") + 1]) if "--saida" in a else RAIZ / "saidas" / f"pares_{a[1]}.tsv"
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text("c\tp\tdata_c\tjanela\tcontrole\n" + "".join(
            f"{d['c']}\t{d['p']}\t{d['data_c']}\t{d['janela']}\t{d['controle'] or '-'}\n" for d in lista),
            encoding="utf-8")
        print(f"{len(lista)} linhas em {saida}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
