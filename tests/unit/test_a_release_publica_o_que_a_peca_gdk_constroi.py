"""A release publica todo arquivo que o `construir.sh` da peça GDK gera e que o pino aponta.

O install baixa do release da versão cada `*_url` do `assets/gdk-runtime/pino.txt`. Um arquivo
que o job `peca-gdk` compila e não sobe, ou que o `github-release` não exige, vira 404 no
computador de quem instala.
"""
from __future__ import annotations

import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_FONTE = _RAIZ / "assets" / "gdk-runtime"
_RELEASE = _RAIZ / ".github" / "workflows" / "release.yml"


def _job(release: str, nome: str) -> str:
    depois = release.split(f"\n  {nome}:\n", 1)[1]
    return re.split(r"\n  [a-z][a-z0-9-]*:\n", depois, maxsplit=1)[0]


def _o_que_o_construir_gera() -> set[str]:
    construir = (_FONTE / "construir.sh").read_text(encoding="utf-8")
    return set(re.findall(r'-o "\$saida/([^"]+)"', construir))


def _o_que_o_pino_aponta() -> set[str]:
    linhas = (_FONTE / "pino.txt").read_text(encoding="utf-8").splitlines()
    pares = dict(ln.split("=", 1) for ln in linhas if "=" in ln and not ln.startswith("#"))
    return {v.rsplit("/", 1)[-1] for k, v in pares.items() if k.endswith("_url")}


def _saida_do_construir(job: str) -> str:
    achado = re.search(r"construir\.sh (\S+) --conferir", job)
    assert achado, "o job peca-gdk não roda o construir.sh com --conferir"
    return achado.group(1).rstrip("/")


def _caminhos_do_upload(job: str) -> list[str]:
    passo = job.split("actions/upload-artifact@", 1)[1]
    bloco = passo.split("path:", 1)[1].split("if-no-files-found:", 1)[0]
    return [ln.strip().lstrip("|").strip() for ln in bloco.splitlines() if ln.strip().strip("|")]


def _exigidos(release: str) -> set[str]:
    linhas = _job(release, "github-release").splitlines()
    linha = next(ln for ln in linhas if "sums.py conferir" in ln)
    return set(re.findall(r"'([^']+)'", linha.split("--exigir", 1)[1]))


def _sobe(arquivo: str, saida: str, caminhos: list[str]) -> bool:
    return any(c.rstrip("/") in (saida, f"{saida}/{arquivo}") for c in caminhos)


def test_o_construir_gera_todo_arquivo_que_o_pino_aponta() -> None:
    gerados = _o_que_o_construir_gera()
    assert gerados, "o construir.sh não gera arquivo nenhum"
    assert _o_que_o_pino_aponta() <= gerados


def test_o_job_peca_gdk_sobe_todo_arquivo_que_o_construir_gera() -> None:
    job = _job(_RELEASE.read_text(encoding="utf-8"), "peca-gdk")
    saida = _saida_do_construir(job)
    caminhos = _caminhos_do_upload(job)
    faltam = sorted(a for a in _o_que_o_construir_gera() if not _sobe(a, saida, caminhos))
    assert not faltam, f"o job peca-gdk compila e não sobe: {faltam}"
    assert "if-no-files-found: error" in job


def test_a_release_exige_todo_arquivo_da_peca_e_do_pino() -> None:
    exigidos = _exigidos(_RELEASE.read_text(encoding="utf-8"))
    faltam = sorted((_o_que_o_construir_gera() | _o_que_o_pino_aponta()) - exigidos)
    assert not faltam, f"o github-release publica sem exigir: {faltam}"
