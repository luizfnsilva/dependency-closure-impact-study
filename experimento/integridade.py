"""Modulo de integridade do experimento V (PROTOCOLO_V_2026-10-02 §3.5, §6.6; INTERFACES §1, §3).

Tres coisas, so biblioteca padrao:
  1. cadeia de hash do JSONL por par: h_i = sha256(L_{i-1} || C_i), com C_i = JSON canonico do
     registro sem `h`, L_{i-1} = bytes da linha anterior sem a quebra e L_0 = hex ASCII do
     sha256 de config.json (a mesma regra que analise/analise.py confere);
  2. a guarda de execucao confirmatoria (§6.6): sem `doi`, ou com qualquer sha256 ausente ou
     divergente do arquivo em disco, a corrida RECUSA (codigo 2) antes de tocar qualquer par;
  3. o congelamento: calcula os sha256 de modulos, wheels e cadeia de ferramentas para o
     `config.json` (V-0c). Uso:  python integridade.py {modulos|toolchain|wheels|conferir}

Codigos de saida do experimento: 2 recusa/guarda/janela; 3 cadeia ou integridade quebrada;
4 defeito de pipeline; 5 ferramenta do oraculo fora de contrato.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as imd
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "config.json"
# EMENDA 2 (2026-10-04, depois do DOI, antes de qualquer corrida confirmatória): `auditoria/` sai do conjunto congelado.
# É ferramenta do V-0b (roda antes do congelamento, nunca na corrida) e não sobe ao repositório público de CI.
PACOTES = ("nucleo", "adaptadores", "detectores", "ganchos", "oraculo", "analise", "ensaio", "ci")
RAIZES_SOLTAS = ("corre.py", "integridade.py", "quadro.py")
EXT_CODIGO = (".py", ".sh")
RE_DOI = re.compile(r"^10\.\d{4,9}/\S+$")
RE_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class Recusa(SystemExit):
    """Saida com codigo: 2 guarda/recusa, 3 integridade, 4 defeito, 5 oraculo."""

    def __init__(self, codigo: int, msg: str):
        super().__init__(codigo)
        self.codigo, self.msg = codigo, msg
        print(f"[recusa {codigo}] {msg}", file=sys.stderr)


def canonico(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_arquivo(caminho: str | Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def carregar_config(caminho: str | Path = CONFIG) -> tuple[dict, str]:
    p = Path(caminho)
    if not p.is_file():
        raise Recusa(2, f"config.json ausente: {p}")
    return json.loads(p.read_bytes()), sha256_arquivo(p)


# ------------------------------------------------------------------ cadeia de hash
def _linha(reg: dict, anterior: bytes) -> tuple[dict, bytes]:
    corpo = {k: v for k, v in reg.items() if k != "h"}
    h = sha256_bytes(anterior + canonico(corpo))
    completo = {**corpo, "h": h}
    return completo, canonico(completo)


def verificar_cadeia(caminho: str | Path, sha_cfg: str) -> tuple[int, bytes]:
    """Confere o arquivo inteiro; devolve (n_linhas, ultima_linha_ou_origem). Recusa 3 se quebrar."""
    anterior = sha_cfg.encode("ascii")
    p = Path(caminho)
    n = 0
    if p.exists() and p.stat().st_size:
        dados = p.read_bytes()
        if not dados.endswith(b"\n"):
            raise Recusa(3, f"{p}: ultima linha sem quebra (corrida interrompida no meio de uma escrita)")
        for i, L in enumerate(dados.split(b"\n")[:-1], 1):
            try:
                reg = json.loads(L)
            except json.JSONDecodeError:
                raise Recusa(3, f"{p}: linha {i} nao e JSON") from None
            esperado, bruto = _linha(reg, anterior)
            if reg.get("h") != esperado["h"] or bruto != L:
                raise Recusa(3, f"{p}: cadeia quebrada na linha {i}")
            anterior, n = L, n + 1
    return n, anterior


class Cadeia:
    """Escritor append-only. Nunca sobrescreve: arquivo existente so continua (`retomar`), depois
    de a cadeia inteira ser conferida."""

    def __init__(self, caminho: str | Path, sha_cfg: str, retomar: bool = False):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        existe = self.caminho.exists() and self.caminho.stat().st_size > 0
        if existe and not retomar:
            raise Recusa(2, f"{self.caminho} ja existe; use --retomar (a saida nunca e sobrescrita)")
        self.n, self.anterior = verificar_cadeia(self.caminho, sha_cfg)
        self.sha_cfg = sha_cfg

    def anexar(self, reg: dict) -> dict:
        completo, bruto = _linha(reg, self.anterior)
        with open(self.caminho, "ab") as f:
            f.write(bruto + b"\n")
            f.flush()
            os.fsync(f.fileno())
        self.anterior, self.n = bruto, self.n + 1
        return completo

    def registros(self) -> list[dict]:
        if not self.caminho.exists():
            return []
        return [json.loads(L) for L in self.caminho.read_bytes().split(b"\n") if L]


# ------------------------------------------------------------------ arquivos congelados
def arquivos_congelados(raiz: Path = RAIZ) -> list[str]:
    """Todo .py, .sh, decl_*.json e ci/* dos pacotes do §11.1 + os modulos soltos do runner
    (INTERFACES §3). Caminhos relativos, ordenados. Fora: __pycache__, saidas/."""
    achados: set[str] = {m for m in RAIZES_SOLTAS if (raiz / m).is_file()}
    for pac in PACOTES:
        base = raiz / pac
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if not f.is_file() or "__pycache__" in f.parts:
                continue
            rel = f.relative_to(raiz).as_posix()
            if pac in ("ci", "auditoria") or f.suffix in EXT_CODIGO or re.fullmatch(r"decl_.*\.json", f.name):
                achados.add(rel)
    return sorted(achados)


def calcular_modulos(raiz: Path = RAIZ) -> dict[str, str]:
    return {r: sha256_arquivo(raiz / r) for r in arquivos_congelados(raiz)}


# ------------------------------------------------------------------ toolchain
def _linha1(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        return (r.stdout.splitlines() or [""])[0]
    except OSError:
        return ""


def _bin(nome: str) -> str:
    achado = shutil.which(nome, path="/usr/local/bin:/usr/bin:/bin")
    return os.path.realpath(achado) if achado else ""


def medir_toolchain(bin_tz: str | Path | None = None) -> dict:
    """Sha256 dos binarios e versoes dpkg medidos AGORA, sem rodar nada sobre par (substituto do
    digest de imagem quando nao ha docker: PROTOCOLO_V §3.2, §12.3; vai para a EMENDA 1)."""
    gcc = _bin("gcc")
    cc1 = subprocess.run([gcc, "-print-prog-name=cc1"], capture_output=True, text=True).stdout.strip() if gcc else ""
    bins = {"gcc": gcc, "cc1": cc1, "make": _bin("make")}
    if bin_tz:
        bins |= {"zic": str(Path(bin_tz) / "zic"), "zdump": str(Path(bin_tz) / "zdump")}
    sha = {k: (sha256_arquivo(os.path.realpath(v)) if v and os.path.isfile(v) else "") for k, v in bins.items()}

    def dpkg(pac: str) -> str:
        try:   # fora de Debian/Ubuntu nao ha dpkg-query: medida vazia -> a guarda recusa com motivo, sem traceback
            r = subprocess.run(["dpkg-query", "-W", "-f=${Version}", pac], capture_output=True, text=True)
        except OSError:
            return ""
        return r.stdout.strip() if r.returncode == 0 else ""
    return {"imagem_digest": None, "binarios": sha,
            "dpkg": {"gcc-13": dpkg("gcc-13"), "make": dpkg("make")},
            "gcc_linha1": _linha1(["gcc", "--version"]), "make_linha1": _linha1(["make", "--version"]),
            "python": platform.python_version(), "npm": _linha1(["npm", "--version"])}


def wheels_instalados() -> dict:
    out = {}
    for nome in ("networkx", "pygments"):
        try:
            out[nome] = imd.version(nome)
        except imd.PackageNotFoundError:
            out[nome] = ""
    return out


# ------------------------------------------------------------------ guarda confirmatoria (§6.6)
def problemas_congelamento(cfg: dict, raiz: Path = RAIZ, bin_tz: str | Path | None = None) -> list[str]:
    """Lista TODOS os motivos de recusa (vazia = pode rodar). Nenhum acesso a par ou repositorio."""
    p: list[str] = []
    doi = cfg.get("doi")
    if not isinstance(doi, str) or not RE_DOI.match(doi):
        p.append("config.doi ausente ou invalido (esperado 10.NNNN/...)")
    dep = (cfg.get("protocolo") or {}).get("sha256_deposito")
    if not isinstance(dep, str) or not RE_HEX64.match(dep):
        p.append("protocolo.sha256_deposito ausente")
    else:
        princ = (cfg.get("sementes") or {}).get("principal")
        if princ != int.from_bytes(bytes.fromhex(dep)[:8], "big"):
            p.append("sementes.principal != primeiros 64 bits de sha256_deposito (§2.5)")
    if (cfg.get("sementes") or {}).get("bootstrap") != 10_000:
        p.append("sementes.bootstrap != 10000 (§6.2)")
    # modulos: todo arquivo congelado presente e igual; nenhum a mais, nenhum a menos
    declarados = cfg.get("modulos") or {}
    reais = calcular_modulos(raiz)
    for rel in sorted(set(declarados) | set(reais)):
        if rel not in declarados:
            p.append(f"modulo nao congelado em config.modulos: {rel}")
        elif rel not in reais:
            p.append(f"modulo de config.modulos ausente no disco: {rel}")
        elif not (isinstance(declarados[rel], str) and RE_HEX64.match(declarados[rel])):
            p.append(f"sha256 ausente para {rel}")
        elif declarados[rel] != reais[rel]:
            p.append(f"sha256 diverge do arquivo: {rel}")
    # wheels
    inst = wheels_instalados()
    for nome in ("networkx", "pygments"):
        w = (cfg.get("wheels") or {}).get(nome) or {}
        if not (w.get("versao") and w.get("arquivo") and RE_HEX64.match(w.get("sha256") or "")):
            p.append(f"wheels.{nome} incompleto (versao, arquivo, sha256)")
        elif inst.get(nome) != w["versao"]:
            p.append(f"wheel {nome}: instalado {inst.get(nome)!r} != config {w['versao']!r}")
    # cadeia de ferramentas (substitui o digest de imagem se este for nulo)
    tc = cfg.get("toolchain") or {}
    medido = medir_toolchain(bin_tz)
    if tc.get("imagem_digest") in (None, ""):
        bins = tc.get("binarios") or {}
        for k in ("gcc", "cc1", "make", "zic", "zdump"):
            if not RE_HEX64.match(bins.get(k) or ""):
                p.append(f"toolchain.binarios.{k} ausente (sem imagem_digest)")
            elif medido["binarios"].get(k) and medido["binarios"][k] != bins[k]:
                p.append(f"toolchain.binarios.{k} diverge do binario em uso")
        for k in ("gcc-13", "make"):
            if not (tc.get("dpkg") or {}).get(k):
                p.append(f"toolchain.dpkg.{k} ausente")
            elif medido["dpkg"][k] != tc["dpkg"][k]:
                p.append(f"toolchain.dpkg.{k}: medido {medido['dpkg'][k]!r} != config {tc['dpkg'][k]!r}")
    if medido["gcc_linha1"] != tc.get("gcc_linha1"):
        p.append(f"gcc: {medido['gcc_linha1']!r} != config {tc.get('gcc_linha1')!r}")
    if not medido["make_linha1"].startswith("GNU Make 4.3"):
        p.append(f"make: {medido['make_linha1']!r} != GNU Make 4.3")
    if not str(medido["python"]).startswith(".".join(str(tc.get("python", "")).split(".")[:2]) + "."):
        p.append(f"python {medido['python']} fora da serie de config {tc.get('python')!r}")
    ci = cfg.get("ci") or {}
    if os.environ.get("GITHUB_ACTIONS") != "true" and ci.get("local_autorizado") is not True:
        p.append("fora de GitHub Actions sem ci.local_autorizado (decisao D4, §3.5)")
    return p


def guarda_confirmatoria(caminho: str | Path = CONFIG, raiz: Path = RAIZ,
                         bin_tz: str | Path | None = None) -> tuple[dict, str]:
    cfg, sha = carregar_config(caminho)
    prob = problemas_congelamento(cfg, raiz, bin_tz)
    if prob:
        resto = f"\n  ... e mais {len(prob) - 12} motivos" if len(prob) > 12 else ""
        raise Recusa(2, "execucao confirmatoria recusada (§6.6):\n  - " + "\n  - ".join(prob[:12]) + resto)
    return cfg, sha


# ------------------------------------------------------------------ CLI de congelamento (V-0c)
def main(argv: list[str] | None = None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    if not a or a[0] not in ("modulos", "toolchain", "wheels", "conferir"):
        print(__doc__)
        return 2
    if a[0] == "modulos":
        print(json.dumps(calcular_modulos(), indent=1, sort_keys=True))
    elif a[0] == "toolchain":
        print(json.dumps(medir_toolchain(a[1] if len(a) > 1 else None), indent=1, sort_keys=True))
    elif a[0] == "wheels":
        print(json.dumps(wheels_instalados(), indent=1))
    else:
        cfg, _ = carregar_config()
        prob = problemas_congelamento(cfg, RAIZ, a[1] if len(a) > 1 else None)
        print("\n".join(prob) if prob else "congelamento integro")
        return 2 if prob else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
