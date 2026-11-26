"""A catraca do ``suppress(Exception)`` em ``daemon/`` e ``core/``: a contagem por arquivo não sobe.

A chamada nova que decide o estado do aparelho usa o dono dos avisos
(``daemon/passos_do_laco.py``); limpeza (fechar, apagar, cancelar) pode calar, dentro do teto.
O teto desce à mão quando um arquivo cala menos.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
PASTAS = ("daemon", "core")

TETO: dict[str, int] = {
    "daemon/connection.py": 31,
    "daemon/ganho_da_haptica.py": 5,
    "daemon/ipc_handlers.py": 67,
    "daemon/ipc_rumble_policy.py": 2,
    "daemon/ipc_server.py": 4,
    "daemon/launch_env.py": 13,
    "daemon/lifecycle.py": 33,
    "daemon/sensor_hub.py": 10,
    "daemon/subsystems/alto_falante.py": 13,
    "daemon/subsystems/base.py": 1,
    "daemon/subsystems/bt_mic.py": 7,
    "daemon/subsystems/conexoes.py": 1,
    "daemon/subsystems/coop.py": 24,
    "daemon/subsystems/external_identity.py": 15,
    "daemon/subsystems/gamepad.py": 38,
    "daemon/subsystems/hotkey.py": 29,
    "daemon/subsystems/identity.py": 5,
    "daemon/subsystems/keyboard.py": 6,
    "daemon/subsystems/luz_do_mic.py": 5,
    "daemon/subsystems/mouse.py": 10,
    "daemon/subsystems/ouvinte_do_som.py": 2,
    "daemon/subsystems/tato_vivo.py": 4,
    "daemon/subsystems/vigia_do_laco.py": 2,
    "daemon/udp_server.py": 1,
    "core/backend_pydualsense.py": 37,
    "core/evdev_reader.py": 7,
    "core/o_dono_do_evento.py": 1,
    "core/physical_report_reader.py": 3,
    "core/rumble.py": 1,
}


def _caladas(fonte: str) -> int:
    """Quantas chamadas ``suppress(Exception)`` (o nome ou ``contextlib.suppress``) o código faz."""
    n = 0
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        nome = alvo.id if isinstance(alvo, ast.Name) else getattr(alvo, "attr", "")
        if (nome == "suppress" and len(no.args) == 1 and isinstance(no.args[0], ast.Name)
                and no.args[0].id == "Exception"):
            n += 1
    return n


def _contagem() -> dict[str, int]:
    contagem: dict[str, int] = {}
    for pasta in PASTAS:
        for caminho in sorted((RAIZ / pasta).rglob("*.py")):
            n = _caladas(caminho.read_text(encoding="utf-8"))
            if n:
                contagem[str(caminho.relative_to(RAIZ))] = n
    return contagem


def test_a_contagem_de_suppress_de_tudo_nao_sobe_em_arquivo_nenhum() -> None:
    subiram = {
        arquivo: (n, TETO.get(arquivo, 0))
        for arquivo, n in _contagem().items() if n > TETO.get(arquivo, 0)
    }
    assert not subiram, f"suppress(Exception) acima do teto (agora, teto): {subiram}"


@pytest.mark.parametrize("fonte", [
    "import contextlib\nwith contextlib.suppress(Exception):\n    pass\n",
    "from contextlib import suppress\nwith suppress(Exception):\n    pass\n",
])
def test_a_regua_conta_as_duas_formas(fonte: str) -> None:
    assert _caladas(fonte) == 1
    assert _caladas(fonte.replace("Exception", "OSError")) == 0
