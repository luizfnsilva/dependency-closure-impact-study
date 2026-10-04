# Analise V — CONFIRMATORIO
Gerado por `analise/analise.py` diretamente dos JSONL; nada somado entre corpora; Lua e replica, reportada a parte.

## Entradas
| arquivo | corpus | linhas | cadeia | sha256 | preenchidos (ensaio) |
|---|---|---|---|---|---|
| experimento/saidas/tz.jsonl | tz | 1944 | integra | b0916e3f4154748240faaaa10b77585bca0161c2d7b0579805390445cfea827c | {} |
| experimento/saidas/zlib.jsonl | zlib | 1054 | integra | 4261a7e550b5bf84c7bb6eaf207f96f43e94b1eccd0e01a56fcc5f53bca6ffbd | {} |
| experimento/saidas/lua.jsonl | lua | 1237 | integra | fe23a17c1e6033692f705e5634b7df999393739344f300f77114d50604a64f23 | {} |

## tz

Pares primarios: 903; executados: 839.

### Bracos (§6.1)
| braco | pares | inseguros | frac | Wilson 95% | inst FN | inst FP | mediana precisao-teto | prec. indef. | mediana revocacao | rev. indef. |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 | 839 | 0 | 0.000000 | [0.000000, 0.004558] | 0 | 10011 | 0.000000 | 25 | 1.000000 | 489 |
| A0+d3 | 839 | 0 | 0.000000 | [0.000000, 0.004558] | 0 | 1154 | 1.000000 | 443 | 1.000000 | 489 |
| A0+d4-ingenuo | 839 | 0 | 0.000000 | [0.000000, 0.004558] | 0 | 9780 | 0.000000 | 25 | 1.000000 | 489 |
| A0+d4-preciso | 839 | 0 | 0.000000 | [0.000000, 0.004558] | 0 | 9929 | 0.000000 | 25 | 1.000000 | 489 |
| A_full | 839 | 0 | 0.000000 | [0.000000, 0.004558] | 0 | 1070 | 1.000000 | 443 | 1.000000 | 489 |
| B-ret | 839 | 0 | 0.000000 | [0.000000, 0.004558] | 0 | 494123 | 0.000000 | 0 | 1.000000 | 489 |
| B-sem | 839 | 215 | 0.256257 | [0.227874, 0.286862] | 541 | 2336 | 0.000000 | 346 | 0.500000 | 489 |

### Classes — primario (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.004558] |  [, ] | nao_exercida |
| FP | T2 | 8857 | 570 | 530 | 0.631704 [0.598535, 0.663673] | 0.884727 [0.812819, 0.941329] | exercida |
| FP | T1a | 206 | 76 | 24 | 0.028605 [0.019297, 0.042211] | 0.020577 [0.010090, 0.034740] | exercida |
| FP | T5 | 948 | 465 | 65 | 0.077473 [0.061248, 0.097550] | 0.094696 [0.040540, 0.165250] | exercida |

### Classes — multirrotulo (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.004558] |  [, ] | nao_exercida |
| FP | T2 | 8857 | 570 | 530 | 0.631704 [0.598535, 0.663673] | 0.884727 [0.812819, 0.941329] | exercida |
| FP | T1a | 231 | 76 | 25 | 0.029797 [0.020263, 0.043618] | 0.023075 [0.011579, 0.037891] | exercida |
| FP | T5 | 948 | 465 | 65 | 0.077473 [0.061248, 0.097550] | 0.094696 [0.040540, 0.165250] | exercida |

### Classes — alt_c (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.004558] |  [, ] | nao_exercida |
| FP | T2 | 8857 | 570 | 530 | 0.631704 [0.598535, 0.663673] | 0.884727 [0.812819, 0.941329] | exercida |
| FP | T1a | 206 | 76 | 24 | 0.028605 [0.019297, 0.042211] | 0.020577 [0.010090, 0.034740] | exercida |
| FP | T5 | 948 | 465 | 65 | 0.077473 [0.061248, 0.097550] | 0.094696 [0.040540, 0.165250] | exercida |

### Classes — ablacao (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | d3 (T2) | 0 | 0 | 0 | 0.000000 [0.000000, 0.004558] |  [, ] | descritivo |
| FN | d4-preciso (T1a) | 0 | 0 | 0 | 0.000000 [0.000000, 0.004558] |  [, ] | descritivo |
| FN | SOBREPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.004558] |  [, ] | descritivo |
| FN | COMPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.004558] |  [, ] | descritivo |
| FN | NAO_REMOVIDA | 0 | 0 | 0 | 0.000000 [0.000000, 0.004558] |  [, ] | descritivo |
| FP | d3 (T2) | 8857 | 570 | 530 | 0.631704 [0.598535, 0.663673] | 0.884727 [0.812819, 0.941329] | descritivo |
| FP | d4-preciso (T1a) | 82 | 23 | 14 | 0.016687 [0.009965, 0.027813] | 0.008191 [0.002680, 0.015852] | descritivo |
| FP | SOBREPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.004558] | 0.000000 [0.000000, 0.000000] | descritivo |
| FP | COMPOSTA | 2 | 2 | 1 | 0.001192 [0.000210, 0.006720] | 0.000200 [0.000000, 0.000696] | descritivo |
| FP | NAO_REMOVIDA | 1070 | 468 | 70 | 0.083433 [0.066566, 0.104097] | 0.106882 [0.050828, 0.178668] | descritivo |

### Descritores por ano (§4.7)
| ano | pares | exec. | NAO_EXEC | NAO_DET pares | identidade pares | ciclo pares | pendente pares | grafo vazio |
|---|---|---|---|---|---|---|---|---|
| 2012 | 11 | 0 | 11 | 0 | 0 | 0 | 0 | 0 |
| 2013 | 57 | 4 | 53 | 0 | 0 | 0 | 0 | 0 |
| 2014 | 141 | 141 | 0 | 0 | 15 | 0 | 0 | 0 |
| 2015 | 62 | 62 | 0 | 0 | 7 | 0 | 0 | 0 |
| 2016 | 99 | 99 | 0 | 0 | 12 | 0 | 0 | 0 |
| 2017 | 55 | 55 | 0 | 0 | 2 | 0 | 0 | 0 |
| 2018 | 93 | 93 | 0 | 0 | 2 | 0 | 0 | 0 |
| 2019 | 75 | 75 | 0 | 0 | 2 | 0 | 0 | 0 |
| 2020 | 53 | 53 | 0 | 0 | 1 | 0 | 0 | 0 |
| 2021 | 38 | 38 | 0 | 0 | 4 | 0 | 0 | 0 |
| 2022 | 86 | 86 | 0 | 0 | 9 | 0 | 0 | 0 |
| 2023 | 32 | 32 | 0 | 0 | 1 | 0 | 0 | 0 |
| 2024 | 36 | 36 | 0 | 0 | 3 | 0 | 0 | 0 |
| 2025 | 15 | 15 | 0 | 0 | 1 | 0 | 0 | 0 |
| 2026 | 50 | 50 | 0 | 0 | 5 | 0 | 0 | 0 |
| todos | 903 | 839 | 64 | 0 | 64 | 0 | 0 | 0 |

Controles: nulos 903 (violacoes 0); placebo 50, com AIS != vazio (reportado como T4): 0; tags 88.

## zlib

Pares primarios: 502; executados: 500.

### Bracos (§6.1)
| braco | pares | inseguros | frac | Wilson 95% | inst FN | inst FP | mediana precisao-teto | prec. indef. | mediana revocacao | rev. indef. |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 | 500 | 3 | 0.006000 | [0.002043, 0.017490] | 28 | 2775 | 0.066667 | 89 | 1.000000 | 289 |
| A0+d3 | 500 | 3 | 0.006000 | [0.002043, 0.017490] | 28 | 1822 | 0.250000 | 149 | 1.000000 | 289 |
| A0+d2-extraido | 500 | 3 | 0.006000 | [0.002043, 0.017490] | 28 | 2776 | 0.066667 | 90 | 1.000000 | 289 |
| A0+d6 | 500 | 0 | 0.000000 | [0.000000, 0.007624] | 0 | 4143 | 0.000000 | 0 | 1.000000 | 289 |
| A_full | 500 | 0 | 0.000000 | [0.000000, 0.007624] | 0 | 3225 | 0.000000 | 58 | 1.000000 | 289 |
| B-ret | 500 | 0 | 0.000000 | [0.000000, 0.007624] | 0 | 7012 | 0.000000 | 0 | 1.000000 | 289 |
| B-sem | 500 | 51 | 0.102000 | [0.078434, 0.131635] | 201 | 204 | 1.000000 | 205 | 1.000000 | 289 |
| B-make | 500 | 3 | 0.006000 | [0.002043, 0.017490] | 28 | 2760 | 0.066667 | 90 | 1.000000 | 289 |

### Classes — primario (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | T4 | 28 | 13 | 3 | 0.006000 [0.002043, 0.017490] | 1.000000 [1.000000, 1.000000] | exercida |
| FN | T3m-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | nao_exercida |
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | nao_exercida |
| FP | T3m-FP | 15 | 15 | 1 | 0.002000 [0.000353, 0.011241] | 0.005405 [0.000000, 0.017268] | exercida |
| FP | T2 | 918 | 15 | 83 | 0.166000 [0.135958, 0.201135] | 0.330811 [0.267180, 0.395665] | exercida |
| FP | T5 | 1842 | 15 | 235 | 0.470000 [0.426648, 0.513809] | 0.663784 [0.598076, 0.727735] | exercida |

### Classes — multirrotulo (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | T4 | 28 | 13 | 3 | 0.006000 [0.002043, 0.017490] | 1.000000 [1.000000, 1.000000] | exercida |
| FN | T3m-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | nao_exercida |
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | nao_exercida |
| FP | T3m-FP | 15 | 15 | 1 | 0.002000 [0.000353, 0.011241] | 0.005405 [0.000000, 0.017268] | exercida |
| FP | T2 | 918 | 15 | 83 | 0.166000 [0.135958, 0.201135] | 0.330811 [0.267180, 0.395665] | exercida |
| FP | T5 | 1842 | 15 | 235 | 0.470000 [0.426648, 0.513809] | 0.663784 [0.598076, 0.727735] | exercida |

### Classes — alt_c (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | T4 | 28 | 13 | 3 | 0.006000 [0.002043, 0.017490] | 1.000000 [1.000000, 1.000000] | exercida |
| FN | T3m-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | nao_exercida |
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | nao_exercida |
| FP | T3m-FP | 15 | 15 | 1 | 0.002000 [0.000353, 0.011241] | 0.005405 [0.000000, 0.017268] | exercida |
| FP | T2 | 918 | 15 | 83 | 0.166000 [0.135958, 0.201135] | 0.330811 [0.267180, 0.395665] | exercida |
| FP | T5 | 1842 | 15 | 235 | 0.470000 [0.426648, 0.513809] | 0.663784 [0.598076, 0.727735] | exercida |

### Classes — ablacao (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | d3 (T2) | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | descritivo |
| FN | d2-extraido (T3m-FN) | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | descritivo |
| FN | d6 (T4) | 28 | 13 | 3 | 0.006000 [0.002043, 0.017490] | 1.000000 [1.000000, 1.000000] | descritivo |
| FN | SOBREPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | descritivo |
| FN | COMPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | descritivo |
| FN | NAO_REMOVIDA | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | descritivo |
| FP | d3 (T2) | 953 | 15 | 90 | 0.180000 [0.148805, 0.216075] | 0.343423 [0.278912, 0.409907] | descritivo |
| FP | d2-extraido (T3m-FP) | 15 | 15 | 1 | 0.002000 [0.000353, 0.011241] | 0.005405 [0.000000, 0.017268] | descritivo |
| FP | d6 (T4) | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | descritivo |
| FP | SOBREPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | descritivo |
| FP | COMPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.007624] | 0.000000 [0.000000, 0.000000] | descritivo |
| FP | NAO_REMOVIDA | 1807 | 15 | 229 | 0.458000 [0.414815, 0.501826] | 0.651171 [0.584676, 0.715694] | descritivo |

### Descritores por ano (§4.7)
| ano | pares | exec. | NAO_EXEC | NAO_DET pares | identidade pares | ciclo pares | pendente pares | grafo vazio |
|---|---|---|---|---|---|---|---|---|
| 2011 | 55 | 55 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2012 | 82 | 80 | 2 | 0 | 0 | 0 | 0 | 0 |
| 2013 | 29 | 29 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2014 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2015 | 18 | 18 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2016 | 50 | 50 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2017 | 35 | 35 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2018 | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2019 | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2020 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2021 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2022 | 44 | 44 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2023 | 36 | 36 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2024 | 45 | 45 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | 32 | 32 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | 49 | 49 | 0 | 0 | 0 | 0 | 0 | 0 |
| todos | 502 | 500 | 2 | 0 | 0 | 0 | 0 | 0 |

Controles: nulos 502 (violacoes 0); placebo 50, com AIS != vazio (reportado como T4): 0; tags 0.

## lua (replica, separada do zlib)

Pares primarios: 600; executados: 572.

### Bracos (§6.1)
| braco | pares | inseguros | frac | Wilson 95% | inst FN | inst FP | mediana precisao-teto | prec. indef. | mediana revocacao | rev. indef. |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 | 572 | 0 | 0.000000 | [0.000000, 0.006671] | 0 | 4836 | 0.250000 | 3 | 1.000000 | 197 |
| A0+d3 | 572 | 0 | 0.000000 | [0.000000, 0.006671] | 0 | 4286 | 0.383484 | 42 | 1.000000 | 197 |
| A0+d2-extraido | 572 | 0 | 0.000000 | [0.000000, 0.006671] | 0 | 4841 | 0.242424 | 3 | 1.000000 | 197 |
| A_full | 572 | 0 | 0.000000 | [0.000000, 0.006671] | 0 | 4290 | 0.383484 | 42 | 1.000000 | 197 |
| B-ret | 572 | 0 | 0.000000 | [0.000000, 0.006671] | 0 | 18768 | 0.029412 | 0 | 1.000000 | 197 |
| B-sem | 572 | 66 | 0.115385 | [0.091730, 0.144171] | 239 | 335 | 1.000000 | 74 | 1.000000 | 197 |
| B-make | 572 | 0 | 0.000000 | [0.000000, 0.006671] | 0 | 4836 | 0.250000 | 3 | 1.000000 | 197 |

### Classes — primario (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | T4 | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | nao_exercida |
| FN | T3g-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | nao_exercida |
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | nao_exercida |
| FP | T3g-FP | 1 | 1 | 1 | 0.001748 [0.000309, 0.009836] | 0.000207 [0.000000, 0.000672] | nao_exercida |
| FP | T2 | 497 | 35 | 52 | 0.090909 [0.070000, 0.117277] | 0.102771 [0.063756, 0.145629] | exercida |
| FP | T5 | 4338 | 35 | 313 | 0.547203 [0.506231, 0.587545] | 0.897022 [0.854266, 0.935832] | exercida |

### Classes — multirrotulo (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | T4 | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | nao_exercida |
| FN | T3g-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | nao_exercida |
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | nao_exercida |
| FP | T3g-FP | 1 | 1 | 1 | 0.001748 [0.000309, 0.009836] | 0.000207 [0.000000, 0.000672] | nao_exercida |
| FP | T2 | 497 | 35 | 52 | 0.090909 [0.070000, 0.117277] | 0.102771 [0.063756, 0.145629] | exercida |
| FP | T5 | 4338 | 35 | 313 | 0.547203 [0.506231, 0.587545] | 0.897022 [0.854266, 0.935832] | exercida |

### Classes — alt_c (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | T4 | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | nao_exercida |
| FN | T3g-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | nao_exercida |
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | nao_exercida |
| FP | T3g-FP | 1 | 1 | 1 | 0.001748 [0.000309, 0.009836] | 0.000207 [0.000000, 0.000672] | nao_exercida |
| FP | T2 | 497 | 35 | 52 | 0.090909 [0.070000, 0.117277] | 0.102771 [0.063756, 0.145629] | exercida |
| FP | T5 | 4338 | 35 | 313 | 0.547203 [0.506231, 0.587545] | 0.897022 [0.854266, 0.935832] | exercida |

### Classes — ablacao (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | d3 (T2) | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | descritivo |
| FN | d2-extraido (T3g-FN) | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | descritivo |
| FN | SOBREPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | descritivo |
| FN | COMPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | descritivo |
| FN | NAO_REMOVIDA | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] |  [, ] | descritivo |
| FP | d3 (T2) | 550 | 35 | 55 | 0.096154 [0.074619, 0.123077] | 0.113730 [0.072661, 0.159346] | descritivo |
| FP | d2-extraido (T3g-FP) | 1 | 1 | 1 | 0.001748 [0.000309, 0.009836] | 0.000207 [0.000000, 0.000672] | descritivo |
| FP | SOBREPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] | 0.000000 [0.000000, 0.000000] | descritivo |
| FP | COMPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.006671] | 0.000000 [0.000000, 0.000000] | descritivo |
| FP | NAO_REMOVIDA | 4285 | 35 | 309 | 0.540210 [0.499235, 0.580648] | 0.886063 [0.840412, 0.927009] | descritivo |

### Descritores por ano (§4.7)
| ano | pares | exec. | NAO_EXEC | NAO_DET pares | identidade pares | ciclo pares | pendente pares | grafo vazio |
|---|---|---|---|---|---|---|---|---|
| 2010 | 69 | 62 | 7 | 0 | 0 | 0 | 0 | 0 |
| 2011 | 55 | 50 | 5 | 0 | 0 | 0 | 0 | 0 |
| 2012 | 18 | 18 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2013 | 37 | 37 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2014 | 94 | 91 | 3 | 0 | 0 | 0 | 0 | 0 |
| 2015 | 63 | 62 | 1 | 0 | 0 | 0 | 0 | 0 |
| 2016 | 19 | 19 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2017 | 44 | 42 | 2 | 0 | 0 | 0 | 0 | 0 |
| 2018 | 28 | 19 | 9 | 0 | 0 | 0 | 0 | 0 |
| 2019 | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2020 | 24 | 24 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2021 | 21 | 21 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2022 | 18 | 18 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2023 | 21 | 20 | 1 | 0 | 0 | 0 | 0 | 0 |
| 2024 | 25 | 25 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| todos | 600 | 572 | 28 | 0 | 0 | 0 | 0 | 0 |

Controles: nulos 600 (violacoes 0); placebo 37, com AIS != vazio (reportado como T4): 0; tags 0.

## Hipoteses (§7)
| H | corpus | estatistica | p | p Holm | estado |
|---|---|---|---|---|---|
| H1a | tz | 0/839 | 0.000000 | 0.000000 | nao refutada |
| H1b | lua | 0/572 | 0.000010 | 0.000010 | nao refutada |
| H8 | tz x zlib | {"tz": [55, 537], "zlib": [228, 82]} | 0.000000 | 0.000000 | nao refutada |
| H2 | tz | 0/210 |  |  | nao refutada |
| H2 | zlib | 0/204 |  |  | nao refutada |
| H2 | lua | 0/429 |  |  | nao refutada |
| H3 | tz A0+d3 | 0/839 |  |  | nao refutada |
| H3 | tz A0+d4-preciso | 0/839 |  |  | nao refutada |
| H3 | zlib A0+d3 | 0/500 |  |  | nao refutada |
| H3 | zlib A0+d2-extraido | 0/500 |  |  | nao refutada |
| H3 | lua A0+d3 | 0/572 |  |  | nao refutada |
| H3 | lua A0+d2-extraido | 0/572 |  |  | nao refutada |
| H4 | tz | 0/839 |  |  | REFUTADA |
| H5 | tz | 0/0 |  |  | nao_aplicavel (FN < 30) |
| H5 | zlib | 0/28 |  |  | nao_aplicavel (FN < 30) |
| H5 | lua | 0/0 |  |  | nao_aplicavel (FN < 30) |
| H6 | tz | 215/839 |  |  | nao refutada |
| H6 | zlib | 51/500 |  |  | nao refutada |
| H6 | lua | 66/572 |  |  | nao refutada |
| H7a | tz T1a | 0 |  |  | incompleta (r_tipo ausente em 839 pares) |
| H7a | tz T2 | 0 |  |  | incompleta (r_tipo ausente em 839 pares) |
| H7a | zlib T2 | 0 |  |  | incompleta (r_tipo ausente em 500 pares) |
| H7a | lua T2 | 0 |  |  | incompleta (r_tipo ausente em 572 pares) |
| H7b | zlib | 0 |  |  | incompleta (r_tipo ausente em 500 pares) |

## Regra do §8
| dominio | tese rejeitada no dominio | estado |
|---|---|---|
| tz | false | decidido |
| build C (zlib, Lua) | false | decidido |

Resultado negativo nos dois dominios: false
