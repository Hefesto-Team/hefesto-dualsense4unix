"""O-VDF-COM-BYTE-FORA-DE-UTF8-PASSA-IGUAL-NOS-DOIS-CAMINHOS-01: um dono lê todo vdf da ponte.

O ``localconfig.vdf`` da Steam pode guardar um byte que não é UTF-8 (um apelido em Latin-1). O
``--gravar-vdf`` já lia com ``surrogateescape``; o ``--ligar`` e o ``--desligar-fora-da-lista``
liam estrito e davam erro. Agora ``ler_vdf``/``escrever_vdf`` são os donos, e o byte sai do vdf
igual ao que entrou. Lar de mentira (``HOME`` falso); o vdf é sempre o de mentira.

A MORDIDA: com a leitura estrita de volta num caminho, o status vira erro com o vdf intacto e o
teste daquele caminho reprova nomeando o byte; sem o ``errors`` na escrita, o byte vira ``U+FFFD``
ou a troca levanta.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import steam_input_ponte as ponte
from tests.unit.test_o_steam_input_por_jogo_segue_a_lista import _montar_lar

_ANTES = b'\t"SteamController_PSSupport"\t\t"0"'
_COM_BYTE = b'\t"Apelido"\t\t"caf\xe9"\n' + _ANTES


@pytest.fixture()
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    casa = _montar_lar(tmp_path)
    assert casa["home"].resolve() != Path.home().resolve()
    bruto = casa["vdf"].read_bytes()
    assert _ANTES in bruto
    casa["vdf"].write_bytes(bruto.replace(_ANTES, _COM_BYTE))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(casa["home"] / ".config"))
    monkeypatch.setattr(ponte, "steam_running", lambda: False)
    monkeypatch.setattr(ponte, "steam_game_running", lambda: False)
    return casa


def _byte_igual(antes: bytes, depois: bytes) -> None:
    assert b'"caf\xe9"' in depois, "o byte 0xe9 não saiu igual ao que entrou"
    assert depois.count(b"\xe9") == antes.count(b"\xe9") == 1
    assert b"\xef\xbf\xbd" not in depois


def test_o_ligar_passa_o_byte_igual(lar: dict[str, Path]) -> None:
    antes = lar["vdf"].read_bytes()
    status, _, detalhe = ponte.garantir_ponte(lar["home"])
    assert status == ponte.PONTE_LIGADA, detalhe
    depois = lar["vdf"].read_bytes()
    assert depois != antes
    _byte_igual(antes, depois)


def test_o_desligar_fora_da_lista_passa_o_byte_igual(lar: dict[str, Path]) -> None:
    antes = lar["vdf"].read_bytes()
    status, detalhe = ponte.garantir_fora_da_lista_desligado(lar["home"])
    assert status == ponte.PONTE_DESLIGADA, detalhe
    depois = lar["vdf"].read_bytes()
    assert depois != antes
    _byte_igual(antes, depois)


def test_gravar_vdf_continua_passando_o_byte_igual(lar: dict[str, Path], tmp_path: Path) -> None:
    origem = tmp_path / "novo.vdf"
    origem.write_bytes(lar["vdf"].read_bytes())
    ponte.gravar_vdf(lar["vdf"], origem)
    assert lar["vdf"].read_bytes() == origem.read_bytes()
