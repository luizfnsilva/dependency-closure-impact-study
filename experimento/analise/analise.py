#!/usr/bin/env python3
"""Analise do experimento V (PROTOCOLO_V_2026-10-02 §6, §7, §8; INTERFACES §1, §2.6).

So le os registros por par (JSONL encadeado por hash, INTERFACES §1) e o config.json. Nao
toca repositorio, oraculo, grafo, adaptador, detector nem gancho: nao importa nenhum modulo
do experimento. So biblioteca padrao; testes exatos em math.comb + fractions (sem scipy).

Saidas (na pasta de saida):
  por_par_<corpus>.csv        §6.1, uma linha por par x braco (NAO_EXECUTADO contado)
  resumo_bracos_<corpus>.csv  §6.1 agregado por braco DENTRO do corpus
  por_classe_<corpus>.csv     §6.2: atribuicao primaria, multirrotulo, precedencia alt_c e
                              ablacao (§4.6 a-c); Wilson 95% por pares; bootstrap por par
                              (10^4) para fracoes de instancias; "nao_exercida" se < 5
  hipoteses.json              §7 H1a-H8, Holm sobre {H1a,H1b,H8}, regra do §8
  mcnemar.json                §6.3, A0 x A0+gancho, pareado, descritivo
  sensibilidades.json         §6.4
  descritores.csv             §4.7, por corpus x ano
  controles.json              §5, pares nulos e placebo
  relatorio.md                as mesmas tabelas em Markdown
Nada e somado entre corpora (§6.3). O Lua (replica) sai em arquivos e secoes proprios.

Modos (guardas):
  confirmatorio (padrao): entradas saidas/{tz,zlib,lua,npm}.jsonl; exige config.json com
      doi, sementes.principal = primeiros 64 bits de protocolo.sha256_deposito,
      sementes.bootstrap = 10^4 e modulos["analise/analise.py"] = sha256 deste arquivo
      (codigo 2 se faltar); registros com janela "quadro", oraculo "real", sha_config e
      cadeia integros (codigo 3 se divergir).
  --ensaio: arquivos explicitos de saidas/ensaio/; janela "ensaio", oraculo "sintetico";
      toda saida marcada ENSAIO; nunca e resultado (§11.3).
  --teste: so registros do gerador de teste (janela "teste_sintetico"); marca TESTE.

Leituras declaradas (escolhas de implementacao, todas antes dos dados):
  L1 "classe nao exercida" (§6.2) conta as instancias em MULTIRROTULO da classe no corpus
     (a regra da classe casou), nao so as primarias.
  L2 ablacao (§4.6 b): ganchos isolados = os que entram em A_full (d3, d4-preciso,
     d2-extraido, d6, conforme o corpus); d4-ingenuo e braco de teste da H4 e fica fora.
     Instancia removida por 1 gancho isolado -> esse gancho; por >= 2 -> SOBREPOSTA;
     por nenhum isolado mas por A_full -> COMPOSTA; por nenhum -> NAO_REMOVIDA.
  L3 §8: dominio tz = {tz}; dominio build C = {zlib, lua} (os corpora confirmatorios do
     §2.2); a linha so com zlib sai ao lado, descritiva.
  L4 Holm com a familia fixa de 3; hipotese nao testavel entra com p = 1 (conservador) e
     sai como nao testavel, nunca como refutada ou confirmada.
  L5 H7 usa os efeitos gravados em r_tipo (so regras com efeito); com r_tipo ausente em
     algum par executado do corpus, a H7 ali e "incompleta" (sem decisao).
  L6 H8 replica (tz x Lua) sai descritiva, fora da familia Holm.
  L7 sensibilidades: W' e atribuicao anterior recalculam FN/FP/seguro; rotulos, NC e r_tipo
     nao sao recalculaveis sem os detectores e saem "nao_recalculada".
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from operator import itemgetter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]          # experimento/
ESTE_ARQUIVO = Path(__file__).resolve()
CHAVE_MODULO = "analise/analise.py"

ALFA = 0.05
P0_H1 = Fraction(2, 100)                 # H1a/H1b: H0 p >= 0,02 (§7)
LIMIAR_EXERCIDA = 5                      # §6.2
LIMIAR_H5_N = 30                         # §7 H5
LIMIAR_H5_FRAC = Fraction(1, 10)
LIMIAR_PREC_S8 = 0.90                    # §8
B_PROTOCOLO = 10_000                     # §6.2
Z95 = statistics.NormalDist().inv_cdf(0.975)

CORPORA = ("tz", "zlib", "lua", "npm")
CONFIRMATORIOS = ("tz", "zlib", "lua")
BRACOS = ("A0", "A0+d3", "A0+d4-ingenuo", "A0+d4-preciso", "A0+d2-extraido", "A0+d6",
          "A_full", "B-ret", "B-sem", "B-make")
APLICA = {                                          # §5 / INTERFACES §1
    "tz": {"A0", "A0+d3", "A0+d4-ingenuo", "A0+d4-preciso", "A_full", "B-ret", "B-sem"},
    "zlib": {"A0", "A0+d3", "A0+d2-extraido", "A0+d6", "A_full", "B-ret", "B-sem", "B-make"},
    "lua": {"A0", "A0+d3", "A0+d2-extraido", "A_full", "B-ret", "B-sem", "B-make"},
}
GANCHOS = ("A0+d3", "A0+d4-ingenuo", "A0+d4-preciso", "A0+d2-extraido", "A0+d6", "A_full")
ISOLADOS = {"tz": ("A0+d3", "A0+d4-preciso"),                      # L2
            "zlib": ("A0+d3", "A0+d2-extraido", "A0+d6"),
            "lua": ("A0+d3", "A0+d2-extraido")}
CLASSE_DO_GANCHO = {"A0+d3": "T2", "A0+d4-preciso": "T1a", "A0+d2-extraido": "T3",
                    "A0+d6": "T4"}
H3_GANCHOS = {"tz": ("A0+d3", "A0+d4-preciso"), "zlib": ("A0+d3", "A0+d2-extraido"),
              "lua": ("A0+d3", "A0+d2-extraido")}

ORDEM = {   # §4.6: precedencia padrao e alternativa (c)
    "padrao": {"FN": ("T4", "T3-FN", "T1b", "INCLASSIFICADO-FN"),
               "FP": ("T3-FP", "T2", "T1a", "T5")},
    "alt_c": {"FN": ("T4", "T3-FN", "T1b", "INCLASSIFICADO-FN"),
              "FP": ("T2", "T3-FP", "T1a", "T5")},
}
CLASSES = {  # classes aplicaveis por corpus e lado (§4.5)
    "tz": {"FN": {"INCLASSIFICADO-FN"}, "FP": {"T2", "T1a", "T5"}},
    "zlib": {"FN": {"T4", "T3-FN", "INCLASSIFICADO-FN"}, "FP": {"T3-FP", "T2", "T5"}},
    "lua": {"FN": {"T4", "T3-FN", "INCLASSIFICADO-FN"}, "FP": {"T3-FP", "T2", "T5"}},
    "npm": {"FN": {"T1b", "INCLASSIFICADO-FN"}, "FP": {"T5"}},
}
EXCLUSIVOS = {"FN": "INCLASSIFICADO-FN", "FP": "T5"}
CAUSAS = {"nao_constroi_p", "nao_constroi_c", "zic_recusa_p", "zic_recusa_c", "teto"}
CONTROLES = (None, "nulo", "placebo", "tag")
ENSAIO_PREENCHE = ("nao_executado",)   # INTERFACES §1; ausente nos JSONL do ensaio V-0b
OBRIGATORIOS = ("corpus", "janela", "controle", "p", "c", "nao_executado", "oraculo", "U",
                "S", "AIS", "bracos", "instancias")
MODOS = {  # modo -> (janela exigida, oraculo exigido, marca)
    "confirmatorio": ("quadro", "real", "CONFIRMATORIO"),
    "ensaio": ("ensaio", "sintetico", "ENSAIO"),
    "teste": ("teste_sintetico", "gerador_teste", "TESTE"),
}


class Recusa(Exception):
    """Recusa de rodar: codigo 2 = guarda (modo, config); 3 = cadeia ou integridade."""

    def __init__(self, codigo: int, msg: str):
        super().__init__(msg)
        self.codigo = codigo


# ----------------------------------------------------------------------------- estatistica

def wilson(x: int, n: int) -> tuple[float | None, float | None]:
    """IC de Wilson 95% (Wilson 1927) para x/n."""
    if n == 0:
        return None, None
    ph, z2 = x / n, Z95 * Z95
    den = 1 + z2 / n
    centro = (ph + z2 / (2 * n)) / den
    meia = Z95 * math.sqrt(ph * (1 - ph) / n + z2 / (4 * n * n)) / den
    return (0.0 if x == 0 else max(0.0, centro - meia),
            1.0 if x == n else min(1.0, centro + meia))


def binom_cauda_inferior(x: int, n: int, p0: Fraction) -> float:
    """P(X <= x), X ~ Bin(n, p0), exato (teste unilateral de H0: p >= p0)."""
    a, b = p0.numerator, p0.denominator
    num = sum(math.comb(n, k) * a ** k * (b - a) ** (n - k) for k in range(x + 1))
    return float(Fraction(num, b ** n))


def fisher_bilateral(t: tuple[tuple[int, int], tuple[int, int]]) -> float:
    """Fisher exato bilateral 2x2: soma das tabelas com margens fixas e probabilidade
    <= a observada (comparacao exata em inteiros)."""
    (a, b), (c, d) = t
    r1, r2, k1 = a + b, c + d, a + c
    n = r1 + r2
    lo, hi = max(0, k1 - r2), min(k1, r1)
    peso = {i: math.comb(r1, i) * math.comb(r2, k1 - i) for i in range(lo, hi + 1)}
    obs = peso[a]
    return float(Fraction(sum(w for w in peso.values() if w <= obs), math.comb(n, k1)))


def mcnemar_exato(b: int, c: int) -> float:
    """McNemar exato bilateral sobre os discordantes b, c (binomial com p = 1/2)."""
    m = b + c
    if m == 0:
        return 1.0
    cauda = sum(math.comb(m, i) for i in range(min(b, c) + 1))
    return float(min(Fraction(1), Fraction(2 * cauda, 2 ** m)))


def holm(ps: dict[str, float | None], alfa: float = ALFA) -> tuple[dict, dict]:
    """Holm (1979) passo-abaixo. p None (nao testavel) entra como 1 e nunca rejeita (L4)."""
    m = len(ps)
    ordem = sorted(ps, key=lambda h: (1.0 if ps[h] is None else ps[h], h))
    ajust, corrente = {}, 0.0
    for i, h in enumerate(ordem):
        corrente = max(corrente, min(1.0, (m - i) * (1.0 if ps[h] is None else ps[h])))
        ajust[h] = corrente
    return ajust, {h: ps[h] is not None and ajust[h] <= alfa for h in ps}


def regra_de_tres(n: int) -> float | None:
    """Limite superior 95% para proporcao com 0 eventos em n."""
    return 3 / n if n else None


def _quantis(xs: list[float]) -> tuple[float | None, float | None]:
    if len(xs) < 2:
        return (xs[0], xs[0]) if xs else (None, None)
    q = statistics.quantiles(xs, n=40, method="inclusive")
    return q[0], q[-1]


def bootstrap_fracoes(nums: dict, lado_de: dict, dens: dict[str, list[int]], semente: str,
                      B: int) -> dict:
    """Bootstrap por par (§6.2): reamostra pares com reposicao, B vezes, com
    random.Random(semente); para cada chave, fracao = soma(num)/soma(den do lado).
    Devolve chave -> (lo 2,5%, hi 97,5%, reamostras com denominador zero)."""
    n = len(next(iter(dens.values()))) if dens else 0
    if n == 0 or not nums:
        return {k: (None, None, 0) for k in nums}
    rng, pop = random.Random(semente), range(n)
    amostras: dict = {k: [] for k in nums}
    indef: Counter = Counter()
    for _ in range(B):
        idx = rng.choices(pop, k=n)
        ig = itemgetter(*idx) if n > 1 else (lambda v, j=idx[0]: (v[j],))
        soma_den = {lado: sum(ig(v)) for lado, v in dens.items()}
        for k, v in nums.items():
            d = soma_den[lado_de[k]]
            if d:
                amostras[k].append(sum(ig(v)) / d)
            else:
                indef[k] += 1
    return {k: (*_quantis(amostras[k]), indef[k]) for k in nums}


def _mediana(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


# ----------------------------------------------------------------------- leitura e cadeia

def canonico(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_arquivo(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def ler_jsonl(caminho: Path) -> tuple[list[bytes], list[dict]]:
    dados = Path(caminho).read_bytes()
    if dados and not dados.endswith(b"\n"):
        raise Recusa(3, f"{caminho}: ultima linha sem quebra (arquivo truncado?)")
    linhas = dados.split(b"\n")[:-1] if dados else []
    if any(not L for L in linhas):
        raise Recusa(3, f"{caminho}: linha vazia")
    try:
        return linhas, [json.loads(L) for L in linhas]
    except json.JSONDecodeError as e:
        raise Recusa(3, f"{caminho}: JSON invalido ({e})") from None


def conferir_cadeia(linhas: list[bytes], regs: list[dict], sha_cfg: str | None,
                    exigir: bool, nome: str) -> str:
    """INTERFACES §1: h_i = sha256(L_{i-1} || C_i), L_0 = hex do sha256 do config.json,
    C_i = JSON canonico sem h; a linha gravada e o JSON canonico com h."""
    if not regs:
        return "vazia"
    com_h = sum("h" in r for r in regs)
    if com_h == 0 and not exigir:
        return "ausente"
    if com_h != len(regs):
        raise Recusa(3, f"{nome}: {len(regs) - com_h} linha(s) sem h")
    if sha_cfg is None:
        raise Recusa(2, f"{nome}: cadeia presente, mas sem config.json para a origem")
    anterior = sha_cfg.encode("ascii")
    for i, (L, r) in enumerate(zip(linhas, regs), 1):
        corpo = {k: v for k, v in r.items() if k != "h"}
        if r["h"] != hashlib.sha256(anterior + canonico(corpo)).hexdigest():
            raise Recusa(3, f"{nome}: cadeia quebrada na linha {i}")
        if canonico(r) != L:
            raise Recusa(3, f"{nome}: linha {i} fora da forma canonica")
        anterior = L
    return "integra"


# --------------------------------------------------------------------------- integridade

def _conj(x, nome: str, ctx: str) -> set:
    if not isinstance(x, list) or any(not isinstance(e, str) for e in x) or x != sorted(set(x)):
        raise Recusa(3, f"{ctx}: {nome} nao e lista ordenada sem repeticao")
    return set(x)


def _conferir_braco(B, U: set, AIS: set, ctx: str) -> None:
    if not isinstance(B, dict) or set(B) != {"EIS", "FN", "FP", "seguro"}:
        raise Recusa(3, f"{ctx}: braco mal formado")
    E = _conj(B["EIS"], "EIS", ctx)
    if not E <= U:
        raise Recusa(3, f"{ctx}: EIS fora de U")
    if (B["FN"] != sorted(AIS - E) or B["FP"] != sorted(E - AIS)
            or B["seguro"] is not (not (AIS - E))):
        raise Recusa(3, f"{ctx}: FN/FP/seguro nao batem com EIS e AIS")


def primario(lado: str, multi, ordem: str = "padrao") -> str:
    """Atribuicao exclusiva pela precedencia do §4.6 (padrao ou alternativa c)."""
    for k in ORDEM[ordem][lado]:
        if k in multi:
            return k
    raise Recusa(3, f"rotulo sem precedencia: {lado} {multi}")


def _conferir_multi(corpus: str, lado: str, multi, ctx: str) -> None:
    if lado not in ("FN", "FP") or not isinstance(multi, list) or not multi:
        raise Recusa(3, f"{ctx}: instancia sem lado ou sem rotulo")
    if len(set(multi)) != len(multi) or not set(multi) <= CLASSES[corpus][lado]:
        raise Recusa(3, f"{ctx}: rotulos {multi} invalidos para {corpus}/{lado}")
    if EXCLUSIVOS[lado] in multi and len(multi) > 1:
        raise Recusa(3, f"{ctx}: {EXCLUSIVOS[lado]} nao e exclusivo")


def _conferir_r_tipo(rt, AIS: set, eis0: set, elems: set, ctx: str) -> None:
    if not isinstance(rt, dict):
        raise Recusa(3, f"{ctx}: r_tipo mal formado")
    for regra, ef in rt.items():
        partes = regra.split(":")
        ok = ((partes[0] == "rho" and len(partes) == 3 and partes[2] in "MADR"
               and len(partes[2]) == 1 and ">" in partes[1])
              or (partes[0] == "alfa" and len(partes) == 2 and ">" in partes[1]))
        if not ok or not isinstance(ef, dict) or set(ef) != {"fn_novo", "removidas"}:
            raise Recusa(3, f"{ctx}: regra {regra!r} mal formada")
        if not _conj(ef["fn_novo"], "fn_novo", ctx) <= (AIS & eis0):
            raise Recusa(3, f"{ctx}: {regra} fn_novo fora de AIS ∩ EIS(A0)")
        if not _conj(ef["removidas"], "removidas", ctx) <= elems:
            raise Recusa(3, f"{ctx}: {regra} removeu elemento sem instancia em A0")


def conferir_registro(r: dict, corpus: str, ctx: str) -> None:
    """Integridade mecanica de um registro (INTERFACES §1). Falha = defeito de pipeline."""
    for k in OBRIGATORIOS:
        if k not in r:
            raise Recusa(3, f"{ctx}: campo {k} ausente")
    if r["corpus"] != corpus:
        raise Recusa(3, f"{ctx}: corpus {r['corpus']} != {corpus}")
    if r["controle"] not in CONTROLES or (r["controle"] == "tag" and corpus != "tz"):
        raise Recusa(3, f"{ctx}: controle {r['controle']!r} invalido")
    if r.get("ano") is None and not r.get("data_c"):
        raise Recusa(3, f"{ctx}: sem ano nem data_c")
    ne = r["nao_executado"]
    if ne is not None:
        if not isinstance(ne, dict) or ne.get("causa") not in CAUSAS:
            raise Recusa(3, f"{ctx}: causa de NAO_EXECUTADO invalida")
        if (r["U"] or r["S"] or r["AIS"] or r["instancias"]
                or any(v is not None for v in (r["bracos"] or {}).values())):
            raise Recusa(3, f"{ctx}: par NAO_EXECUTADO com conteudo")
        return
    U = _conj(r["U"], "U", ctx)
    AIS = _conj(r["AIS"], "AIS", ctx)
    if not AIS <= U:
        raise Recusa(3, f"{ctx}: AIS fora de U")
    br = r["bracos"]
    if not isinstance(br, dict) or br.get("A0") is None:
        raise Recusa(3, f"{ctx}: sem braco A0")
    if corpus in APLICA:
        if set(br) != set(BRACOS):
            raise Recusa(3, f"{ctx}: conjunto de bracos != {BRACOS}")
        for b in BRACOS:
            if (br[b] is None) == (b in APLICA[corpus]):
                raise Recusa(3, f"{ctx}: braco {b} {'ausente' if br[b] is None else 'indevido'}"
                                f" em {corpus} (§5)")
    for b, B in br.items():
        if B is not None:
            _conferir_braco(B, U, AIS, f"{ctx}[{b}]")
    if br.get("B-ret") is not None and set(br["B-ret"]["EIS"]) != U:
        raise Recusa(3, f"{ctx}: B-ret com EIS != U")
    a0 = br["A0"]
    vistos = sorted((i.get("e"), i.get("lado")) for i in r["instancias"])
    esperado = sorted([(e, "FN") for e in a0["FN"]] + [(e, "FP") for e in a0["FP"]])
    if vistos != esperado:
        raise Recusa(3, f"{ctx}: instancias != FN/FP do braco A0")
    for i in r["instancias"]:
        _conferir_multi(corpus, i["lado"], i.get("multi"), ctx)
        if "primario" in i and i["primario"] != primario(i["lado"], i["multi"]):
            raise Recusa(3, f"{ctx}: primario {i['primario']} contraria a precedencia §4.6")
    if corpus in CONFIRMATORIOS and not isinstance(r.get("nc"), bool) and (
            r["controle"] is None or r.get("nc") is not None):
        raise Recusa(3, f"{ctx}: nc ausente")
    if r.get("news_so_comentario") not in (None, True, False):
        raise Recusa(3, f"{ctx}: news_so_comentario nao e booleano")
    if r.get("r_tipo") is not None:
        _conferir_r_tipo(r["r_tipo"], AIS, set(a0["EIS"]), set(a0["FN"]) | set(a0["FP"]), ctx)
    sens = r.get("sens")
    if sens is not None:
        if corpus != "tz":
            raise Recusa(3, f"{ctx}: sens so existe no tz")
        if sens.get("AIS_1970_2037") is not None and not _conj(
                sens["AIS_1970_2037"], "AIS_1970_2037", ctx) <= U:
            raise Recusa(3, f"{ctx}: AIS_1970_2037 fora de U")
        for b, B in (sens.get("d1_anterior") or {}).items():
            if b not in BRACOS:
                raise Recusa(3, f"{ctx}: d1_anterior com braco {b}")
            if B is not None:
                _conferir_braco(B, U, AIS, f"{ctx}[d1_anterior {b}]")


def ano(r: dict) -> int:
    return int(r["ano"]) if r.get("ano") is not None else int(str(r["data_c"])[:4])


def _pid(r: dict) -> dict:
    return {"p": r["p"], "c": r["c"]}


def _executados(regs: list[dict]) -> list[dict]:
    return [r for r in regs if r["nao_executado"] is None]


def _nd(r: dict) -> int:
    nd = (r.get("descritores") or {}).get("NAO_DETERMINISTICO") or {}
    return len(nd.get("p", [])) + len(nd.get("c", []))


# -------------------------------------------------------------------------- por par §6.1

def metricas_par(B: dict, r: dict) -> dict:
    E, A, U = set(B["EIS"]), set(r["AIS"]), r["U"]
    inter = len(E & A)
    return {"seguro": B["seguro"], "n_FN": len(B["FN"]), "n_FP": len(B["FP"]),
            "n_AIS": len(A), "n_EIS": len(E), "n_U": len(U),
            "revocacao": inter / len(A) if A else None,
            "precisao_teto": inter / len(E) if E else None,
            "EIS_sobre_U": len(E) / len(U) if U else None}


def linhas_por_par(regs: list[dict], marca: str, corpus: str) -> list[dict]:
    out = []
    for r in regs:
        base = {"marca": marca, "corpus": corpus, "p": r["p"], "c": r["c"], "ano": ano(r),
                "controle": r["controle"] or "", "nao_executado": "", "nc": r.get("nc")}
        if r["nao_executado"] is not None:
            out.append({**base, "nao_executado": r["nao_executado"]["causa"]})
            continue
        for b in BRACOS:
            B = r["bracos"].get(b)
            if B is not None:
                out.append({**base, "braco": b, **metricas_par(B, r)})
    return out


def resumo_bracos(regs: list[dict]) -> list[dict]:
    """§6.1 agregado no corpus: pares seguros, Wilson da fracao insegura, medianas;
    metricas indefinidas (AIS = vazio, EIS = vazio) ficam fora e sao contadas."""
    out = []
    for b in BRACOS:
        Bs = [(r, r["bracos"][b]) for r in regs if r["bracos"].get(b) is not None]
        if not Bs:
            continue
        ms = [metricas_par(B, r) for r, B in Bs]
        n, ins = len(ms), sum(not m["seguro"] for m in ms)
        lo, hi = wilson(ins, n)
        rev = [m["revocacao"] for m in ms if m["revocacao"] is not None]
        prec = [m["precisao_teto"] for m in ms if m["precisao_teto"] is not None]
        fr = [m["EIS_sobre_U"] for m in ms if m["EIS_sobre_U"] is not None]
        out.append({"braco": b, "n_pares": n, "seguros": n - ins, "inseguros": ins,
                    "frac_inseguros": ins / n, "wilson_lo": lo, "wilson_hi": hi,
                    "instancias_FN": sum(m["n_FN"] for m in ms),
                    "instancias_FP": sum(m["n_FP"] for m in ms),
                    "mediana_revocacao": _mediana(rev), "revocacao_indefinida": n - len(rev),
                    "mediana_precisao_teto": _mediana(prec),
                    "precisao_indefinida": n - len(prec),
                    "mediana_EIS_sobre_U": _mediana(fr), "EIS_sobre_U_indefinida": n - len(fr)})
    return out


# ------------------------------------------------------------------------ por classe §6.2

def nome_relato(corpus: str, rotulo: str) -> str:
    """T3 vira T3m (zlib, mantida a mao) ou T3g (Lua, gerada) so no relato (§2.2)."""
    if rotulo.startswith("T3-"):
        return {"zlib": "T3m", "lua": "T3g"}.get(corpus, "T3") + rotulo[2:]
    return rotulo


def _removida(eis: set, e: str, lado: str) -> bool:
    return e not in eis if lado == "FP" else e in eis


def categoria_ablacao(corpus: str, eis_por_braco: dict, e: str, lado: str) -> str:
    """§4.6 b, leitura L2."""
    rem = [h for h in ISOLADOS[corpus] if _removida(eis_por_braco[h], e, lado)]
    if len(rem) == 1:
        return rem[0].replace("A0+", "")
    if rem:
        return "SOBREPOSTA"
    return "COMPOSTA" if _removida(eis_por_braco["A_full"], e, lado) else "NAO_REMOVIDA"


def _classe_do_gancho(corpus: str, atribuicao: str, lado: str, cat: str) -> str:
    """Classe que o gancho isolado ataca (§4.5), so para leitura da linha de ablacao."""
    cl = CLASSE_DO_GANCHO.get("A0+" + cat) if atribuicao == "ablacao" else None
    if cl is None:
        return ""
    return nome_relato(corpus, f"T3-{lado}") if cl == "T3" else cl


def _categorias_ablacao(corpus: str) -> list[str]:
    return [h.replace("A0+", "") for h in ISOLADOS[corpus]] + ["SOBREPOSTA", "COMPOSTA",
                                                               "NAO_REMOVIDA"]


def tabela_classes(regs: list[dict], corpus: str, marca: str, semente: str | None,
                   B: int) -> list[dict]:
    """§6.2. Uma linha por (atribuicao, lado, categoria). Atribuicoes: primario (§4.6
    padrao), multirrotulo (a), alt_c (c), ablacao (b). Instancias, elementos distintos e
    pares com >= 1 instancia lado a lado; fracao dos pares com Wilson; fracao das instancias
    do lado com bootstrap por par (semente None = sem bootstrap)."""
    n = len(regs)
    cont: dict = defaultdict(lambda: [0] * n)
    elems: dict = defaultdict(set)
    dens = {"FN": [0] * n, "FP": [0] * n}
    for i, r in enumerate(regs):
        eis = {b: set(v["EIS"]) for b, v in r["bracos"].items() if v is not None}
        for inst in r["instancias"]:
            e, lado, multi = inst["e"], inst["lado"], inst["multi"]
            dens[lado][i] += 1
            chaves = {("primario", lado, primario(lado, multi)),
                      ("alt_c", lado, primario(lado, multi, "alt_c"))}
            chaves |= {("multirrotulo", lado, k) for k in multi}
            if corpus in ISOLADOS:
                chaves.add(("ablacao", lado, categoria_ablacao(corpus, eis, e, lado)))
            for k in chaves:
                cont[k][i] += 1
                elems[k].add(e)
    chaves = [(a, lado, k) for a in ("primario", "multirrotulo", "alt_c")
              for lado in ("FN", "FP") for k in ORDEM["padrao"][lado]]
    if corpus in ISOLADOS:
        chaves += [("ablacao", lado, k) for lado in ("FN", "FP")
                   for k in _categorias_ablacao(corpus)]
    tot = {lado: sum(v) for lado, v in dens.items()}
    nums = {k: cont[k] for k in chaves if tot[k[1]] and (k[0] == "ablacao"
                                                        or k[2] in CLASSES[corpus][k[1]])}
    boot = (bootstrap_fracoes(nums, {k: k[1] for k in nums}, dens, semente, B)
            if semente is not None else {})
    out = []
    for k in chaves:
        a, lado, cat = k
        v = cont[k] if k in cont else [0] * n
        ni, pares = sum(v), sum(1 for x in v if x)
        lo, hi = wilson(pares, n)
        bl, bh, bi = boot.get(k, (None, None, None))
        if a == "ablacao":
            status = "descritivo"
        elif cat not in CLASSES[corpus][lado]:
            status = "nao_se_aplica"
        else:
            km = ("multirrotulo", lado, cat)
            nm = sum(cont[km]) if km in cont else 0
            status = "exercida" if nm >= LIMIAR_EXERCIDA else "nao_exercida"     # L1
        out.append({"marca": marca, "corpus": corpus, "atribuicao": a, "lado": lado,
                    "categoria": nome_relato(corpus, cat) if a != "ablacao" else cat,
                    "classe_do_gancho": _classe_do_gancho(corpus, a, lado, cat),
                    "n_instancias": ni, "elementos_distintos": len(elems.get(k, ())),
                    "pares_com_instancia": pares, "n_pares": n,
                    "frac_pares": pares / n if n else None, "wilson_lo": lo, "wilson_hi": hi,
                    "instancias_do_lado": tot[lado],
                    "frac_lado": ni / tot[lado] if tot[lado] else None,
                    "boot_lo": bl, "boot_hi": bh, "boot_reamostras_indefinidas": bi,
                    "frac_todas_instancias": ni / (tot["FN"] + tot["FP"])
                    if tot["FN"] + tot["FP"] else None,
                    "status": status})
    return out


# ------------------------------------------------------------------------- hipoteses §7

def _conj_dados(regs: list[dict], rotulos=True, nc=True, r_tipo=True) -> dict:
    return {"regs": regs, "rotulos": rotulos, "nc": nc, "r_tipo": r_tipo}


def _vazio(D: dict, k: str) -> bool:
    return k not in D or not D[k]["regs"]


def _h1(D: dict, corpus: str, pred) -> dict:
    if _vazio(D, corpus):
        return {"corpus": corpus, "status": "nao_testavel", "p": None}
    regs = D[corpus]["regs"]
    ex = [{**_pid(r), "elementos": el} for r in regs if (el := pred(r))]
    n, x = len(regs), len(ex)
    lo, hi = wilson(x, n)
    return {"corpus": corpus, "status": "testada", "n_pares": n, "pares_com_evento": x,
            "proporcao": x / n, "wilson": [lo, hi], "H0": "p >= 0.02 (binomial exato unilateral)",
            "p": binom_cauda_inferior(x, n, P0_H1), "exemplos": ex}


def h1a(D: dict) -> dict:
    r = _h1(D, "tz", lambda r: r["bracos"]["A0"]["FN"])
    r["enunciado"] = "tz: proporcao de pares com FN(A0) > 0 e < 2%"
    return r


def h1b(D: dict) -> dict:
    if not _vazio(D, "lua") and not D["lua"]["rotulos"]:
        return {"corpus": "lua", "status": "nao_recalculada", "p": None}
    r = _h1(D, "lua", lambda r: sorted(i["e"] for i in r["instancias"] if "T4" in i["multi"]))
    r["enunciado"] = "Lua: proporcao de pares com instancia T4-FN e < 2%"
    return r


def h2(D: dict) -> dict:
    out = {}
    for k in CONFIRMATORIOS:
        if _vazio(D, k):
            out[k] = {"status": "nao_testavel", "refutada": None}
            continue
        if not D[k]["nc"]:
            out[k] = {"status": "nao_recalculada", "refutada": None}
            continue
        nc = [r for r in D[k]["regs"] if r["nc"]]
        ce = [{**_pid(r), "elementos": r["bracos"]["A0"]["FN"]} for r in nc
              if r["bracos"]["A0"]["FN"]]
        manip = [_pid(r) for r in nc if r["bracos"].get("A_full") is not None
                 and r["bracos"]["A_full"]["EIS"] != r["bracos"]["A0"]["EIS"]]
        lo, hi = wilson(len(ce), len(nc))
        out[k] = {"status": "testada" if nc else "nao_testavel (n_NC = 0)",
                  "n_nc": len(nc), "pares_nc_com_FN": len(ce),
                  "limite_regra_de_tres": regra_de_tres(len(nc)) if not ce else None,
                  "wilson": [lo, hi], "refutada": bool(ce) if nc else None,
                  "contraexemplos": ce,
                  "checagem_manipulacao_EIS_A0_difere_A_full": {"n": len(manip), "pares": manip}}
    return out


def _fn_novos(regs: list[dict], braco: str) -> tuple[int, list[dict]]:
    n, ce = 0, []
    for r in regs:
        B = r["bracos"].get(braco)
        if B is None:
            continue
        n += 1
        novo = sorted(set(B["FN"]) - set(r["bracos"]["A0"]["FN"]))
        if novo:
            ce.append({**_pid(r), "elementos": novo})
    return n, ce


def h3(D: dict) -> dict:
    out = {}
    for k, ganchos in H3_GANCHOS.items():
        out[k] = {}
        for g in ganchos:
            n, ce = _fn_novos(D[k]["regs"], g) if not _vazio(D, k) else (0, [])
            out[k][g] = {"status": "testada" if n else "nao_testavel", "n_pares": n,
                         "pares_com_FN_novo": len(ce),
                         "instancias_FN_novas": sum(len(x["elementos"]) for x in ce),
                         "refutada": bool(ce) if n else None, "contraexemplos": ce,
                         "subclasse_exploratoria": bool(ce)}
    return out


def h4(D: dict) -> dict:
    n, ce = _fn_novos(D["tz"]["regs"], "A0+d4-ingenuo") if not _vazio(D, "tz") else (0, [])
    return {"corpus": "tz", "status": "testada" if n else "nao_testavel", "n_pares": n,
            "pares_com_FN_novo": len(ce),
            "instancias_FN_novas": sum(len(x["elementos"]) for x in ce),
            "refutada": (not ce) if n else None, "exemplos_FN_novo": ce}


def h5(D: dict) -> dict:
    out = {}
    for k in CONFIRMATORIOS:
        if _vazio(D, k) or not D[k]["rotulos"]:
            out[k] = {"status": "nao_testavel" if _vazio(D, k) else "nao_recalculada",
                      "refutada": None}
            continue
        fn = [i for r in D[k]["regs"] for i in r["instancias"] if i["lado"] == "FN"]
        inc = sum(1 for i in fn if "INCLASSIFICADO-FN" in i["multi"])
        lo, hi = wilson(inc, len(fn))
        base = {"instancias_FN": len(fn), "INCLASSIFICADO_FN": inc,
                "frac": inc / len(fn) if fn else None, "wilson": [lo, hi]}
        if len(fn) < LIMIAR_H5_N:
            out[k] = {**base, "status": f"nao_aplicavel (FN < {LIMIAR_H5_N})", "refutada": None}
        else:
            ref = Fraction(inc, len(fn)) > LIMIAR_H5_FRAC
            out[k] = {**base, "status": "testada", "refutada": ref,
                      "taxonomia": "incompleta" if ref else "completa no lado FN"}
    return out


def h6(D: dict) -> dict:
    out = {}
    for k in CONFIRMATORIOS:
        if _vazio(D, k):
            out[k] = {"status": "nao_testavel", "refutada": None}
            continue
        com = [r for r in D[k]["regs"] if r["bracos"].get("B-sem") is not None]
        if not com:
            out[k] = {"status": "nao_testavel (sem B-sem)", "refutada": None}
            continue
        ins = [_pid(r) for r in com if not r["bracos"]["B-sem"]["seguro"]]
        out[k] = {"status": "testada", "n_pares": len(com),
                  "pares_B_sem_inseguro": len(ins), "refutada": not ins,
                  "efeito": "pipeline suspeito: investigar antes de interpretar outra H"
                  if not ins else "", "exemplos": ins[:50]}
    return out


def _efeitos_r_tipo(regs: list[dict]) -> dict:
    tot: dict = defaultdict(lambda: {"fn_novo": 0, "pares_com_efeito": 0,
                                     "removidas": Counter()})
    for r in regs:
        rot = {i["e"]: i["multi"] for i in r["instancias"]}
        for regra, ef in r["r_tipo"].items():
            t = tot[regra]
            t["fn_novo"] += len(ef["fn_novo"])
            t["pares_com_efeito"] += 1
            for e in ef["removidas"]:
                t["removidas"].update(rot[e])
    return tot


def h7(D: dict) -> dict:
    """(a) nenhuma rho remove >= 1 instancia de T1a (tz) / T2 (cada corpus) sem criar FN
    no corpus; (b) alguma alfa remove 100% das T4-FN do zlib. Leitura L5."""
    out: dict = {"a": {}, "b": {}}

    def pronto(k):
        if _vazio(D, k):
            return "nao_testavel"
        if not D[k]["rotulos"] or not D[k]["r_tipo"]:
            return "nao_recalculada"
        falta = sum(r.get("r_tipo") is None for r in D[k]["regs"])
        return f"incompleta (r_tipo ausente em {falta} pares)" if falta else ""

    alvos = [("tz", "T1a"), ("tz", "T2"), ("zlib", "T2"), ("lua", "T2")]
    for k, cl in alvos:
        st = pronto(k)
        if st:
            out["a"].setdefault(k, {})[cl] = {"status": st, "refutada": None}
            continue
        regs = D[k]["regs"]
        n_cl = sum(cl in i["multi"] for r in regs for i in r["instancias"])
        ef = _efeitos_r_tipo(regs)
        rhos = {g: {"remove": v["removidas"][cl], "fn_novo": v["fn_novo"],
                    "pares_com_efeito": v["pares_com_efeito"]}
                for g, v in sorted(ef.items()) if g.startswith("rho:") and v["removidas"][cl]}
        seguras = sorted(g for g, v in rhos.items() if v["fn_novo"] == 0)
        out["a"].setdefault(k, {})[cl] = {
            "status": "testada" if n_cl else "nao_testavel (classe sem instancia)",
            "instancias_da_classe": n_cl,
            "classe_exercida": n_cl >= LIMIAR_EXERCIDA,
            "refutada": bool(seguras) if n_cl else None,
            "exprimivel_por_regra_tipada": bool(seguras) if n_cl else None,
            "rho_seguras_que_removem": seguras, "rho_que_removem": rhos}
    st = pronto("zlib")
    if st:
        out["b"]["zlib"] = {"status": st, "refutada": None}
    else:
        regs = D["zlib"]["regs"]
        n4 = sum("T4" in i["multi"] for r in regs for i in r["instancias"])
        ef = _efeitos_r_tipo(regs)
        alfas = {g: {"remove": v["removidas"]["T4"], "fn_novo": v["fn_novo"]}
                 for g, v in sorted(ef.items()) if g.startswith("alfa:")}
        todas = sorted(g for g, v in alfas.items() if n4 and v["remove"] == n4)
        out["b"]["zlib"] = {
            "status": "testada" if n4 else "nao_testavel (T4 sem instancia)",
            "instancias_T4": n4, "classe_exercida": n4 >= LIMIAR_EXERCIDA,
            "refutada": (not todas) if n4 else None,
            "T4_exprimivel_por_regra_tipada": bool(todas) if n4 else None,
            "alfa_que_removem_todas": todas, "alfa": alfas}
    return out


def _tabela_h8(regs: list[dict]) -> tuple[int, int]:
    """(pares com >= 50% das FP em T5, pares com < 50%), so pares com >= 1 FP."""
    maioria = menor = 0
    for r in regs:
        fp = [i for i in r["instancias"] if i["lado"] == "FP"]
        if fp:
            t5 = sum("T5" in i["multi"] for i in fp)
            if 2 * t5 >= len(fp):
                maioria += 1
            else:
                menor += 1
    return maioria, menor


def _fisher_corpora(D: dict, a: str, b: str) -> dict:
    if _vazio(D, a) or _vazio(D, b):
        return {"status": "nao_testavel", "p": None}
    if not (D[a]["rotulos"] and D[b]["rotulos"]):
        return {"status": "nao_recalculada", "p": None}
    ta, tb = _tabela_h8(D[a]["regs"]), _tabela_h8(D[b]["regs"])
    if sum(ta) == 0 or sum(tb) == 0:
        return {"status": "nao_testavel (corpus sem par com FP)", "p": None,
                "tabela": {a: ta, b: tb}}
    return {"status": "testada", "linhas": [a, b],
            "colunas": ["frac_T5 >= 0.5", "frac_T5 < 0.5"],
            "tabela": {a: list(ta), b: list(tb)},
            "frac_maioria_T5": {a: ta[0] / sum(ta), b: tb[0] / sum(tb)},
            "p": fisher_bilateral((ta, tb))}


def h8(D: dict) -> dict:
    r = _fisher_corpora(D, "tz", "zlib")
    r["enunciado"] = "Fisher exato bilateral: corpus (tz, zlib) x (>= 50% das FP do par sao T5)"
    return r


def regra_secao_8(D: dict) -> dict:
    """§8: dominio em que A0 e seguro em todo par e tem precisao-teto mediana >= 0,90 em
    todos os corpora confirmatorios do dominio -> tese rejeitada ali (leitura L3)."""
    def cond(k):
        if _vazio(D, k):
            return {"status": "ausente", "condicao": None}
        regs = D[k]["regs"]
        prec = [m for r in regs
                if (m := metricas_par(r["bracos"]["A0"], r)["precisao_teto"]) is not None]
        seg = all(r["bracos"]["A0"]["seguro"] for r in regs)
        med = _mediana(prec)
        return {"status": "avaliado", "n_pares": len(regs), "A0_seguro_em_todo_par": seg,
                "pares_inseguros": sum(not r["bracos"]["A0"]["seguro"] for r in regs),
                "mediana_precisao_teto": med, "precisao_indefinida": len(regs) - len(prec),
                "condicao": None if med is None and seg else (seg and med >= LIMIAR_PREC_S8)}

    def dominio(cs):
        por = {k: cond(k) for k in cs}
        cc = [v["condicao"] for v in por.values()]
        dec = None if any(c is None for c in cc) else all(cc)
        return {"corpora": por, "tese_rejeitada_no_dominio": dec,
                "status": "decidido" if dec is not None else "nao_decidivel"}

    tz, c = dominio(("tz",)), dominio(("zlib", "lua"))
    return {"limiar_precisao": LIMIAR_PREC_S8, "tz": tz, "build_C": c,
            "build_C_so_zlib_descritivo": dominio(("zlib",)),
            "resultado_negativo_nos_dois_dominios":
                (tz["tese_rejeitada_no_dominio"] and c["tese_rejeitada_no_dominio"])
                if None not in (tz["tese_rejeitada_no_dominio"],
                                c["tese_rejeitada_no_dominio"]) else None}


def avaliar_hipoteses(D: dict) -> dict:
    """D: corpus -> {"regs": pares primarios executados, "rotulos", "nc", "r_tipo"}."""
    H = {"H1a": h1a(D), "H1b": h1b(D), "H2": h2(D), "H3": h3(D), "H4": h4(D), "H5": h5(D),
         "H6": h6(D), "H7": h7(D), "H8": h8(D)}
    ps = {h: H[h]["p"] for h in ("H1a", "H1b", "H8")}
    ajust, rej = holm(ps)
    for h in ps:
        H[h]["p_holm"] = ajust[h] if ps[h] is not None else None
        H[h]["rejeita_H0_sob_holm"] = rej[h] if ps[h] is not None else None
        H[h]["refutada"] = (not rej[h]) if ps[h] is not None else None
    H["holm"] = {"familia": list(ps), "alfa": ALFA, "p": ps, "p_ajustado": ajust,
                 "nota": "p ausente entra como 1 e nunca rejeita (leitura L4)"}
    H["H8_replica_tz_lua_descritivo"] = _fisher_corpora(D, "tz", "lua")
    susp = sorted(k for k, v in H["H6"].items() if v.get("refutada"))
    H["interpretacao_suspensa_por_H6"] = susp
    H["secao_8"] = regra_secao_8(D)
    return H


# ------------------------------------------------------------------------ McNemar §6.3

def mcnemar(regs: list[dict]) -> dict:
    out = {}
    for g in GANCHOS:
        ps = [(r["bracos"]["A0"]["seguro"], r["bracos"][g]["seguro"]) for r in regs
              if r["bracos"].get(g) is not None]
        if not ps:
            continue
        b = sum(a and not h for a, h in ps)
        c = sum(h and not a for a, h in ps)
        out[g] = {"n_pares": len(ps), "seguro_A0_inseguro_gancho": b,
                  "inseguro_A0_seguro_gancho": c,
                  "ambos_seguros": sum(a and h for a, h in ps),
                  "ambos_inseguros": sum(not a and not h for a, h in ps),
                  "p_exato_bilateral": mcnemar_exato(b, c), "descritivo": True}
    return out


# ----------------------------------------------------------------- controles e descritores

def controles(regs: list[dict], corpus: str) -> dict:
    """§5: par nulo exige EIS = AIS = vazio (B-ret fica fora: EIS = U por definicao);
    violacao aborta. Placebo exige AIS = vazio; AIS != vazio e reportado como T4."""
    nulos = [r for r in regs if r["controle"] == "nulo"]
    for r in _executados(nulos):
        if r["AIS"] or any(B is not None and B["EIS"] for b, B in r["bracos"].items()
                           if b != "B-ret"):
            raise Recusa(3, f"{corpus}: par nulo {r['p'][:12]} com EIS ou AIS != vazio "
                            "(defeito de pipeline, §5)")
    plac = [r for r in regs if r["controle"] == "placebo"]
    pe = _executados(plac)
    t4 = [{**_pid(r), "elementos": r["AIS"]} for r in pe if r["AIS"]]
    return {"nulo": {"n": len(nulos), "executados": len(_executados(nulos)), "violacoes": 0},
            "placebo": {"n": len(plac), "executados": len(pe), "AIS_nao_vazio": len(t4),
                        "instancias_T4": sum(len(x["elementos"]) for x in t4),
                        "reportados_como_T4": t4},
            "tag": {"n": sum(r["controle"] == "tag" for r in regs)}}


def descritores(regs: list[dict], corpus: str, marca: str) -> list[dict]:
    """§4.7 por ano (pares primarios), mais uma linha 'todos' DENTRO do corpus."""
    grupos: dict = defaultdict(list)
    for r in regs:
        grupos[ano(r)].append(r)
    out = []
    for a in sorted(grupos) + ["todos"]:
        rs = grupos[a] if a != "todos" else regs
        ne = Counter(r["nao_executado"]["causa"] for r in rs if r["nao_executado"])
        ds = [r.get("descritores") or {} for r in rs if r["nao_executado"] is None]
        out.append({
            "marca": marca, "corpus": corpus, "ano": a, "pares": len(rs),
            "executados": len(ds), "nao_executado": sum(ne.values()),
            **{f"nao_executado_{k}": ne.get(k, 0) for k in sorted(CAUSAS)},
            "nao_det_pares": sum(_nd(r) > 0 for r in rs if r["nao_executado"] is None),
            "nao_det_elementos": sum(_nd(r) for r in rs if r["nao_executado"] is None),
            "identidade_pares": sum(bool(d.get("MUDANCA_DE_IDENTIDADE")) for d in ds),
            "identidade_elementos": sum(len(d.get("MUDANCA_DE_IDENTIDADE") or []) for d in ds),
            "ciclo_pares": sum(bool(d.get("CICLO")) for d in ds),
            "ciclo_componentes": sum(len(d.get("CICLO") or []) for d in ds),
            "pendente_pares": sum(bool(d.get("PENDENTE")) for d in ds),
            "pendente_nomes": sum(len(d.get("PENDENTE") or []) for d in ds),
            "grafo_vazio_pares": sum(bool(d.get("GRAFO_VAZIO")) for d in ds)})
    return out


# ------------------------------------------------------------------- sensibilidades §6.4

def _rebracos(r: dict, ais: list[str], bracos: dict) -> dict:
    A = set(ais)
    novos = {}
    for b in BRACOS:
        B = bracos.get(b)
        if B is not None:
            E = set(B["EIS"])
            novos[b] = {"EIS": sorted(E), "FN": sorted(A - E), "FP": sorted(E - A),
                        "seguro": not (A - E)}
        else:
            novos[b] = None
    return {**r, "AIS": sorted(A), "bracos": novos, "instancias": [], "r_tipo": None}


def sens_janela_w(regs: list[dict]) -> tuple[str, list[dict]]:
    falta = sum((r.get("sens") or {}).get("AIS_1970_2037") is None for r in regs)
    if falta:
        return (f"ausente em {falta} de {len(regs)} pares", [])
    return "calculada", [_rebracos(r, r["sens"]["AIS_1970_2037"], r["bracos"]) for r in regs]


def sens_d1_anterior(regs: list[dict]) -> tuple[str, list[dict]]:
    falta = sum((r.get("sens") or {}).get("d1_anterior") is None for r in regs)
    if falta:
        return (f"ausente em {falta} de {len(regs)} pares", [])
    return "calculada", [_rebracos(r, r["AIS"], r["sens"]["d1_anterior"]) for r in regs]


def sensibilidades(prim: dict, tags: list[dict], tabelas: dict) -> dict:
    """prim: corpus -> pares primarios executados. Cada sensibilidade reavalia os bracos e
    as hipoteses que o dado permite (leitura L7); a principal nao muda."""
    out: dict = {}
    if prim.get("tz"):
        for nome, f in (("janela_W_1970_2037", sens_janela_w),
                        ("atribuicao_comentario_anterior", sens_d1_anterior)):
            st, rs = f(prim["tz"])
            out[nome] = {"corpus": "tz", "status": st}
            if rs:
                D = {"tz": _conj_dados(rs, rotulos=False, nc=(nome == "janela_W_1970_2037"),
                                       r_tipo=False)}
                out[nome].update({"bracos": resumo_bracos(rs), "hipoteses": avaliar_hipoteses(D)})
    te = _executados(tags)
    news = [r for r in te if r.get("news_so_comentario") is True]
    out["pares_de_tags_tz"] = {"corpus": "tz", "n": len(tags), "executados": len(te),
                               "status": "calculada" if te else "ausente",
                               "concordancia_NEWS_nao_confirmatoria": {   # §3.4
                                   "tags_so_comentario": len(news),
                                   "com_AIS_vazio": sum(not r["AIS"] for r in news),
                                   "discordantes": [_pid(r) for r in news if r["AIS"]]}}
    if te:
        out["pares_de_tags_tz"].update({
            "bracos": resumo_bracos(te),
            "hipoteses": avaliar_hipoteses({"tz": _conj_dados(te)})})
    sem_nd = {k: [r for r in rs if _nd(r) == 0] for k, rs in prim.items()}
    out["exclusao_nao_deterministico"] = {
        "pares_excluidos": {k: len(prim[k]) - len(sem_nd[k]) for k in prim},
        "bracos": {k: resumo_bracos(v) for k, v in sem_nd.items()},
        "hipoteses": avaliar_hipoteses({k: _conj_dados(v) for k, v in sem_nd.items()})}
    out["atribuicoes"] = {k: [{x: lin[x] for x in ("atribuicao", "lado", "categoria",
                                                   "n_instancias", "frac_lado")}
                              for lin in t] for k, t in tabelas.items()}
    return out


# ------------------------------------------------------------------------------ escrita

def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:.6f}"
    return v


def escrever_csv(caminho: Path, linhas: list[dict]) -> None:
    cols: list[str] = []
    for lin in linhas:
        cols += [k for k in lin if k not in cols]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", restval="")
    w.writeheader()
    for lin in linhas:
        w.writerow({k: _fmt(v) for k, v in lin.items()})
    caminho.write_text(buf.getvalue(), encoding="utf-8")


def escrever_json(caminho: Path, obj) -> None:
    caminho.write_text(json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")


def _md(cab: list[str], linhas: list[list]) -> str:
    def c(v):
        v = _fmt(v)
        return str(v).replace("|", "\\|")
    s = "| " + " | ".join(cab) + " |\n|" + "---|" * len(cab) + "\n"
    return s + "".join("| " + " | ".join(c(v) for v in lin) + " |\n" for lin in linhas)


def _status_h(v: dict) -> str:
    if v.get("refutada") is None:
        return v.get("status", "")
    return "REFUTADA" if v["refutada"] else "nao refutada"


def relatorio_md(marca: str, entradas: list[dict], por_corpus: dict, H: dict,
                 ctrl: dict) -> str:
    s = [f"# Analise V — {marca}\n"]
    if marca != "CONFIRMATORIO":
        s.append(f"**{marca}: nao e resultado.**\n")
    s.append("Gerado por `analise/analise.py` diretamente dos JSONL; nada somado entre "
             "corpora; Lua e replica, reportada a parte.\n\n## Entradas\n")
    s.append(_md(["arquivo", "corpus", "linhas", "cadeia", "sha256", "preenchidos (ensaio)"],
                 [[e["arquivo"], e["corpus"], e["linhas"], e["cadeia"], e["sha256"],
                   json.dumps(e["campos_ausentes_preenchidos_com_null"])] for e in entradas]))
    for k in CORPORA:
        if k not in por_corpus:
            continue
        pc = por_corpus[k]
        tit = {"lua": " (replica, separada do zlib)", "npm": " (descritivo)"}.get(k, "")
        s.append(f"\n## {k}{tit}\n\nPares primarios: {pc['n_primarios']}; executados: "
                 f"{pc['n_executados']}.\n\n### Bracos (§6.1)\n")
        s.append(_md(["braco", "pares", "inseguros", "frac", "Wilson 95%", "inst FN", "inst FP",
                      "mediana precisao-teto", "prec. indef.", "mediana revocacao", "rev. indef."],
                     [[b["braco"], b["n_pares"], b["inseguros"], b["frac_inseguros"],
                       f"[{_fmt(b['wilson_lo'])}, {_fmt(b['wilson_hi'])}]", b["instancias_FN"],
                       b["instancias_FP"], b["mediana_precisao_teto"], b["precisao_indefinida"],
                       b["mediana_revocacao"], b["revocacao_indefinida"]]
                      for b in pc["bracos"]]))
        if pc["classes"]:
            for a in ("primario", "multirrotulo", "alt_c", "ablacao"):
                ls = [x for x in pc["classes"] if x["atribuicao"] == a
                      and x["status"] != "nao_se_aplica"]
                if not ls:
                    continue
                s.append(f"\n### Classes — {a} (§6.2)\n")
                s.append(_md(["lado", "categoria", "instancias", "elem. distintos", "pares",
                              "frac pares [Wilson]", "frac lado [bootstrap]", "status"],
                             [[x["lado"], x["categoria"] + (f" ({x['classe_do_gancho']})"
                                                            if x["classe_do_gancho"] else ""),
                               x["n_instancias"], x["elementos_distintos"],
                               x["pares_com_instancia"],
                               f"{_fmt(x['frac_pares'])} [{_fmt(x['wilson_lo'])}, "
                               f"{_fmt(x['wilson_hi'])}]",
                               f"{_fmt(x['frac_lado'])} [{_fmt(x['boot_lo'])}, "
                               f"{_fmt(x['boot_hi'])}]", x["status"]] for x in ls]))
        if pc.get("npm"):
            n = pc["npm"]
            s.append(f"\nFrequencia de 'versao resolvida muda com manifesto igual': "
                     f"{n['pares_com_mudanca']}/{n['executados']} "
                     f"[Wilson {_fmt(n['wilson'][0])}, {_fmt(n['wilson'][1])}].\n")
        s.append("\n### Descritores por ano (§4.7)\n")
        s.append(_md(["ano", "pares", "exec.", "NAO_EXEC", "NAO_DET pares", "identidade pares",
                      "ciclo pares", "pendente pares", "grafo vazio"],
                     [[d["ano"], d["pares"], d["executados"], d["nao_executado"],
                       d["nao_det_pares"], d["identidade_pares"], d["ciclo_pares"],
                       d["pendente_pares"], d["grafo_vazio_pares"]] for d in pc["descritores"]]))
        c = ctrl.get(k, {})
        if c:
            s.append(f"\nControles: nulos {c['nulo']['n']} (violacoes 0); placebo "
                     f"{c['placebo']['n']}, com AIS != vazio (reportado como T4): "
                     f"{c['placebo']['AIS_nao_vazio']}; tags {c['tag']['n']}.\n")
    s.append("\n## Hipoteses (§7)\n")
    lin = []
    for h in ("H1a", "H1b", "H8"):
        v = H[h]
        lin.append([h, v.get("corpus", "tz x zlib"),
                    f"{v.get('pares_com_evento', '')}/{v.get('n_pares', '')}"
                    if h != "H8" else json.dumps(v.get("tabela")), v.get("p"),
                    v.get("p_holm"), _status_h(v)])
    for k, v in H["H2"].items():
        lin.append(["H2", k, f"{v.get('pares_nc_com_FN', '')}/{v.get('n_nc', '')}",
                    "", "", _status_h(v)])
    for k, gs in H["H3"].items():
        for g, v in gs.items():
            lin.append(["H3", f"{k} {g}", f"{v['pares_com_FN_novo']}/{v['n_pares']}", "", "",
                        _status_h(v)])
    v = H["H4"]
    lin.append(["H4", "tz", f"{v['pares_com_FN_novo']}/{v['n_pares']}", "", "", _status_h(v)])
    for k, v in H["H5"].items():
        lin.append(["H5", k, f"{v.get('INCLASSIFICADO_FN', '')}/{v.get('instancias_FN', '')}",
                    "", "", _status_h(v)])
    for k, v in H["H6"].items():
        lin.append(["H6", k, f"{v.get('pares_B_sem_inseguro', '')}/{v.get('n_pares', '')}",
                    "", "", _status_h(v)])
    for k, cls in H["H7"]["a"].items():
        for cl, v in cls.items():
            lin.append(["H7a", f"{k} {cl}", len(v.get("rho_seguras_que_removem", [])), "", "",
                        _status_h(v)])
    for k, v in H["H7"]["b"].items():
        lin.append(["H7b", k, len(v.get("alfa_que_removem_todas", [])), "", "", _status_h(v)])
    s.append(_md(["H", "corpus", "estatistica", "p", "p Holm", "estado"], lin))
    if H["interpretacao_suspensa_por_H6"]:
        s.append(f"\n**H6 refutada em {H['interpretacao_suspensa_por_H6']}: interpretacao "
                 "das demais hipoteses suspensa ali.**\n")
    s8 = H["secao_8"]
    s.append("\n## Regra do §8\n")
    s.append(_md(["dominio", "tese rejeitada no dominio", "estado"],
                 [["tz", s8["tz"]["tese_rejeitada_no_dominio"], s8["tz"]["status"]],
                  ["build C (zlib, Lua)", s8["build_C"]["tese_rejeitada_no_dominio"],
                   s8["build_C"]["status"]]]))
    s.append(f"\nResultado negativo nos dois dominios: "
             f"{_fmt(s8['resultado_negativo_nos_dois_dominios'])}\n")
    return "".join(s)


# --------------------------------------------------------------------------------- main

def _carregar_config(caminho: Path | None, modo: str) -> tuple[dict | None, str | None]:
    if caminho is None or not caminho.exists():
        if modo == "ensaio":
            return None, None
        raise Recusa(2, f"config.json ausente: {caminho}")
    return json.loads(caminho.read_bytes()), sha256_arquivo(caminho)


def _guarda_confirmatoria(cfg: dict) -> None:
    if not cfg.get("doi"):
        raise Recusa(2, "config.json sem doi: analise confirmatoria recusada (§6.6)")
    dep = (cfg.get("protocolo") or {}).get("sha256_deposito")
    if not isinstance(dep, str) or len(dep) != 64:
        raise Recusa(2, "config.json sem sha256_deposito do protocolo")
    sem = cfg.get("sementes") or {}
    if sem.get("principal") != int.from_bytes(bytes.fromhex(dep)[:8], "big"):
        raise Recusa(2, "sementes.principal != primeiros 64 bits do sha256 do deposito (§2.5)")
    if sem.get("bootstrap") != B_PROTOCOLO:
        raise Recusa(2, f"sementes.bootstrap != {B_PROTOCOLO} (§6.2)")
    if (cfg.get("modulos") or {}).get(CHAVE_MODULO) != sha256_arquivo(ESTE_ARQUIVO):
        raise Recusa(2, f"sha256 de {CHAVE_MODULO} difere de config.modulos (congelamento)")


def carregar(entradas: list[Path], modo: str, sha_cfg: str | None) -> tuple[dict, list[dict]]:
    janela, oraculo, _ = MODOS[modo]
    por_corpus: dict = {}
    info = []
    for arq in entradas:
        linhas, regs = ler_jsonl(arq)
        cad = conferir_cadeia(linhas, regs, sha_cfg, exigir=(modo != "ensaio"), nome=str(arq))
        corpora = {r.get("corpus") for r in regs}
        if len(corpora) > 1 or (corpora and not corpora <= set(CORPORA)):
            raise Recusa(3, f"{arq}: corpus {sorted(map(str, corpora))} (um por arquivo)")
        corpus = corpora.pop() if corpora else None
        if corpus in por_corpus:
            raise Recusa(2, f"{arq}: corpus {corpus} ja lido de outro arquivo")
        vistos, preenchidos = set(), Counter()
        for i, r in enumerate(regs, 1):
            ctx = f"{arq.name}:{i}"
            if modo == "ensaio":            # so no ensaio: lacuna de interface contada, nunca
                for campo in ENSAIO_PREENCHE:   # silenciosa (vai para as saidas)
                    if campo not in r:
                        r[campo] = None
                        preenchidos[campo] += 1
            if r.get("janela") != janela or (r.get("oraculo") or {}).get("modo") != oraculo:
                raise Recusa(3, f"{ctx}: janela/oraculo ({r.get('janela')}, "
                                f"{(r.get('oraculo') or {}).get('modo')}) proibidos no modo {modo}")
            if modo != "ensaio" and r.get("sha_config") != sha_cfg:
                raise Recusa(3, f"{ctx}: sha_config diverge do config.json")
            if modo == "ensaio" and "sha_config" in r and sha_cfg and r["sha_config"] not in (
                    None, sha_cfg):
                raise Recusa(3, f"{ctx}: sha_config diverge do config.json")
            conferir_registro(r, corpus, ctx)
            chave = (r["p"], r["c"], r["controle"])
            if chave in vistos:
                raise Recusa(3, f"{ctx}: par repetido {chave}")
            vistos.add(chave)
        if corpus:
            por_corpus[corpus] = regs
        info.append({"arquivo": str(arq), "corpus": corpus, "linhas": len(regs),
                     "cadeia": cad, "sha256": sha256_arquivo(arq),
                     "campos_ausentes_preenchidos_com_null": dict(sorted(preenchidos.items()))})
    return por_corpus, info


def analisar(por_corpus: dict, modo: str, cfg: dict | None, B: int | None = None) -> dict:
    """Calcula tudo, sem escrever. Devolve as estruturas de saida."""
    marca = MODOS[modo][2]
    sem = (cfg or {}).get("sementes") or {}
    base = sem.get("principal") if modo == "confirmatorio" else sem.get("ensaio", 0)
    B = B if B is not None else int(sem.get("bootstrap", B_PROTOCOLO))
    prim, res, ctrl, tabelas, tags = {}, {}, {}, {}, []
    for k in CORPORA:
        if k not in por_corpus:
            continue
        regs = por_corpus[k]
        # populacao ordenada pelo sha de c (INTERFACES §3): reamostragem nao depende da
        # ordem do arquivo
        prim_todos = sorted((r for r in regs if r["controle"] is None),
                            key=lambda r: (r["c"], r["p"]))
        ex = _executados(prim_todos)
        ctrl[k] = controles(regs, k)
        if k == "tz":
            tags = [r for r in regs if r["controle"] == "tag"]
        pc = {"n_primarios": len(prim_todos), "n_executados": len(ex),
              "por_par": linhas_por_par(regs, marca, k), "bracos": resumo_bracos(ex),
              "descritores": descritores(prim_todos, k, marca), "mcnemar": mcnemar(ex),
              "classes": []}
        if k == "npm":
            x = sum(bool(r["AIS"]) for r in ex)
            pc["npm"] = {"executados": len(ex), "pares_com_mudanca": x,
                         "wilson": list(wilson(x, len(ex))),
                         "nao_executado_teto": sum(1 for r in prim_todos if r["nao_executado"]
                                                   and r["nao_executado"]["causa"] == "teto")}
        else:
            pc["classes"] = tabela_classes(ex, k, marca, f"{base}:bootstrap:{k}", B)
            tabelas[k] = pc["classes"]
            prim[k] = ex
        res[k] = pc
    D = {k: _conj_dados(v) for k, v in prim.items()}
    H = avaliar_hipoteses(D)
    return {"marca": marca, "por_corpus": res, "hipoteses": H, "controles": ctrl,
            "mcnemar": {k: v["mcnemar"] for k, v in res.items()},
            "sensibilidades": sensibilidades(prim, tags, tabelas),
            "bootstrap": {"reamostras": B, "semente": f"{base}:bootstrap:<corpus>"}}


def escrever(saida: Path, A: dict, entradas: list[dict]) -> list[Path]:
    saida.mkdir(parents=True, exist_ok=True)
    marca, feitos = A["marca"], []

    def j(nome, obj):
        p = saida / nome
        escrever_json(p, {"marca": marca, "entradas": entradas, **obj})
        feitos.append(p)

    for k, pc in A["por_corpus"].items():
        for nome, ls in ((f"por_par_{k}.csv", pc["por_par"]),
                         (f"resumo_bracos_{k}.csv",
                          [{"marca": marca, "corpus": k, **b} for b in pc["bracos"]]),
                         (f"por_classe_{k}.csv", pc["classes"])):
            if ls:
                escrever_csv(saida / nome, ls)
                feitos.append(saida / nome)
    desc = [d for pc in A["por_corpus"].values() for d in pc["descritores"]]
    if desc:
        escrever_csv(saida / "descritores.csv", desc)
        feitos.append(saida / "descritores.csv")
    j("hipoteses.json", {"hipoteses": A["hipoteses"], "bootstrap": A["bootstrap"]})
    j("mcnemar.json", {"mcnemar": A["mcnemar"]})
    j("sensibilidades.json", {"sensibilidades": A["sensibilidades"]})
    j("controles.json", {"controles": A["controles"],
                         "npm": {k: v["npm"] for k, v in A["por_corpus"].items() if "npm" in v}})
    p = saida / "relatorio.md"
    p.write_text(relatorio_md(marca, entradas, A["por_corpus"], A["hipoteses"],
                              A["controles"]), encoding="utf-8")
    feitos.append(p)
    return feitos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--ensaio", action="store_true", help="registros da janela de ensaio")
    g.add_argument("--teste", action="store_true", help="registros do gerador de teste")
    ap.add_argument("--config", type=Path, default=RAIZ / "config.json")
    ap.add_argument("--saida", type=Path, default=None)
    ap.add_argument("entradas", nargs="*", type=Path)
    a = ap.parse_args(argv)
    modo = "ensaio" if a.ensaio else "teste" if a.teste else "confirmatorio"
    try:
        cfg, sha_cfg = _carregar_config(a.config, modo)
        if modo == "confirmatorio":
            _guarda_confirmatoria(cfg)
            entradas = a.entradas or [RAIZ / "saidas" / f"{k}.jsonl" for k in CORPORA
                                      if (RAIZ / "saidas" / f"{k}.jsonl").exists()]
            saida = a.saida or RAIZ / "saidas" / "analise"
        else:
            entradas = a.entradas
            saida = a.saida or (RAIZ / "saidas" / "ensaio" / "analise" if modo == "ensaio"
                                else None)
            if saida is None:
                raise Recusa(2, "--teste exige --saida")
        if not entradas:
            raise Recusa(2, "nenhum arquivo de entrada")
        por_corpus, info = carregar(entradas, modo, sha_cfg)
        A = analisar(por_corpus, modo, cfg)
        feitos = escrever(saida, A, info)
    except Recusa as e:
        print(f"RECUSA ({e.codigo}): {e}", file=sys.stderr)
        return e.codigo
    print(json.dumps({"marca": A["marca"], "saidas": [str(p) for p in feitos]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
