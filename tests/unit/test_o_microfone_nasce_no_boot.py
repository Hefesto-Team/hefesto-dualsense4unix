"""O microfone do controle que JÁ ESTAVA na mesa quando o daemon subiu nasce no ar."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
    BtMicSubsystem,
    RegistroDePedidosDeCanal,
)
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm
from hefesto_dualsense4unix.testing import FakeController

P1 = "aabbcc0000b1"

HEADSET = "alsa_input.usb-Fabricante_Headset_USB-00.mono-fallback"


P2 = "aabbcc0000b2"


class _ControleNaMesa(FakeController):
    """O `FakeController` que sabe dizer QUEM está conectado."""

    def __init__(self, *uniqs: str) -> None:
        super().__init__(transport="usb")
        self.uniqs = list(uniqs)

    def alvos_conectados(self) -> dict[str, str | None]:
        if not self.is_connected():
            return {}
        return {f"hidraw{i}": u for i, u in enumerate(self.uniqs)}

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u, "connected": self.is_connected()} for u in self.uniqs]

    def set_mic_led(self, aceso: bool, *, uniq: str | None = None) -> None:  # type: ignore[override]
        del uniq
        self.mic_led_history.append(bool(aceso))


class _EleitorDublado:
    """O eleitor de bancada: só vira dono na eleição CONFERIDA, como o real."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []
        self.eleito: str | None = None
        self.fonte_do_eleito: str | None = None

    def eleger_o_controle(self, uniq: str, conectados: list[str]) -> Any:
        del conectados
        self.chamadas.append(uniq)
        self.eleito = uniq
        self.fonte_do_eleito = f"hefesto_mic_{uniq[-6:]}"
        return elm.ResultadoDaEleicao(ok=True, alvo=uniq, ativo=self.fonte_do_eleito)


def _config(**extra: Any) -> DaemonConfig:
    return DaemonConfig(  # type: ignore[arg-type]
        poll_hz=200,
        auto_reconnect=False,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False,
        ps_button_action="none",
        mic_button_toggles_system=False,
        **extra,
    )


class _Mesa:
    def __init__(self) -> None:
        self.registro = RegistroDePedidosDeCanal()
        self.subsystem = BtMicSubsystem(registro=self.registro)
        self.outro_microfone: str | None = None
        self.eleitor = _EleitorDublado()
        self.pedidos: list[str | None] = []


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Mesa]:
    m = _Mesa()

    async def _sem_o_supervisor_de_verdade(self: Daemon) -> None:
        m.subsystem._config = self.config

    monkeypatch.setattr(Daemon, "_start_bt_mic", _sem_o_supervisor_de_verdade)
    agendar = hotkey.agendar_o_nascimento_do_microfone

    def _anotar_o_pedido(daemon: Any, *, uniq: str | None) -> Any:
        m.pedidos.append(uniq)
        return agendar(daemon, uniq=uniq)

    monkeypatch.setattr(hotkey, "agendar_o_nascimento_do_microfone", _anotar_o_pedido)
    monkeypatch.setattr(elm, "outra_captura_elegivel", lambda: m.outro_microfone)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
    )
    anterior_pedidor = elm.registrar_pedidor_de_canal(m.subsystem.pedir_canal)
    anteriores_palavra = elm.registrar_dizedor_do_no_ar(
        m.subsystem.no_ar, m.subsystem.esquecer_a_palavra, m.subsystem.palavra_no_ar
    )
    try:
        yield m
    finally:
        elm.registrar_pedidor_de_canal(anterior_pedidor)
        elm.registrar_dizedor_do_no_ar(*anteriores_palavra)


async def _subir_e_esperar_a_partida(
    mesa: _Mesa, config: DaemonConfig, uniqs: tuple[str, ...] = (P1,)
) -> Daemon:
    """Sobe o `Daemon` com o controle JÁ plugado e espera a partida acabar."""
    controle = _ControleNaMesa(*uniqs)
    store = StateStore()
    daemon = Daemon(controller=controle, bus=EventBus(), store=store, config=config)
    daemon._eleitor_de_microfone = mesa.eleitor  # type: ignore[attr-defined]
    tarefa = asyncio.create_task(daemon.run())
    try:
        for _ in range(1000):
            if set(uniqs) <= set(mesa.pedidos) or tarefa.done():
                break
            await asyncio.sleep(0.01)
        faltam = [u for u in uniqs if u not in mesa.pedidos]
        assert not faltam, f"a partida não pediu o nascimento de {len(faltam)} controle(s)"
        for _ in range(50):
            em_voo = [t for t in hotkey._NASCIMENTOS_EM_VOO if not t.done()]
            if not em_voo:
                break
            await asyncio.gather(*em_voo, return_exceptions=True)
    finally:
        daemon.stop()
        await asyncio.wait_for(tarefa, timeout=10)
    return daemon


@pytest.mark.asyncio
async def test_o_controle_plugado_na_partida_nasce_no_ar(mesa: _Mesa) -> None:
    daemon = await _subir_e_esperar_a_partida(mesa, _config())

    assert hotkey._no_ar_da_sessao(daemon).esta(P1), (
        "o controle que já estava plugado quando o daemon subiu não nasceu no "
        "ar — é o microfone MUDO depois do restart do `install.sh`"
    )
    assert mesa.registro.no_ar().get(P1) is True, (
        "a palavra não foi dita na partida — o `0x32` sai desligado"
    )
    assert P1 in mesa.registro.abertos(), "o canal do controle não foi pedido"
    assert mesa.eleitor.eleito == P1, (
        "numa máquina sem outro microfone, o controle da partida não virou a "
        "fonte padrão"
    )


@pytest.mark.asyncio
async def test_a_partida_nao_toma_o_microfone_de_quem_tem_headset(
    mesa: _Mesa,
) -> None:
    """A metade que tem de entrar JUNTO: sem ela, curar a partida piora a máquina."""
    mesa.outro_microfone = HEADSET

    daemon = await _subir_e_esperar_a_partida(mesa, _config())

    assert mesa.eleitor.chamadas == [], (
        "a partida do daemon elegeu o controle numa máquina com headset: "
        f"{mesa.eleitor.chamadas}"
    )
    assert mesa.eleitor.eleito is None
    assert hotkey._no_ar_da_sessao(daemon).esta(P1), (
        "não tomar o padrão custou o AR — o microfone tem de nascer ligado"
    )


@pytest.mark.asyncio
async def test_a_recusa_dela_vale_na_partida(mesa: _Mesa) -> None:
    """`microfone: false` no `maquina.json`: a partida não liga o que ela desligou."""
    daemon = await _subir_e_esperar_a_partida(
        mesa, _config(bt_mic_recusados=lambda: frozenset({P1}))
    )

    assert not hotkey._no_ar_da_sessao(daemon).esta(P1)
    assert mesa.registro.no_ar() == {}, "a palavra foi dita a quem ela calou"
    assert mesa.registro.abertos() == frozenset(), "o canal foi pedido mesmo assim"
    assert mesa.eleitor.chamadas == []


@pytest.mark.asyncio
async def test_a_partida_nao_passa_por_cima_do_controle_que_ela_escolheu(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dois controles na mesa, e o usuário escolheu o SEGUNDO como microfone padrão."""
    from pathlib import Path

    estado = Path.home() / ".local" / "state" / "wireplumber"
    estado.mkdir(parents=True, exist_ok=True)
    (estado / "default-nodes").write_text(
        f"[default-nodes]\ndefault.configured.audio.source=hefesto_mic_{P2[-6:]}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        Daemon, "aplicar_gamepad_para_multiplos_controles", lambda self: None
    )
    daemon = await _subir_e_esperar_a_partida(mesa, _config(), (P1, P2))

    assert mesa.eleitor.chamadas == [P2], (
        "a partida do daemon elegeu outro controle por cima da escolha gravada "
        f"dela: {mesa.eleitor.chamadas}"
    )
    no_ar = hotkey._no_ar_da_sessao(daemon)
    assert no_ar.esta(P1) and no_ar.esta(P2), (
        "respeitar a escolha dela custou o AR de um dos dois"
    )


MESA_DE_QUATRO = ("aabbcc0000b1", "aabbcc0000b2", "aabbcc0000b3", "aabbcc0000b4")


@pytest.mark.asyncio
@pytest.mark.parametrize("quantos", [1, 2, 4], ids=["um", "dois", "quatro"])
async def test_a_partida_com_o_connect_lento_nasce_cada_controle_no_ar(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch, quantos: int
) -> None:
    """O connect de boot mais lento que o primeiro tique: o runner do CI."""
    from hefesto_dualsense4unix.daemon import connection

    original = connection.reapply_mic_after_connect

    async def _lento(daemon: Any, *args: Any, **kwargs: Any) -> Any:
        await asyncio.sleep(0.2)
        return await original(daemon, *args, **kwargs)

    monkeypatch.setattr(connection, "reapply_mic_after_connect", _lento)
    nascer = hotkey.nascer_no_ar

    async def _nascer_devagar(daemon: Any, uniq: str) -> bool:
        await asyncio.sleep(0.3)
        return bool(await nascer(daemon, uniq))

    monkeypatch.setattr(hotkey, "nascer_no_ar", _nascer_devagar)
    monkeypatch.setattr(
        Daemon, "aplicar_gamepad_para_multiplos_controles", lambda self: None
    )
    uniqs = MESA_DE_QUATRO[:quantos]
    daemon = await _subir_e_esperar_a_partida(mesa, _config(), uniqs)

    no_ar = hotkey._no_ar_da_sessao(daemon)
    fora = [u for u in uniqs if not no_ar.esta(u)]
    assert not fora, f"com o connect lento, {len(fora)} de {quantos} controle(s) não nasceram no ar"
    assert mesa.eleitor.chamadas == [uniqs[0]], mesa.eleitor.chamadas
