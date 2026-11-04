"""O contrato do IPC tem um dono só, o `docs/protocol/ipc-unix-socket.md`.

A docstring do `daemon/ipc_server.py` copiava à mão a lista dos métodos e envelhecia a cada um que
mudava (a linha do `daemon.status` ficou sem o `appid` e o `ambiente`). A lista saiu do código, e
o que só a docstring dizia está no protocolo.
"""
from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
SERVIDOR = RAIZ / "src/hefesto_dualsense4unix/daemon/ipc_server.py"
PROTOCOLO = RAIZ / "docs/protocol/ipc-unix-socket.md"

OS_DA_DOCSTRING_DE_ANTES = (
    "profile.switch", "profile.list", "profile.reaplicar", "trigger.set", "trigger.reset",
    "led.set", "led.player_set", "identity.renumber", "identity.number.set", "rumble.set",
    "rumble.stop", "rumble.passthrough", "rumble.motores.set", "daemon.status",
    "daemon.state_full", "controller.list", "controller.target.set", "daemon.reload",
    "launch_env.refresh", "mouse.emulation.set", "mouse.emulation.restore",
    "desktop.arranjo.apply", "keyboard.emulation.set", "desktop.status.set",
    "navegacao.interna.set", "navegacao.foco", "navegacao.big_picture.set", "coop.set",
    "coop.sync", "speaker.set", "mic.set", "mic.canal.set", "mic.led.set", "sensor.set",
)
_LINHA_DE_CONTRATO = re.compile(r"^\s*[a-z_]+(?:\.[a-z_]+)+\s+\{[^}\n]*\}\s*->", re.MULTILINE)


def _o_gerador() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "gerar_contrato_ipc", RAIZ / "scripts/gerar-contrato-ipc.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _docstring_do_servidor() -> str:
    return ast.get_docstring(ast.parse(SERVIDOR.read_text(encoding="utf-8")), clean=False) or ""


def _citado(metodo: str, texto: str) -> bool:
    return f"`{metodo}`" in texto or f"`{metodo} " in texto


def test_todo_metodo_do_dispatcher_esta_no_protocolo() -> None:
    """MORDIDA: tirar o `daemon.status` do protocolo reprova aqui."""
    metodos = [m for m, _h in _o_gerador().metodos_do_dispatcher(RAIZ)]
    documento = PROTOCOLO.read_text(encoding="utf-8")

    assert "daemon.status" in metodos and len(metodos) > 30
    assert [m for m in metodos if not _citado(m, documento)] == []


def test_o_que_a_docstring_dizia_esta_na_prosa_do_protocolo() -> None:
    """Nada se perdeu: cada método da lista de antes tem parâmetro e retorno escritos à mão."""
    prosa = _o_gerador().prosa_sem_o_bloco(PROTOCOLO.read_text(encoding="utf-8"))

    assert [m for m in OS_DA_DOCSTRING_DE_ANTES if not _citado(m, prosa)] == []


def test_a_docstring_do_servidor_nao_copia_o_contrato() -> None:
    """MORDIDA: devolver a linha `daemon.status {} -> …` à docstring reprova aqui."""
    docstring = _docstring_do_servidor()

    assert _LINHA_DE_CONTRATO.findall(docstring) == []
    assert "docs/protocol/ipc-unix-socket.md" in docstring


def test_a_docstring_do_servidor_cabe_no_limite_da_casa() -> None:
    spec = importlib.util.spec_from_file_location(
        "check_docstring_longa", RAIZ / "scripts/check_docstring_longa.py"
    )
    assert spec is not None and spec.loader is not None
    regua = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(regua)

    assert regua.docstrings_longas(SERVIDOR.read_text(encoding="utf-8")) == []
