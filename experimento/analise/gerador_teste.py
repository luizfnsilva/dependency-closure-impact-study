"""GERADOR SINTETICO — SO PARA OS TESTES DE analise.py. NUNCA PARA DADO REAL.

Monta registros por par no formato de INTERFACES §1 a partir de conjuntos escritos a mao
no teste. Nao le repositorio, oraculo, grafo, adaptador, detector nem gancho; nao importa
nenhum modulo do experimento (nem analise.py: a cadeia e a precedencia daqui sao
reescritas de forma independente, para que o teste confira a analise contra outra
implementacao).

Separacao estrutural (conferida em test_analise.py):
  - todo registro sai com janela "teste_sintetico" e oraculo "gerador_teste"; analise.py
    recusa esses valores nos modos confirmatorio e ensaio (codigo 3);
  - gravar() recusa qualquer destino dentro de experimento/saidas/;
  - analise.py nao importa este modulo.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

JANELA = "teste_sintetico"
ORACULO = "gerador_teste"
_SAIDAS_PROIBIDAS = (Path(__file__).resolve().parents[1] / "saidas").resolve()

BRACOS = ("A0", "A0+d3", "A0+d4-ingenuo", "A0+d4-preciso", "A0+d2-extraido", "A0+d6",
          "A_full", "B-ret", "B-sem", "B-make")
APLICA = {
    "tz": ("A0", "A0+d3", "A0+d4-ingenuo", "A0+d4-preciso", "A_full", "B-ret", "B-sem"),
    "zlib": ("A0", "A0+d3", "A0+d2-extraido", "A0+d6", "A_full", "B-ret", "B-sem", "B-make"),
    "lua": ("A0", "A0+d3", "A0+d2-extraido", "A_full", "B-ret", "B-sem", "B-make"),
}
_PADRAO = {"FN": "INCLASSIFICADO-FN", "FP": "T5"}


def sha_falso(*partes) -> str:
    return hashlib.sha1(("teste:" + ":".join(map(str, partes))).encode()).hexdigest()


def _braco(eis, ais: set) -> dict:
    E = set(eis)
    return {"EIS": sorted(E), "FN": sorted(ais - E), "FP": sorted(E - ais), "seguro": not (ais - E)}


def par(corpus: str, i: int, U, AIS, eis: dict | None = None, rotulos: dict | None = None, *,
        nc: bool = False, controle: str | None = None, ano: int = 2015,
        r_tipo: dict | None = None, sens: dict | None = None, nd: int = 0,
        primarios: dict | None = None, extra: dict | None = None) -> dict:
    """Um par executado. eis: braco -> conjunto EIS (A0 obrigatorio no uso real do teste;
    ganchos ausentes herdam o EIS de A0; B-ret = U; B-sem = vazio; B-make = EIS de A0).
    rotulos: elemento -> lista multirrotulo (padrao: FP -> T5, FN -> INCLASSIFICADO-FN).
    primarios: elemento -> primario gravado (para testar a conferencia)."""
    U, A = set(U), set(AIS)
    eis = dict(eis or {})
    e0 = set(eis.get("A0", ()))
    padrao = {"B-ret": U, "B-sem": set()}
    bracos = {b: (_braco(eis.get(b, padrao.get(b, e0)), A) if b in APLICA[corpus] else None)
              for b in BRACOS}
    a0 = bracos["A0"]
    rot = rotulos or {}
    inst = []
    for lado in ("FN", "FP"):
        for e in a0[lado]:
            d = {"e": e, "lado": lado, "multi": list(rot.get(e, [_PADRAO[lado]]))}
            if primarios and e in primarios:
                d["primario"] = primarios[e]
            inst.append(d)
    reg = {"v": 1, "corpus": corpus, "janela": JANELA, "controle": controle,
           "p": sha_falso(corpus, i, "p", controle), "c": sha_falso(corpus, i, "c", controle),
           "data_p": f"{ano}-01-01T00:00:00Z", "data_c": f"{ano}-01-02T00:00:00Z", "ano": ano,
           "semente_sorteio": 0, "nao_executado": None,
           "oraculo": {"modo": ORACULO, "dig": None},
           "U": sorted(U), "S": {}, "AIS": sorted(A), "bracos": bracos, "instancias": inst,
           "nc": nc, "r_tipo": r_tipo, "sens": sens,
           "descritores": {"NAO_DETERMINISTICO": {"p": [f"nd{j}" for j in range(nd)], "c": []},
                           "MUDANCA_DE_IDENTIDADE": [], "CICLO": [], "PENDENTE": [],
                           "GRAFO_VAZIO": False}}
    reg.update(extra or {})
    return reg


def nao_executado(corpus: str, i: int, causa: str, ano: int = 2015) -> dict:
    return {"v": 1, "corpus": corpus, "janela": JANELA, "controle": None,
            "p": sha_falso(corpus, i, "p"), "c": sha_falso(corpus, i, "c"),
            "data_c": f"{ano}-01-02T00:00:00Z", "ano": ano, "semente_sorteio": 0,
            "nao_executado": {"causa": causa, "detalhe": "gerador de teste"},
            "oraculo": {"modo": ORACULO, "dig": None}, "U": [], "S": {}, "AIS": [],
            "bracos": {b: None for b in BRACOS}, "instancias": [], "nc": False,
            "r_tipo": None, "sens": None, "descritores": {}}


def config_teste(pasta: Path, **sobre) -> tuple[Path, str]:
    cfg = {"v": 1, "doi": None, "uso": "SO TESTE",
           "sementes": {"principal": None, "ensaio": 0, "bootstrap": 10000}}
    cfg.update(sobre)
    p = Path(pasta) / "config.json"
    p.write_text(json.dumps(cfg, sort_keys=True), encoding="utf-8")
    return p, hashlib.sha256(p.read_bytes()).hexdigest()


def _linha(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def gravar(caminho: Path, registros: list[dict], sha_cfg: str) -> Path:
    """Grava com sha_config e cadeia h_i = sha256(linha anterior || JSON sem h)."""
    caminho = Path(caminho).resolve()
    if _SAIDAS_PROIBIDAS in caminho.parents:
        raise RuntimeError("gerador de teste nao grava em experimento/saidas/")
    anterior, linhas = sha_cfg.encode("ascii"), []
    for r in registros:
        r = {k: v for k, v in r.items() if k != "h"}
        r["sha_config"] = sha_cfg
        r["h"] = hashlib.sha256(anterior + _linha(r)).hexdigest()
        anterior = _linha(r)
        linhas.append(anterior)
    caminho.write_bytes(b"".join(L + b"\n" for L in linhas))
    return caminho
