"""O microfone do controle que JÁ ESTAVA na mesa quando o daemon subiu nasce no ar.

A LACUNA, e ela era a primeira coisa que uma máquina nova via
------------------------------------------------------------------------------
A NASCE-LIGADO-MIC-01 (17/09/2026) pôs o microfone no ar na chegada do
controle, e a régua dela mediu os caminhos de conexão pelas funções que eles
chamam. Faltou o caminho que não chama nenhuma delas: a PARTIDA do daemon.
`Daemon.run` conecta por conta própria, publica `CONTROLLER_CONNECTED` e
restaura o perfil — e o `reconnect_loop` nasce com `was_connected` e a foto por
alvo tiradas depois disso, então quem já estava plugado nunca vira borda.

Medido no journal dela em 18/09/2026 (só leitura): nenhuma das partidas do dia
com `controller_connected` no boot teve um `mic_nasceu_no_ar`; os nascimentos só
apareciam no hotplug. Numa máquina nova é o PRIMEIRO caso: o `install.sh`
reinicia o daemon com o controle no cabo, e o microfone ficava MUDO com a tela
dizendo que ele nasce ligado.

POR QUE O DUBLÊ TEM ALVOS DE VERDADE
------------------------------------------------------------------------------
Com o `FakeController` cru esta régua fica verde sobre o buraco: sem
`alvos_conectados`, `connection.alvos_conectados_de` devolve `None`, o `uniq`
vira `None` e `agendar_o_nascimento_do_microfone` devolve `None` sem nascer
nada — com ou sem a cura. O controle daqui diz QUEM está na mesa.

O QUE NÃO SOBE AQUI, e a razão é a máquina de quem roda a suíte
------------------------------------------------------------------------------
O `BtMicSubsystem` de verdade não sobe: com um pedido de canal aberto, o
supervisor dele pergunta ao `pactl` vivo e pode carregar módulo no servidor de
som. Os ganchos da palavra e do pedido são os do subsystem, no mesmo molde de
`test_nasce_ligado_mic_01_o_microfone_nasce_no_ar.py` — o registro é o de
verdade, sem a thread. O eleitor é dublado pela mesma razão, e a pergunta
"existe outro microfone?" é dublada no dono (`outra_captura_elegivel`).

A MORDIDA
------------------------------------------------------------------------------
Tire o `reaplicar_som_em_todos_os_alvos` do connect de boot em
`daemon/lifecycle.py` e o primeiro caso reprova. Troque a condição de
`hotkey._nascer_no_ar_na_vez` de volta para só `eleito is None` e o segundo
reprova — que é o que o cético avisou: curar a partida sem curar a eleição faria
CADA partida do daemon tomar o microfone de quem tem headset. Tire a guarda da
recusa e o terceiro reprova. Tire a pergunta pela escolha gravada
(`hotkey._a_escolha_gravada_e_de_outro_controle`) e o quarto reprova: a partida
com dois controles voltaria a sobrescrever o microfone que ela escolheu.
"""

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

#: Endereço SINTÉTICO, da faixa que o portão de fixtures permite.
P1 = "aabbcc0000b1"

#: O microfone de verdade de quem não é ela: um headset USB genérico.
HEADSET = "alsa_input.usb-Fabricante_Headset_USB-00.mono-fallback"


#: O segundo controle da mesa — a partida com dois é o que separa "o primeiro da
#: fila" de "o que ela escolheu".
P2 = "aabbcc0000b2"


class _ControleNaMesa(FakeController):
    """O `FakeController` que sabe dizer QUEM está conectado.

    `alvos_conectados` e `describe_controllers` são as duas leituras por alvo
    que o nascimento usa; `set_mic_led` aceita o `uniq` como o backend real.
    """

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


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Mesa]:
    m = _Mesa()

    async def _sem_o_supervisor_de_verdade(self: Daemon) -> None:
        # O `config` da recusa chega ao subsystem de bancada pelo mesmo
        # caminho do `start`: é ele quem o subsystem lê.
        m.subsystem._config = self.config

    monkeypatch.setattr(Daemon, "_start_bt_mic", _sem_o_supervisor_de_verdade)
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
    """Sobe o `Daemon` com o controle JÁ plugado e espera a partida acabar.

    "Acabou" é o poll loop ter dado um tique — o connect de boot vem antes
    dele — e as tarefas de nascimento em voo terem terminado. Um `sleep`
    solto mediria um instante e daria verde intermitente.
    """
    controle = _ControleNaMesa(*uniqs)
    store = StateStore()
    daemon = Daemon(controller=controle, bus=EventBus(), store=store, config=config)
    daemon._eleitor_de_microfone = mesa.eleitor  # type: ignore[attr-defined]
    tarefa = asyncio.create_task(daemon.run())
    try:
        for _ in range(300):
            if store.counter("poll.tick") >= 1:
                break
            await asyncio.sleep(0.01)
        assert store.counter("poll.tick") >= 1, "o daemon não chegou ao poll loop"
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
    """A metade que tem de entrar JUNTO: sem ela, curar a partida piora a máquina.

    Cada partida do daemon — inclusive o restart do próprio `install.sh` —
    passaria a escrever `set-default-source` por cima do headset da pessoa.
    """
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
    """`microfone: false` no `maquina.json`: a partida não liga o que ela desligou.

    A fonte chamável é a mesma que `Daemon.__init__` fia sobre o
    `maquina.json`; passá-la montada exerce a regra sem escrever no disco.
    """
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
    """Dois controles na mesa, e ela escolheu o SEGUNDO como microfone padrão.

    O `default.configured.audio.source` do WirePlumber diz o canal do P2. A
    partida solta um nascimento por controle em ordem de `alvos_conectados`, e
    o P1 vem primeiro: com a mesa sem dono ele elegia e sobrescrevia a escolha
    dela — a cada restart do `install.sh`, a cada atualização, a cada login.

    MORDIDA: tire a pergunta `_a_escolha_gravada_e_de_outro_controle` de
    `hotkey._o_nascimento_pode_tomar_o_padrao` e o P1 aparece nas chamadas.
    """
    from pathlib import Path

    estado = Path.home() / ".local" / "state" / "wireplumber"
    estado.mkdir(parents=True, exist_ok=True)
    (estado / "default-nodes").write_text(
        f"[default-nodes]\ndefault.configured.audio.source=hefesto_mic_{P2[-6:]}\n",
        encoding="utf-8",
    )

    # A AUTO-01.1 sai da partida de dois: dois controles na mesa ligam a
    # emulação sozinhos no poll loop, o vpad nasce por `evdev.UInput`, e a
    # VIGIA-DE-APARELHO-01 reprova a sessão (medido: dois nós recusados). A
    # emulação não é desta régua.
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
