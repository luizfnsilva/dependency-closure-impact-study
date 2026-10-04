# Additional analyses (not part of the frozen confirmatory code)

Everything in this folder was written or run **after** the confirmatory outputs existed. None of it changes the
frozen code in `experimento/` or the confirmatory outputs in `experimento/saidas/`.

| File | What it does | Status |
|---|---|---|
| `resultados/` | outputs of the frozen `experimento/analise/analise.py`, run once over `experimento/saidas/{tz,zlib,lua}.jsonl` | confirmatory analysis |
| `resultados/relatorio_lua_sem_readline.md` | the same frozen analysis over the 48-pair Lua execution without `libreadline-dev` (now in `experimento/saidas/execucao_3_sem_readline/lua.jsonl`) | Amendment 5, analysis 1 |
| `compara_execucoes.py`, `compara_executados.py` | compare records between runs (all fields except `h` and `sha_config`) | reproducibility checks |
| `descritivas_revisao.py`, `resultados/descritivas_revisao.json` | pooled precision, pairs with an empty AIS, executed null pairs, from the frozen per-pair CSVs | descriptive |
| `r_tipo.py`, `h7_exploratoria.py`, `resultados/h7_*.json` | the H7 typed-rule family, implemented after the data because the frozen code lacked it; decided by the frozen `analise.h7` | **exploratory** (Deviation 6) |

Output folders under `experimento/saidas/`:
- `execucao_1/`, `execucao_2/`: the cancelled runs 1 and 2 (Amendments 3 and 4);
- `execucao_3_sem_readline/`: the Lua run without `libreadline-dev` and its re-execution (Amendment 5);
- `*.parte-K-de-16.jsonl`: the parallel parts that `corre.py juntar` merged into `tz.jsonl` and `lua.jsonl` (Amendment 4).
