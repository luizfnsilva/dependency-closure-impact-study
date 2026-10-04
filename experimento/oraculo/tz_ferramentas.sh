#!/usr/bin/env bash
# Compila zic e zdump UMA vez a partir do commit de congelamento tz@bec4d95a
# (PROTOCOLO_V_2026-10-02 §3.1, §12.3). As ferramentas do sistema e o zic.c de cada
# commit nao sao usados. Grava <bin>/{zic,zdump,SHA256SUMS,ORIGEM}.
# Nao le nenhum par: so o commit de congelamento.
# Aborta (2) se `gcc --version` nao for 13.3.0 ou `make --version` nao for 4.3 (§12.3: alvo
# ubuntu-24.04), e se config.json fixar toolchain.binarios.zic/zdump e o sha compilado divergir.
# Sem sha fixado em config.json, imprime o sha e avisa (a fixacao e da EMENDA 1).
# Uso: tz_ferramentas.sh <repo_tz> <bin>
# Codigos: 0 ok; 2 uso/erro/versao/sha.
set -euo pipefail
export LC_ALL=C SOURCE_DATE_EPOCH=0
unset TZ MAKEFLAGS MFLAGS
CONG=bec4d95af5bc600df799bdec8964a4c78e9b57b3
[ $# -eq 2 ] || { echo "uso: $0 <repo_tz> <bin>" >&2; exit 2; }
repo=$1 bin=$2
[ "$(git -C "$repo" rev-parse --verify -q "$CONG^{commit}")" = "$CONG" ] \
  || { echo "tz_ferramentas: $CONG ausente em $repo" >&2; exit 2; }
gcc --version | head -n1 | grep -Eq '\) 13\.3\.0$' \
  || { echo "tz_ferramentas: gcc nao e 13.3.0: $(gcc --version | head -n1)" >&2; exit 2; }
make --version | head -n1 | grep -Eq '^GNU Make 4\.3$' \
  || { echo "tz_ferramentas: make nao e 4.3: $(make --version | head -n1)" >&2; exit 2; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git -C "$repo" archive --format=tar "$CONG" | tar -x -C "$tmp"
# VERSION fixa e GIT_DIR invalido: a regra `version` do Makefile nao consulta git
# (tz@bec4d95a:Makefile:732-742), logo o binario nao depende do diretorio.
(cd "$tmp" && GIT_DIR=/nonexistent make -s CC=gcc \
   CFLAGS="-O2 -ffile-prefix-map=$tmp=." LDFLAGS= VERSION=bec4d95a zic zdump) >&2
mkdir -p "$bin"
cp "$tmp/zic" "$tmp/zdump" "$bin/"
(cd "$bin" && sha256sum zic zdump > SHA256SUMS)
{
  echo "tz $CONG"
  gcc --version | head -n1
  make --version | head -n1
  echo "CC=gcc CFLAGS=-O2 -ffile-prefix-map=<tmp>=. VERSION=bec4d95a SOURCE_DATE_EPOCH=0"
} > "$bin/ORIGEM"
cfg="$(dirname "$0")/../config.json"
for f in zic zdump; do
  got=$(sed -n "s/^\([0-9a-f]*\)  $f\$/\1/p" "$bin/SHA256SUMS")
  pin=$(sed -n "s/.*\"$f\": *\"\([0-9a-f]\{64\}\)\".*/\1/p" "$cfg" 2>/dev/null | head -n1)
  if [ -z "$pin" ]; then echo "tz_ferramentas: AVISO: sha de $f nao fixado em config.json (EMENDA 1)" >&2
  elif [ "$pin" != "$got" ]; then echo "tz_ferramentas: sha de $f ($got) difere do fixado ($pin)" >&2; exit 2
  fi
done
cat "$bin/SHA256SUMS"
