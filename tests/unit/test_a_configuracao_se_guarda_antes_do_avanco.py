"""D-2011-A-CONFIGURACAO-SE-GUARDA-ANTES-DO-AVANCO: o avanço que muda perfis guarda a cópia.

O avanço do ``dev`` que muda ``profiles/`` ou ``mods/`` guarda antes uma cópia datada da
configuração de quem usa, com o commit de origem no nome, e mantém as três mais novas; o que não
os toca não copia nada, e a cópia que não coube segura o avanço. Repositório e lar de mentira.

AS MORDIDAS (feitas com a cura devolvida): sem a cópia reprova o caso do perfil byte a byte; a
faixa que copia sempre reprova o caso do avanço que não toca; sem a poda reprova o caso da quarta
cópia; o avanço que segue sem a cópia reprova o caso da cópia que não coube.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import versao_ao_abrir as va
from tests.unit import test_o_app_abre_na_versao_mais_recente_do_dev as base

Casa = base.Casa
casa = base.casa
_sem_jogo = base._sem_jogo

PERFIS = f"{va.PASTA_DO_SERVICO}hefesto_dualsense4unix/profiles/novo.py"
EXTENSOES = f"{va.PASTA_DO_SERVICO}hefesto_dualsense4unix/mods/novo.py"


@pytest.fixture
def lar(casa: Casa, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = casa.base / "config"
    (config / "profiles").mkdir(parents=True)
    for jogador in ("p1", "p2", "p3", "p4"):
        (config / "profiles" / f"{jogador}.json").write_bytes(f"perfil {jogador}\n".encode())
    (config / "mods.json").write_text('{"extensoes": []}\n', encoding="utf-8")
    from hefesto_dualsense4unix.utils import xdg_paths

    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: config)
    return config


def _copias(casa: Casa) -> list[Path]:
    pasta = casa.base / "estado" / va.PASTA_DAS_COPIAS
    return sorted(pasta.iterdir()) if pasta.is_dir() else []


def _avancar(casa: Casa, caminho: str, **ganchos: Any) -> bool:
    alvo = casa.publicar(caminho)
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) == alvo
    return va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=lambda _i: None, **ganchos)


@pytest.mark.parametrize("caminho", [PERFIS, EXTENSOES])
def test_o_avanco_que_muda_perfis_ou_extensoes_guarda_a_copia_byte_a_byte(
        casa: Casa, lar: Path, caminho: str) -> None:
    """D-2011-A-CONFIGURACAO-SE-GUARDA-ANTES-DO-AVANCO: a cópia nasce antes do avanço."""
    antes = casa.topo()
    assert _avancar(casa, caminho)
    [copia] = _copias(casa)
    assert copia.name.endswith(f"-{antes[:va.CURTO]}")
    for arquivo in sorted(lar.rglob("*")):
        if arquivo.is_file():
            assert (copia / arquivo.relative_to(lar)).read_bytes() == arquivo.read_bytes()
    assert f"configuração guardada em {copia}" in at.caminho_do_registro().read_text(
        encoding="utf-8")


def test_o_avanco_que_nao_toca_perfis_nem_extensoes_nao_copia_nada(
        casa: Casa, lar: Path) -> None:
    assert _avancar(casa, f"{va.PASTA_DO_SERVICO}hefesto_dualsense4unix/daemon/novo.py")
    assert _copias(casa) == []


def test_so_as_tres_copias_mais_novas_ficam(casa: Casa, lar: Path) -> None:
    commits = []
    for n in range(4):
        commits.append(casa.topo())
        assert _avancar(casa, PERFIS.replace("novo", f"novo{n}"))
    nomes = [c.name for c in _copias(casa)]
    assert len(nomes) == 3
    assert [n.split("-")[1] for n in nomes] == [c[:va.CURTO] for c in commits[1:]]


def test_a_copia_que_nao_coube_segura_o_avanco(
        casa: Casa, lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def sem_espaco(*_a: object, **_k: object) -> None:
        raise OSError("sem espaço")

    monkeypatch.setattr(shutil, "copytree", sem_espaco)
    inicio = casa.topo()
    assert _avancar(casa, PERFIS) is False
    assert casa.topo() == inicio


def test_sem_configuracao_o_avanco_segue_sem_copia(casa: Casa) -> None:
    assert _avancar(casa, PERFIS)
    assert _copias(casa) == []
