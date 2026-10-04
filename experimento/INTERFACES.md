# INTERFACES — experimento V (V-0a)

Fonte: `../aparato/PROTOCOLO_V_2026-10-02.md` (§ = seção dele); em conflito vale o protocolo. Python 3.11; terceiros só `networkx` e `pygments` (wheels em `config.json`); estatística em biblioteca padrão.

## 0. Guardas

- `executar.py --modo {fixture,ensaio,confirmatorio}`:
  - `fixture`: só `nucleo/fixtures/{a6_tz,a7_c}`; único modo pré-DOI com oráculo real.
  - `ensaio`: só pares com p **e** c na janela de ensaio; oráculo sintético forçado; grava em `saidas/ensaio/`; nunca é resultado.
  - `confirmatorio`: sai com código 2 se `doi` nulo, se algum sha256 de `config.json` faltar ou divergir do arquivo, ou se `GITHUB_ACTIONS≠true` e `ci.local_autorizado=false` (D4).
- `janela(corpus, sha) -> "quadro"|"ensaio"|"fora"`, por ancestralidade git:
  - tz: ensaio ⇔ sha ⊑ `7550cb98da5f42e9e551f10caa725ce0b6b571b8`; quadro ⇔ data de autor ou de commit ≥ 2012-09-01;
  - zlib: ensaio ⇔ `bcf78a20978d76f64b7cd46d1a4d7a79a578c77b` ⊑ sha ⊑ `9712272c78b9d9c93746d9c8e156a3728c65ca72`; quadro ⇔ `10daf0d4d7815447799d555d04d30325836e1d44` ⊏ sha;
  - Lua: ensaio ⇔ datas de autor e de commit < 2010-01-01; quadro ⇔ alguma ≥ 2010-01-01.
- Em `ensaio`, p ou c com `janela≠"ensaio"` aborta a corrida inteira.
- `oraculo/*.sh` saem com código 9 se o alvo não for diretório de fixture, salvo `V_MODO=confirmatorio` e `doi` não nulo.

## 1. Registro por par — `saidas/<corpus>.jsonl`

Conjuntos são listas ordenadas. Nó tz: `R:<NOME>`, `Z:<nome>`, `L:<nome>`, `F:<arquivo>`; nó C: caminho relativo. Elemento tz: nome de saída; C: `<x>.o`.

```json
{"v":1, "corpus":"tz|zlib|lua|npm",
 "janela":"quadro|ensaio|fixture", "controle":null|"nulo"|"placebo"|"tag",
 "p":"<sha40>", "c":"<sha40>", "data_p":"<iso8601>", "data_c":"<iso8601>", "ano":2014,
 "semente_sorteio":0, "sha_config":"<hex>",
 "nao_executado":null|{"causa":"nao_constroi_p|nao_constroi_c|zic_recusa_p|zic_recusa_c|teto","detalhe":"..."},
 "oraculo":{"modo":"real|sintetico","dig":{"p1":"","p2":"","c1":"","c2":""}|null},
 "U":[], "S":{"<no>":"M|A|D|R"}, "AIS":[],
 "bracos":{"A0":B,"A0+d3":B,"A0+d4-ingenuo":B,"A0+d4-preciso":B,"A0+d2-extraido":B,
           "A0+d6":B,"A_full":B,"B-ret":B,"B-sem":B,"B-make":B},
 "instancias":[{"e":"<elem>","lado":"FN|FP","primario":"<rotulo>","multi":["<rotulo>"]}],
 "nc":true,
 "r_tipo":{"<regra>":{"fn_novo":[],"removidas":[]}},
 "sens":{"AIS_1970_2037":[]|null,"d1_anterior":{"<braco>":B}|null},
 "descritores":{"NAO_DETERMINISTICO":{"p":[],"c":[]},"MUDANCA_DE_IDENTIDADE":[],
                "CICLO":[["<no>"]],"AUTOLACO":["<no>"],"PENDENTE":[],"GRAFO_VAZIO":false},
 "h":"<hex>"}
```

- `B = {"EIS":[],"FN":[],"FP":[],"seguro":bool}` ou `null` se o braço não se aplica (§5): d4 só tz; d2-extraído e B-make só zlib/Lua; d6 só zlib. FN = AIS∖EIS, FP = EIS∖AIS, seguro ⇔ FN = ∅. EIS = U ∩ d1(reach(G,S)).
- Divergência `networkx` × `bfs_ref` aborta antes de gravar (§4.1).
- `U` = universo declarado nos dois lados ∩ elementos que o oráculo produz nos dois lados; o resto entra em `MUDANCA_DE_IDENTIDADE`. `AIS` já exclui `NAO_DETERMINISTICO`.
- `instancias` vêm só de A0. `rotulo ∈ {T1a,T1b,T2,T3-FN,T3-FP,T4,T5,INCLASSIFICADO-FN}`; T3 vira T3m (zlib) ou T3g (Lua) só no relato. `primario` segue §4.6 (FN: T4>T3-FN>T1b>INCL.; FP: T3-FP>T2>T1a>T5). A precedência alternativa (c) e a ablação (b) saem de `multi` e `bracos` no `analise.py`.
- `r_tipo` (H7) guarda só regras com efeito. Chaves: `rho:<orig>><dest>:<M|A|D|R>` e `alfa:<orig>><dest>`.
- `sens` só no tz: segunda janela do `zdump` e atribuição de comentário à estrofe anterior.
- Com `nao_executado≠null`, `U`, `S`, `AIS`, `bracos` e `instancias` ficam vazios. O par é contado e nunca reposto.
- **Cadeia.** `C_i` = JSON canônico (`sort_keys=True`, `separators=(",",":")`, `ensure_ascii=False`, UTF-8) do registro sem `h`. `h_i = sha256(L_{i-1} ‖ C_i)`, com `L_{i-1}` = bytes da linha anterior sem `\n` e `L_0` = hex do sha256 de `config.json`. A linha gravada é o JSON canônico com `h`.

## 2. API

### 2.1 `nucleo/` — sem import de `adaptadores`, `detectores` nem `ganchos`

```python
# reach.py  -- unico ponto de entrada do fecho; SEMPRE diferencial
def reach(G: nx.DiGraph, S: Iterable[str]) -> frozenset[str]
    # S ∪ ⋃ nx.descendants(G,s); s∉V(G) contribui só s. Roda também bfs_ref; divergência levanta
    # DivergenciaNucleo (aborta a corrida inteira). S str/bytes -> TypeError. reach_diferencial é alias.
def eis(G, S, U, elemento: Callable[[str], str|None]) -> frozenset[str]   # U ∩ d1(reach(G,S))
def descritores(G, S=()) -> dict   # CICLO: CFC com >1 nó; AUTOLACO: nós com u→u (contados à parte, não são CICLO);
                                   # GRAFO_VAZIO: |E| = 0; S não altera o resultado
def pendentes(G, definidos) -> list[str]   # nós de G fora de `definidos`; o runner grava adaptador.pendentes(a)
class DivergenciaNucleo(RuntimeError)
def adjacencia(G) -> dict[str, set[str]]
# bfs_ref.py: ≤ 40 linhas, só biblioteca padrão
def bfs_ref(adj: dict[str, set[str]], S) -> frozenset[str]
```

Aresta u→v = "v consome u". `nx.descendants` e `bfs_ref` só existem em `nucleo/` (teste de AST em `nucleo/test_aceitacao.py`). Runner, detectores (via `ctx["reach"]`, injetado) e `diferencial_parser` (parâmetro `reach`) chamam `reach`/`eis`, nunca `nx.descendants`: todo par e todo braço, inclusive T3, T4 e o critério NC, passam pelo diferencial.

### 2.2 `adaptadores/` — `tz.py`, `cbuild.py`, `npm.py`, cada um com ≤ 400 linhas

- Todo literal de arquivo fica em `decl_<corpus>.json` com citação `<repo>@<sha>:<arq>:<linha>`: lista `TDATA` de reserva, entradas de configuração, d6 do zlib, cabeçalho gerado, globs de placebo.
- `Arvore` é um commit lido por `git show` e `git ls-tree` (`git_arvore.py`).

```python
ESPEC: dict[str, str]                       # (i) campo -> especificação citada
def d1_nos(a) -> dict[str, bytes]           # nó -> bytes atribuídos
def d1_tipo(no) -> str                      # tz {Rule,Zone,Link,F}; C {fonte,cabecalho,cabecalho_gerado,configuracao,objeto}
def d1_elemento(no) -> str | None
def d1_universo(ap, ac) -> set[str]
def semente(ap, ac) -> dict[str, str]       # nó -> M|A|D|R
def b_sem(S, U) -> set[str]                 # tz: Z/L de S; C: x.o de x.c ∈ S
def d2_declarado(a) -> nx.DiGraph           # attr origem ∈ {"declarada","config"}
def d2_extraido(a) -> tuple[nx.DiGraph, dict] | None   # gcc -MM; cobertura {"c_total","c_ok"}
def d3_checksum(no, a) -> str               # tz: léxico zic(8); C: tokens pygments sem Comment.* nem espaço
def d4_intervalos(a) -> dict[tuple[str,str], list[tuple[float,float]]] | None  # (R,Z) -> [ini, fim]
def d4_alteradas(R, ap, ac) -> list[tuple[str,int,float]]   # (lado, FROM, TO) de p△c
D5: dict | None                             # só npm: {"resolucao":"por_data","espec":...}
def d6_globais(a) -> set[str]               # zlib: de decl; tz/Lua: set()
D7 = "fecho_sobre_ciclo_e_conta"
def d8_nao_det(a) -> set[str]               # declarado a priori; vazio salvo citação
def pendentes(a) -> set[str]
def b_make(ac, S) -> set[str] | None        # make -t; touch S; make -n --debug=b; alvos .o "Must remake"
```

- Ferramentas permitidas (§4.3 iv): `git`, `make -pn`, `make -t/-n` (só em `b_make` e no diferencial do parser), `gcc -MM` (só em `d2_extraido`) e `pygments`.
- No zlib, `make -pn -f Makefile.in`, sem rodar `configure` (o `configure` compila testes).
- G = G_p ∪ G_c.

### 2.3 `detectores/` — congelados antes de `ganchos/`

```python
def rotular(corpus, inst: list[tuple[str,str]], ctx) -> dict[str, list[str]]   # elemento -> multi
def primario(lado, multi, precedencia="padrao"|"alt_c") -> str
def nc(corpus, ctx) -> bool                                                     # §5
```

- `ctx`: árvores p e c, S, U, G_decl, G_obs (vindo do runner), mais os intervalos e as linhas alteradas de d4.
- T2 no tz usa um léxico próprio do módulo (PARTILHADO). T2 em C usa `gcc -fpreprocessed -dD -E -P` nos dois lados (INDEPENDENTE).

### 2.4 `ganchos/` — importar `detectores` é proibido (auditoria por AST)

Assinatura única: `aplicar(G, S: dict, dados: dict) -> (G', S')`. O gancho não chama `reach`.

- `d3.py`: tira de S o nó com `d3_checksum` igual nos dois lados.
- `d4.py`:
  - `ingenuo`: poda R→Z se toda linha alterada [FROM,TO] é disjunta de todo intervalo;
  - `preciso`: poda só se todo FROM > UNTIL+1 em todo intervalo. Nunca poda Rule anterior ao início da linha de Zone, nem no ano do UNTIL ou no seguinte.
- `d2x.py`: troca as arestas de conteúdo de G_decl pelas de G_obs e mantém as `config`.
- `d6.py`: acrescenta arestas global → todo nó objeto.
- `r_tipo.py`: `regras(tipos) -> list[str]` e `aplicar_regra(G, S, regra, d1_tipo)`, com busca exaustiva (H7).
- A_full = d3 ∘ d4-preciso ∘ d2x ∘ d6, restrito ao que se aplica.

### 2.5 `oraculo/` — shell; nunca chama Python do experimento

| script | entrada | saída em `<saida>/` | código |
|---|---|---|---|
| `tz_zdump.sh <repo> <sha> <bin> <saida> [a,b]` | `zic`/`zdump` de `tz@bec4d95a` em `<bin>`; `TDATA` do commit ou reserva; `a,b`=1800,2100 | `<nome>.zdump` (`zdump -v -c a,b`, `TZDIR`); `manifesto.tsv`: `nome  especie  sha256` | 3 zic recusa |
| `c_build.sh <zlib\|lua> <repo> <sha> <saida>` | gcc 13.3.0, make 4.3, `SOURCE_DATE_EPOCH=0`, comandos §3.2 | `objs/*.o`; `manifesto.tsv`: `objeto  sha256  bytes` | 4 não constrói |
| `npm_lock.sh <manifesto> <data> <saida>` | npm 10.9.4 `--package-lock-only --before` | `package-lock.json`, `resolvido.tsv` | 5 teto |

- O runner chama cada lado duas vezes. Elemento cujo sha256 difere entre as duas execuções vai para `NAO_DETERMINISTICO`.
- Igualdade de elemento = igualdade do sha256 do arquivo inteiro.
- Os três scripts saem com 0 em sucesso e 9 pela guarda.

`ensaio/sintetico.py`: `ais_sintetico(U, semente, p, c, q=0.1) -> set[str]`, Bernoulli(q) por elemento com `random.Random(f"{semente}:{p}:{c}")`. Só o oráculo é trocado; o resto do pipeline roda igual.

### 2.6 `analise/analise.py`

**Entrada:** `saidas/<corpus>.jsonl` e `config.json`. O script recalcula a cadeia e o `sha_config` e recusa o arquivo se divergirem. `--ensaio` lê `saidas/ensaio/` e marca "ENSAIO" em toda saída.

**Saídas, em `saidas/analise/`:**
- `por_par_<corpus>.csv`, §6.1, por braço: seguro, |FN|, |FP|, revocação, precisão-teto, |EIS|/|U|; os indefinidos são contados;
- `por_classe_<corpus>.csv`, §6.2: instâncias, elementos distintos e pares com ≥ 1 instância; frações por primário, multirrótulo, alt_c e ablação; Wilson 95% e bootstrap com 10⁴ reamostragens; "não exercida" quando < 5;
- `hipoteses.json`: para H1a–H8, estatística, p, p Holm sobre {H1a,H1b,H8}, refutada e contraexemplos (par, elemento);
- `mcnemar.json` e `sensibilidades.json` (§6.4);
- `descritores.csv`, por corpus × ano.

Nunca soma entre corpora, e o Lua sai separado. Binomial exato, Fisher e McNemar exato em `math.comb`, sem scipy.

`executar.py pares <corpus>` grava `saidas/pares_<corpus>.tsv` (`c  p  data_c  janela  controle`) usando só `git` e `make -pn`.

## 3. `config.json`

```json
{"v":1, "doi":null,
 "protocolo":{"arquivo":"artigos/V/aparato/PROTOCOLO_V_2026-10-02.md","sha256_deposito":null},
 "sementes":{"principal":null,"ensaio":0,"bootstrap":10000},
 "corpora":{"tz":{"congelamento":"bec4d95a…","data_min":"2012-09-01","ensaio_ultimo":"7550cb98…"},
            "zlib":{"congelamento":"767c4c94…","apos":"10daf0d4…","ensaio":["bcf78a20…","9712272c…"]},
            "lua":{"congelamento":"0b29f408…","data_min":"2010-01-01","amostra":600}},
 "modulos":{"<caminho relativo>":"<sha256>"},
 "wheels":{"networkx":{"versao":"","arquivo":"","sha256":""},"pygments":{"versao":"","arquivo":"","sha256":""}},
 "toolchain":{"imagem_digest":null,
   "binarios":{"gcc":"","cc1":"","make":"","zic":"","zdump":""},
   "dpkg":{"gcc-13":"","make":""},
   "gcc_linha1":"gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0","python":"3.11.x","npm":"10.9.4"},
 "ci":{"runner":"ubuntu-24.04","local_autorizado":false}}
```

- `principal = int.from_bytes(sha256(bytes do depósito)[:8], "big")`.
- Sorteios: `random.Random(f"{principal}:{uso}")` com `uso ∈ {lua_amostra, reexec_10pct, npm_raizes, bootstrap:<corpus>}`, sobre a população ordenada pelo sha de c.
- `modulos` cobre todo `.py`, `.sh`, `decl_*.json` e `ci/*` de `nucleo`, `adaptadores`, `detectores`, `ganchos`, `oraculo`, `analise`, `ensaio` e `auditoria`, mais `executar.py`.
- Sem docker, `imagem_digest` fica nulo e `binarios` + `dpkg` o substituem. Isso fica anotado para o V-0c.
- `ci/oraculo.yml`:
  - aborta se `gcc --version | head -1` ≠ `gcc_linha1` ou se `make --version` ≠ 4.3;
  - instala os wheels com `pip install --require-hashes -r ci/requirements.txt`.

## 4. Layout (§11.1; `+` = adição)

```
experimento/
  INTERFACES.md  config.json  executar.py(+)
  nucleo/       reach.py bfs_ref.py test_aceitacao.py (A1–A7) fixtures/{a6_tz,a7_c}/
  adaptadores/  tz.py cbuild.py npm.py git_arvore.py(+) decl_{tz,zlib,lua}.json(+)
  detectores/   rotular.py nc.py
  ganchos/      d3.py d4.py d2x.py d6.py r_tipo.py
  oraculo/      tz_zdump.sh c_build.sh npm_lock.sh
  analise/      analise.py
  ensaio/(+)    sintetico.py
  auditoria/(+) auditar.py   # §4.3 i–iv; grep de U/artefato e §10.3; ganchos↛detectores; oraculo↛python
  ci/           oraculo.yml requirements.txt
  saidas/       <corpus>.jsonl  pares_<corpus>.tsv  ensaio/  fixtures/  analise/
```
