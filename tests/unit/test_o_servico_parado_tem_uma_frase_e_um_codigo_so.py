"""O-SERVICO-PARADO-TEM-UMA-FRASE-E-UM-CODIGO-SO-01.

Com o socket ausente, todo subcomando que fala com o serviço diz a mesma frase, que ensina a
subir o serviço, e sai com o mesmo código (3); o erro do socket vai ao diário, não à tela.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_mic
from hefesto_dualsense4unix.cli import ipc_client as ipc_client_mod
from hefesto_dualsense4unix.cli.app import app

runner = CliRunner()

FRASE = "O serviço do Hefesto está parado. Suba com `hefesto-dualsense4unix daemon start`."

COMANDOS = [
    ["speaker", "status"],
    ["speaker", "volume", "50"],
    ["speaker", "mute"],
    ["speaker", "release"],
    ["mic", "mute"],
    ["mic", "unmute"],
    ["mic", "release"],
    ["mic", "led-on"],
    ["mic", "led-release"],
    ["mic", "canal", "on"],
    ["mic", "volume", "50"],
    ["daemon", "pause"],
    ["daemon", "resume"],
    ["freestyle", "on"],
    ["mouse", "status"],
    ["gamepad", "status"],
    ["coop", "status"],
    ["controller", "list"],
]


@pytest.fixture(autouse=True)
def sem_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ipc_client_mod, "ipc_socket_path", lambda: tmp_path / "nao-existe.sock")


@pytest.mark.parametrize("comando", COMANDOS, ids=[" ".join(c) for c in COMANDOS])
def test_o_servico_parado_diz_a_mesma_frase_e_sai_com_3(comando: list[str]) -> None:
    resultado = runner.invoke(app, comando)

    assert resultado.exit_code == 3, resultado.output
    assert FRASE in " ".join(resultado.output.split())
    assert "Errno" not in resultado.output
    assert "Traceback" not in resultado.output


@pytest.mark.parametrize(
    "erro", [PermissionError(13, "negado"), ConnectionResetError(104, "caiu")],
    ids=["socket-de-outro-dono", "conexao-caida"],
)
@pytest.mark.parametrize("comando", [["speaker", "status"], ["mouse", "status"]],
                         ids=["speaker", "mouse"])
def test_so_o_socket_ausente_ou_recusado_diz_que_o_servico_parou(
    monkeypatch: pytest.MonkeyPatch, erro: OSError, comando: list[str]
) -> None:
    """O-SERVICO-PARADO-TEM-UMA-FRASE-E-UM-CODIGO-SO-01: o serviço vivo não manda subir outro."""
    from hefesto_dualsense4unix.app import ipc_bridge

    def _falha(*_a: object, **_k: object) -> None:
        raise erro

    monkeypatch.setattr(ipc_bridge, "_run_call", _falha)
    resultado = runner.invoke(app, comando)

    assert resultado.exit_code == 1, resultado.output
    assert "parado" not in resultado.output
    assert "sem resposta a tempo" in resultado.output


def test_toda_acao_aceita_pelo_mic_aparece_na_mensagem_de_acao_invalida() -> None:
    resultado = runner.invoke(app, ["mic", "inexistente"])

    assert resultado.exit_code == 2
    dita = " ".join(resultado.output.split())
    aceitas = {
        *cmd_mic._ACTION_FLAG, *cmd_mic._ACOES_FIRMWARE, *cmd_mic._ACOES_LED,
        *cmd_mic._ACOES_BT, *cmd_mic._ACOES_DE_VALOR,
    }
    assert {"canal", "volume", "led-on", "bt-status", "release"} <= aceitas
    faltam = [acao for acao in sorted(aceitas) if acao not in dita]
    assert not faltam, f"a mensagem esqueceu: {faltam}"
