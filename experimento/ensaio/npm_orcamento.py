"""Orcamento do estudo npm (PROTOCOLO_V_2026-10-02 §2.3; §11.3 V-0b). So BYTES.

O §2.3 manda o batedor, que nao ve desfecho, medir antes do DOI se o estudo cabe no teto
de 200 MB de download. Este script mede exatamente isso e nada mais:
  - quadro npm-high-impact@1.13.0 com shasum conferido (adaptadores/npm.py:quadro);
  - 200 raizes sorteadas com uma semente PROVISORIA (a real e o sha256 do protocolo
    depositado, §2.5; ainda nao existe). A amostra real sera outra;
  - para cada janela mensal 2019-01 -> 2025-12 e cada raiz, o MESMO comando do oraculo
    (oraculo/npm_lock.sh --orcamento, V_MODO=orcamento): o lockfile e o log sao apagados
    sem leitura; so voltam bytes e codigo de saida;
  - cache compartilhado com --prefer-offline: cada packument completo e baixado uma vez
    no estudo inteiro, como no oraculo;
  - o proprio batedor respeita o teto (§2.1 g): cotas reservadas por execucao paralela;
    ao atingir o teto, para e reporta "nao cabe" com o que ja mediu.
Nada aqui compara lockfiles entre janelas, nem guarda nomes ou versoes por raiz. As
janelas rodam em ordem dispersa (extremos, meio, quartos...) para que uma parada
antecipada ainda cubra o periodo; o registro e so o acumulado agregado por janela.

Uso (de experimento/):
  <venv>/bin/python -m ensaio.npm_orcamento --quadro <npm-high-impact-1.13.0.tgz> \
      --estado <dir> --saida saidas/ensaio/npm_orcamento.json [--paralelo 4] \
      [--paralelo-primeira 1] [--max-janelas 84] [--semente-provisoria 0]
Execucoes simultaneas podem baixar o mesmo packument duas vezes (as duas veem o cache
vazio): isso so SOBRE-estima o download do oraculo, que roda em serie.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptadores import npm  # noqa: E402

EXP = Path(__file__).resolve().parents[1]
ORACULO = EXP / "oraculo" / "npm_lock.sh"


def ordem_dispersa(n: int) -> list[int]:
    """0, n-1, meio, quartos, ... (cada indice uma vez)."""
    if n <= 0:
        return []
    out, fila = [0] + ([n - 1] if n > 1 else []), [(0, n - 1)]
    while fila:
        a, b = fila.pop(0)
        if b - a < 2:
            continue
        m = (a + b) // 2
        out.append(m)
        fila += [(a, m), (m, b)]
    return out


def du(caminho: Path) -> int:
    t = 0
    for raiz, _, arqs in os.walk(caminho):
        for a in arqs:
            try:
                t += os.lstat(os.path.join(raiz, a)).st_size
            except OSError:
                pass
    return t


class Orcamento:
    def __init__(self, estado: Path, teto: int, paralelo: int):
        self.estado, self.teto, self.paralelo = estado, teto, paralelo
        self.trava = threading.Lock()
        self.reservado = 0
        self.rodando = 0

    def acumulado(self) -> int:
        p = self.estado / "baixados"
        return int(p.read_text().strip() or 0) if p.exists() else 0

    def roda(self, man: Path, data: str, cota_total: bool = False) -> tuple[int, int, str]:
        """Reserva para esta execucao o livre dividido pelas vagas ainda nao ocupadas;
        a soma das cotas nunca passa do teto."""
        with self.trava:
            livre = self.teto - self.acumulado() - self.reservado
            vagas = max(self.paralelo - self.rodando, 1)
            cota = livre if cota_total else max(livre // vagas, 0)
            self.reservado += cota
            self.rodando += 1
        try:
            if cota <= 0:
                return 0, 5, "teto"
            env = dict(os.environ, V_MODO="orcamento", V_NPM_ESTADO=str(self.estado),
                       V_NPM_TETO=str(self.teto), V_NPM_COTA=str(cota))
            r = subprocess.run([str(ORACULO), "--orcamento", str(man), data], env=env,
                               capture_output=True, text=True)
            linha = r.stdout.rstrip("\n").split("\t")
            b = int(linha[0]) if linha and linha[0].isdigit() else 0
            return b, r.returncode, (linha[2] if len(linha) > 2 else "")
        finally:
            with self.trava:
                self.reservado -= cota
                self.rodando -= 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quadro", required=True)
    ap.add_argument("--estado", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--paralelo", type=int, default=4)
    ap.add_argument("--paralelo-primeira", type=int, default=1,
                    help="primeira janela (cache frio) em serie: evita baixar o mesmo "
                         "packument em duas execucoes simultaneas")
    ap.add_argument("--max-janelas", type=int, default=None)
    ap.add_argument("--semente-provisoria", default="0")
    ap.add_argument("--nota", default=None, help="nota livre gravada no relatorio")
    a = ap.parse_args()

    estado = Path(a.estado).resolve()
    (estado / "manifestos").mkdir(parents=True, exist_ok=True)
    teto = int(npm._DECL["teto_bytes"]["valor"])
    nomes = npm.quadro(a.quadro)
    raizes = npm.sortear_raizes(nomes, a.semente_provisoria)
    mans = []
    for i, r in enumerate(raizes):
        p = estado / "manifestos" / f"{i:03d}" / "package.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(npm.manifesto(r))
        mans.append(p)
    js = npm.janelas()
    ordem = ordem_dispersa(len(js))[: a.max_janelas or len(js)]
    orc = Orcamento(estado, teto, a.paralelo)
    h = npm.hashes(a.quadro)
    rel = {
        "v": 1, "corpus": "npm", "modo": "orcamento",
        "aviso": ("SEMENTE PROVISORIA: amostra de raizes sorteada com semente "
                  f"'{a.semente_provisoria}', nao com o sha256 do protocolo depositado "
                  "(§2.5). So mede bytes; nenhum lockfile foi lido ou comparado."),
        "quadro": {"pacote": npm._DECL["quadro"]["pacote"], "versao": npm._DECL["quadro"]["versao"],
                   "sha1": h["sha1"], "sha256": h["sha256"], "n_nomes": len(nomes),
                   "shasum_confere": h["sha1"] == npm._DECL["quadro"]["shasum"]},
        "semente_provisoria": a.semente_provisoria, "n_raizes": len(raizes),
        "n_janelas_total": len(js), "teto_bytes": teto, "paralelo": a.paralelo,
        "paralelo_primeira": a.paralelo_primeira,
        "medida": npm._DECL["teto_bytes"]["medida"],
        "janelas": [], "parou_no_teto": False, "nota": a.nota,
        "acumulado_no_inicio": orc.acumulado(),
    }
    saida = Path(a.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for k, idx in enumerate(ordem, 1):
        data = js[idx]
        ti, a0 = time.time(), orc.acumulado()
        orc.paralelo = a.paralelo_primeira if k == 1 else a.paralelo
        with ThreadPoolExecutor(orc.paralelo) as ex:
            res = list(ex.map(lambda m: orc.roda(m, data), mans))
        cod, err = Counter(), Counter()
        for m, (_, c, e) in zip(mans, res):
            if c in (5, 7):            # cota parcial ou falha transitoria: uma vez, sozinho
                _, c, e = orc.roda(m, data, cota_total=True)
            cod[str(c)] += 1
            if e:
                err[e] += 1
        rel["janelas"].append({
            "k": k, "janela": data, "acumulado_bytes": orc.acumulado(),
            "marginal_bytes": orc.acumulado() - a0,
            "cache_descomprimido_bytes": du(estado / "cache" / "_cacache" / "content-v2"),
            "codigos": dict(sorted(cod.items())), "erros_npm": dict(sorted(err.items())),
            "segundos": round(time.time() - ti, 1)})
        rel["segundos_total"] = round(time.time() - t0, 1)
        if cod.get("5"):
            rel["parou_no_teto"] = True
        saida.write_text(json.dumps(rel, ensure_ascii=False, indent=1) + "\n")
        print(json.dumps(rel["janelas"][-1]), flush=True)
        if rel["parou_no_teto"]:
            break
    feitas = len(rel["janelas"])
    B = orc.acumulado()
    ult = rel["janelas"][-1]["marginal_bytes"] if feitas else 0
    rel["estimativa"] = {
        "janelas_medidas": feitas,
        "bytes_medidos": B,
        "teto_cota_superior_bytes": B if feitas == len(js) else B + (len(js) - feitas) * ult,
        "regra": ("exato para a amostra provisoria se todas as janelas rodaram; senao "
                  "medido + (janelas restantes x marginal da ultima janela medida), cota "
                  "superior porque a marginal cai conforme as janelas se adensam"),
    }
    est = rel["estimativa"]["teto_cota_superior_bytes"]
    rel["cabe"] = (not rel["parou_no_teto"]) and est <= teto
    saida.write_text(json.dumps(rel, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"bytes_medidos": B, "estimativa": est, "cabe": rel["cabe"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
