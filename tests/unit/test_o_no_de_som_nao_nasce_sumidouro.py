"""O nó de som não entra no daemon como SUMIDOURO — medido em 07/09/2026.

O QUE ESTA RÉGUA EXISTE PARA IMPEDIR
-------------------------------------
O `AltoFalanteSubsystem` (`daemon/subsystems/alto_falante.py`) está órfão: não
consta de `SUBSYSTEM_REGISTRY` nem do `run()` de `daemon/lifecycle.py`. A
leitura fácil — e ela foi escrita num despacho — é *"então é só ligar as duas
metades, como o `BtMicSubsystem`"*.

**Ligá-lo hoje não é cura, é regressão**, e a medição é esta:

    pactl load-module module-null-sink sink_name=hefesto_som_<hex6>
        format=s16le rate=48000 channels=2
        sink_properties="device.description='Alto-falante do controle' …"

e **mais nada**. Nenhum `module-loopback`. O monitor do nó não vai a lugar
nenhum — o nó aceita o áudio e o joga fora.

Com os quatro DualSense na mesa dela (medido em 07/09/2026: dois no cabo, dois
no rádio), `AltoFalanteSubsystem.alvos()` devolve **os quatro**, e os quatro
nasceriam com o MESMO rótulo `Alto-falante do controle` — porque
`GerenciadorDeNosDeSom._construir` chama `SinkVirtualPipeWire(uniq=uniq)` sem
rótulo próprio, e o default é a constante `DESCRICAO_PROVISORIA`. Quatro entradas
idênticas e mudas na lista de som dela, ao lado das DUAS placas reais que hoje
FUNCIONAM pelo cabo. Ela escolhe uma das quatro e o som some.

QUEM JÁ TINHA ESCRITO ISTO, E COM ESTAS PALAVRAS
-------------------------------------------------
`app/audio_saida.py` é a segunda implementação do mesmo nó, mais nova e mais
cuidadosa, e ela nomeia o defeito na invariante 4 do `PlanoDoNo`:

    *"sem rota não se carrega módulo nenhum. Um `module-null-sink` sozinho
    seria exatamente o sink que aceita o áudio e o joga fora."*

`rota_do_no` recusa no rádio (`ponte_do_radio=None` é *"o estado de hoje e o
padrão de propósito"*) e, no cabo, só publica quando `sink_do_controle` resolve
a placa DAQUELE controle pela identidade. O `AltoFalanteSubsystem` não faz
nenhuma das duas coisas.

O QUE ESTA RÉGUA PERMITE — e é metade do desenho
-------------------------------------------------
Ela **não** proíbe ligar o subsystem. Ela trava o PAR: *se ele subir, o nó tem
de ter rota*. A cura correta — dar ao gerenciador o portão de rota e o
`module-loopback`, com UM dono para a pergunta "onde este nó entrega?" — passa
nesta régua. Só a fiação crua reprova.

Régua de PRODUTO, não de texto: ela sobe um `Daemon` de verdade e olha o que
foi mandado ao `pactl`, em vez de ler o fonte do `run()`. Ler o fonte é como
esta casa já fabricou verde sobre nada.
"""
from __future__ import annotations

import asyncio

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.integrations.alto_falante_bt import SinkVirtualPipeWire
from hefesto_dualsense4unix.testing import FakeController

#: MAC FORJADO, da faixa sintética que o portão de fixtures permite
#: (`tests/unit/test_anonimato_de_fixtures.py`). Nem mascarado se usa o OUI
#: real da bancada dela: a régua pega por FORMA, e está certa.
_UNIQ = "aa:bb:cc:00:00:ab"


def _state() -> ControllerState:
    return ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )


def _config(**over: object) -> DaemonConfig:
    base: dict[str, object] = dict(
        poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
        autoswitch_enabled=False, mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False, ps_button_action="none",
        mic_button_toggles_system=False,
    )
    base.update(over)
    return DaemonConfig(**base)  # type: ignore[arg-type]


def test_o_no_publicado_hoje_nao_leva_o_som_a_lugar_nenhum() -> None:
    """A MEDIÇÃO, congelada: o nó sobe sozinho, sem `module-loopback`.

    Este é o fato que torna a fiação uma regressão. Se um dia ele passar a
    emitir o loopback, ESTE teste reprova — e é o sinal de que a fiação virou
    possível, não de que algo quebrou. Leia o teste de baixo antes de mexer.
    """
    gravado: list[list[str]] = []

    def runner(argv: list[str]) -> str:
        gravado.append(argv)
        return "77\n"

    assert SinkVirtualPipeWire(uniq=_UNIQ, runner=runner).iniciar() is True

    juntos = [" ".join(argv) for argv in gravado]
    assert any("module-null-sink" in linha for linha in juntos), juntos
    assert not any("module-loopback" in linha for linha in juntos), (
        "o nó de som passou a ter rota — a fiação no `run()` deixou de ser "
        "regressão, e o teste do par abaixo é quem manda agora"
    )


@pytest.mark.asyncio
async def test_o_boot_nao_publica_no_de_som_sem_rota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O PAR, e é ele que morde: subir o daemon não pode criar sumidouro.

    Duas saídas honestas, e as duas passam:

    * o subsystem continua órfão → nenhum `load-module` acontece;
    * o subsystem foi ligado JUNTO com a rota → todo `module-null-sink`
      publicado tem um `module-loopback` ao lado.

    A terceira — ligado sem rota — é a regressão, e é a única que reprova.
    """
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
    )
    mandados: list[list[str]] = []

    def _recorder(argv: list[str]) -> str | None:
        mandados.append(list(argv))
        return "77\n"

    # O seam é o `_rodar` do módulo: `SinkVirtualPipeWire.__init__` resolve
    # `runner or _rodar` nos globais no momento da construção, então o patch
    # alcança os nós que o daemon criar por conta própria. Nada toca o PipeWire.
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.alto_falante_bt._rodar", _recorder
    )

    store = StateStore()
    daemon = Daemon(
        controller=FakeController(transport="usb", states=[_state()]),
        bus=EventBus(), store=store, config=_config(),
    )
    run_task = asyncio.create_task(daemon.run())
    for _ in range(500):
        if store.counter("poll.tick") >= 1:
            break
        await asyncio.sleep(0.01)
    daemon.stop()
    await run_task

    carregados = [
        " ".join(argv) for argv in mandados if "load-module" in " ".join(argv)
    ]
    sinks = [linha for linha in carregados if "module-null-sink" in linha]
    loopbacks = [linha for linha in carregados if "module-loopback" in linha]

    assert len(sinks) <= len(loopbacks), (
        "o daemon publicou nó de som SEM rota — cada `module-null-sink` sem um "
        "`module-loopback` ao lado é um sink que aceita o áudio e o joga fora "
        "(a invariante 4 de `app/audio_saida.py`). Com os quatro DualSense na "
        "mesa isso põe quatro entradas mudas e de nome igual na lista de som "
        f"dela. Publicados: {sinks}"
    )


def test_a_suite_nao_carrega_modulo_de_som_no_pipewire_dela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SOM-DELA-01: um nó construído SEM runner injetado não sobe de verdade.

    O estrago que esta régua fecha foi medido em 07/09/2026 e estava na
    máquina dela: **52 sinks fantasma** `hefesto_som_<hex6>` na lista de som,
    publicados por processo de teste — o daemon não tem uma linha de
    `som_sink_publicado` no `journalctl`. A porta é
    `SinkVirtualPipeWire.__init__`, que resolve `runner or _rodar`.

    A MORDIDA, e ela não toca no som dela: o segundo bloco devolve ao `_rodar`
    um dublê que ACEITA a escrita — o mundo sem a guarda — e o mesmo nó sobe.
    A única diferença entre os dois blocos é a fixture de sessão.
    """
    from hefesto_dualsense4unix.integrations import alto_falante_bt

    # Com a guarda de pé (fixture `_nenhum_modulo_de_som_de_verdade`).
    no = alto_falante_bt.SinkVirtualPipeWire(uniq=_UNIQ)
    assert no.iniciar() is False
    assert no.module_id is None

    # A cura ARRANCADA: um `_rodar` que aceita escrever, como seria sem ela.
    monkeypatch.setattr(alto_falante_bt, "_rodar", lambda argv: "123\n")
    solto = alto_falante_bt.SinkVirtualPipeWire(uniq=_UNIQ)
    assert solto.iniciar() is True, (
        "sem a guarda o nó sobe — é exatamente por aqui que os 52 fantasmas "
        "entraram no PipeWire dela"
    )
    assert solto.module_id == "123"


def test_a_guarda_recusa_a_escrita_e_deixa_a_leitura_passar() -> None:
    """Ler não muda nada dela; só `load-module`/`unload-module` são recusados.

    Uma guarda que cortasse TUDO seria fácil e errada: o `estado()` do nó
    pergunta ao servidor, e há régua que lê. O contrato é o par — a escrita
    volta `None`, a leitura chega ao `pactl`.
    """
    import shutil

    from hefesto_dualsense4unix.integrations import alto_falante_bt

    escrita = alto_falante_bt._rodar(
        ["pactl", "load-module", "module-null-sink", "sink_name=nao_deve_subir"]
    )
    assert escrita is None

    if shutil.which("pactl") is None:  # pragma: no cover — CI sem servidor
        pytest.skip("sem `pactl` nesta máquina: não há leitura a delegar")
    leitura = alto_falante_bt._rodar(["pactl", "list", "sinks", "short"])
    assert leitura is not None, "a guarda comeu a LEITURA — ela só pode comer escrita"
    assert "nao_deve_subir" not in leitura
