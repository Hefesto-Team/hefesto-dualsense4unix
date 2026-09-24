"""A-MIRA-POR-MOVIMENTO-NA-TELA-01 — a mira que nunca andou, e o chip dela.

A SEGUNDA PALAVRA DELA, 23/09/2026: um botão «Mira Virtual» ao lado de
Giroscópio e Acelerômetro, POR CONTROLE, com a dica *«Usar os movimentos do
controle como mira (analógico R), para pessoas com deficiência motora.»*

O ACHADO QUE ABRE ESTE ARQUIVO, e ele é o defeito vivo
-------------------------------------------------------
**A MIRA NUNCA ANDOU NO PRODUTO.** O motor (`gamepad.aplicar_o_movimento`)
pergunta ``getattr(daemon, "_garantir_sensor_hub", None)`` e, sem resposta,
devolve os quatro eixos intactos. O `Daemon` de verdade (`daemon/lifecycle.py`)
não tinha o método — só o `IpcServer` tinha. As réguas da
MOVIMENTO-EM-QUALQUER-MASCARA-01 davam verde porque os três dublês de daemon
penduravam ``_garantir_sensor_hub=lambda: hub`` num `SimpleNamespace`: **o
dublê tinha o que o real não tem**, e a mira ficou verde sem mover um eixo.

Por isso a primeira seção daqui NÃO dubla o daemon: monta o `Daemon` real, o
`IpcServer` real e o `SensorHub` real (só o leitor do nó é de mentira, porque
não há aparelho), e roda o tique real — o `dispatch_gamepad` do P1 e o
`CoopManager.forward_all` dos P2 a P4.

MORDIDA: apague ``Daemon._garantir_sensor_hub`` de `daemon/lifecycle.py` e as
réguas da seção 1 reprovam dizendo que o analógico direito saiu parado.

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``), nunca um OUI real.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)
from hefesto_dualsense4unix.testing import FakeController

_P1, _P2, _P3, _P4 = (
    "aa:bb:cc:00:00:01",
    "aa:bb:cc:00:00:02",
    "aa:bb:cc:00:00:03",
    "aa:bb:cc:00:00:04",
)

#: Um giro de pulso de verdade, em graus/s no eixo `yaw` (y): bem acima da zona
#: morta padrão e abaixo do teto, então a deflexão é franca e não satura.
_GIRO = (0.0, 150.0, 0.0)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    """O `REGISTRO` dos sensores é do processo: nada desta régua vaza dele."""
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


# ---------------------------------------------------------------------------
# 1. O DAEMON DE VERDADE — a cura do achado
# ---------------------------------------------------------------------------


class _LeitorDoNo:
    """O leitor do nó «Motion Sensors» — a única peça de mentira da torneira.

    Do tamanho do `MotionSensorReader` para o que o hub pergunta: `start()`
    afirma que abriu (o hub DESCARTA quem não afirma), `snapshot()` devolve os
    três eixos e `consume_angulo()` drena.
    """

    def __init__(self, giro: tuple[float, float, float]) -> None:
        self._giro = giro

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(x=self._giro[0], y=self._giro[1], z=self._giro[2])

    def consume_angulo(self) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)


def _hub(giro_por_uniq: dict[str, tuple[float, float, float]]) -> SensorHub:
    """O `SensorHub` REAL, com o nó e o leitor dublados — nenhum aparelho aberto."""
    hub = SensorHub(
        motion_factory=lambda uniq, node: _LeitorDoNo(giro_por_uniq[uniq]),
        touch_factory=lambda uniq, node: _LeitorDoNo((0.0, 0.0, 0.0)),
        gamepad_factory=lambda uniq, node: _LeitorDoNo((0.0, 0.0, 0.0)),
        descobrir_motion=lambda: {u: Path(f"/dev/input/event-{u}") for u in giro_por_uniq},
        descobrir_touch=dict,
        descobrir_gamepad=dict,
        auto_manutencao=False,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)
    return hub


def _mesa_de_verdade(
    tmp_path: Path, transporte: str, hub: SensorHub
) -> tuple[Daemon, IpcServer]:
    """O `Daemon` e o `IpcServer` do produto, ligados como o `start_ipc` liga."""
    controle = FakeController(transport=transporte)  # type: ignore[arg-type]
    # A IDENTIDADE DO P1 como o backend real a publica (`primary_uniq`): é
    # isto que o `primary_identity` do tique lê — nenhum monkeypatch nele.
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle,
        store=daemon.store,
        profile_manager=gerente,
        socket_path=tmp_path / "mira.sock",
        daemon=daemon,
    )
    # O hub mora no SERVIDOR, como no produto (`_garantir_sensor_hub` do mixin
    # o cria no primeiro uso); a régua só o injeta antes, com o leitor dublado.
    servidor._sensor_hub = hub
    daemon._ipc_server = servidor
    gerente.apply_movimento(
        Profile(
            name="Com mira",
            match=MatchAny(type="any"),
            movimento=ProfileMovimentoConfig(destino="analogico_direito"),
        )
    )
    return daemon, servidor


class _Vpad:
    """O gamepad virtual: guarda o que o JOGO receberia."""

    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        pass


def _estado(transporte: str) -> ControllerState:
    return ControllerState(
        battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport=transporte  # type: ignore[arg-type]
    )


def _tique_do_p1(
    monkeypatch: pytest.MonkeyPatch, daemon: Daemon, hub: SensorHub, transporte: str
) -> _Vpad:
    """Dois tiques do `dispatch_gamepad`, com a reconciliação do hub no meio.

    O primeiro tique REGISTRA A DEMANDA (é o que abre o leitor, na volta de
    manutenção do hub); o segundo lê o giro. É o mesmo ritmo do produto, com a
    volta de um segundo trocada por uma chamada.
    """
    # As duas extras do tique que não são da mira — o arming de launch e o aviso
    # de troca de modo leem arquivos da Steam e o barramento; ficam de fora.
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    vpad = _Vpad()
    daemon._gamepad_device = vpad
    gp.dispatch_gamepad(daemon, _estado(transporte), frozenset())
    hub.reconciliar()
    gp.dispatch_gamepad(daemon, _estado(transporte), frozenset())
    return vpad


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_a_mira_anda_no_daemon_de_verdade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str
) -> None:
    """O P1, no cabo e no rádio, com o `Daemon` que o produto sobe.

    MORDIDA: apague ``Daemon._garantir_sensor_hub`` e este teste reprova — era
    o estado do produto até 24/09/2026.
    """
    hub = _hub({_P1: _GIRO})
    daemon, _servidor = _mesa_de_verdade(tmp_path, transporte, hub)
    vpad = _tique_do_p1(monkeypatch, daemon, hub, transporte)
    assert vpad.analog, "o tique nem chegou ao vpad"
    assert vpad.analog[-1]["rx"] != 128, (
        f"o controle girou {_GIRO} graus/s e o analógico direito saiu parado "
        f"({vpad.analog[-1]}) — o `Daemon` real não entrega o hub ao motor")


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_a_mira_anda_nos_jogadores_2_3_e_4_no_daemon_de_verdade(
    tmp_path: Path, transporte: str
) -> None:
    """Os P2 a P4, pelo `CoopManager` real sobre o mesmo `Daemon` real.

    *"cara nenhuma solução pode ser feita só pro p1"* — e o laço dos
    secundários passa `self._daemon` ao motor, que é este objeto.
    """
    giros = {_P2: _GIRO, _P3: _GIRO, _P4: _GIRO}
    hub = _hub(giros)
    daemon, _servidor = _mesa_de_verdade(tmp_path, transporte, hub)
    gerente = co.CoopManager(daemon)
    vpads: dict[str, _Vpad] = {}
    for n, uniq in enumerate(sorted(giros), start=2):
        vpads[uniq] = _Vpad()
        gerente._players[uniq] = co._SecondaryPlayer(
            identity=uniq,
            evdev_path=f"/dev/input/event{n}",
            reader=SimpleNamespace(
                snapshot=lambda: SimpleNamespace(
                    lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                    buttons_pressed=frozenset()),
                grab_state="held",
            ),
            player_index=n,
            vpad=vpads[uniq],
        )
    gerente.forward_all()
    hub.reconciliar()
    gerente.forward_all()
    for uniq, vpad in sorted(vpads.items()):
        assert vpad.analog[-1]["rx"] != 128, (
            f"o jogador {uniq} girou o controle e não mirou — o `Daemon` real "
            f"não entrega o hub ao laço dos secundários")


def test_o_hub_da_mira_e_o_mesmo_do_ipc(tmp_path: Path) -> None:
    """UM HUB SÓ POR SESSÃO. Dois hubs abririam dois leitores no mesmo nó e
    duas máquinas de `EVIOCGRAB` brigando pelo interruptor de sensor dela.

    MORDIDA: faça o `Daemon` criar o próprio `SensorHub` (copiar o método do
    mixin, em vez de delegar) e este teste reprova.
    """
    hub = _hub({_P1: _GIRO})
    daemon, servidor = _mesa_de_verdade(tmp_path, "usb", hub)
    assert daemon._garantir_sensor_hub() is servidor._garantir_sensor_hub() is hub


def test_sem_servidor_os_eixos_saem_como_entraram(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O instante antes de o IPC subir (ou um IPC que caiu): sem hub, sem mira,
    e SEM AVISO — o motor pediria o hub 60 vezes por segundo.

    MORDIDA: devolva ``None`` em vez de ``HUB_AUSENTE`` e este teste reprova
    pelo aviso `roteador_de_movimento_falhou` a cada tique.
    """
    from structlog.testing import capture_logs

    hub = _hub({_P1: _GIRO})
    daemon, _servidor = _mesa_de_verdade(tmp_path, "usb", hub)
    daemon._ipc_server = None
    with capture_logs() as logs:
        vpad = _tique_do_p1(monkeypatch, daemon, hub, "usb")
    assert vpad.analog and vpad.analog[-1]["rx"] == 128
    avisos = [e for e in logs if e.get("event") == "roteador_de_movimento_falhou"]
    assert not avisos, f"o tique sem servidor registrou {len(avisos)} aviso(s): {avisos}"


# ---------------------------------------------------------------------------
# 2. O MOTOR POR PEÇA — `core/roteador_de_movimento.py` e o filtro do report
# ---------------------------------------------------------------------------
#
# A mira era UM arranjo por perfil (`D-0809-A-NAVEGACAO-E-GLOBAL-NO-PERFIL`); o
# chip «Mira Virtual» mora no cartão de CADA controle. A regra de decisão é uma
# só, a do `leds` e do `rumble` por controle: a peça que tem opinião usa a dela,
# campo a campo por cima da do perfil; a peça calada segue a do perfil.


def _mira(**kw: Any) -> Any:
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    base: dict[str, Any] = {"destino": rot.DESTINO_ANALOGICO_DIREITO}
    base.update(kw)
    return rot.ArranjoDeMovimento(**base)


def test_o_arranjo_desligado_nao_move_nada() -> None:
    """O arranjo `nenhum` guarda os números dos deslizantes e não move o eixo.

    MORDIDA: tire o ``if not arranjo.ligado`` de `deflexao` e este teste
    reprova — o `SO_NAS_PECAS` que o tique recebe moveria o analógico direito
    de TODA a mesa como se fosse uma mira ligada.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    desligado = _mira(destino=rot.DESTINO_NENHUM, sensibilidade=12)
    assert rot.deflexao((0.0, 200.0, 0.0), desligado) == (0, 0)
    assert rot.pixels((0.0, 30.0, 0.0), desligado) == (0.0, 0.0)
    assert rot.deflexao((0.0, 200.0, 0.0), rot.SO_NAS_PECAS) == (0, 0)


def test_o_arranjo_desligado_guarda_os_numeros_dela() -> None:
    """`montar` devolve o arranjo mesmo com a mira apagada; `resolver`, não.

    O «Ignorar tremor até» que ela ajustou num controle de mira apagada não
    pode sumir só porque a mira não está andando.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    secao = ProfileMovimentoConfig(destino="nenhum", zona_morta_graus_s=25.0)
    assert rot.resolver(secao) is None
    montado = rot.montar(secao)
    assert montado.zona_morta_graus_s == 25.0 and not montado.ligado


def test_so_uma_peca_mira_e_o_tique_ainda_chama_o_motor() -> None:
    """Sem mira no perfil e com o chip aceso no P3, o `ativo()` NÃO pode dizer
    `None`: os dois laços do tique só chamam o motor quando ele responde.

    MORDIDA: devolva `None` no lugar de `SO_NAS_PECAS` e este teste reprova —
    o P3 ficaria calado junto com a mesa.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    store = SimpleNamespace()
    rot.definir_ativo(store, None)
    assert rot.ativo(store) is None, "sem mira nenhuma o tique pagou o motor"
    rot.definir_por_peca(store, {_P3: _mira()})
    assert rot.ativo(store) is rot.SO_NAS_PECAS
    rot.definir_por_peca(store, {_P3: _mira(destino=rot.DESTINO_NENHUM)})
    assert rot.ativo(store) is None, "a peça de mira APAGADA acordou o motor"


def test_a_peca_com_opiniao_manda_e_a_calada_segue_o_perfil() -> None:
    """A ordem de decisão, nos dois sentidos.

    MORDIDA: faça `da_peca` ignorar o mapa e este teste reprova pelo P3; faça-o
    ignorar a mesa e ele reprova pelo P2.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    store = SimpleNamespace()
    mesa = _mira(sensibilidade=4)
    rot.definir_ativo(store, mesa)
    rot.definir_por_peca(store, {
        _P3: _mira(sensibilidade=11),
        _P4: _mira(destino=rot.DESTINO_NENHUM),
    })
    ativo = rot.ativo(store)
    assert rot.da_peca(store, _P2, ativo) is mesa, "o P2 calado não seguiu o perfil"
    assert rot.da_peca(store, _P3, ativo).sensibilidade == 11, (
        "o P3 tem a mira dele e recebeu a do perfil")
    assert rot.da_peca(store, _P4, ativo) is None, (
        "o P4 APAGOU o chip e mira assim mesmo, pela mira do perfil")
    # As DUAS grafias da mesma peça (com e sem dois-pontos) são a mesma peça.
    assert rot.da_peca(store, "aabbcc000003", ativo).sensibilidade == 11


def test_a_peca_sobrepoe_o_perfil_campo_a_campo() -> None:
    """A peça que só escreveu o destino HERDA do perfil a sensibilidade e o
    tremor — é o `model_fields_set` que separa escrito de padrão.

    MORDIDA: troque `_campos_escritos` por todos os campos da seção e este
    teste reprova: o destino da peça apagaria o tremor que ela ajustou no
    perfil com o padrão 3,0.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    perfil = ProfileMovimentoConfig(destino="nenhum", zona_morta_graus_s=30.0,
                                    sensibilidade=9)
    peca = ProfileMovimentoConfig(destino="analogico_direito")
    arranjo = rot.arranjo_da_peca(perfil, peca)
    assert arranjo.ligado
    assert arranjo.zona_morta_graus_s == 30.0 and arranjo.sensibilidade == 9


def test_o_perfil_sem_mira_por_peca_apaga_a_do_anterior() -> None:
    """O CAMINHO-CONTAGIO-01 por peça: o P3 do jogo de ontem não mira no de hoje."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    store = SimpleNamespace()
    rot.definir_por_peca(store, {_P3: _mira()})
    rot.definir_por_peca(store, {})
    assert rot.por_peca(store) == {}
    assert rot.ativo(store) is None


def _janela_viva() -> bytes:
    """Uma janela de motion com giro, aceleração e um dedo no touchpad."""
    from hefesto_dualsense4unix.core.virtual_motion import TAMANHO_DA_JANELA

    janela = bytearray(range(1, TAMANHO_DA_JANELA + 1))
    return bytes(janela)


def test_a_camera_nao_anda_em_dobro_no_caminho_virtual() -> None:
    """A PEÇA QUE MIRA PERDE O GIROSCÓPIO da janela do vpad, e SÓ ele.

    Ordem dela, 23/09/2026: *na mira, a câmera não pode andar em dobro*. No
    caminho `uhid` o jogo recebe o giro nativo pela janela de motion; com a
    mira ligada o mesmo gesto chegaria DUAS vezes — pelo giroscópio e pelo
    analógico direito. O acelerômetro, o carimbo de tempo e o touchpad seguem.

    MORDIDA: tire o ``and not self.roteado(uniq)`` do `filtrar` e este teste
    reprova.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.core.virtual_motion import (
        FAIXA_ACELEROMETRO,
        FAIXA_GIROSCOPIO,
    )

    store = SimpleNamespace()
    rot.definir_ativo(store, None)
    rot.definir_por_peca(store, {_P3: _mira()})
    rot.sincronizar_o_filtro(store)
    janela = _janela_viva()
    do_p3 = REGISTRO.filtrar(_P3, janela)
    assert do_p3[FAIXA_GIROSCOPIO] == bytes(6), "o P3 mira e o jogo ainda recebe o giro"
    assert do_p3[FAIXA_ACELEROMETRO] == janela[FAIXA_ACELEROMETRO]
    assert do_p3[12:] == janela[12:], "a mira apagou o carimbo ou o touchpad"
    assert REGISTRO.filtrar(_P2, janela) is janela, "o P2 não mira e perdeu o giro"
    # O INTERRUPTOR DELA CONTINUA DIZENDO O QUE ELA ESCOLHEU: o sensor segue
    # LIGADO, porque é ele que move a mira.
    assert REGISTRO.estado(_P3).giroscopio is True


def test_a_mira_do_perfil_tira_o_giro_de_quem_nao_tem_opiniao() -> None:
    """Com a mira no PERFIL, toda peça calada mira — e perde o giro nativo; a
    peça que APAGOU o chip continua mandando o giro ao jogo."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.core.virtual_motion import FAIXA_GIROSCOPIO

    store = SimpleNamespace()
    rot.definir_ativo(store, _mira())
    rot.definir_por_peca(store, {_P4: _mira(destino=rot.DESTINO_NENHUM)})
    rot.sincronizar_o_filtro(store)
    janela = _janela_viva()
    assert REGISTRO.filtrar(_P2, janela)[FAIXA_GIROSCOPIO] == bytes(6)
    assert REGISTRO.filtrar(_P4, janela) is janela
    # E o perfil seguinte, sem mira, devolve o giro a todo mundo.
    rot.definir_ativo(store, None)
    rot.definir_por_peca(store, {})
    rot.sincronizar_o_filtro(store)
    assert REGISTRO.filtrar(_P2, janela) is janela
