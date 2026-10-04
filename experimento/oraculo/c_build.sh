#!/usr/bin/env bash
# Oraculo C para zlib e Lua (PROTOCOLO_V_2026-10-02 §3.2; INTERFACES §0 e §2.5).
# Executor de terceiros: gcc 13.3.0 + GNU Make 4.3 fixados, SOURCE_DATE_EPOCH=0,
# -O2 -g0 -ffile-prefix-map=<raiz>=. ; AIS = objetos cujos bytes diferem.
# Nunca chama Python do experimento, nem o fecho, nem os adaptadores.
#
# Uso:
#   c_build.sh <zlib|lua> <repo> <lado> <saida>
#       um lado, uma execucao. Grava <saida>/objs/<objeto>, <saida>/manifesto.tsv
#       (objeto<TAB>sha256<TAB>bytes), <saida>/build.log, <saida>/cadeia.txt e,
#       no Lua, <saida>/cflags.txt.
#   c_build.sh --par <zlib|lua> <repo> <p> <c> <saida>
#       par: cada lado DUAS vezes (<saida>/{p1,p2,c1,c2}) e <saida>/comparacao.tsv
#       (objeto<TAB>classe; classe em AIS, IGUAL, NAO_DETERMINISTICO_p,
#       NAO_DETERMINISTICO_c, MUDANCA_DE_IDENTIDADE). Universo = objetos
#       construidos nos dois lados (§3.2).
# <repo>/<lado> e um diretorio (fixture) ou <repo> e um repositorio git e <lado> um commit.
#
# zlib (§3.2):  CC=<gcc> CFLAGS="-O2 -g0 -ffile-prefix-map=$PWD=." ./configure --static
#               make libz.a
# Lua  (§3.2):  make CC=<gcc> TESTS= CFLAGS="<CFLAGS do commit sem -g*, -O*, -march*,
#               -fsanitize*> -O2 -g0 -ffile-prefix-map=$PWD=." <o | ALL_O>
#               CFLAGS e ALL_O expandidos pelo proprio make (banco de make -p -n do
#               commit, com TESTS=); alvo o quando o makefile o define.
#
# Guarda (INTERFACES §0): sai com 9, sem construir nada, se <repo> nao estiver sob
# nucleo/fixtures/, salvo V_MODO=confirmatorio e "doi" nao nulo em config.json.
# Cadeia: aborta (2) se `gcc --version` ou `make --version` divergirem do fixado.
# Codigos: 0 ok; 2 uso/ferramenta/cadeia; 4 nao constroi; 9 guarda.
set -euo pipefail
export LC_ALL=C
unset MAKEFLAGS MFLAGS CFLAGS CPPFLAGS LDFLAGS CC TZ

AQUI=$(cd "$(dirname "$0")" && pwd -P)
EXP=$(dirname "$AQUI")
GCC_LINHA1='gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0'   # §3.2, §12.3
MAKE_LINHA1='GNU Make 4.3'                                  # §3.2, §12.3
CAMINHO=/usr/bin:/bin

morre() { echo "c_build: $2" >&2; exit "$1"; }
linha1() { local t; t=$("$@"); printf '%s\n' "${t%%$'\n'*}"; }   # sem pipe: nada de SIGPIPE sob pipefail

guarda() {
  local real fx
  real=$(cd "$1" 2>/dev/null && pwd -P) || morre 2 "repo inexistente: $1"
  fx=$(cd "$EXP/nucleo/fixtures" 2>/dev/null && pwd -P) || fx=/nenhum
  case "$real/" in "$fx"/*) return 0 ;; esac
  if [ "${V_MODO:-}" = confirmatorio ] && [ -f "$EXP/config.json" ] \
     && grep -Eq '"doi"[[:space:]]*:[[:space:]]*"[^"]+"' "$EXP/config.json"; then
    return 0
  fi
  morre 9 "guarda: $real nao e fixture e nao ha V_MODO=confirmatorio com doi"
}

verifica_cadeia() {
  GCC=$(PATH=$CAMINHO command -v gcc) || morre 2 "gcc ausente"
  local g m
  g=$(linha1 "$GCC" --version)
  m=$(PATH=$CAMINHO linha1 make --version)
  [ "$g" = "$GCC_LINHA1" ] || morre 2 "gcc divergente: '$g' != '$GCC_LINHA1'"
  [ "$m" = "$MAKE_LINHA1" ] || morre 2 "make divergente: '$m' != '$MAKE_LINHA1'"
}

cadeia() {   # saida: versoes e sha256 dos binarios da cadeia (registro, §3.2)
  {
    linha1 "$GCC" --version
    PATH=$CAMINHO linha1 make --version
    local b
    for b in "$GCC" "$("$GCC" -print-prog-name=cc1)" "$(PATH=$CAMINHO command -v make)" \
             "$(PATH=$CAMINHO command -v as)" "$(PATH=$CAMINHO command -v ar)"; do
      b=$(readlink -f "$b")
      printf '%s  %s\n' "$(sha256sum < "$b" | cut -d' ' -f1)" "$b"
    done
  } > "$1/cadeia.txt"
}

materializa() {   # repo lado destino; lista dos arquivos versionados em destino.lista
  if [ -d "$1/$2" ]; then
    cp -R "$1/$2/." "$3/"
    (cd "$3" && find . -type f | sed 's|^\./||' | sort) > "$3.lista"
    return 0
  fi
  local top
  top=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || morre 2 "lado invalido: $2"
  [ "$(cd "$top" && pwd -P)" = "$(cd "$1" && pwd -P)" ] || morre 2 "$1 nao e raiz de repositorio git"
  git -C "$1" rev-parse --verify -q "$2^{commit}" >/dev/null || morre 2 "commit invalido: $2"
  : > "$3.lista"
  local meta caminho modo tipo oid
  # blob a blob (git cat-file): bytes exatos do commit, sem filtros de exportacao
  while IFS= read -r -d '' reg; do
    meta=${reg%%$'\t'*}; caminho=${reg#*$'\t'}
    read -r modo tipo oid <<< "$meta"
    [ "$tipo" = blob ] || continue
    mkdir -p "$3/$(dirname "$caminho")"
    if [ "$modo" = 120000 ]; then
      ln -s "$(git -C "$1" cat-file blob "$oid")" "$3/$caminho"
    else
      git -C "$1" cat-file blob "$oid" > "$3/$caminho"
      [ "$modo" = 100755 ] && chmod +x "$3/$caminho"
    fi
    printf '%s\n' "$caminho" >> "$3.lista"
  done < <(git -C "$1" ls-tree -r -z "$2")
  sort -o "$3.lista" "$3.lista"
}

roda() {   # dir comando...: ambiente limpo e fixo (§3.2)
  local d=$1; shift
  (cd "$d" && env -i PATH="$CAMINHO" LC_ALL=C TZ=UTC SOURCE_DATE_EPOCH=0 HOME="$d" "$@")
}

constroi_zlib() {   # src saida -> 0 | 4
  local src=$1 saida=$2
  [ -f "$src/configure" ] || { echo "sem configure" >> "$saida/build.log"; return 4; }
  [ -x "$src/configure" ] || chmod +x "$src/configure"
  roda "$src" env CC="$GCC" CFLAGS="-O2 -g0 -ffile-prefix-map=$src=." ./configure --static \
    >> "$saida/build.log" 2>&1 || return 4
  roda "$src" make libz.a >> "$saida/build.log" 2>&1 || return 4
}

constroi_lua() {   # src saida tmp -> 0 | 4
  local src=$1 saida=$2 tmp=$3
  [ -f "$src/makefile" ] || { echo "sem makefile" >> "$saida/build.log"; return 4; }
  printf '%s\n' 'v-oraculo-imprime:' \
    '	@: $(info V_CFLAGS=$(CFLAGS)) $(info V_ALL_O=$(ALL_O))' > "$tmp/aux.mk"
  roda "$src" make -p -n -f makefile -f "$tmp/aux.mk" TESTS= v-oraculo-imprime \
    > "$tmp/banco.txt" 2>> "$saida/build.log" || true
  local cf allo alvo w filt=""
  cf=$(awk '/^V_CFLAGS=/ { sub(/^V_CFLAGS=/, ""); print; exit }' "$tmp/banco.txt")
  allo=$(awk '/^V_ALL_O=/ { sub(/^V_ALL_O=/, ""); print; exit }' "$tmp/banco.txt")
  alvo=$(awk '/^# Files$/ { f = 1; next }
              f && /^# Not a target/ { n = 1; next }
              f && /^$/ { n = 0; next }
              f && !n && /^o:/ { print "o"; exit }' "$tmp/banco.txt")
  [ -n "$alvo" ] || alvo=$allo
  [ -n "${alvo//[[:space:]]/}" ] || { echo "sem alvo o nem ALL_O" >> "$saida/build.log"; return 4; }
  set -f
  for w in $cf; do
    case $w in -g*|-O*|-march*|-fsanitize*) ;; *) filt="$filt $w" ;; esac
  done
  filt="${filt# } -O2 -g0 -ffile-prefix-map=$src=."
  printf 'CFLAGS_commit=%s\nCFLAGS_oraculo=%s\nalvo=%s\n' "$cf" "$filt" "$alvo" > "$saida/cflags.txt"
  # shellcheck disable=SC2086
  roda "$src" make CC="$GCC" TESTS= CFLAGS="$filt" $alvo >> "$saida/build.log" 2>&1 \
    || { set +f; return 4; }
  set +f
}

um_lado() {   # corpus repo lado saida -> 0 | 4
  local corpus=$1 repo=$2 lado=$3 saida=$4 tmp rc=0
  tmp=$(mktemp -d)
  mkdir -p "$tmp/src" "$saida/objs"
  : > "$saida/manifesto.tsv"; : > "$saida/build.log"
  materializa "$repo" "$lado" "$tmp/src"
  cadeia "$saida"
  case $corpus in
    zlib) constroi_zlib "$tmp/src" "$saida" || rc=$? ;;
    lua)  constroi_lua "$tmp/src" "$saida" "$tmp" || rc=$? ;;
  esac
  if [ "$rc" -eq 0 ]; then
    (cd "$tmp/src" && find . -name '*.o' -type f | sed 's|^\./||' | sort) > "$tmp/objs.lista"
    local o
    while IFS= read -r o; do
      grep -Fxq -- "$o" "$tmp/src.lista" && continue   # objeto versionado nao e saida
      mkdir -p "$saida/objs/$(dirname "$o")"
      cp "$tmp/src/$o" "$saida/objs/$o"
      printf '%s\t%s\t%s\n' "$o" "$(sha256sum < "$tmp/src/$o" | cut -d' ' -f1)" \
        "$(wc -c < "$tmp/src/$o" | tr -d ' ')" >> "$saida/manifesto.tsv"
    done < "$tmp/objs.lista"
  fi
  rm -rf "$tmp"
  return "$rc"
}

compara() {   # saida: <saida>/{p1,p2,c1,c2}/manifesto.tsv -> <saida>/comparacao.tsv
  # Por objeto: presenca/sha diferente entre as duas execucoes do mesmo lado ->
  # NAO_DETERMINISTICO_<lado>; senao, presente em um so lado -> MUDANCA_DE_IDENTIDADE;
  # senao, sha256 de p != de c -> AIS (cmp byte a byte); igual -> IGUAL.
  awk -F '\t' '
    FNR == 1 { k++ }
    { nomes[$1] = 1; sha[k, $1] = $2 }
    function chave(j, n) { return ((j, n) in sha) ? sha[j, n] : "-" }
    END {
      for (n in nomes) {
        c = ""
        if (chave(1, n) != chave(2, n)) c = "NAO_DETERMINISTICO_p"
        if (chave(3, n) != chave(4, n)) c = (c == "" ? "" : c ",") "NAO_DETERMINISTICO_c"
        if (c == "") {
          a1 = ((1, n) in sha); a3 = ((3, n) in sha)
          if (a1 != a3) c = "MUDANCA_DE_IDENTIDADE"
          else c = (sha[1, n] == sha[3, n]) ? "IGUAL" : "AIS"
        }
        print n "\t" c
      }
    }' "$1/p1/manifesto.tsv" "$1/p2/manifesto.tsv" "$1/c1/manifesto.tsv" "$1/c2/manifesto.tsv" \
    | sort > "$1/comparacao.tsv"
  # conferencia byte a byte (cmp) dos objetos classificados por sha256
  local n c
  while IFS="$(printf '\t')" read -r n c; do
    case $c in
      AIS)   ! cmp -s "$1/p1/objs/$n" "$1/c1/objs/$n" || morre 2 "cmp diverge do sha256 em $n" ;;
      IGUAL) cmp -s "$1/p1/objs/$n" "$1/c1/objs/$n" || morre 2 "cmp diverge do sha256 em $n" ;;
    esac
  done < "$1/comparacao.tsv"
}

if [ "${1:-}" = "--par" ]; then
  [ $# -eq 6 ] || morre 2 "uso: $0 --par <zlib|lua> <repo> <p> <c> <saida>"
  CORPUS=$2 REPO=$3 P=$4 C=$5 SAIDA=$6
  case $CORPUS in zlib|lua) ;; *) morre 2 "corpus invalido: $CORPUS" ;; esac
  guarda "$REPO"
  verifica_cadeia
  mkdir -p "$SAIDA"
  for lado in p c; do
    alvo=$P; [ "$lado" = c ] && alvo=$C
    for k in 1 2; do
      rm -rf "${SAIDA:?}/$lado$k"
      mkdir -p "$SAIDA/$lado$k"
      if ! um_lado "$CORPUS" "$REPO" "$alvo" "$SAIDA/$lado$k"; then
        printf 'nao_constroi_%s\t%s\n' "$lado" "$SAIDA/$lado$k/build.log" > "$SAIDA/nao_executado.tsv"
        exit 4
      fi
    done
  done
  rm -f "$SAIDA/nao_executado.tsv"
  compara "$SAIDA"
  exit 0
fi

[ $# -eq 4 ] || morre 2 "uso: $0 <zlib|lua> <repo> <lado> <saida>"
CORPUS=$1 REPO=$2 LADO=$3 SAIDA=$4
case $CORPUS in zlib|lua) ;; *) morre 2 "corpus invalido: $CORPUS" ;; esac
guarda "$REPO"
verifica_cadeia
mkdir -p "$SAIDA"
um_lado "$CORPUS" "$REPO" "$LADO" "$SAIDA" || exit 4
exit 0
