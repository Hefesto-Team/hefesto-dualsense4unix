"""O-JOGO-DA-JANELA-STEAM-APP-E-O-MESMO-DO-APPID-01 (03/10/2026).

O jogo da Steam visto pela janela (``steam_app_<N>``, sem appid) e o visto
pela biblioteca (appid ``<N>``) são UM jogo: a identidade é uma só, e quem a
dá é `_identidade`. Antes, o da janela virava ``janela:steam_app_<N>``, não
achava o dono gravado como ``<N>`` e dava `nome_ocupado` a cada varredura.
"""
from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal
from hefesto_dualsense4unix.profiles import loader

_PERFIL_DELA = {
    "name": "Marvel's Guardians of the Galaxy",
    "match": {"type": "criteria", "window_class": ["steam_app_1088850"]},
    "priority": 80,
}


def _com_o_perfil(tmp_path: Path) -> Path:
    destino = tmp_path / "perfis"
    destino.mkdir()
    (destino / "marvels_guardians_of_the_galaxy.json").write_text(
        json.dumps(_PERFIL_DELA, ensure_ascii=False), encoding="utf-8"
    )
    return destino


def test_o_jogo_da_janela_steam_app_tem_o_perfil_do_appid(tmp_path: Path) -> None:
    destino = _com_o_perfil(tmp_path)
    jogo = JogoLocal(
        appid="",
        nome="Marvel's Guardians of the Galaxy",
        fonte="janela",
        chave="steam_app_1088850",
    )

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=[jogo])

    assert resultado.por_desfecho("nome_ocupado") == ()
    linhas = resultado.por_desfecho("ja_tinha_perfil")
    assert [(x.arquivo, x.identidade) for x in linhas] == [
        ("marvels_guardians_of_the_galaxy.json", "1088850")
    ]


def test_a_identidade_da_janela_steam_app_e_a_do_appid() -> None:
    assert loader._identidade("", "steam_app_1088850") == "1088850"
    assert loader._identidade("", "STEAM_APP_1088850") == "1088850"
    assert loader._identidade("1088850", "") == "1088850"


def test_chave_de_janela_fora_da_steam_segue_janela_classe() -> None:
    assert loader._identidade("", "FORJA") == "janela:forja"
    assert loader._identidade("", "com.libretro.RetroArch") == (
        "janela:com.libretro.retroarch"
    )
    # O prefixo só vale inteiro: «steam_app_» sem número e «steam_app_1x» não são Steam.
    assert loader._identidade("", "steam_app_").startswith("janela:")
    assert loader._identidade("", "steam_app_12x").startswith("janela:")


def test_dois_jogos_de_nomes_diferentes_com_o_mesmo_slug_seguem_nome_ocupado(
    tmp_path: Path,
) -> None:
    """O aviso verdadeiro continua: outro jogo, mesmo slug."""
    destino = _com_o_perfil(tmp_path)
    outro = JogoLocal(
        appid="",
        nome="Marvel's Guardians of the Galaxy",
        fonte="janela",
        chave="steam_app_999",
    )

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=[outro])

    assert [x.desfecho for x in resultado.linhas] == ["nome_ocupado"]
