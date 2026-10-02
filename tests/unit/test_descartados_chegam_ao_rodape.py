"""CONFIG-06 (23/08/2026) — o que a gravação descartou CHEGA à tela."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o rodapé importa gui_dialogs, que puxa Gtk no topo")

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.config import (
    secao_mesa,
    secao_orcamento,
)


from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.maquina import (
    MAQUINA_SCHEMA_VERSION,
    MaquinaConfig,
    caminho_da_maquina,
)
from hefesto_dualsense4unix.utils import xdg_paths

DISCO_COM_CAMPO_INVALIDO: dict[str, Any] = {
    "version": MAQUINA_SCHEMA_VERSION,
    "orcamento": {"teto": "turbo"},
    "mesa": {"altura_da_antena": "acima"},
}

ROTULO_DO_ORCAMENTO = secao_orcamento.TITULO
ROTULO_DA_MESA = secao_mesa.TITULO


@pytest.fixture
def arquivo(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta bancada — e a prova de que ele não é o dela."""
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    return caminho


def _corromper(arquivo: Path) -> None:
    arquivo.write_text(json.dumps(DISCO_COM_CAMPO_INVALIDO), encoding="utf-8")


class _Servidor(IpcHandlersMixin):
    """O mixin de handlers com o mínimo que o ``machine.declare`` toca."""

    def __init__(self) -> None:
        self.daemon = SimpleNamespace(_maquina=MaquinaConfig())  # type: ignore[assignment]


def _estado() -> ControllerState:
    return ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )


@pytest.mark.asyncio
async def test_o_handler_devolve_os_descartados_no_corpo_do_sucesso(
    arquivo: Path,
) -> None:
    """A metade "e DIZ" da cura de 23/08.

    MORDE: trocando ``gravar_maquina_com_descartes`` por ``gravar_maquina`` no
    ``_handle_machine_declare`` — o embrulho estreita o resultado para ``bool``
    e a chave some do corpo.
    """
    _corromper(arquivo)
    resposta = await _Servidor()._handle_machine_declare(
        {"maquina": {"mesa": {"linha_de_visada": "livre"}}}
    )
    assert resposta == {"ok": True, "descartados": ["orcamento"]}
    documento = json.loads(arquivo.read_text(encoding="utf-8"))
    assert documento["mesa"] == {"altura_da_antena": "acima", "linha_de_visada": "livre"}
    assert "orcamento" not in documento


@pytest.mark.asyncio
async def test_sem_descarte_o_corpo_e_o_de_sempre(arquivo: Path) -> None:
    """Lista vazia não vai no corpo — silêncio ali é a resposta certa."""
    assert await _Servidor()._handle_machine_declare(
        {"maquina": {"mesa": {"linha_de_visada": "livre"}}}
    ) == {"ok": True}


@pytest.mark.asyncio
async def test_a_lista_atravessa_o_fio(
    tmp_path: Path, arquivo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ponte da GUI → JSON-RPC → daemon → disco → e a lista de volta.

    Um elo que só existe no fio: a FORMA do corpo. Uma ponte que lesse
    ``result["campos"]`` passa em todo teste de unidade e falha aqui.

    Socket próprio em ``tmp_path`` e ``XDG_RUNTIME_DIR`` isolado: o daemon VIVO
    da máquina dela nunca é tocado.

    MORDE: tirando o ``_rotulos_dos_descartados`` do ramo do ``ok`` na
    ``machine_declare_detalhado`` — reprova com ``()`` no lugar do rótulo.
    """
    _corromper(arquivo)
    import shutil
    import tempfile

    berco = Path(tempfile.mkdtemp(prefix="hef-fio-"))
    runtime = berco / "run"
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    assert xdg_paths.runtime_dir().parent == runtime, (
        "o runtime resolveu fora do de mentira: a ponte falaria com o da máquina")
    caminho = runtime / "hefesto-dualsense4unix" / "d.sock"
    assert len(str(caminho)) < 100, (
        f"o berço do socket mede {len(str(caminho))} caracteres e o teto do "
        f"`AF_UNIX` é 108: {caminho}. Esta régua morreria por endereço longo, "
        f"não por defeito.")
    servidor = IpcServer(
        controller=FakeController(transport="usb", states=[_estado()]),
        store=StateStore(),
        profile_manager=None,  # type: ignore[arg-type]
        socket_path=caminho,
        daemon=SimpleNamespace(_maquina=MaquinaConfig()),
    )
    monkeypatch.setenv(
        "HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME", "d.sock"
    )
    await servidor.start()
    try:
        laco = asyncio.get_running_loop()
        resposta = await laco.run_in_executor(
            None,
            ipc_bridge.machine_declare_detalhado,
            {"mesa": {"linha_de_visada": "livre"}},
        )
    finally:
        await servidor.stop()
        shutil.rmtree(berco, ignore_errors=True)
    assert resposta == (True, None, (ROTULO_DO_ORCAMENTO,))


def test_a_ponte_nunca_entrega_identificador_de_protocolo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``orcamento`` vira "Orçamento"; ``mesa`` vira ROTULO_DA_MESA."""
    monkeypatch.setattr(
        ipc_bridge,
        "_safe_call",
        lambda *a, **k: (
            True,
            {"ok": True, "descartados": ["mesa", "orcamento"]},
        ),
    )
    ok, motivo, descartados = ipc_bridge.machine_declare_detalhado(
        {"mesa": {"linha_de_visada": "livre"}}
    )
    assert (ok, motivo) == (True, None)
    assert descartados == (ROTULO_DA_MESA, ROTULO_DO_ORCAMENTO)


def test_o_embrulho_de_duas_pontas_continua_valendo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``machine_declare`` segue devolvendo ``(ok, motivo)`` — contrato de quem já chama.

    A função está no ``__all__``, e trocar a aridade dela quebraria todo
    chamador que não fosse migrado na mesma leva. Aditivo é a regra desta
    fronteira (ver ``apply_draft``/``apply_draft_detalhado``).
    """
    monkeypatch.setattr(
        ipc_bridge,
        "_safe_call",
        lambda *a, **k: (True, {"ok": True, "descartados": ["mesa"]}),
    )
    assert ipc_bridge.machine_declare({"mesa": {"linha_de_visada": "livre"}}) == (True, None)


def test_corpo_torto_do_daemon_nao_derruba_o_aplicar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Daemon velho (sem a chave) e valor torto caem no silêncio, não no traceback."""
    corpos: list[dict[str, Any]] = [
        {"ok": True},
        {"ok": True, "descartados": "orcamento"},
        {"ok": True, "descartados": [None, "", "orcamento"]},
    ]
    monkeypatch.setattr(
        ipc_bridge, "_safe_call", lambda *a, **k: (True, corpos.pop(0))
    )
    assert ipc_bridge.machine_declare_detalhado({"mesa": {"linha_de_visada": "livre"}})[2] == ()
    assert ipc_bridge.machine_declare_detalhado({"mesa": {"linha_de_visada": "livre"}})[2] == ()
    assert ipc_bridge.machine_declare_detalhado({"mesa": {"linha_de_visada": "livre"}})[2] == (
        ROTULO_DO_ORCAMENTO,
    )


