"""O nó de som não entra no daemon como SUMIDOURO — medido em 07/09/2026.

O QUE ESTA RÉGUA EXISTE PARA IMPEDIR
-------------------------------------
O `AltoFalanteSubsystem` (`daemon/subsystems/alto_falante.py`) está órfão: não
consta de `SUBSYSTEM_REGISTRY` nem do `run()` de `daemon/lifecycle.py`. A
leitura fácil — e ela foi escrita num despacho — é *"então é só ligar as duas
metades, como o `BtMicSubsystem`"*.

**A METADE DE CIMA FOI CURADA EM 09/09/2026 (SOM-POR-CONTROLE-01), e o texto
que a descrevia fica como registro do que custou.** Até 08/09 o nó subia assim:

    pactl load-module module-null-sink sink_name=hefesto_som_<hex6>
        format=s16le rate=48000 channels=2
        sink_properties="device.description='Alto-falante do controle' …"

e **mais nada**. Nenhum `module-loopback`, e os quatro com o MESMO rótulo. Hoje
`SinkVirtualPipeWire` recebe uma `RotaDoNo` e sobe o `module-loopback` junto
quando há rota, e o `GerenciadorDeNosDeSom` batiza cada um «Alto-falante do
Controle N». **O que continua faltando para ligá-lo são as TRÊS linhas do
registro** — `daemon/subsystems/__init__.py`, `daemon/lifecycle.py` e
`daemon/connection.py` —, e nenhuma delas estava na posse daquela sprint.

Com os quatro DualSense na mesa dela (medido em 07/09/2026: dois no cabo, dois
no rádio), `AltoFalanteSubsystem.alvos()` devolve **os quatro**, e os quatro
nasceriam com o MESMO rótulo genérico — porque
`GerenciadorDeNosDeSom._construir` chama `SinkVirtualPipeWire(uniq=uniq)` sem
rótulo próprio, e o default era uma constante de rótulo genérico. Quatro entradas
idênticas e mudas na lista de som dela, ao lado das DUAS placas reais que hoje
FUNCIONAM pelo cabo. Ela escolhe uma das quatro e o som some.

QUEM JÁ TINHA ESCRITO ISTO, E COM ESTAS PALAVRAS
-------------------------------------------------
`app/audio_saida.py` é a segunda implementação do mesmo nó, mais nova e mais
cuidadosa, e ela nomeia o defeito na invariante 4 do `PlanoDoNo`:

    *"sem rota não se carrega módulo nenhum. Um `module-null-sink` sozinho
    seria exatamente o sink que aceita o áudio e o joga fora."*

`rota_do_no` recusa no rádio (`ponte_do_radio=None` é *"o estado de hoje e o
padrão de propósito"*) e, no cabo, só entrega quando `sink_do_controle` resolve
a placa DAQUELE controle pela identidade. **Desde 09/09/2026 ele mora em
`integrations/alto_falante_bt` e é o subsystem quem o chama** — o daemon não
importa `app/`, e por isso a resposta mudou de endereço em vez de ganhar uma
segunda cópia.

E a invariante 4 mudou de forma: `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`
(decisão DELA) diz que o nó é publicado mesmo sem rota — *"nó que some quebra o
jogo que o escolheu"*. O que sobra dela, e é o que este arquivo trava, é que
**um `module-null-sink` publicado pelo DAEMON tenha o `module-loopback` ao
lado**: o daemon só publica quem tem rota; quem não tem, ele nem constrói.

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


def test_o_no_com_rota_leva_o_som_ao_aparelho_e_sem_rota_nao_engana() -> None:
    """A MEDIÇÃO, refeita em 09/09/2026: o nó só liga o que ele tem para ligar.

    **FATO SUBSTITUÍDO.** Este teste se chamava
    `test_o_no_publicado_hoje_nao_leva_o_som_a_lugar_nenhum` e exigia que
    NENHUM `module-loopback` fosse emitido — congelando a medição que tornava a
    fiação uma regressão. A rota existe desde a SOM-POR-CONTROLE-01, e o que se
    mede agora é o PAR: com rota o loopback sai, sem rota ele não sai.

    MORDIDA: emita o loopback também quando `rota is None` e a segunda metade
    reprova — o produto ligaria o som a um sink que ninguém resolveu.
    """
    from hefesto_dualsense4unix.integrations.alto_falante_bt import RotaDoNo

    def _gravar() -> tuple[list[list[str]], object]:
        gravado: list[list[str]] = []

        def runner(argv: list[str]) -> str:
            gravado.append(argv)
            return "77\n"

        return gravado, runner

    com, runner_com = _gravar()
    assert SinkVirtualPipeWire(
        uniq=_UNIQ,
        runner=runner_com,  # type: ignore[arg-type]
        rota=RotaDoNo(True, sink="alsa_output.usb-x", por_onde="cabo"),
    ).iniciar() is True
    juntos = [" ".join(argv) for argv in com]
    assert any("module-null-sink" in linha for linha in juntos), juntos
    assert any("module-loopback" in linha for linha in juntos), juntos

    sem, runner_sem = _gravar()
    assert SinkVirtualPipeWire(
        uniq=_UNIQ, runner=runner_sem  # type: ignore[arg-type]
    ).iniciar() is True
    soltos = [" ".join(argv) for argv in sem]
    assert any("module-null-sink" in linha for linha in soltos), soltos
    assert not any("module-loopback" in linha for linha in soltos), soltos


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

    O ESPIÃO NO `subprocess.run` (validação da A-SUITE-NAO-PERGUNTA-AO-SOM-01,
    14/09/2026). Com o dublê do SOM-DE-MENTIRA na sessão, um `load-module` que
    escapasse da guarda também voltava `None` — o dublê responde rc=1 —, e o
    primeiro bloco passava com a guarda do alto-falante ARRANCADA (medido: 37
    verdes nos três arquivos que tocam a guarda). O espião responde como um
    servidor que ACEITA, igual à régua do microfone em
    `test_o_som_e_o_volume_respeitam_o_recuo.py`, e o veredito deixa de depender
    do dublê e da máquina.

    MORDIDA: em `_nenhum_modulo_de_som_de_verdade`, deixe o `alto_falante_bt`
    sem o `_sem_escrever_no_som`, e o primeiro bloco reprova.
    """
    import subprocess

    from hefesto_dualsense4unix.integrations import alto_falante_bt
    from tests.conftest import _som_de_verdade

    if _som_de_verdade():
        pytest.skip("HEFESTO_SOM_DE_VERDADE=1: a guarda de escrita está desligada a pedido")

    chegaram: list[list[str]] = []

    def _run(argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        chegaram.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="123\n", stderr="")

    monkeypatch.setattr(alto_falante_bt.subprocess, "run", _run)
    monkeypatch.setattr(alto_falante_bt.shutil, "which", lambda _nome: "/usr/bin/pactl")

    # Com a guarda de pé (fixture `_nenhum_modulo_de_som_de_verdade`).
    no = alto_falante_bt.SinkVirtualPipeWire(uniq=_UNIQ)
    assert no.iniciar() is False
    assert no.module_id is None
    escritas = [argv for argv in chegaram if "load-module" in argv]
    assert escritas == [], f"o `load-module` passou pela guarda: {escritas}"

    # A cura ARRANCADA: um `_rodar` que aceita escrever, como seria sem ela.
    monkeypatch.setattr(alto_falante_bt, "_rodar", lambda argv: "123\n")
    solto = alto_falante_bt.SinkVirtualPipeWire(uniq=_UNIQ)
    assert solto.iniciar() is True, (
        "sem a guarda o nó sobe — é exatamente por aqui que os 52 fantasmas "
        "entraram no PipeWire dela"
    )
    assert solto.module_id == "123"


def test_a_guarda_recusa_a_escrita_e_deixa_a_leitura_passar() -> None:
    """A guarda recusa `load-module`/`unload-module` e entrega a leitura a quem
    está por baixo dela — e quem está por baixo, aqui, é um ESPIÃO.

    Uma guarda que cortasse TUDO no `_rodar` seria fácil e errada: o `estado()`
    do nó pergunta ao servidor, e há régua que lê com um `runner` próprio. O
    contrato é o par — a escrita volta `None` sem chegar a ninguém, a leitura
    chega inteira a quem está por baixo.

    FATO SUBSTITUÍDO (13/09/2026, A-SUITE-NAO-PERGUNTA-AO-SOM-01). Este teste
    lia `pactl list sinks short` do servidor de som DE VERDADE, com a razão
    «ler não muda nada dela». Ler trava junto quando o servidor trava — e o
    dela travou duas vezes naquele dia —, e o veredito passava a depender da
    máquina. O par medido é o mesmo; o servidor de quem roda saiu da conta, e
    quem prova que a suíte inteira não o alcança é
    `test_a_suite_nao_conversa_com_o_som_dela.py`.

    MORDIDA: faça `_sem_escrever_no_som` delegar também as escritas, e a
    primeira metade reprova; faça-o devolver `None` para tudo, e a segunda.
    """
    from tests.conftest import _sem_escrever_no_som

    vistos: list[list[str]] = []

    def espiao(argv: list[str]) -> str:
        vistos.append(list(argv))
        return "97\thefesto_som_0000ab\tPipeWire\ts16le 2ch 48000Hz\tIDLE\n"

    guarda = _sem_escrever_no_som(espiao)

    assert guarda(
        ["pactl", "load-module", "module-null-sink", "sink_name=nao_deve_subir"]
    ) is None
    assert guarda(["pactl", "unload-module", "97"]) is None
    assert vistos == [], f"a escrita chegou a quem está por baixo da guarda: {vistos}"

    leitura = guarda(["pactl", "list", "sinks", "short"])
    assert leitura is not None, "a guarda comeu a LEITURA — ela só pode comer escrita"
    assert "hefesto_som_0000ab" in leitura
    assert vistos == [["pactl", "list", "sinks", "short"]], vistos
