#!/usr/bin/env python3
"""DESCRITIVO pós-análise (resposta à simulação de revisão, 2026-10-04). Lê só os CSV do analise.py congelado
(analise_v/final/por_par_<corpus>.csv). Por corpus e braço, sobre pares PRIMÁRIOS executados:
  n; pares com AIS vazio; pares com precisão definida; precisão POOLED = soma|EIS∩AIS| / soma|EIS|;
e, sobre os pares nulos executados, quantos houve. Imprime JSON."""
import csv, json, sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent / "analise_v" / "final"
out = {}
for c in ("tz", "zlib", "lua"):
    rows = list(csv.DictReader(open(BASE / f"por_par_{c}.csv", encoding="utf-8")))
    ex = [r for r in rows if r["nao_executado"] in ("", "None", "False") and r["controle"] in ("", "None")]
    nul = {(r["p"], r["c"]) for r in rows if r["controle"] == "nulo" and r["nao_executado"] in ("", "None", "False")}
    por = defaultdict(lambda: {"n": 0, "AIS_vazio": 0, "prec_definida": 0, "tp": 0, "eis": 0})
    for r in ex:
        b = por[r["braco"]]
        b["n"] += 1
        n_ais, n_eis, n_fp = int(r["n_AIS"]), int(r["n_EIS"]), int(r["n_FP"])
        b["AIS_vazio"] += n_ais == 0
        b["prec_definida"] += r["precisao_teto"] not in ("", "None")
        b["tp"] += n_eis - n_fp
        b["eis"] += n_eis
    out[c] = {"nulos_executados": len(nul),
              "bracos": {k: {**v, "precisao_pooled": round(v["tp"] / v["eis"], 4) if v["eis"] else None}
                         for k, v in por.items()}}
json.dump(out, sys.stdout, indent=1)
