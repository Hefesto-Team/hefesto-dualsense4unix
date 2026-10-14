"""A versão do firmware aparece no doctor, e nunca se atualiza daqui.

A-VERSAO-DO-FIRMWARE-APARECE-NO-DOCTOR-E-NUNCA-SE-ATUALIZA-DAQUI-01. O daemon lê o
`update_version` (feature 0x20) quando cada controle conecta; o `controller.list` o carrega
em `firmware`, e o doctor o mostra na linha do controle e avisa abaixo do `0x0224`, a partir do
qual o SDL trata o controle de outro jeito. O doctor só LÊ: o único pedido ao daemon que
esta régua deixa passar é de leitura.

A MORDIDA: inverter a comparação de `_linhas_do_firmware` (`<` por `>=`) reprova
`test_o_aviso_so_vem_abaixo_do_limite`; tirar o `"firmware"` de `describe_controllers`
reprova `test_a_versao_que_o_daemon_leu_chega_ao_doctor`.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core.backend_pydualsense import LIMITE_DA_VIBRACAO_V2
from tests.unit.test_o_controle_vibra_no_modo_do_firmware_dele import (
    _backend,
    _feature_0x20,
    _handle,
)


def _controle(numero: int, firmware: Any, **mais: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "connected": True, "transport": "usb", "numero": numero, "firmware": firmware,
    }
    base.update(mais)
    return base


def _tags(linhas: list[tuple[str, str]]) -> list[str]:
    return [tag for tag, _mensagem in linhas]


def test_o_limite_e_o_do_backend() -> None:
    assert LIMITE_DA_VIBRACAO_V2 == 0x0224


def test_a_versao_sai_na_linha_do_controle() -> None:
    linhas = cmd_doctor._linhas_do_firmware([_controle(2, 0x0630, transport="bt")])
    assert linhas == [("[ OK ]", "controle 2 (rádio): firmware 0x0630")]


@pytest.mark.parametrize(
    ("lida", "avisa"),
    [(0x0630, False), (0x0225, False), (0x0224, False), (0x0223, True), (0x0215, True)],
)
def test_o_aviso_so_vem_abaixo_do_limite(lida: int, avisa: bool) -> None:
    (linha,) = cmd_doctor._linhas_do_firmware([_controle(1, lida)])
    assert (linha[0] == "[WARN]") is avisa, linha
    assert f"firmware 0x{lida:04x}" in linha[1]


def test_o_aviso_diz_onde_atualizar_e_que_o_hefesto_nao_atualiza() -> None:
    (tag, mensagem) = cmd_doctor._linhas_do_firmware([_controle(1, 0x0215)])[0]
    assert tag == "[WARN]"
    assert "PS5" in mensagem and "aplicativo da Sony no Windows" in mensagem, mensagem
    assert "o Hefesto nunca atualiza firmware" in mensagem, mensagem
    assert "0x0224" in mensagem, mensagem


def test_o_edge_mostra_a_versao_e_nunca_avisa() -> None:
    (linha,) = cmd_doctor._linhas_do_firmware([_controle(1, 0x0100, edge=True)])
    assert linha == ("[ OK ]", "controle 1 (cabo): firmware 0x0100")


def test_versao_nao_lida_e_informacao_e_nunca_aviso() -> None:
    linhas = cmd_doctor._linhas_do_firmware([_controle(3, None), _controle(4, True)])
    assert _tags(linhas) == ["[INFO]", "[INFO]"], linhas
    assert "ainda não foi lida" in linhas[0][1]


def test_controle_desconectado_e_entrada_estranha_nao_viram_linha() -> None:
    controles = [
        _controle(1, 0x0630, connected=False),
        {"connected": False, "transport": None, "is_primary": False},
        "lixo",
        None,
    ]
    assert cmd_doctor._linhas_do_firmware(controles) == []
    assert cmd_doctor._linhas_do_firmware(None) == []
    assert cmd_doctor._linhas_do_firmware({"controllers": []}) == []


def test_sem_numero_cai_na_posicao() -> None:
    controle = _controle(0, 0x0630)
    del controle["numero"]
    (linha,) = cmd_doctor._linhas_do_firmware([controle])
    assert linha[1].startswith("controle 1 "), linha


def test_a_versao_que_o_daemon_leu_chega_ao_doctor(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cadeia inteira: a feature 0x20 na conexão, o `controller.list` e a linha do doctor."""
    paginas = {
        "/dev/hidraw3": _feature_0x20(0x0630),
        "/dev/hidraw7": _feature_0x20(0x0223, bt=True),
    }
    monkeypatch.setattr(
        backend_mod, "_read_feature_via_hidraw",
        lambda path, report_id, size, opener=None: paginas[path],
    )
    um = _handle(path=b"/dev/hidraw3")
    dois = _handle(path=b"/dev/hidraw7", bt=True)
    um.connected = dois.connected = True
    backend = _backend(aabbcc000001=um, aabbcc000002=dois)
    backend._conhecer_o_firmware("aabbcc000001", um)
    backend._conhecer_o_firmware("aabbcc000002", dois)

    entradas = backend.describe_controllers()

    assert [e["firmware"] for e in entradas] == [0x0630, 0x0223]
    assert [e["edge"] for e in entradas] == [False, False]
    linhas = cmd_doctor._linhas_do_firmware(
        [{**e, "connected": True, "numero": i + 1} for i, e in enumerate(entradas)]
    )
    assert linhas[0] == ("[ OK ]", "controle 1 (cabo): firmware 0x0630"), linhas
    assert linhas[1][0] == "[WARN]", linhas
    assert linhas[1][1].startswith("controle 2 (rádio): firmware 0x0223"), linhas


def test_controle_nunca_lido_vai_como_vazio() -> None:
    backend = _backend(aabbcc000001=_handle())
    (entrada,) = backend.describe_controllers()
    assert entrada["firmware"] is None


def test_o_doctor_so_pergunta_e_a_linha_entra_no_bloco_do_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamados: list[str] = []

    class _Cliente:
        async def __aenter__(self) -> _Cliente:
            return self

        async def __aexit__(self, *_a: Any) -> None:
            return None

        async def call(self, metodo: str, *_a: Any, **_k: Any) -> dict[str, Any]:
            chamados.append(metodo)
            if metodo == "controller.list":
                return {"controllers": [_controle(1, 0x0215), _controle(2, 0x0630)]}
            return {"profiles": []} if metodo == "profile.list" else {"paused": False}

    monkeypatch.setattr(cmd_doctor.IpcClient, "connect", lambda *_a, **_k: _Cliente())

    linhas = asyncio.run(cmd_doctor._daemon_checks())

    do_firmware = [(t, m) for t, m in linhas if "firmware 0x" in m]
    assert _tags(do_firmware) == ["[WARN]", "[ OK ]"], linhas
    assert set(chamados) <= {
        "daemon.status", "profile.list", "daemon.state_full", "controller.list",
    }, chamados


def test_daemon_que_nao_conhece_o_pedido_nao_derruba_o_bloco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.cli.ipc_client import IpcError

    class _Cliente:
        async def __aenter__(self) -> _Cliente:
            return self

        async def __aexit__(self, *_a: Any) -> None:
            return None

        async def call(self, metodo: str, *_a: Any, **_k: Any) -> dict[str, Any]:
            if metodo == "controller.list":
                raise IpcError(-32601, "método desconhecido")
            return {"profiles": []} if metodo == "profile.list" else {"paused": False}

    monkeypatch.setattr(cmd_doctor.IpcClient, "connect", lambda *_a, **_k: _Cliente())

    linhas = asyncio.run(cmd_doctor._daemon_checks())

    assert ("[ OK ]", "IPC responde (daemon.status atendido)") in linhas, linhas
    assert not any("firmware" in m for _t, m in linhas), linhas
