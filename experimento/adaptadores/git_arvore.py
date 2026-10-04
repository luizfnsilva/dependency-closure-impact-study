"""Leitura de uma arvore de arquivos para os adaptadores (INTERFACES §2.2).

Arvore: um commit lido so por `git` (rev-parse, ls-tree, cat-file, log), a unica
ferramenta de historico permitida pelo §4.3 (iv) do protocolo.
ArvoreDir: a mesma interface sobre um diretorio simples, para as fixtures A6/A7.

Interface comum usada pelos adaptadores:
    a.sha            identificador do lado (sha40 ou "dir:<caminho>")
    a.listar()       caminhos relativos de todos os arquivos (ordenados)
    a.ler(caminho)   bytes do arquivo, ou None se ausente
    a.meta()         {"sha", "pais", "data_autor", "data_commit"}
"""
from __future__ import annotations

import subprocess
from pathlib import Path


class Arvore:
    def __init__(self, repo: str | Path, sha: str):
        self.repo = str(repo)
        self.sha = self._git("rev-parse", "--verify", f"{sha}^{{commit}}").decode().strip()
        self._lista: list[str] | None = None
        self._conj: frozenset[str] | None = None

    def _git(self, *args: str) -> bytes:
        return subprocess.run(["git", "-C", self.repo, *args], check=True,
                              capture_output=True).stdout

    def listar(self) -> list[str]:
        if self._lista is None:
            out = self._git("ls-tree", "-r", "-z", "--name-only", self.sha)
            self._lista = sorted(p.decode("utf-8", "surrogateescape")
                                 for p in out.split(b"\0") if p)
            self._conj = frozenset(self._lista)
        return self._lista

    def ler(self, caminho: str) -> bytes | None:
        self.listar()
        if caminho not in self._conj:
            return None
        return self._git("cat-file", "blob", f"{self.sha}:{caminho}")

    def meta(self) -> dict:
        h, pais, da, dc = self._git("log", "-1", "--format=%H%n%P%n%aI%n%cI",
                                    self.sha).decode().splitlines()[:4]
        return {"sha": h, "pais": pais.split(), "data_autor": da, "data_commit": dc}


class ArvoreDir:
    def __init__(self, raiz: str | Path):
        self.raiz = Path(raiz).resolve()
        self.repo = None
        self.sha = f"dir:{self.raiz}"

    def listar(self) -> list[str]:
        return sorted(str(p.relative_to(self.raiz)) for p in self.raiz.rglob("*")
                      if p.is_file())

    def ler(self, caminho: str) -> bytes | None:
        p = self.raiz / caminho
        return p.read_bytes() if p.is_file() else None

    def meta(self) -> dict:
        return {"sha": self.sha, "pais": [], "data_autor": None, "data_commit": None}
