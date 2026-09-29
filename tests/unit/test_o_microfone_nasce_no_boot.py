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
        #: os `uniq` cujo nascimento foi PEDIDO, na ordem do pedido: a barreira da partida
        self.pedidos: list[str | None] = []


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Mesa]:
    m = _Mesa()

    async def _sem_o_supervisor_de_verdade(self: Daemon) -> None:
        # O `config` da recusa chega ao subsystem de bancada pelo mesmo
        # caminho do `start`: é ele quem o subsystem lê.
        m.subsystem._config = self.config

    monkeypatch.setattr(Daemon, "_start_bt_mic", _sem_o_supervisor_de_verdade)
    agendar = hotkey.agendar_o_nascimento_do_microfone

    def _anotar_o_pedido(daemon: Any, *, uniq: str | None) -> Any:
        # O espião anota e devolve a tarefa do dono. O `nascer_o_microfone_ao_conectar`
        # importa o nome na hora da chamada (`connection.py`), e o chama para todo
        # `uniq`, inclusive o que ela recusou: a recusa mora DEPOIS do pedido.
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
    """Sobe o `Daemon` com o controle JÁ plugado e espera a partida acabar.

    "Acabou" é o nascimento PEDIDO para cada `uniq` da mesa, e as tarefas desses
    nascimentos terminadas. O primeiro tique do poll loop não serve: o
    `lifecycle.py` cria o poll loop ANTES do connect de boot, e o connect só pede o
    nascimento no fim do `reaplicar_som_em_todos_os_alvos`, depois de dois `await`
    por controle. No runner do CI o tique vinha antes do pedido, o conjunto em voo
    estava vazio e o `stop` chegava antes do nascimento (a corrida 36503520655).
    Vale para um, dois ou quatro controles. Um `sleep` solto mediria um instante.
    """
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


#: A mesa de um a quatro jogadores, na faixa forjada da casa.
MESA_DE_QUATRO = ("aabbcc0000b1", "aabbcc0000b2", "aabbcc0000b3", "aabbcc0000b4")


@pytest.mark.asyncio
@pytest.mark.parametrize("quantos", [1, 2, 4], ids=["um", "dois", "quatro"])
async def test_a_partida_com_o_connect_lento_nasce_cada_controle_no_ar(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch, quantos: int
) -> None:
    """O connect de boot mais lento que o primeiro tique: o runner do CI.

    `lifecycle.py` cria o poll loop ANTES do connect de boot, e o nascimento de
    cada controle é pedido depois de dois `await` por alvo. Com 0,2 s em cada
    `reapply_mic_after_connect`, o primeiro tique chega antes de qualquer pedido;
    e com 0,3 s no `nascer_no_ar` (a eleição que pergunta ao servidor de som), o
    nascimento ainda corre quando a partida termina. A barreira que esperava o
    tique parava o daemon antes do nascimento, e a régua olhava o ar antes de
    ele acabar (a corrida 36503520655, no 3.11). Sem o atraso do nascimento, a
    máquina daqui termina o nascimento dentro do `shutdown` e a barreira velha
    passa: os dois atrasos juntos são o mundo lento. MORDIDA
    (O-CI-DA-DEV-VOLTA-A-VERDE-02): volte a barreira para o `poll.tick` e os três
    reprovam.
    """
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
    # A emulação de vários controles não é desta régua (o mesmo motivo do caso de dois).
    monkeypatch.setattr(
        Daemon, "aplicar_gamepad_para_multiplos_controles", lambda self: None
    )
    uniqs = MESA_DE_QUATRO[:quantos]
    daemon = await _subir_e_esperar_a_partida(mesa, _config(), uniqs)

    no_ar = hotkey._no_ar_da_sessao(daemon)
    fora = [u for u in uniqs if not no_ar.esta(u)]
    assert not fora, f"com o connect lento, {len(fora)} de {quantos} controle(s) não nasceram no ar"
    assert mesa.eleitor.chamadas == [uniqs[0]], mesa.eleitor.chamadas
