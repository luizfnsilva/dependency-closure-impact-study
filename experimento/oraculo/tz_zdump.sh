#!/usr/bin/env bash
# Oraculo tz (PROTOCOLO_V_2026-10-02 §3.1; INTERFACES §0 e §2.5).
# Executor de terceiros: zic e zdump compilados UMA vez de tz@bec4d95a
# (tz_ferramentas.sh). Nunca chama Python do experimento, nem o fecho, nem os
# adaptadores; le so a arvore do lado e os binarios.
#
# Uso:
#   tz_zdump.sh <repo> <lado> <bin> <saida> [a,b]
#       um lado, uma execucao: zic -d <dir> sobre os arquivos de dados do lado;
#       para cada nome de saida, zdump -v -c a,b <nome> com <dir> como TZDIR
#       (caminho absoluto; ver nota em um_lado).
#       Grava <saida>/zdump/<nome>.zdump, <saida>/manifesto.tsv
#       (nome<TAB>especie<TAB>sha256), <saida>/dados.txt, <saida>/zic.stderr.
#   tz_zdump.sh --par <repo> <p> <c> <bin> <saida> [a,b]
#       par: cada lado DUAS vezes (<saida>/{p1,p2,c1,c2}) e <saida>/comparacao.tsv
#       (nome<TAB>classe; classe em AIS, IGUAL, NAO_DETERMINISTICO_p,
#       NAO_DETERMINISTICO_c, MUDANCA_DE_IDENTIDADE, AUSENTE = declarado e nao
#       produzido nos dois lados).
# <repo>/<lado> e um diretorio (fixture) ou <repo> e um repositorio git e <lado> um commit.
# Janela padrao 1800,2100 (§3.1); sensibilidade W' = 1970,2037 (§6.4).
#
# Guarda (INTERFACES §0): sai com 9, sem ler nada, se o ALVO EFETIVO nao estiver sob
# nucleo/fixtures/, salvo V_MODO=confirmatorio e "doi" nao nulo em config.json.
# Alvo efetivo = <repo> e, quando <repo>/<lado> e diretorio, o realpath desse diretorio
# (symlink que escapa e recusado). <lado> com '/', '..', vazio, '.' ou '-' inicial: 9.
# Falha do zdump em QUALQUER nome (cod. 2) aborta o par: e defeito de ferramenta, nunca
# propriedade dos dados; nada e classificado (nao vira AIS nem NAO_EXECUTADO).
# Codigos: 0 ok; 2 uso/ferramenta; 3 zic recusa os dados; 9 guarda.
# Escreve em <saida>: faltantes.txt (arquivo da lista de dados ausente), tdata_fonte.txt
# (makefile | reserva_sem_makefile | reserva_sem_tdata | reserva_make_falhou |
# reserva_dinamico), identicos aos descritores do adaptador (tz.dados_status).
set -euo pipefail
export LC_ALL=C
unset TZ MAKEFLAGS MFLAGS

AQUI=$(cd "$(dirname "$0")" && pwd -P)
EXP=$(dirname "$AQUI")
JANELA_PADRAO=1800,2100
# Lista fixa do §2.5, usada quando o Makefile do lado nao define TDATA.
# Igual a adaptadores/decl_tz.json:tdata_reserva (conferido por teste).
RESERVA="africa antarctica asia australasia europe northamerica southamerica etcetera factory backward"
EXCLUIR="backzone"   # §2.5: backzone fora

morre() { echo "tz_zdump: $2" >&2; exit "$1"; }

guarda() {   # repo lado
  local real fx efet
  case "$2" in
    ''|.|-*|/*|*/*|*..*) morre 9 "guarda: lado invalido: '$2'" ;;
  esac
  real=$(cd "$1" 2>/dev/null && pwd -P) || morre 2 "repo inexistente: $1"
  fx=$(cd "$EXP/nucleo/fixtures" 2>/dev/null && pwd -P) || fx=/nenhum
  efet=$real
  [ -d "$real/$2" ] && efet=$(cd "$real/$2" && pwd -P)
  case "$real/" in "$fx"/*) case "$efet/" in "$fx"/*) return 0 ;; esac ;; esac
  if [ "${V_MODO:-}" = confirmatorio ] && [ -f "$EXP/config.json" ] \
     && grep -Eq '"doi"[[:space:]]*:[[:space:]]*"[^"]+"' "$EXP/config.json"; then
    return 0
  fi
  morre 9 "guarda: $efet nao e fixture e nao ha V_MODO=confirmatorio com doi"
}

verifica_bin() {
  [ -x "$BIN/zic" ] && [ -x "$BIN/zdump" ] && [ -f "$BIN/SHA256SUMS" ] \
    || morre 2 "faltam zic/zdump/SHA256SUMS em $BIN (rode tz_ferramentas.sh)"
  (cd "$BIN" && sha256sum --quiet -c SHA256SUMS) >&2 || morre 2 "sha256 de zic/zdump diverge"
}

materializa() {   # repo lado destino
  if [ -d "$1/$2" ]; then
    cp -R "$1/$2/." "$3/"
  else
    local top
    top=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || morre 2 "lado invalido: $2"
    [ "$(cd "$top" && pwd -P)" = "$(cd "$1" && pwd -P)" ] || morre 2 "$1 nao e raiz de repositorio git"
    git -C "$1" rev-parse --verify -q "$2^{commit}" >/dev/null || morre 2 "commit invalido: $2"
    git -C "$1" archive --format=tar "$2" | tar -x -C "$3"
  fi
}

lista_dados() {   # dir saida: arquivos de dados do lado (§2.5), um por linha
  # TDATA e expandido pelo make SO sobre o Makefile, num diretorio vazio (mesmo contexto
  # do adaptador). Makefile com $(shell|wildcard|eval|file), include ou != nao e
  # executado: lista fixa (reserva_dinamico).
  local d=$1 v="" fonte=reserva_sem_makefile out tm
  if [ -f "$d/Makefile" ]; then
    if grep -Eq '[$][({][[:space:]]*(shell|wildcard|eval|file)[[:space:]]|^[[:space:]]*-?(include|sinclude)[[:space:]]|!=' "$d/Makefile"; then
      fonte=reserva_dinamico
    else
      tm=$(mktemp -d); cp "$d/Makefile" "$tm/Makefile"
      out=$(cd "$tm" && printf '%s\n' '$(info __V_VAL__=$(TDATA))' '__v_alvo: ;' \
          | timeout 60 env -i PATH="$PATH" LC_ALL=C make -pn -r -R -f Makefile -f - __v_alvo 2>/dev/null) || out=""
      rm -rf "$tm"
      if printf '%s\n' "$out" | grep -q '^__V_VAL__='; then
        v=$(printf '%s\n' "$out" | sed -n 's/^__V_VAL__=//p' | head -n1)
        fonte=makefile; [ -n "${v//[[:space:]]/}" ] || fonte=reserva_sem_tdata
      else
        fonte=reserva_make_falhou
      fi
    fi
  fi
  [ -n "${v//[[:space:]]/}" ] || v=$RESERVA
  echo "$fonte" > "$2/tdata_fonte.txt"
  local f
  for f in $v; do
    case " $EXCLUIR " in *" $f "*) continue ;; esac
    if [ -f "$d/$f" ]; then echo "$f"; else echo "$f" >> "$2/faltantes.txt"; fi
  done | awk '!visto[$0]++'
}

# Nomes de saida e especie, lidos dos arquivos de dados por zic(8) de tz@bec4d95a:
# lexico zic.8:336-345; tipos de linha e palavras-chave zic.8:346-359;
# Zone NAME (campo 2) zic.8:571; continuacao zic.8:677-689; Link TARGET LINK-NAME
# (campo 3) zic.8:745-778. So para listar nomes; nao calcula nada.
AWK_NOMES='
BEGIN { WS = " \t\r" sprintf("%c%c", 11, 12); KW[1] = "rule"; KW[2] = "zone"; KW[3] = "link" }
function lexa(s,   n, i, c, q, f, tem) {
  n = 0; f = ""; q = 0; tem = 0
  for (i = 1; i <= length(s); i++) {
    c = substr(s, i, 1)
    if (q) { if (c == "\"") q = 0; else f = f c; continue }
    if (c == "\"") { q = 1; tem = 1; continue }
    if (c == "#") break
    if (index(WS, c)) { if (tem) { F[++n] = f; f = ""; tem = 0 } ; continue }
    f = f c; tem = 1
  }
  if (tem) F[++n] = f
  return q ? -1 : n
}
function kw(w,   lw, k, achado, m) {
  lw = tolower(w)
  if (lw == "") return ""
  for (k = 1; k <= 3; k++) if (lw == KW[k]) return lw
  m = 0
  for (k = 1; k <= 3; k++) if (substr(KW[k], 1, length(lw)) == lw) { achado = KW[k]; m++ }
  return (m == 1) ? achado : ""
}
FNR == 1 { cont = 0 }
{
  n = lexa($0)
  if (n < 0) { cont = 0; next }
  if (n == 0) next
  if (cont) { cont = (n >= 3 && n <= 7) ? (n > 3) : 0; next }
  t = kw(F[1])
  if (t == "zone" && n >= 5 && n <= 9) { print F[2] "\tZone"; cont = (n > 5) }
  else if (t == "link" && n == 3) print F[3] "\tLink"
}'

um_lado() {   # repo lado saida janela -> 0 | 3
  local repo=$1 lado=$2 saida=$3 janela=$4 tmp
  tmp=$(mktemp -d)
  mkdir -p "$tmp/src" "$tmp/zi" "$saida/zdump"
  : > "$saida/manifesto.tsv"; : > "$saida/faltantes.txt"; : > "$saida/zdump.stderr"
  materializa "$repo" "$lado" "$tmp/src"
  lista_dados "$tmp/src" "$saida" > "$saida/dados.txt"
  local -a arqs=()
  mapfile -t arqs < "$saida/dados.txt"
  if [ ${#arqs[@]} -gt 0 ]; then
    if ! (cd "$tmp/src" && "$BIN/zic" -d "$tmp/zi" "${arqs[@]}" < /dev/null) 2> "$saida/zic.stderr"; then
      rm -rf "$tmp"
      return 3
    fi
    (cd "$tmp/src" && awk "$AWK_NOMES" "${arqs[@]}") \
      | sort -t "$(printf '\t')" -k1,1 -k2,2 -u \
      | awk -F '\t' '{ if ($1 in e) e[$1] = e[$1] "+" $2; else e[$1] = $2 } END { for (n in e) print n "\t" e[n] }' \
      | sort > "$tmp/nomes.tsv"
    # zdump em lote (uma invocacao para todos os nomes produzidos pelo zic).
    # (1) O zdump de tz@bec4d95a nao le TZDIR do ambiente (TZDIR e constante de
    #     compilacao: tz@bec4d95a:NEWS:869-871, localtime.c:870-875); o equivalente e
    #     passar o caminho absoluto <dir>/<nome> e retirar o prefixo <dir>/ de cada linha.
    # (2) Com varios argumentos, o zdump alinha o nome a largura do maior argumento
    #     (tz@bec4d95a:zdump.c:523-530,792: "%-*s  "); a saida de cada nome e reposta
    #     na forma de uma invocacao com so esse nome: "<nome>" + 2 espacos + resto.
    local nome esp sha
    while IFS="$(printf '\t')" read -r nome esp; do
      if [ -f "$tmp/zi/$nome" ]; then
        mkdir -p "$(dirname "$saida/zdump/$nome")"
        : > "$saida/zdump/$nome.zdump"
        printf '%s\0' "$tmp/zi/$nome" >> "$tmp/caminhos"
      fi
    done < "$tmp/nomes.tsv"
    if [ -s "$tmp/caminhos" ]; then
      xargs -0 -n 50 "$BIN/zdump" -v -c "$janela" < "$tmp/caminhos" 2>> "$saida/zdump.stderr" \
        | awk -v pre="$tmp/zi/" -v dir="$saida/zdump" '
            index($0, pre) != 1 { print "linha inesperada: " $0 > "/dev/stderr"; erro = 1; next }
            {
              s = substr($0, length(pre) + 1); k = index(s, "  ")
              if (k == 0) { print "linha inesperada: " $0 > "/dev/stderr"; erro = 1; next }
              n = substr(s, 1, k - 1); r = substr(s, k)
              sub(/^ +/, "", r)
              if (n != atual) { if (atual != "") close(arq); atual = n; arq = dir "/" n ".zdump" }
              print n "  " r >> arq
            }
            END { exit erro }' \
        || morre 2 "zdump falhou (ver $saida/zdump.stderr)"
    fi
    while IFS="$(printf '\t')" read -r nome esp; do
      sha=AUSENTE
      if [ -f "$tmp/zi/$nome" ]; then
        sha=$(sha256sum < "$saida/zdump/$nome.zdump" | cut -d' ' -f1)
      fi
      printf '%s\t%s\t%s\n' "$nome" "$esp" "$sha" >> "$saida/manifesto.tsv"
    done < "$tmp/nomes.tsv"
  fi
  rm -rf "$tmp"
  return 0
}

compara() {   # saida: <saida>/{p1,p2,c1,c2}/manifesto.tsv -> <saida>/comparacao.tsv
  # Presente = declarado e produzido (sha256 de 64 hex). Por nome:
  #  presenca/especie/sha diferente entre as duas execucoes do mesmo lado -> NAO_DETERMINISTICO_<lado>;
  #  senao, presente em um so lado ou especie diferente -> MUDANCA_DE_IDENTIDADE (§3.1, §4.7);
  #  senao, sha256 de p != de c -> AIS; igual -> IGUAL.
  awk -F '\t' '
    FNR == 1 { k++ }
    { nomes[$1] = 1; if ($3 ~ /^[0-9a-f]+$/ && length($3) == 64) { esp[k, $1] = $2; sha[k, $1] = $3 } }
    function chave(j, n) { return ((j, n) in esp) ? esp[j, n] "|" sha[j, n] : "-" }
    END {
      for (n in nomes) {
        c = ""
        if (chave(1, n) != chave(2, n)) c = "NAO_DETERMINISTICO_p"
        if (chave(3, n) != chave(4, n)) c = (c == "" ? "" : c ",") "NAO_DETERMINISTICO_c"
        if (c == "") {
          a1 = ((1, n) in esp); a3 = ((3, n) in esp)
          if (!a1 && !a3) c = "AUSENTE"
          else if (a1 != a3) c = "MUDANCA_DE_IDENTIDADE"
          else if (esp[1, n] != esp[3, n]) c = "MUDANCA_DE_IDENTIDADE"
          else c = (sha[1, n] == sha[3, n]) ? "IGUAL" : "AIS"
        }
        print n "\t" c
      }
    }' "$1/p1/manifesto.tsv" "$1/p2/manifesto.tsv" "$1/c1/manifesto.tsv" "$1/c2/manifesto.tsv" \
    | sort > "$1/comparacao.tsv"
}

if [ "${1:-}" = "--par" ]; then
  [ $# -ge 6 ] && [ $# -le 7 ] || morre 2 "uso: $0 --par <repo> <p> <c> <bin> <saida> [a,b]"
  REPO=$2 P=$3 C=$4 BIN=$5 SAIDA=$6 JANELA=${7:-$JANELA_PADRAO}
  guarda "$REPO" "$P"; guarda "$REPO" "$C"
  verifica_bin
  mkdir -p "$SAIDA"
  for lado in p c; do
    alvo=$P; [ "$lado" = c ] && alvo=$C
    for k in 1 2; do
      rm -rf "${SAIDA:?}/$lado$k"
      mkdir -p "$SAIDA/$lado$k"
      if ! um_lado "$REPO" "$alvo" "$SAIDA/$lado$k" "$JANELA"; then
        printf 'zic_recusa_%s\t%s\n' "$lado" "$SAIDA/$lado$k/zic.stderr" > "$SAIDA/nao_executado.tsv"
        exit 3
      fi
    done
  done
  rm -f "$SAIDA/nao_executado.tsv"
  compara "$SAIDA"
  exit 0
fi

[ $# -ge 4 ] && [ $# -le 5 ] || morre 2 "uso: $0 <repo> <lado> <bin> <saida> [a,b]"
REPO=$1 LADO=$2 BIN=$3 SAIDA=$4 JANELA=${5:-$JANELA_PADRAO}
guarda "$REPO" "$LADO"
verifica_bin
mkdir -p "$SAIDA"
um_lado "$REPO" "$LADO" "$SAIDA" "$JANELA" || exit 3
exit 0
