"""A extensão só se instala, se atualiza e se confere por endereço com cifra.

Num lar de mentira: o dublê do ``_git`` conta as chamadas e responde «repository not found»;
nenhuma prova fala com a rede.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import (
    FRASE_SEM_CIFRA,
    Entrada,
    InstalacaoRecusadaError,
    Lugares,
    atualizar,
    commit_novo,
    commit_remoto,
    gravar_registro,
    instalar,
    ler_registro,
)
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

lar = _base.lar
curto = _base.curto


@pytest.fixture
def chamadas(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    feitas: list[list[str]] = []

    def git(args: Any, **_: Any) -> subprocess.CompletedProcess[str]:
        feitas.append(list(args))
        return subprocess.CompletedProcess(["git", *args], 128, "",
                                           "fatal: repository not found")

    monkeypatch.setattr(instalador, "_git", git)
    return feitas


@pytest.mark.parametrize("endereco", [
    "http://exemplo.org/dono/extensao", "HTTP://exemplo.org/dono/extensao",
    "git://exemplo.org/dono/extensao", "ext::sh -c x", "fd::3"])
def test_o_endereco_sem_cifra_recusa_antes_do_git(lar: Lugares, chamadas: list[list[str]],
                                                  endereco: str) -> None:
    """D-1911-A-EXTENSAO-SO-SE-INSTALA-DE-ENDERECO-COM-CIFRA: sem cifra, nada chega ao git."""
    with pytest.raises(InstalacaoRecusadaError) as recusa:
        instalar(endereco, lugares=lar)
    assert recusa.value.frase == FRASE_SEM_CIFRA
    assert chamadas == []
    assert not lar.registro.exists()


@pytest.mark.parametrize("endereco", [
    "https://exemplo.org/dono/extensao", "ssh://git@exemplo.org/dono/extensao",
    "git@exemplo.org:dono/extensao", "file:///srv/dono/extensao"])
def test_o_endereco_com_cifra_segue_para_o_git(lar: Lugares, chamadas: list[list[str]],
                                               endereco: str) -> None:
    with pytest.raises(InstalacaoRecusadaError) as recusa:
        instalar(endereco, lugares=lar)
    assert recusa.value.frase != FRASE_SEM_CIFRA
    assert [c[0] for c in chamadas] == ["clone"] and endereco in chamadas[0]


def test_a_pasta_local_segue_para_a_copia(lar: Lugares, curto: Path) -> None:
    pasta = curto / "fontes" / "exemplo"
    pasta.mkdir(parents=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps({
        "id": "exemplo", "nome": "Exemplo", "versao": "1.0.0", "api": ">=2,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["tema"], "tema": {},
        "permissoes": []}), encoding="utf-8")  # (noqa-acento)
    assert instalar(str(pasta), lugares=lar).entrada.origem == "local"


def _anotando(perguntas: list[str]) -> Any:
    def remoto(endereco: str, _ref: str | None) -> instalador.RespostaDoRemoto:
        perguntas.append(endereco)
        return instalador.RespostaDoRemoto("b" * 40)
    return remoto


def _sem_cifra(lar: Lugares) -> Entrada:
    entrada = Entrada(id="exemplo", nome="Exemplo", versao="1.0.0", origem="comunidade",
                      endereco="http://exemplo.org/dono/extensao", commit="a" * 40, ligada=True)
    gravar_registro(lar.registro, {"exemplo": entrada})
    return entrada


def test_a_instalada_sem_cifra_nao_pergunta_ao_git_e_diz_o_motivo(
        lar: Lugares, monkeypatch: pytest.MonkeyPatch) -> None:
    perguntas: list[str] = []
    monkeypatch.setattr(instalador, "perguntar_ao_remoto", _anotando(perguntas))
    assert commit_novo(_sem_cifra(lar), lugares=lar) is None
    assert perguntas == []
    entrada = ler_registro(lar.registro)["exemplo"]
    assert entrada.motivo_da_espera == FRASE_SEM_CIFRA and entrada.ligada


def test_o_atualizar_e_o_commit_remoto_recusam_sem_cifra(lar: Lugares,
                                                         chamadas: list[list[str]]) -> None:
    _sem_cifra(lar)
    with pytest.raises(InstalacaoRecusadaError, match="precisa ser https ou ssh"):
        atualizar("exemplo", lugares=lar)
    with pytest.raises(InstalacaoRecusadaError, match="precisa ser https ou ssh"):
        commit_remoto("git://exemplo.org/dono/extensao", None)
    assert chamadas == []


def test_a_vigia_nao_atualiza_a_instalada_sem_cifra(lar: Lugares,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    entrada = _sem_cifra(lar)
    perguntas: list[str] = []
    monkeypatch.setattr(instalador, "perguntar_ao_remoto", _anotando(perguntas))
    sup = _base._supervisor(lar, procurar_bwrap=False)
    assert asyncio.run(sup.atualizar_sozinha(entrada)) is False
    assert perguntas == []
    assert ler_registro(lar.registro)["exemplo"].motivo_da_espera == FRASE_SEM_CIFRA
