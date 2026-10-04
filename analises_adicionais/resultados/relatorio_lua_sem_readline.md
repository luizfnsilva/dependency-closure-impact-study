# Analise V — CONFIRMATORIO
Gerado por `analise/analise.py` diretamente dos JSONL; nada somado entre corpora; Lua e replica, reportada a parte.

## Entradas
| arquivo | corpus | linhas | cadeia | sha256 | preenchidos (ensaio) |
|---|---|---|---|---|---|
| experimento/saidas/lua.jsonl | lua | 1237 | integra | 9fa9b0b27cedbfdcaf0314b29f0d1476d56c1d8d7baf05ea3d4789b4efb0eb54 | {} |

## lua (replica, separada do zlib)

Pares primarios: 600; executados: 48.

### Bracos (§6.1)
| braco | pares | inseguros | frac | Wilson 95% | inst FN | inst FP | mediana precisao-teto | prec. indef. | mediana revocacao | rev. indef. |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 | 48 | 0 | 0.000000 | [0.000000, 0.074100] | 0 | 566 | 0.281746 | 0 | 1.000000 | 14 |
| A0+d3 | 48 | 0 | 0.000000 | [0.000000, 0.074100] | 0 | 510 | 0.368421 | 3 | 1.000000 | 14 |
| A0+d2-extraido | 48 | 0 | 0.000000 | [0.000000, 0.074100] | 0 | 565 | 0.305556 | 0 | 1.000000 | 14 |
| A_full | 48 | 0 | 0.000000 | [0.000000, 0.074100] | 0 | 509 | 0.368421 | 3 | 1.000000 | 14 |
| B-ret | 48 | 0 | 0.000000 | [0.000000, 0.074100] | 0 | 1542 | 0.029412 | 0 | 1.000000 | 14 |
| B-sem | 48 | 7 | 0.145833 | [0.072482, 0.271672] | 30 | 39 | 1.000000 | 4 | 1.000000 | 14 |
| B-make | 48 | 0 | 0.000000 | [0.000000, 0.074100] | 0 | 566 | 0.281746 | 0 | 1.000000 | 14 |

### Classes — primario (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | T4 | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | nao_exercida |
| FN | T3g-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | nao_exercida |
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | nao_exercida |
| FP | T3g-FP | 1 | 1 | 1 | 0.020833 [0.003687, 0.108992] | 0.001767 [0.000000, 0.006400] | nao_exercida |
| FP | T2 | 56 | 33 | 7 | 0.145833 [0.072482, 0.271672] | 0.098940 [0.006802, 0.238868] | exercida |
| FP | T5 | 509 | 34 | 30 | 0.625000 [0.483628, 0.747847] | 0.899293 [0.759587, 0.991709] | exercida |

### Classes — multirrotulo (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | T4 | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | nao_exercida |
| FN | T3g-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | nao_exercida |
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | nao_exercida |
| FP | T3g-FP | 1 | 1 | 1 | 0.020833 [0.003687, 0.108992] | 0.001767 [0.000000, 0.006400] | nao_exercida |
| FP | T2 | 56 | 33 | 7 | 0.145833 [0.072482, 0.271672] | 0.098940 [0.006802, 0.238868] | exercida |
| FP | T5 | 509 | 34 | 30 | 0.625000 [0.483628, 0.747847] | 0.899293 [0.759587, 0.991709] | exercida |

### Classes — alt_c (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | T4 | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | nao_exercida |
| FN | T3g-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | nao_exercida |
| FN | INCLASSIFICADO-FN | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | nao_exercida |
| FP | T3g-FP | 1 | 1 | 1 | 0.020833 [0.003687, 0.108992] | 0.001767 [0.000000, 0.006400] | nao_exercida |
| FP | T2 | 56 | 33 | 7 | 0.145833 [0.072482, 0.271672] | 0.098940 [0.006802, 0.238868] | exercida |
| FP | T5 | 509 | 34 | 30 | 0.625000 [0.483628, 0.747847] | 0.899293 [0.759587, 0.991709] | exercida |

### Classes — ablacao (§6.2)
| lado | categoria | instancias | elem. distintos | pares | frac pares [Wilson] | frac lado [bootstrap] | status |
|---|---|---|---|---|---|---|---|
| FN | d3 (T2) | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | descritivo |
| FN | d2-extraido (T3g-FN) | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | descritivo |
| FN | SOBREPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | descritivo |
| FN | COMPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | descritivo |
| FN | NAO_REMOVIDA | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] |  [, ] | descritivo |
| FP | d3 (T2) | 56 | 33 | 7 | 0.145833 [0.072482, 0.271672] | 0.098940 [0.006802, 0.238868] | descritivo |
| FP | d2-extraido (T3g-FP) | 1 | 1 | 1 | 0.020833 [0.003687, 0.108992] | 0.001767 [0.000000, 0.006400] | descritivo |
| FP | SOBREPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] | 0.000000 [0.000000, 0.000000] | descritivo |
| FP | COMPOSTA | 0 | 0 | 0 | 0.000000 [0.000000, 0.074100] | 0.000000 [0.000000, 0.000000] | descritivo |
| FP | NAO_REMOVIDA | 509 | 34 | 30 | 0.625000 [0.483628, 0.747847] | 0.899293 [0.759587, 0.991709] | descritivo |

### Descritores por ano (§4.7)
| ano | pares | exec. | NAO_EXEC | NAO_DET pares | identidade pares | ciclo pares | pendente pares | grafo vazio |
|---|---|---|---|---|---|---|---|---|
| 2010 | 69 | 0 | 69 | 0 | 0 | 0 | 0 | 0 |
| 2011 | 55 | 0 | 55 | 0 | 0 | 0 | 0 | 0 |
| 2012 | 18 | 0 | 18 | 0 | 0 | 0 | 0 | 0 |
| 2013 | 37 | 0 | 37 | 0 | 0 | 0 | 0 | 0 |
| 2014 | 94 | 0 | 94 | 0 | 0 | 0 | 0 | 0 |
| 2015 | 63 | 0 | 63 | 0 | 0 | 0 | 0 | 0 |
| 2016 | 19 | 0 | 19 | 0 | 0 | 0 | 0 | 0 |
| 2017 | 44 | 0 | 44 | 0 | 0 | 0 | 0 | 0 |
| 2018 | 28 | 0 | 28 | 0 | 0 | 0 | 0 | 0 |
| 2019 | 34 | 0 | 34 | 0 | 0 | 0 | 0 | 0 |
| 2020 | 24 | 0 | 24 | 0 | 0 | 0 | 0 | 0 |
| 2021 | 21 | 0 | 21 | 0 | 0 | 0 | 0 | 0 |
| 2022 | 18 | 0 | 18 | 0 | 0 | 0 | 0 | 0 |
| 2023 | 21 | 0 | 21 | 0 | 0 | 0 | 0 | 0 |
| 2024 | 25 | 18 | 7 | 0 | 0 | 0 | 0 | 0 |
| 2025 | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| todos | 600 | 48 | 552 | 0 | 0 | 0 | 0 | 0 |

Controles: nulos 600 (violacoes 0); placebo 37, com AIS != vazio (reportado como T4): 0; tags 0.

## Hipoteses (§7)
| H | corpus | estatistica | p | p Holm | estado |
|---|---|---|---|---|---|
| H1a | tz | / |  |  | nao_testavel |
| H1b | lua | 0/48 | 0.379185 | 1.000000 | REFUTADA |
| H8 | tz x zlib | null |  |  | nao_testavel |
| H2 | tz | / |  |  | nao_testavel |
| H2 | zlib | / |  |  | nao_testavel |
| H2 | lua | 0/17 |  |  | nao refutada |
| H3 | tz A0+d3 | 0/0 |  |  | nao_testavel |
| H3 | tz A0+d4-preciso | 0/0 |  |  | nao_testavel |
| H3 | zlib A0+d3 | 0/0 |  |  | nao_testavel |
| H3 | zlib A0+d2-extraido | 0/0 |  |  | nao_testavel |
| H3 | lua A0+d3 | 0/48 |  |  | nao refutada |
| H3 | lua A0+d2-extraido | 0/48 |  |  | nao refutada |
| H4 | tz | 0/0 |  |  | nao_testavel |
| H5 | tz | / |  |  | nao_testavel |
| H5 | zlib | / |  |  | nao_testavel |
| H5 | lua | 0/0 |  |  | nao_aplicavel (FN < 30) |
| H6 | tz | / |  |  | nao_testavel |
| H6 | zlib | / |  |  | nao_testavel |
| H6 | lua | 7/48 |  |  | nao refutada |
| H7a | tz T1a | 0 |  |  | nao_testavel |
| H7a | tz T2 | 0 |  |  | nao_testavel |
| H7a | zlib T2 | 0 |  |  | nao_testavel |
| H7a | lua T2 | 0 |  |  | incompleta (r_tipo ausente em 48 pares) |
| H7b | zlib | 0 |  |  | nao_testavel |

## Regra do §8
| dominio | tese rejeitada no dominio | estado |
|---|---|---|
| tz |  | nao_decidivel |
| build C (zlib, Lua) |  | nao_decidivel |

Resultado negativo nos dois dominios: 
