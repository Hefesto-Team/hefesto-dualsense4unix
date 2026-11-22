"""A conferência da extensão sem rede no arranque não vira recusa.

A-CONFERENCIA-DA-EXTENSAO-SEM-REDE-NO-ARRANQUE-NAO-VIRA-RECUSA-01. No boot do computador a rede
sobe depois do serviço, e o ``ls-remote`` da primeira conferência saía com erro: o diário trazia
``mods_atualizacao_recusada`` em ``warning``, o mesmo nome da recusa de verdade da versão nova, e
sem o que o git disse. Os repositórios são ``git init`` locais, abertos por ``file://``; o
endereço que sumiu faz o ``ls-remote`` sair com erro, como a rede fora. Nenhuma prova fala com a
rede de fora.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o supervisor sem o ramo
``SemRespostaDoGitError`` reprova o caso da rede fora pela frase «a falta de rede não é recusa»;
o ``commit_novo`` que levanta a recusa comum no lugar da falta de resposta reprova o mesmo caso e o
da frase do motivo; o ``perguntar_ao_remoto`` que descarta o ``stderr`` reprova o caso do motivo.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador, supervisor
from hefesto_dualsense4unix.mods.instalador import (
    InstalacaoRecusadaError,
    Lugares,
    SemRespostaDoGitError,
    commit_novo,
    commit_remoto,
    ler_registro,
    perguntar_ao_remoto,
)
from tests.unit import test_a_extensao_instalada_pelo_git_se_atualiza_sozinha as _vizinho

curto, lar = _vizinho.curto, _vizinho.lar
remoto = _vizinho.remoto
_instalar_ligada, _supervisor_rapido = _vizinho._instalar_ligada, _vizinho._supervisor_rapido


class _Diario:
    def __init__(self) -> None:
        self.linhas: list[tuple[str, str, dict[str, Any]]] = []

    def __getattr__(self, nivel: str) -> Any:
        def anotar(nome: str, **campos: Any) -> None:
            self.linhas.append((nivel, nome, campos))
        return anotar

    def nomes(self, nivel: str | None = None) -> list[str]:
        return [n for lv, n, _c in self.linhas if nivel in (None, lv)]


def _conferir(lar: Lugares, monkeypatch: pytest.MonkeyPatch) -> tuple[_Diario, Any]:
    diario = _Diario()
    monkeypatch.setattr(supervisor, "logger", diario)
    entrada = ler_registro(lar.registro)["exemplo"]
    sup = _supervisor_rapido(lar)
    sup.espera_depois_da_falha_s = 600.0
    sup.piso_da_atualizacao_s = 60.0

    async def uma() -> bool:
        return bool(await sup.atualizar_sozinha(entrada))

    assert asyncio.run(uma()) is False
    return diario, sup


def test_a_rede_fora_grava_o_aviso_de_sem_rede_e_nao_a_recusa(
    lar: Lugares, remoto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=21600.0)
    shutil.rmtree(remoto)
    diario, _sup = _conferir(lar, monkeypatch)
    assert "mods_atualizacao_recusada" not in diario.nomes(), \
        "a falta de rede não é recusa"
    assert diario.nomes("info") == ["mods_sem_rede_para_conferir"]
    campos = diario.linhas[0][2]
    assert campos["mod"] == "exemplo"
    assert "Could not read from remote repository" in campos["motivo"]
    assert str(remoto) not in campos["motivo"]
    assert campos["proxima_as"].count(":") == 2


def test_a_proxima_conferencia_sem_rede_marca_600_segundos(
    lar: Lugares, remoto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=21600.0)
    shutil.rmtree(remoto)
    antes = time.monotonic()
    _diario, sup = _conferir(lar, monkeypatch)
    assert 595 <= sup._proxima_conferencia["exemplo"] - antes <= 606


def test_a_recusa_de_verdade_segue_em_aviso_e_tambem_marca_600_segundos(
    lar: Lugares, remoto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=21600.0)

    def recusa(*_a: Any, **_k: Any) -> None:
        raise InstalacaoRecusadaError("O manifesto pede um Hefesto mais novo.")

    monkeypatch.setattr(supervisor, "atualizar", recusa)
    _publicar_outro(remoto)
    antes = time.monotonic()
    diario, sup = _conferir(lar, monkeypatch)
    assert diario.nomes() == ["mods_atualizacao_recusada"]
    assert diario.linhas[0][0] == "warning"
    assert 595 <= sup._proxima_conferencia["exemplo"] - antes <= 606


def _publicar_outro(origem: Path) -> None:
    _vizinho._publicar(origem, "0.2.0")


def test_o_git_ausente_segue_recusa_com_o_motivo(
    lar: Lugares, remoto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=21600.0)

    def sem_git(*_a: Any, **_k: Any) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", sem_git)
    diario, _sup = _conferir(lar, monkeypatch)
    assert diario.nomes() == ["mods_atualizacao_recusada"]
    assert "não respondeu: git" in diario.linhas[0][2]["err"]


def test_a_referencia_que_nao_existe_e_recusa_e_diz_qual(
    lar: Lugares, remoto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=21600.0)
    registro = ler_registro(lar.registro)
    registro["exemplo"].ref = "v9"
    instalador.gravar_registro(lar.registro, registro)
    diario, _sup = _conferir(lar, monkeypatch)
    assert diario.nomes("info") == []
    assert diario.nomes("warning") == ["mods_atualizacao_recusada"]
    assert "«v9» não existe" in diario.linhas[0][2]["err"]


def test_o_remoto_devolve_o_motivo_junto(lar: Lugares, remoto: Path) -> None:
    achou = perguntar_ao_remoto(f"file://{remoto}", None)
    assert achou.commit and achou.respondeu and achou.motivo == ""
    sem_ref = perguntar_ao_remoto(f"file://{remoto}", "v9")
    assert sem_ref.commit is None and sem_ref.respondeu
    assert sem_ref.motivo == "a referência «v9» não existe"
    assert commit_remoto(f"file://{remoto}", "v9") is None
    shutil.rmtree(remoto)
    sumiu = perguntar_ao_remoto(f"file://{remoto}", None)
    assert sumiu.commit is None and not sumiu.respondeu
    assert sumiu.motivo and str(remoto) not in sumiu.motivo


def test_o_commit_novo_sem_resposta_levanta_a_falta_de_resposta_com_o_motivo(
    lar: Lugares, remoto: Path
) -> None:
    _instalar_ligada(lar, remoto)
    shutil.rmtree(remoto)
    with pytest.raises(SemRespostaDoGitError, match="não respondeu") as erro:
        commit_novo(ler_registro(lar.registro)["exemplo"])
    assert erro.value.motivo
    assert isinstance(erro.value, InstalacaoRecusadaError)
