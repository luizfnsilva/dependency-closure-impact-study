#!/usr/bin/env bash
# Oraculo npm (PROTOCOLO_V_2026-10-02 §2.3, §3.3; INTERFACES §0 e §2.5). Estudo
# DESCRITIVO (T1b), nao confirmatorio. Executor de terceiros: o resolvedor do
# proprio npm (npm 10.9.4 sobre node v22.22.0, §12.3),
#   npm install --package-lock-only --before=<data>
# (npm@10.9.4:docs/content/using-npm/config.md:215-229). Nao reimplementa semver,
# nunca chama Python do experimento, nem o fecho, nem os adaptadores.
#
# Uso:
#   npm_lock.sh <manifesto> <data> <saida>
#       uma execucao do oraculo. <manifesto> = um package.json; <data> = instante
#       AAAA-MM-DD ou AAAA-MM-DDTHH:MM:SS[.sss]Z. Grava em <saida>/:
#         package-lock.json   o lockfile produzido pelo npm
#         resolvido.tsv       nome<TAB>versoes (versoes distintas do nome no lockfile,
#                             ordenadas, separadas por virgula; sem a raiz "" e sem
#                             entradas link; package-lock-json.md:124-149)
#         execucao.tsv        chave<TAB>valor: data, node, npm, bytes, codigo, erro
#         npm.stderr          log do npm (--loglevel=http)
#       O runner chama cada lado DUAS vezes; nome cujas versoes diferem entre as
#       duas execucoes do mesmo lado e NAO_DETERMINISTICO (INTERFACES §2.5).
#   npm_lock.sh --orcamento <manifesto> <data>
#       so mede o download (exige V_MODO=orcamento): roda o MESMO comando num
#       diretorio temporario e o apaga sem ler o lockfile; imprime
#       "bytes<TAB>codigo<TAB>codigo de erro do npm" (sem nome nem versao).
#       Nao produz desfecho (§2.3: o batedor que mede o orcamento nao ve desfecho).
#
# Estado compartilhado, V_NPM_ESTADO (obrigatorio): cache do npm ($V_NPM_ESTADO/cache,
# usado com --prefer-offline: cada packument e baixado uma vez no estudo, config.md:
# 1171-1178) e o contador acumulado de bytes baixados ($V_NPM_ESTADO/baixados).
# Teto (§2.3): V_NPM_TETO, padrao 200000000 (= adaptadores/decl_npm.json:teto_bytes,
# conferido por teste), vale para o estudo inteiro. V_NPM_COTA (opcional) limita os
# bytes desta execucao (o orquestrador paralelo reserva cotas para nao passar o teto).
# Medida do download: um contador CONNECT local (node, embutido abaixo) por onde o npm
# fala com a rede; conta os bytes recebidos do servidor (TLS: cabecalhos e corpo
# comprimido). Ao passar da cota, derruba os tuneis e o script sai com 5.
# Com --before o npm pede o packument COMPLETO (pacote@19.0.1:lib/fetcher.js:79).
#
# Guarda (INTERFACES §0): o modo oraculo sai com 9, sem rodar nada, se <manifesto>
# nao estiver sob nucleo/fixtures/, salvo V_MODO=confirmatorio e "doi" nao nulo.
# Codigos: 0 ok; 2 uso/ferramenta; 5 teto (NAO_EXECUTADO(teto)); 6 o resolvedor recusa
# (ETARGET, E404, ERESOLVE...: NAO_EXECUTADO(resolvedor), codigo do npm em
# execucao.tsv); 7 falha transitoria de rede (o runner repete); 9 guarda. Interrompido por
# TERM/INT: soma os bytes ja baixados ao contador e sai com 2.
set -euo pipefail
export LC_ALL=C

AQUI=$(cd "$(dirname "$0")" && pwd -P)
EXP=$(dirname "$AQUI")
TETO_PADRAO=200000000
NPM_VERSAO=10.9.4
NODE_VERSAO=${V_NODE:-v22.22.0}
REGISTRY=https://registry.npmjs.org/
# Codigos do npm tratados como recusa do resolvedor (nao como falha de rede).
RECUSA="ETARGET ENOVERSIONS E404 E410 ERESOLVE EINVALIDTAGNAME EINVALIDPACKAGENAME EUNSUPPORTEDPROTOCOL EBADENGINE EBADPLATFORM EJSONPARSE"

morre() { echo "npm_lock: $2" >&2; exit "$1"; }

guarda() {
  local real dir fx
  dir=$(cd "$(dirname "$1")" 2>/dev/null && pwd -P) || morre 2 "manifesto inexistente: $1"
  real=$dir/$(basename "$1")
  fx=$(cd "$EXP/nucleo/fixtures" 2>/dev/null && pwd -P) || fx=/nenhum
  case "$real" in "$fx"/*) return 0 ;; esac
  if [ "${V_MODO:-}" = confirmatorio ] && [ -f "$EXP/config.json" ] \
     && grep -Eq '"doi"[[:space:]]*:[[:space:]]*"[^"]+"' "$EXP/config.json"; then
    return 0
  fi
  morre 9 "guarda: $real nao e fixture e nao ha V_MODO=confirmatorio com doi"
}

verifica_cadeia() {
  command -v node >/dev/null && command -v npm >/dev/null || morre 2 "node/npm ausentes"
  [ "$(node --version)" = "$NODE_VERSAO" ] || morre 2 "node $(node --version) != $NODE_VERSAO"
  [ "$(npm --version 2>/dev/null)" = "$NPM_VERSAO" ] || morre 2 "npm != $NPM_VERSAO"
}

# Contador CONNECT. argv: arqPorta arqBytes cota upstream diretos
# Escreve "<bytes>\t<estourou 0|1>" em arqBytes a cada tunel fechado, no estouro e no
# SIGTERM. upstream (http://h:p) so e usado para hosts fora de "diretos" (NO_PROXY).
CONTADOR_JS='
const net = require("net"), fs = require("fs");
const [arqPorta, arqBytes, cotaS, upstream, diretosS] = process.argv.slice(1);
const cota = cotaS === "inf" ? Infinity : Number(cotaS);
const diretos = (diretosS || "").split(",").map(s => s.trim().replace(/^\*?\./, "")).filter(Boolean);
const direto = h => !upstream || diretos.some(d => h === d || h.endsWith("." + d));
let baixado = 0, estourou = false;
const abertos = new Set();
const grava = () => { fs.writeFileSync(arqBytes + ".t", baixado + "\t" + (estourou ? 1 : 0) + "\n"); fs.renameSync(arqBytes + ".t", arqBytes); };
const conta = n => { baixado += n; if (baixado > cota && !estourou) { estourou = true; for (const s of abertos) s.destroy(); grava(); } };
const liga = (host, porta, pronto, falha) => {
  if (direto(host)) { const s = net.connect(porta, host); s.once("error", falha);
    s.once("connect", () => { s.removeListener("error", falha); pronto(s, Buffer.alloc(0)); }); return; }
  const u = new URL(upstream), s = net.connect(Number(u.port || 80), u.hostname);
  let b = Buffer.alloc(0);
  s.once("error", falha);
  s.on("connect", () => s.write("CONNECT " + host + ":" + porta + " HTTP/1.1\r\nHost: " + host + ":" + porta + "\r\n\r\n"));
  const le = d => { b = Buffer.concat([b, d]); const i = b.indexOf("\r\n\r\n"); if (i < 0) return;
    s.removeListener("data", le); s.removeListener("error", falha);
    if (!/^HTTP\/1\.[01] 200/.test(b.slice(0, i).toString("latin1"))) { s.destroy(); falha(new Error("upstream")); return; }
    pronto(s, b.slice(i + 4)); };
  s.on("data", le);
};
const srv = net.createServer(c => {
  let b = Buffer.alloc(0);
  c.on("error", () => c.destroy());
  const le = d => {
    b = Buffer.concat([b, d]); const i = b.indexOf("\r\n\r\n"); if (i < 0) return;
    c.removeListener("data", le);
    const m = /^CONNECT \[?([^\]\s]+?)\]?:(\d+) HTTP/.exec(b.slice(0, i).toString("latin1"));
    if (!m || estourou) { c.end("HTTP/1.1 " + (estourou ? "509 teto" : "405 so CONNECT") + "\r\n\r\n"); return; }
    liga(m[1], Number(m[2]), (s, resto) => {
      abertos.add(s); abertos.add(c);
      c.write("HTTP/1.1 200 Connection established\r\n\r\n");
      if (resto.length) { conta(resto.length); c.write(resto); }
      const sobra = b.slice(i + 4); if (sobra.length) s.write(sobra);
      s.on("data", d => { conta(d.length); if (!estourou) c.write(d); });
      c.on("data", d => s.write(d));
      const fecha = () => { s.destroy(); c.destroy(); if (abertos.delete(s)) { abertos.delete(c); grava(); } };
      s.on("close", fecha); c.on("close", fecha); s.on("error", fecha);
    }, () => c.end("HTTP/1.1 502 falha\r\n\r\n"));
  };
  c.on("data", le);
});
srv.listen(0, "127.0.0.1", () => { grava(); fs.writeFileSync(arqPorta, String(srv.address().port)); });
process.on("SIGTERM", () => { grava(); process.exit(0); });
'

# Gera resolvido.tsv a partir do lockfile (package-lock-json.md:124-149; nome do
# alias em "name": arborist@8.0.1 lib/shrinkwrap.js:86).
RESOLVIDO_JS='
const fs = require("fs");
const lock = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const m = new Map();
for (const [k, v] of Object.entries(lock.packages || {})) {
  if (k === "" || v.link) continue;
  const i = k.lastIndexOf("node_modules/");
  const nome = v.name || (i >= 0 ? k.slice(i + 13) : k);
  if (!m.has(nome)) m.set(nome, new Set());
  m.get(nome).add(v.version || "");
}
const nomes = [...m.keys()].sort((a, b) => Buffer.compare(Buffer.from(a), Buffer.from(b)));
process.stdout.write(nomes.map(n => n + "\t" + [...m.get(n)].sort().join(",")).join("\n") + (nomes.length ? "\n" : ""));
'

le_acumulado() { [ -s "$ESTADO/baixados" ] && cat "$ESTADO/baixados" || echo 0; }

soma_acumulado() {   # bytes
  (
    flock 8
    local a; a=$(le_acumulado)
    echo $((a + $1)) > "$ESTADO/baixados.t" && mv "$ESTADO/baixados.t" "$ESTADO/baixados"
  ) 8> "$ESTADO/baixados.lock"
}

# Interrompido (TERM/INT): derruba npm e contador e ainda soma os bytes ja baixados.
NPID=""; CPID=""; DIRW=""
interrompe() {
  trap - TERM INT
  if [ -n "$NPID" ]; then kill -TERM "$NPID" 2>/dev/null || true; fi
  if [ -n "$CPID" ]; then kill -TERM "$CPID" 2>/dev/null || true; wait "$CPID" 2>/dev/null || true; fi
  local b=0 e=0
  if [ -n "$DIRW" ] && [ -s "$DIRW/bytes" ]; then read -r b e < "$DIRW/bytes"; fi
  if [ -n "${ESTADO:-}" ]; then soma_acumulado "$b"; fi
  rm -rf "${T:-/nenhum}"
  echo "npm_lock: interrompido ($b bytes somados)" >&2
  exit 2
}

# roda manifesto data dir -> define BYTES, CODIGO, ERRO; lockfile em dir/package-lock.json
roda() {
  local man=$1 data=$2 dir=$3 acum cota porta="" rc est=0
  BYTES=0; CODIGO=0; ERRO=""
  acum=$(le_acumulado)
  cota=$((TETO - acum))
  if [ -n "${V_NPM_COTA:-}" ] && [ "$V_NPM_COTA" -lt "$cota" ]; then cota=$V_NPM_COTA; fi
  if [ "$cota" -le 0 ]; then CODIGO=5; ERRO=teto; return 0; fi
  mkdir -p "$dir/home" "$ESTADO/cache"
  DIRW=$dir
  cp "$man" "$dir/package.json"
  # so o package.json e os tarballs locais ao lado dele (fixture); nunca lockfile,
  # node_modules nem .npmrc do diretorio do manifesto
  find "$(dirname "$man")" -maxdepth 1 -type f -name '*.tgz' -exec cp {} "$dir/" \;
  : > "$dir/u.npmrc"; : > "$dir/g.npmrc"
  node -e "$CONTADOR_JS" "$dir/porta" "$dir/bytes" "$cota" \
       "${HTTPS_PROXY:-${https_proxy:-}}" "${NO_PROXY:-${no_proxy:-}}" &
  CPID=$!
  for _ in $(seq 1 100); do [ -s "$dir/porta" ] && break; sleep 0.05; done
  porta=$(cat "$dir/porta" 2>/dev/null) || true
  [ -n "$porta" ] || { kill "$CPID" 2>/dev/null || true; morre 2 "contador nao subiu"; }
  (cd "$dir" && exec env -i PATH="$PATH" HOME="$dir/home" \
      ${NODE_EXTRA_CA_CERTS:+NODE_EXTRA_CA_CERTS="$NODE_EXTRA_CA_CERTS"} \
      npm install --package-lock-only --before="$data" \
        --registry="$REGISTRY" --cache="$ESTADO/cache" --prefer-offline \
        --https-proxy="http://127.0.0.1:$porta" --proxy="http://127.0.0.1:$porta" \
        --userconfig="$dir/u.npmrc" --globalconfig="$dir/g.npmrc" \
        --no-audit --no-fund --ignore-scripts --update-notifier=false --no-progress \
        --lockfile-version=3 --loglevel=http) > "$dir/npm.stdout" 2> "$dir/npm.stderr" &
  NPID=$!
  # estouro da cota: o contador marca e derruba os tuneis; aqui se encerra o npm na hora
  # (senao ele repete cada pedido recusado com espera crescente)
  while kill -0 "$NPID" 2>/dev/null; do
    if [ -s "$dir/bytes" ] && [ "$(cut -f2 "$dir/bytes")" = 1 ]; then
      kill -TERM "$NPID" 2>/dev/null || true
      break
    fi
    sleep 0.2
  done
  set +e
  wait "$NPID"; rc=$?
  set -e
  NPID=""
  kill -TERM "$CPID" 2>/dev/null || true
  wait "$CPID" 2>/dev/null || true
  CPID=""
  if [ -s "$dir/bytes" ]; then read -r BYTES est < "$dir/bytes"; fi
  soma_acumulado "$BYTES"
  if [ "$est" = 1 ]; then CODIGO=5; ERRO=teto; return 0; fi
  if [ "$rc" -ne 0 ]; then
    ERRO=$(sed -n 's/^npm error code \([A-Z0-9_]*\).*/\1/p' "$dir/npm.stderr" | head -n1)
    case " $RECUSA " in *" ${ERRO:-nenhum} "*) CODIGO=6 ;; *) CODIGO=7 ;; esac
    return 0
  fi
  [ -s "$dir/package-lock.json" ] || { CODIGO=7; ERRO=sem_lockfile; }
}

valida_data() {
  [[ $1 =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,3})?Z)?$ ]] \
    || morre 2 "data invalida: $1"
}

ORCAMENTO=0
if [ "${1:-}" = --orcamento ]; then ORCAMENTO=1; shift; fi
if [ "$ORCAMENTO" = 1 ]; then
  [ $# -eq 2 ] || morre 2 "uso: npm_lock.sh --orcamento <manifesto> <data>"
  [ "${V_MODO:-}" = orcamento ] || morre 9 "guarda: --orcamento exige V_MODO=orcamento"
else
  [ $# -eq 3 ] || morre 2 "uso: npm_lock.sh <manifesto> <data> <saida>"
  guarda "$1"
fi
MAN=$1; DATA=$2
[ -f "$MAN" ] || morre 2 "manifesto inexistente: $MAN"
valida_data "$DATA"
[ -n "${V_NPM_ESTADO:-}" ] || morre 2 "V_NPM_ESTADO nao definido"
mkdir -p "$V_NPM_ESTADO"
ESTADO=$(cd "$V_NPM_ESTADO" && pwd -P)
TETO=${V_NPM_TETO:-$TETO_PADRAO}
verifica_cadeia

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
trap interrompe TERM INT
roda "$MAN" "$DATA" "$T/w"

if [ "$ORCAMENTO" = 1 ]; then
  # o lockfile e o log (que lista nomes buscados) saem sem leitura
  rm -rf "$T/w"
  printf '%s\t%s\t%s\n' "$BYTES" "$CODIGO" "${ERRO:-}"
  exit "$CODIGO"
fi

SAIDA=$3
mkdir -p "$SAIDA"
rm -f "$SAIDA/package-lock.json" "$SAIDA/resolvido.tsv"
[ -f "$T/w/npm.stderr" ] && cp "$T/w/npm.stderr" "$SAIDA/npm.stderr"
if [ "$CODIGO" = 0 ]; then
  cp "$T/w/package-lock.json" "$SAIDA/package-lock.json"
  node -e "$RESOLVIDO_JS" "$SAIDA/package-lock.json" > "$SAIDA/resolvido.tsv"
fi
{
  printf 'data\t%s\n' "$DATA"
  printf 'node\t%s\n' "$(node --version)"
  printf 'npm\t%s\n' "$NPM_VERSAO"
  printf 'bytes\t%s\n' "$BYTES"
  printf 'codigo\t%s\n' "$CODIGO"
  printf 'erro\t%s\n' "$ERRO"
} > "$SAIDA/execucao.tsv"
exit "$CODIGO"
