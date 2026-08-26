"""BORDA-DE-QUEDA-01 — a queda de UM controle, quando outro segue de pé.

O defeito, medido em 26/08/2026 e curado aqui:

1. **O som volta no controle errado.** `reapply_speaker_after_connect(daemon)`
   sem `uniq` cai no `_handle_for(None)` do backend, que é *o primário e mais
   ninguém*. O Controle 2 caía no rádio, voltava, e quem recebia o volume dela
   era o Controle 1 — que nem tinha perdido a posse dos bytes.
2. **A queda não deixa rastro.** `is_connected()` é um `any(...)` sobre os
   handles: com dois na mesa, a queda de um não muda a resposta, a transição
   `online→offline` do `reconnect_loop` nunca dispara, e o controle some sem um
   evento sequer.

Os dois são a MESMA borda vista de dois lados, e é por isso que estão no mesmo
arquivo.
"""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import hefesto_dualsense4unix.daemon.connection as conn_mod
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.events import EventBus, EventTopic

#: Endereços didáticos da casa — máscara de octetos 4 e 5 zerados
#: (`AA:BB:CC:00:00:FF`), a única forma segura em arquivo versionado.
P1 = "aabbcc0000f1"
P2 = "aabbcc0000f2"


class _HandleFalso:
    """O mínimo que `alvos_conectados`/`is_connected` leem de um handle."""

    def __init__(self, connected: bool = True) -> None:
        self.connected = connected


def _backend_com(handles: dict[str, _HandleFalso]) -> PyDualSenseController:
    """Um `PyDualSenseController` com a mesa montada e nada mais.

    `__new__` de propósito: queremos os MÉTODOS REAIS (`is_connected`,
    `alvos_conectados`, `_key_to_uniq`) medidos contra handles de mentira, sem
    pagar o `__init__` que abre hidraw, evdev e threads de report.
    """
    ctrl = PyDualSenseController.__new__(PyDualSenseController)
    ctrl._io_lock = threading.RLock()
    ctrl._handles = handles
    ctrl._primary_key = next(iter(handles), None)
    return ctrl


# --- a régua: o agregado esconde, o alvo mostra -------------------------


def test_o_agregado_diz_sim_enquanto_o_alvo_diz_quem_caiu() -> None:
    """`is_connected()` não muda quando o secundário cai — `alvos_conectados` sim.

    Esta é a MEDIÇÃO do defeito, antes da cura: prova que observar o agregado
    não podia ver a borda, e que a fonte por alvo vê.
    """
    handles = {P1: _HandleFalso(), P2: _HandleFalso()}
    backend = _backend_com(handles)

    assert backend.is_connected() is True
    assert backend.alvos_conectados() == {P1: P1, P2: P2}

    # A queda pela poda de `_handles` (o caminho do `_close_handles`).
    handles.pop(P2)
    assert backend.is_connected() is True, (
        "o agregado continua 'sim' com o Controle 1 de pé — é este o ponto cego"
    )
    assert backend.alvos_conectados() == {P1: P1}


def test_o_alvo_tambem_ve_a_queda_do_handle_que_ficou_no_mapa() -> None:
    """A outra forma da queda: o handle sobra em `_handles` com `connected=False`."""
    handles = {P1: _HandleFalso(), P2: _HandleFalso(connected=False)}
    backend = _backend_com(handles)

    assert backend.is_connected() is True
    assert backend.alvos_conectados() == {P1: P1}


def test_a_key_por_path_nao_vira_endereco_falso() -> None:
    """Key de fallback por path não tem MAC — o valor é None, não um pseudo-MAC."""
    backend = _backend_com({"/dev/hidraw3": _HandleFalso()})
    assert backend.alvos_conectados() == {"/dev/hidraw3": None}


# --- a mordida: a volta do secundário traz o volume DELE ----------------


class _DaemonMagro:
    """Daemon com o mínimo que as funções de borda tocam."""

    def __init__(self, controller: object) -> None:
        self.controller = controller
        self.bus = EventBus()


class _MesaFalsa:
    """Backend enxuto que só sabe dizer quem está na mesa."""

    def __init__(self, alvos: dict[str, str | None]) -> None:
        self.alvos = dict(alvos)

    def is_connected(self) -> bool:
        return bool(self.alvos)

    def alvos_conectados(self) -> dict[str, str | None]:
        return dict(self.alvos)


@pytest.fixture
def reaplicacoes(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    """Grava o `uniq` de cada `reapply_speaker_after_connect` do módulo."""
    vistos: list[str | None] = []

    async def _gravar(daemon: object, *, uniq: str | None = None) -> None:
        vistos.append(uniq)

    monkeypatch.setattr(conn_mod, "reapply_speaker_after_connect", _gravar)
    return vistos


@pytest.mark.asyncio
async def test_a_volta_do_secundario_reaplica_o_volume_dele(
    reaplicacoes: list[str | None],
) -> None:
    """O Controle 2 volta: o volume vai para o ENDEREÇO dele, e só para ele.

    A MORDIDA desta entrega. Arrancado o `uniq` da chamada, a reaplicação sai
    com `None` — que o backend resolve como "o primário" — e o teste reprova
    nomeando quem recebeu o volume alheio.
    """
    daemon = _DaemonMagro(_MesaFalsa({P1: P1, P2: P2}))

    await conn_mod.anunciar_bordas_por_alvo(
        daemon, antes={P1: P1}, agora={P1: P1, P2: P2}
    )

    assert reaplicacoes, (
        "a volta do Controle 2 não reaplicou volume nenhum — o controle que "
        "voltou fica com o volume do firmware, calado"
    )
    assert reaplicacoes == [P2], (
        "o volume do Controle 2 foi parar em "
        f"{[alvo if alvo is not None else 'o primário (uniq=None)' for alvo in reaplicacoes]}"
        f" — o esperado era só {P2}"
    )
    assert P1 not in reaplicacoes, (
        f"o Controle 1 ({P1}) recebeu o volume do Controle 2, e ele nem tinha "
        "perdido a posse dos bytes de áudio"
    )


@pytest.mark.asyncio
async def test_a_queda_do_secundario_vira_evento_com_o_endereco_dele() -> None:
    """A queda que o agregado escondia publica `controller.disconnected` com o `uniq`."""
    daemon = _DaemonMagro(_MesaFalsa({P1: P1}))
    fila = daemon.bus.subscribe(EventTopic.CONTROLLER_DISCONNECTED)

    await conn_mod.anunciar_bordas_por_alvo(
        daemon, antes={P1: P1, P2: P2}, agora={P1: P1}
    )

    assert not fila.empty(), (
        "o Controle 2 sumiu da mesa e nenhum evento foi publicado — é a queda "
        "que hoje não deixa rastro nenhum"
    )
    payload = fila.get_nowait()
    assert payload["uniq"] == P2
    assert payload["reason"] == "alvo_sumiu"
    assert fila.empty(), "o Controle 1 continua de pé e não podia gerar queda"


@pytest.mark.asyncio
async def test_a_mesa_parada_nao_anuncia_nada(
    reaplicacoes: list[str | None],
) -> None:
    """Sem borda nenhuma, nada é publicado e nada é reescrito."""
    daemon = _DaemonMagro(_MesaFalsa({P1: P1, P2: P2}))
    fila = daemon.bus.subscribe(EventTopic.CONTROLLER_DISCONNECTED)

    await conn_mod.anunciar_bordas_por_alvo(
        daemon, antes={P1: P1, P2: P2}, agora={P1: P1, P2: P2}
    )

    assert fila.empty()
    assert reaplicacoes == []


# --- a reaplicação em toda a mesa ---------------------------------------


@pytest.mark.asyncio
async def test_a_reconexao_reaplica_o_som_em_cada_controle(
    reaplicacoes: list[str | None],
) -> None:
    """`reaplicar_som_em_todos_os_alvos` fala com CADA controle, não só o primário."""
    daemon = _DaemonMagro(_MesaFalsa({P1: P1, P2: P2}))

    await conn_mod.reaplicar_som_em_todos_os_alvos(daemon)

    assert reaplicacoes == [P1, P2], (
        f"a reconexão só reaplicou em {reaplicacoes} — os dois controles "
        "perderam a posse dos bytes de áudio, os dois precisam do volume de volta"
    )


@pytest.mark.asyncio
async def test_backend_sem_enumeracao_por_alvo_mantem_o_caminho_antigo(
    reaplicacoes: list[str | None],
) -> None:
    """Dublê sem `alvos_conectados` reaplica no primário, como antes desta linha."""

    class _BackendEnxuto:
        def is_connected(self) -> bool:
            return True

    daemon = _DaemonMagro(_BackendEnxuto())

    assert conn_mod.alvos_conectados_de(daemon) is None, (
        "backend sem o método tem de responder None ('não pergunte por alvo'), "
        "nunca {} ('a mesa está vazia') — confundir os dois publica queda falsa"
    )
    await conn_mod.reaplicar_som_em_todos_os_alvos(daemon)
    assert reaplicacoes == [None]


# --- o laço inteiro, com as bordas que ele agora enxerga -----------------


class _ControleDoLaco:
    """O backend visto pelo `reconnect_loop`, com a mesa mudando entre tiques."""

    def __init__(self) -> None:
        self.alvos: dict[str, str | None] = {P1: P1, P2: P2}

    def connect(self) -> None:
        return None

    def is_connected(self) -> bool:
        return bool(self.alvos)

    def alvos_conectados(self) -> dict[str, str | None]:
        return dict(self.alvos)

    def get_transport(self) -> str:
        return "bt"


class _DaemonDoLaco:
    """Daemon de bancada para o `reconnect_loop`: só o que o laço realmente usa."""

    def __init__(self, controller: _ControleDoLaco, voltas_ate_parar: int) -> None:
        self.controller = controller
        self.bus = EventBus()
        self.voltas = 0
        self._voltas_ate_parar = voltas_ate_parar
        self._hidraw_broker_executor = ThreadPoolExecutor(max_workers=1)

    def _is_stopping(self) -> bool:
        return self.voltas >= self._voltas_ate_parar

    def _arm_input_grace(self) -> None:
        return None

    def is_native_mode(self) -> bool:
        # Curto-circuita o re-hide do broker: ele não é o objeto da medição e
        # falaria com um socket que não existe nesta bancada.
        return True

    async def _run_blocking(self, fn, *args):  # type: ignore[no-untyped-def]
        return fn(*args)


@pytest.mark.asyncio
async def test_o_laco_ve_a_queda_e_a_volta_que_o_agregado_escondia(
    monkeypatch: pytest.MonkeyPatch, reaplicacoes: list[str | None]
) -> None:
    """Ponta a ponta no `reconnect_loop`: o Controle 2 cai, some do journal? não mais.

    O agregado NUNCA se mexe neste roteiro — o Controle 1 fica de pé o tempo
    todo — e é exatamente por isso que os dois ramos históricos do laço
    (`offline→online` e `online→offline`) ficam calados. A borda por alvo é a
    única que fala.
    """
    controle = _ControleDoLaco()
    daemon = _DaemonDoLaco(controle, voltas_ate_parar=4)
    fila = daemon.bus.subscribe(EventTopic.CONTROLLER_DISCONNECTED)

    async def _nada_async(*args, **kwargs):  # type: ignore[no-untyped-def]
        return 0

    monkeypatch.setattr(conn_mod, "registrar_gatilho_da_lightbar", lambda d: None)
    monkeypatch.setattr(conn_mod, "armar_gatilho_da_cor", lambda d: 0)
    monkeypatch.setattr(conn_mod, "vigiar_escritor_cru", _nada_async)
    monkeypatch.setattr(conn_mod, "carimbar_o_nascimento", _nada_async)

    async def _tique(daemon_: _DaemonDoLaco, watch: object) -> bool:
        daemon_.voltas += 1
        if daemon_.voltas == 1:
            controle.alvos.pop(P2)  # o Controle 2 cai no rádio
        elif daemon_.voltas == 3:
            controle.alvos[P2] = P2  # e volta
        return False

    monkeypatch.setattr(conn_mod, "_wait_online_or_hotplug", _tique)

    class _WatchMudo:
        def poll(self) -> bool:
            return False

    try:
        await asyncio.wait_for(
            conn_mod.reconnect_loop(daemon, input_watch=_WatchMudo()), timeout=5.0
        )
    finally:
        daemon._hidraw_broker_executor.shutdown(wait=False)

    quedas = []
    while not fila.empty():
        quedas.append(fila.get_nowait())

    assert [q["uniq"] for q in quedas] == [P2], (
        f"o laço publicou {quedas} — esperava-se UMA queda, a do Controle 2"
    )
    assert reaplicacoes == [P2], (
        f"a volta do Controle 2 reaplicou o som em {reaplicacoes} — o volume "
        "dela tinha de voltar no controle que voltou, e em nenhum outro"
    )
