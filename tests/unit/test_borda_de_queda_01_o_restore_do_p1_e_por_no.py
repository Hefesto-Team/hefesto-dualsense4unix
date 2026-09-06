"""BORDA-DE-QUEDA-01 / E2 — parar o Jogador 1 não desnuda os outros três.

O DEFEITO, provado no código antes desta régua existir
------------------------------------------------------
`daemon/subsystems/gamepad.py`, `_broker_sync_grab` no ramo ``grab=False`` —
o caminho por onde o `stop` do P1 solta o grab — pedia ``client.restore_all``.
E ``restore_all`` não é "restaura o que este caminho escondeu": o servidor o
executa sobre a **lease inteira** (`broker/hidraw_broker.py:689-694` percorre
`by_conn[conn_id]`), e o daemon inteiro fala com o broker por **uma conexão
só** (`integrations/hidraw_broker_client.py`, cliente-lease singleton por
daemon). Logo desligar a emulação do Jogador 1 devolvia à vista o hidraw
físico dos QUATRO — cada secundário com o vpad DELE bem vivo passava a
aparecer no jogo como físico **e** virtual, que é o defeito histórico mais
caro desta casa.

Com UM controle na mesa, `restore_all` e `restore(nó do P1)` são
indistinguíveis: o defeito nasce da pluralidade, e é por isso que régua
nenhuma o via — as que existiam exercitavam uma lease com um nó só.

POR QUE ESTA RÉGUA USA O BROKER DE VERDADE
------------------------------------------
Um dublê de cliente responderia "restore_all foi chamado" e pronto — mas a
frase que interessa é sobre o ESTADO DO SERVIDOR: *quais nós continuaram
escondidos*. Quem sabe isso é o broker, e o alcance de `restore_all` mora
nele, não no cliente. Então aqui sobe o `Broker` real numa thread, num socket
unix real, com o `HidrawBrokerClient` real por cima — só o sistema de arquivos
é dublado (`FakeOps`), que é o mesmo arranjo de `test_hidraw_broker_client.py`
e o que a E5 da sprint pedia ("o broker real sobre um tmpfs com quatro char
devices falsos, com o cliente único do daemon"). Nenhum `/dev` real é tocado,
nenhum `chmod` acontece, e nada disso precisa do aparelho na bancada.

A MORDIDA (§4 do protocolo)
---------------------------
Troque, em `_broker_sync_grab`, a linha

    broker_call_nonblocking(daemon, lambda: client.restore(node))

de volta pelo

    broker_call_nonblocking(daemon, client.restore_all)

e os três testes de alcance caem juntos, nomeando os nós dos jogadores 2, 3 e 4
que voltaram à vista. Foi assim que esta régua foi provada.

O QUE ESTA RÉGUA **NÃO** PROVA, e é de propósito: que a política mudou. Ela
não mudou. O restore continua sem gate de Modo Nativo ("expor nunca é errado",
doutrina "duplicado é melhor que zero controles") e o `restore_all` continua
vivo no EOF/close da lease, que é o único momento em que todos os nós morrem
juntos — os dois estão afirmados abaixo, para que a próxima pessoa que ler
"por nó" não desfaça a assimetria junto com o alcance.
"""
from __future__ import annotations

import contextlib
import os
import socket
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.broker.hidraw_broker import Broker, BrokerState
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import hidraw_broker_client as hbc
from hefesto_dualsense4unix.utils import session

#: A mesa dos quatro: o nó do P1 e os três dos secundários. Os MACs são das
#: faixas da casa, com os octetos 4 e 5 zerados (regra do anonimato).
NO_P1 = "/dev/hidraw3"
SECUNDARIOS: dict[str, str] = {
    "aa:bb:cc:00:00:d2": "/dev/hidraw4",
    "e8:47:3a:00:00:9c": "/dev/hidraw5",
    "02:fe:00:00:00:71": "/dev/hidraw6",
}
TODOS_OS_NOS = [NO_P1, *SECUNDARIOS.values()]


class FakeOps:
    """Dublê de fs com as assinaturas REAIS do FsAclOps — nada de /dev."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def hide(self, node: str, base: str) -> None:
        self.calls.append(("hide", node))

    def restore(self, node: str, base: str, uid: int) -> None:
        self.calls.append(("restore", node))

    def is_exposed_to(self, node: str, uid: int) -> bool:
        return True

    def open_node(self, node: str, base: str) -> int:  # pragma: no cover
        raise AssertionError("esta régua nunca abre nó")

    @property
    def restaurados(self) -> list[str]:
        return [c[1] for c in self.calls if c[0] == "restore"]


def _validator(node: str) -> str | None:
    """Só os quatro nós da mesa são "físicos" para este broker."""
    base = node.rsplit("/", 1)[-1]
    return base if f"/dev/{base}" in TODOS_OS_NOS else None


def _short_socket_dir(tmp_path: Path) -> str:
    """`sun_path` tem limite de ~108 bytes; o tmp_path do pytest pode passar."""
    candidato = tmp_path / "bk"
    if len(str(candidato / "broker.sock")) <= 90:
        candidato.mkdir(exist_ok=True)
        return str(candidato)
    return tempfile.mkdtemp(prefix="hefesto-bq-", dir="/tmp")


def _espera(cond: Callable[[], bool], timeout: float = 2.0) -> bool:
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.01)
    return False


class _VpadFalso:
    def __init__(self) -> None:
        self.flavor = "dualsense"
        self.backend = "uhid"

    def stop(self) -> None: ...


class _ControllerFalso:
    """Backend com `hidraw_path(uniq)` — o gate que o smoke não passa."""

    def __init__(self) -> None:
        self._evdev = SimpleNamespace(set_grab=lambda _g: True, grab_state="held")
        self.nodes: dict[str | None, str | None] = {None: NO_P1, **SECUNDARIOS}

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        return self.nodes.get(uniq)

    def set_rumble(self, weak: int = 0, strong: int = 0) -> None: ...


class _DaemonComLeaseReal:
    """Daemon mínimo cujo cliente do broker é o HidrawBrokerClient de verdade."""

    def __init__(self, socket_path: str) -> None:
        self._gamepad_device: Any = _VpadFalso()
        self._motion_reader = None
        self._coop_manager = None
        self._hidraw_broker_client = hbc.HidrawBrokerClient(socket_path)
        self.config = DaemonConfig()
        self.config.gamepad_emulation_enabled = True
        self.controller = _ControllerFalso()

    def is_native_mode(self) -> bool:
        return False


@pytest.fixture()
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Broker real + lease real + os quatro nós JÁ escondidos.

    O hide dos secundários entra pelo cliente direto de propósito: quem o faz
    no produto é `coop.py::_broker_hide_player`, que não é desta sprint. O que
    esta régua mede é o ALCANCE do restore do P1 sobre um estado de servidor
    que tem quatro nós na mesma lease — e é esse estado que importa.
    """
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *a, **k: None)
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda _d: None)
    monkeypatch.setattr(gp, "stop_motion_reader", lambda _d: None)

    sockdir = _short_socket_dir(tmp_path)
    path = os.path.join(sockdir, "broker.sock")
    listen = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listen.bind(path)
    listen.listen(4)
    ops = FakeOps()
    state = BrokerState(
        allowed_uid=os.getuid(), ops=ops, validator=_validator, log=lambda *a, **k: None
    )
    broker = Broker(state, listen, log=lambda *a, **k: None)
    thread = threading.Thread(target=broker.run, daemon=True)
    thread.start()

    daemon = _DaemonComLeaseReal(path)
    for no in TODOS_OS_NOS:
        assert daemon._hidraw_broker_client.hide(no) is True
    assert sorted(state.hidden) == sorted(TODOS_OS_NOS), "a mesa nasce escondida"
    ops.calls.clear()
    try:
        yield SimpleNamespace(daemon=daemon, state=state, ops=ops, path=path)
    finally:
        with contextlib.suppress(Exception):
            daemon._hidraw_broker_client.close()
        broker.stopping = True
        with (
            socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as poke,
            contextlib.suppress(OSError),
        ):
            poke.connect(path)
        thread.join(timeout=3.0)
        listen.close()
        if os.path.exists(path):
            os.unlink(path)
        if sockdir.startswith("/tmp/hefesto-bq-"):
            os.rmdir(sockdir)


# ---------------------------------------------------------------------------
# O ALCANCE — as três asserções que a mordida derruba
# ---------------------------------------------------------------------------


def test_o_stop_do_p1_restaura_so_o_no_do_p1(mesa: Any) -> None:
    """O aceite da E2, dito pelo SERVIDOR: os três secundários seguem escondidos."""
    gp.stop_gamepad_emulation(mesa.daemon)

    assert _espera(lambda: NO_P1 not in mesa.state.hidden), (
        "o nó do P1 tinha de voltar à vista — o release do grab é dele"
    )
    assert sorted(mesa.state.hidden) == sorted(SECUNDARIOS.values()), (
        "parar o Jogador 1 desnudou o hidraw de quem não é ele: "
        f"escondidos={sorted(mesa.state.hidden)}"
    )
    assert mesa.ops.restaurados == [NO_P1], (
        f"o fs restaurou nó que não era do P1: {mesa.ops.restaurados}"
    )


def test_o_ramo_do_ungrab_pede_restore_de_um_no_so(mesa: Any) -> None:
    """A unidade, sem passar pelo `stop`: `_broker_sync_grab(daemon, False)`."""
    gp._broker_sync_grab(mesa.daemon, False)

    assert mesa.ops.restaurados == [NO_P1]
    assert sorted(mesa.state.hidden) == sorted(SECUNDARIOS.values())


def test_com_um_controle_so_o_efeito_e_o_mesmo_de_antes(
    mesa: Any,
) -> None:
    """A prova de que nada regrediu no caso de UM controle.

    É o caso em que `restore_all` e `restore(nó)` sempre foram
    indistinguíveis — e ele tem de continuar assim, senão a cura teria trocado
    um defeito de pluralidade por um defeito de solidão.
    """
    for no in SECUNDARIOS.values():
        assert mesa.daemon._hidraw_broker_client.restore(no) is True
    mesa.ops.calls.clear()
    assert list(mesa.state.hidden) == [NO_P1]

    gp.stop_gamepad_emulation(mesa.daemon)

    assert mesa.state.hidden == {}, "com um controle só, a mesa fica limpa"
    assert mesa.ops.restaurados == [NO_P1]


# ---------------------------------------------------------------------------
# A POLÍTICA — o que a E2 NÃO podia mexer, e não mexeu
# ---------------------------------------------------------------------------


def test_o_restore_do_p1_continua_sem_gate_de_modo_nativo(mesa: Any) -> None:
    """"Expor nunca é errado" (`gamepad.py`, doutrina duplicado > zero).

    A E2 mudou o ALCANCE de uma chamada, não a assimetria intencional entre
    hide (com gate de Modo Nativo) e restore (sem).
    """
    mesa.daemon.is_native_mode = lambda: True  # type: ignore[method-assign]

    gp._broker_sync_grab(mesa.daemon, False)

    assert mesa.ops.restaurados == [NO_P1], (
        "em Modo Nativo o release do P1 continua expondo o nó dele"
    )


def test_o_eof_da_lease_continua_restaurando_a_mesa_inteira(mesa: Any) -> None:
    """O `restore_all` do EOF é o certo, e a E2 não podia desfazê-lo.

    O close da lease (= daemon morrendo, SIGKILL incluído) é o único momento em
    que todos os nós morrem juntos. `daemon/connection.py` conta com isso.
    """
    mesa.daemon._hidraw_broker_client.close()

    assert _espera(lambda: mesa.state.hidden == {}), (
        "o EOF da lease tem de restaurar TUDO — é a rede da morte suja"
    )
    assert sorted(mesa.ops.restaurados) == sorted(TODOS_OS_NOS)


def test_sem_no_resolvivel_ninguem_e_desnudado(mesa: Any) -> None:
    """Controle arrancado da mesa: `hidraw_path()` devolve None.

    Antes da E2, este caminho caía no `restore_all` e desnudava os quatro
    justamente no pior momento — o P1 sumiu, os outros três seguem jogando.
    Agora não há nó do P1 a restaurar, e ninguém mais é tocado; o EOF da lease
    é a rede para o nó velho (que, com o controle fora, nem existe no /dev).
    """
    mesa.daemon.controller.nodes[None] = None

    gp._broker_sync_grab(mesa.daemon, False)

    assert mesa.ops.restaurados == []
    assert sorted(mesa.state.hidden) == sorted(TODOS_OS_NOS)
