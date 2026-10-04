#!/usr/bin/env python3
"""EXPLORATÓRIA, PÓS-DADOS (DESVIO 6): H7 sobre os registros confirmatórios já gravados.

Para cada par PRIMÁRIO EXECUTADO do JSONL (a cadeia é conferida inteira antes), reconstrói G e S com os adaptadores
congelados, confere que o EIS de A0 recalculado é IGUAL ao gravado (se divergir, o par é contado e fica de fora),
e roda `corre.r_tipo_efeitos` (congelado) com a família R_tipo de `exploratoria/r_tipo.py`. O oráculo NÃO roda:
AIS, FN e FP vêm do registro. A decisão é a do `analise.h7` congelado.
Uso: python exploratoria/h7_exploratoria.py <corpus> <corpus.jsonl> <clone> <saida.json>"""
import json, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent; EXP = AQUI.parent
sys.path.insert(0, str(EXP)); sys.path.insert(0, str(AQUI))
import r_tipo as RT                                    # noqa: E402
import ganchos                                         # noqa: E402
sys.modules["ganchos.r_tipo"] = RT; ganchos.r_tipo = RT
import corre                                           # noqa: E402
from integridade import carregar_config, verificar_cadeia   # noqa: E402
from adaptadores.git_arvore import Arvore             # noqa: E402
sys.path.insert(0, str(EXP / "analise"))
import analise                                         # noqa: E402

corpus, arq, repo, saida = sys.argv[1:5]
cfg, sha_cfg = carregar_config()
verificar_cadeia(arq, sha_cfg)
regs = [json.loads(L) for L in open(arq, "rb").read().split(b"\n") if L.strip()]
prim = [r for r in regs if r["controle"] is None and r["nao_executado"] is None]
if corpus == "tz":
    from adaptadores import tz as A
    chave = "tz"
else:
    from adaptadores import cbuild
    A = cbuild.para(corpus); chave = "c"
ok, diverge = [], []
for i, r in enumerate(prim, 1):
    ap, ac = Arvore(repo, r["p"]), Arvore(repo, r["c"])
    S, G = A.semente(ap, ac), A.grafo(ap, ac)
    U, AIS, a0 = set(r["U"]), set(r["AIS"]), r["bracos"]["A0"]
    e0 = corre._E(U, A.d1_elemento)(G, S)
    if sorted(e0) != sorted(a0["EIS"]) or S != r["S"]:
        diverge.append({"p": r["p"], "c": r["c"]}); continue
    r["r_tipo"] = corre.r_tipo_efeitos(chave, G, S, U, A.d1_elemento, A.d1_tipo, set(a0["EIS"]), AIS,
                                       set(a0["FN"]), set(a0["FP"]))
    ok.append(r)
    if i % 50 == 0:
        print(f"[h7] {i}/{len(prim)}", file=sys.stderr, flush=True)
D = {corpus: analise._conj_dados(ok)}
res = {"rotulo": "EXPLORATORIA pos-dados (DESVIO 6); nao substitui a H7 confirmatoria",
       "corpus": corpus, "pares_primarios_executados": len(prim), "reconstruidos_iguais": len(ok),
       "divergentes_excluidos": diverge, "familia": RT.regras(corre.TIPOS_H7[chave]),
       "h7": analise.h7(D),
       "efeitos_por_regra": {g: {"fn_novo": v["fn_novo"], "pares_com_efeito": v["pares_com_efeito"],
                                 "removidas": dict(v["removidas"])}
                             for g, v in sorted(analise._efeitos_r_tipo(ok).items())}}
Path(saida).write_text(json.dumps(res, indent=1, ensure_ascii=False, default=list), encoding="utf-8")
print(json.dumps({"corpus": corpus, "prim": len(prim), "ok": len(ok), "diverge": len(diverge),
                  "h7": res["h7"]}, ensure_ascii=False, default=list)[:3000])
