#!/usr/bin/env python3
"""EMENDA 3: compara, par a par, os registros da 1ª corrida (cancelada) com os da 2ª, sem `h` e `sha_config`.
Uso: python compara_execucoes.py <exec1.jsonl> <exec2.jsonl>   -> imprime JSON com iguais/diferentes por (p, c, controle)."""
import json, sys

def le(caminho):
    out = {}
    for L in open(caminho, "rb").read().split(b"\n"):
        if L.strip():
            r = json.loads(L)
            out[(r["p"], r["c"], r.get("controle"))] = {k: v for k, v in r.items() if k not in ("h", "sha_config")}
    return out

a, b = le(sys.argv[1]), le(sys.argv[2])
comuns = sorted(set(a) & set(b))
dif = [k for k in comuns if a[k] != b[k]]
campos = {}
for k in dif:
    for f in set(a[k]) | set(b[k]):
        if a[k].get(f) != b[k].get(f):
            campos[f] = campos.get(f, 0) + 1
print(json.dumps({"exec1": len(a), "exec2": len(b), "comuns": len(comuns), "iguais": len(comuns) - len(dif),
                  "diferentes": len(dif), "campos_que_diferem": campos,
                  "exemplos": [list(k) for k in dif[:3]]}, indent=1))
