#!/usr/bin/env python3
"""EMENDA 5: compara, entre duas execuções do mesmo corpus, só os registros EXECUTADOS nas duas (sem `h`, `sha_config`).
Uso: python compara_executados.py <a.jsonl> <b.jsonl>"""
import json, sys

def le(c):
    out = {}
    for L in open(c, "rb").read().split(b"\n"):
        if L.strip():
            r = json.loads(L)
            out[(r["p"], r["c"], r.get("controle"))] = {k: v for k, v in r.items() if k not in ("h", "sha_config")}
    return out

a, b = le(sys.argv[1]), le(sys.argv[2])
ambos = [k for k in a if k in b and not a[k]["nao_executado"] and not b[k]["nao_executado"]]
dif = [k for k in ambos if a[k] != b[k]]
print(json.dumps({"executados_nos_dois": len(ambos), "iguais": len(ambos) - len(dif), "diferentes": len(dif),
                  "so_em_b_executados": sum(1 for k in b if not b[k]["nao_executado"] and (k not in a or a[k]["nao_executado"]))},
                 indent=1))
