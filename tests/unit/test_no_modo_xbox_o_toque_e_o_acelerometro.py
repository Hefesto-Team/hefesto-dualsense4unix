"""NO-MODO-XBOX-TUDO-FUNCIONA-01 — no modo Xbox, o toque e a inclinação chegam.

A ordem dela, 27/09 à noite: *«se tiver no modo xbox é pra literalmente tudo
isso funcionar.»* E a resposta dela às perguntas 1 a 3 da sprint, 28/09 por volta
das 16h50, em escolhas: **os dois** arranjos — (a) o touchpad move o cursor e o
acelerômetro vira analógico, um chip por controle como a Mira Virtual; (b) o
touchpad em zonas vira botões (direcional, L1, L2), para quem não os alcança —,
**por perfil de jogo**, e quem valida é ela.

O pad do modo Xbox é o Xbox 360, e ele não tem touchpad nem sensor: o jogo nunca
veria o dedo nem a inclinação. A cura é TRADUÇÃO, como a da Mira: o toque vira
botão do Xbox 360 ou cursor do computador, e a inclinação vira analógico. A
regra pura é `core/roteador_de_movimento.py`; o motor, `daemon/subsystems/
gamepad.py` (`aplicar_o_toque`, e a inclinação dentro de `aplicar_o_movimento`),
chamado pelos dois laços do tique, P1 a P4. O nó do touchpad da peça fica
grabado pelo hub enquanto a rota anda (`SensorHub.toque_da_peca`), para o dedo
não mover também o ponteiro do computador.

Os MACs são da faixa forjada (`aa:bb:cc`, octetos 4 e 5 zerados). Nenhum nó de
kernel nasce: o `evdev` e o `uinput` são de mentira, e gravam o que o kernel
receberia. Cada seção diz a sua MORDIDA.
"""

from __future__ import annotations

import asyncio
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any, ClassVar, NamedTuple

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import PontoDeToque, TouchState
from hefesto_dualsense4unix.core.virtual_motion import (
    CONTATOS_DO_TOQUE,
    REGISTRO,
    TAMANHO_DA_JANELA,
    TOQUE_INATIVO,
)
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    XBOX360_PRODUCT,
    XBOX360_VENDOR,
)
from hefesto_dualsense4unix.integrations.virtual_pad import CAMINHO_XBOX, make_virtual_pad
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    NASCIMENTO_DOS_CAMPOS,
    ControllerOverrides,
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

#: O touchpad do DualSense, nas unidades do kernel (`TouchpadReader`).
_LARGURA, _ALTURA = 1920, 1080
#: Um dedo no meio do alto da parte do direcional (o terço de cima do
#: retângulo dos dois terços da esquerda): o direcional para cima.
_DEDO_NO_CIMA = (640, 60)
#: No terço da direita: em cima é o L1, embaixo é o L2.
_DEDO_NO_L1 = (1700, 200)
_DEDO_NO_L2 = (1700, 900)
#: A gravidade de um controle na mesa, em g (y sai da face, SDL/`hid-playstation`).
_DEITADO = (0.0, 1.0, 0.0)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    """O `REGISTRO` dos sensores é do processo: nada desta régua vaza dele."""
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


def _inclinado(graus_para_a_frente: float = 0.0, graus_para_a_direita: float = 0.0) -> tuple[
    float, float, float
]:
    """A gravidade de um controle inclinado: para a frente (o nariz desce) e para a direita."""
    import math

    frente = math.radians(graus_para_a_frente)
    direita = math.radians(graus_para_a_direita)
    return (
        -math.sin(direita),
        math.cos(frente) * math.cos(direita),
        math.sin(frente) * math.cos(direita),
    )


def _toque(*dedos: tuple[int, int]) -> TouchState:
    pontos = tuple(
        PontoDeToque(slot=i, x=x, y=y, identidade=10 + i) for i, (x, y) in enumerate(dedos)
    )
    x, y = dedos[0] if dedos else (0, 0)
    return TouchState(
        touching=bool(dedos), x=x, y=y, largura=_LARGURA, altura=_ALTURA, pontos=pontos
    )


# ===========================================================================
# 1 — o perfil: dois campos novos DENTRO de `movimento`
# ===========================================================================


class TestOPerfil:
    """A resposta dela é por perfil de jogo, e a seção é a da Mira.

    MORDIDA: dê a `toque` ou a `acelerometro` um padrão ligado e
    `test_nascem_sem_opiniao` reprova; tire o serializador e
    `test_o_perfil_de_ontem_sai_igual` reprova.
    """

    def test_nascem_sem_opiniao(self) -> None:
        secao = ProfileMovimentoConfig()
        assert secao.toque == "nenhum", "o touchpad nasceria longe do computador"
        assert secao.acelerometro == "nenhum", "o personagem andaria sozinho"
        assert "ProfileMovimentoConfig.toque" in NASCIMENTO_DOS_CAMPOS
        assert "ProfileMovimentoConfig.acelerometro" in NASCIMENTO_DOS_CAMPOS

    def test_o_perfil_de_ontem_sai_igual(self) -> None:
        """Um hefesto antigo recusa o perfil INTEIRO ao ver chave que não conhece."""
        mira = ProfileMovimentoConfig(destino="analogico_direito", sensibilidade=9)
        dump = mira.model_dump()
        assert "toque" not in dump and "acelerometro" not in dump
        volta = ProfileMovimentoConfig.model_validate(dump)
        assert volta == mira

    def test_quem_escreveu_leva_a_chave_inclusive_o_nenhum(self) -> None:
        """A peça que APAGOU o toque por cima do perfil tem opinião, e ela vai."""
        dump = ProfileMovimentoConfig(
            toque="nenhum", acelerometro="analogico_esquerdo").model_dump()
        assert dump["toque"] == "nenhum"
        assert dump["acelerometro"] == "analogico_esquerdo"

    def test_valor_desconhecido_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            ProfileMovimentoConfig(toque="gestos")
        with pytest.raises(ValidationError):
            ProfileMovimentoConfig(acelerometro="mouse")

    def test_a_peca_sobrepoe_so_o_que_escreveu(self) -> None:
        """O chip do toque da peça não apaga a mira que ela herda do perfil."""
        mesa = ProfileMovimentoConfig(destino="analogico_direito", sensibilidade=8)
        peca = ProfileMovimentoConfig(toque="zonas")
        arranjo = rot.arranjo_da_peca(mesa, peca)
        assert arranjo.toque == "zonas"
        assert arranjo.destino == "analogico_direito" and arranjo.sensibilidade == 8


# ===========================================================================
# 2 — a regra pura
# ===========================================================================


class TestAsZonas:
    """O direcional nos dois terços da esquerda; L1 e L2 no terço da direita.

    MORDIDA: troque, em `botoes_das_zonas`, o `BOTAO_DA_ZONA_DE_BAIXO` pelo
    nome da tela (`"l2"`) e `test_o_l2_fala_a_lingua_do_leitor` reprova — o L2
    da zona nunca ligaria o gatilho do jogo nem o «Só enquanto eu segurar».
    """

    def _z(self, *dedos: tuple[int, int]) -> frozenset[str]:
        return rot.botoes_das_zonas(dedos, _LARGURA, _ALTURA)

    def test_cada_zona_aperta_o_seu_botao(self) -> None:
        assert self._z(_DEDO_NO_CIMA) == {"dpad_up"}
        assert self._z((640, 1020)) == {"dpad_down"}
        assert self._z((60, 540)) == {"dpad_left"}
        assert self._z((1220, 540)) == {"dpad_right"}
        assert self._z(_DEDO_NO_L1) == {"l1"}
        assert self._z(_DEDO_NO_L2) == {"l2_btn"}

    def test_o_miolo_do_direcional_nao_aperta_nada(self) -> None:
        assert self._z((640, 540)) == frozenset()
        assert self._z() == frozenset(), "sem dedo, nenhum botão"

    def test_o_canto_e_diagonal(self) -> None:
        assert self._z((60, 60)) == {"dpad_up", "dpad_left"}

    def test_dois_dedos_duas_zonas(self) -> None:
        assert self._z(_DEDO_NO_CIMA, _DEDO_NO_L2) == {"dpad_up", "l2_btn"}

    def test_o_l2_fala_a_lingua_do_leitor(self) -> None:
        from hefesto_dualsense4unix.core.remapeamento_de_botao import GATILHOS

        assert GATILHOS["l2"] == rot.BOTAO_DA_ZONA_DE_BAIXO


class TestAInclinacao:
    """O acelerômetro vira analógico: zona morta, teto, sentido e sensibilidade.

    MORDIDA: tire a zona morta de `deflexao_da_inclinacao` e
    `test_a_mao_que_respira_nao_anda` reprova.
    """

    def _a(self, **kw: Any) -> rot.ArranjoDeMovimento:
        return rot.ArranjoDeMovimento(acelerometro=rot.DESTINO_ANALOGICO_ESQUERDO, **kw)

    def test_a_mao_que_respira_nao_anda(self) -> None:
        assert rot.deflexao_da_inclinacao(_inclinado(4.0), _DEITADO, self._a()) == (0, 0)

    def test_inclinar_para_a_frente_anda_para_a_frente(self) -> None:
        dh, dv = rot.deflexao_da_inclinacao(_inclinado(20.0), _DEITADO, self._a())
        assert dh == 0 and dv < 0, "o nariz desceu e o analógico não foi para cima"

    def test_inclinar_para_a_direita_vai_para_a_direita(self) -> None:
        dh, dv = rot.deflexao_da_inclinacao(_inclinado(0.0, 20.0), _DEITADO, self._a())
        assert dh > 0 and dv == 0

    def test_o_teto_e_o_batente(self) -> None:
        dh, _ = rot.deflexao_da_inclinacao(_inclinado(0.0, 80.0), _DEITADO, self._a())
        assert dh == rot.DEFLEXAO_MAXIMA

    def test_a_sensibilidade_encurta_o_caminho(self) -> None:
        leve = rot.deflexao_da_inclinacao(_inclinado(0.0, 15.0), _DEITADO, self._a())
        forte = rot.deflexao_da_inclinacao(
            _inclinado(0.0, 15.0), _DEITADO, self._a(sensibilidade=12)
        )
        assert forte[0] > leve[0] > 0

    def test_o_neutro_e_como_ela_segura(self) -> None:
        """Quem segura a 30 graus não anda: o neutro é o ângulo da mão dela."""
        mao = _inclinado(30.0)
        assert rot.deflexao_da_inclinacao(mao, mao, self._a()) == (0, 0)

    def test_o_inverter_vale(self) -> None:
        dh, _ = rot.deflexao_da_inclinacao(
            _inclinado(0.0, 20.0), _DEITADO, self._a(inverter_horizontal=True)
        )
        assert dh < 0

    def test_sem_gravidade_nao_ha_angulo(self) -> None:
        assert rot.deflexao_da_inclinacao((0.0, 0.0, 0.0), _DEITADO, self._a()) == (0, 0)

    def test_o_arranjo_sem_inclinacao_nao_move(self) -> None:
        assert rot.deflexao_da_inclinacao(
            _inclinado(40.0), _DEITADO, rot.ArranjoDeMovimento()
        ) == (0, 0)


class TestONeutroEODedo:
    """As duas memórias por peça, no `store`, e o silêncio que recomeça.

    MORDIDA: faça `neutro_da_inclinacao` guardar para sempre o primeiro
    retrato (sem o silêncio) e `test_o_silencio_recentra` reprova.
    """

    def test_o_silencio_recentra(self) -> None:
        store = SimpleNamespace()
        assert rot.neutro_da_inclinacao(store, _P2, _DEITADO, 10.0) == _DEITADO
        mao = _inclinado(30.0)
        assert rot.neutro_da_inclinacao(store, _P2, mao, 10.1) == _DEITADO
        assert rot.neutro_da_inclinacao(store, _P2, mao, 20.0) == mao, (
            "depois de um silêncio o neutro seguiu o de antes — o jogo que abriu "
            "com o controle na mesa andaria para sempre"
        )

    def test_cada_peca_tem_o_seu(self) -> None:
        store = SimpleNamespace()
        rot.neutro_da_inclinacao(store, _P2, _DEITADO, 1.0)
        assert rot.neutro_da_inclinacao(store, _P3, _inclinado(30.0), 1.0) == _inclinado(30.0)

    def test_o_dedo_so_ancora_na_chegada(self) -> None:
        store = SimpleNamespace()
        assert rot.delta_do_toque(store, _P2, [(5, 100, 100)], 1.0) == (0, 0)
        assert rot.delta_do_toque(store, _P2, [(5, 130, 90)], 1.01) == (30, -10)

    def test_o_dedo_que_troca_nao_salta(self) -> None:
        store = SimpleNamespace()
        rot.delta_do_toque(store, _P2, [(5, 100, 100)], 1.0)
        assert rot.delta_do_toque(store, _P2, [(6, 1800, 900)], 1.01) == (0, 0)

    def test_o_segundo_dedo_nao_rouba_o_cursor(self) -> None:
        store = SimpleNamespace()
        rot.delta_do_toque(store, _P2, [(5, 100, 100)], 1.0)
        assert rot.delta_do_toque(store, _P2, [(9, 1800, 900), (5, 110, 100)], 1.01) == (10, 0)

    def test_levantar_zera(self) -> None:
        store = SimpleNamespace()
        rot.delta_do_toque(store, _P2, [(5, 100, 100)], 1.0)
        assert rot.delta_do_toque(store, _P2, [], 1.01) == (0, 0)
        assert rot.delta_do_toque(store, _P2, [(5, 900, 900)], 1.02) == (0, 0)

    def test_o_pixel_do_toque_e_o_da_navegacao(self) -> None:
        from hefesto_dualsense4unix.integrations.uinput_mouse import TOUCHPAD_SENSITIVITY

        assert rot.PIXELS_POR_UNIDADE_DO_TOQUE == TOUCHPAD_SENSITIVITY
        arranjo = rot.ArranjoDeMovimento(toque=rot.TOQUE_CURSOR, sensibilidade=12)
        assert rot.pixels_do_toque(100, 0, arranjo) == (100 * TOUCHPAD_SENSITIVITY * 2, 0.0)


class TestORoteador:
    """A peça que só toca ou só inclina entra no tique; a Mira segue sendo o giro.

    MORDIDA: devolva o `ativo()` ao `valor.ligado` e `test_so_o_toque_entra_no_tique`
    reprova — a peça do toque ficaria fora dos dois laços.
    """

    def test_so_o_toque_entra_no_tique(self) -> None:
        store = SimpleNamespace()
        so_toque = rot.montar(ProfileMovimentoConfig(toque="zonas"))
        rot.definir_ativo(store, so_toque)
        assert rot.ativo(store) is so_toque
        assert not so_toque.ligado, "a Mira acendeu com o toque"

    def test_a_peca_que_so_inclina_entra_pela_peca(self) -> None:
        store = SimpleNamespace()
        rot.definir_ativo(store, None)
        rot.definir_por_peca(
            store, {_P3: rot.montar(ProfileMovimentoConfig(acelerometro="analogico_esquerdo"))}
        )
        mesa = rot.ativo(store)
        assert mesa is rot.SO_NAS_PECAS
        assert rot.da_peca(store, _P3, mesa) is not None
        assert rot.da_peca(store, _P2, mesa) is None

    def test_o_montar_recusa_o_que_nao_sabe(self) -> None:
        with pytest.raises(rot.ArranjoRecusadoError):
            rot.montar(SimpleNamespace(toque="gestos"))
        with pytest.raises(rot.ArranjoRecusadoError):
            rot.montar(SimpleNamespace(acelerometro="mouse"))


class TestOReportDoUhid:
    """No modo DualSense o dedo roteado sai da janela: o mesmo toque não chega duas vezes.

    MORDIDA: tire o `toque` do `REGISTRO.filtrar` e `test_o_dedo_roteado_sai` reprova.
    """

    def _janela(self) -> bytes:
        janela = bytearray(range(1, TAMANHO_DA_JANELA + 1))
        for contato in CONTATOS_DO_TOQUE:
            janela[contato] = 0x05  # dedo 5, APOIADO (bit 7 apagado)
        return bytes(janela)

    def test_o_dedo_roteado_sai(self) -> None:
        store = SimpleNamespace()
        rot.definir_ativo(store, rot.montar(ProfileMovimentoConfig(toque="zonas")))
        rot.definir_por_peca(store, {})
        rot.sincronizar_o_filtro(store)
        janela = self._janela()
        fora = REGISTRO.filtrar(_P2, janela)
        for contato in CONTATOS_DO_TOQUE:
            assert fora[contato] & TOQUE_INATIVO, "o dedo roteado seguiu chegando ao jogo"
            assert fora[contato] & 0x7F == 0x05, "o id do dedo foi apagado"
        assert fora[:12] == janela[:12], "o giro e o acelerômetro foram mexidos"

    def test_sem_rota_a_janela_e_a_mesma(self) -> None:
        store = SimpleNamespace()
        rot.definir_ativo(
            store, rot.montar(ProfileMovimentoConfig(acelerometro="analogico_esquerdo")))
        rot.definir_por_peca(store, {})
        rot.sincronizar_o_filtro(store)
        janela = self._janela()
        assert REGISTRO.filtrar(_P2, janela) is janela


# ===========================================================================
# 3 — o hub: o acelerômetro, o dedo e o nó grabado
# ===========================================================================


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _LeitorDeMovimento:
    """Do tamanho do `MotionSensorReader` para o que o hub pergunta."""

    def __init__(self, acel: tuple[float, float, float] = _DEITADO) -> None:
        self.acel = acel

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(x=0.0, y=0.0, z=0.0)

    def consume_angulo(self) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    def accel_snapshot(self) -> Any:
        return SimpleNamespace(x=self.acel[0], y=self.acel[1], z=self.acel[2])


class _LeitorDoToque:
    """Do tamanho do `TouchpadReader` observador, com a máquina de grab."""

    def __init__(self) -> None:
        self.estado = _toque()
        self.clique = False
        self.grab_state = "off"
        self.grabs: list[bool] = []

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def touch_state(self) -> TouchState:
        return self.estado

    def regions_pressed(self) -> frozenset[str]:
        return frozenset({"touchpad_middle_press"}) if self.clique else frozenset()

    def set_grab(self, querido: bool) -> bool:
        self.grabs.append(querido)
        self.grab_state = "held" if querido else "off"
        return True


def _hub(
    movimento: dict[str, _LeitorDeMovimento],
    toques: dict[str, _LeitorDoToque],
    relogio: _Relogio | None = None,
) -> SensorHub:
    hub = SensorHub(
        motion_factory=lambda uniq, node: movimento[uniq],
        touch_factory=lambda uniq, node: toques[uniq],
        gamepad_factory=lambda uniq, node: _LeitorDeMovimento(),
        descobrir_motion=lambda: {u: Path(f"/dev/input/event-m-{u}") for u in movimento},
        descobrir_touch=lambda: {u: Path(f"/dev/input/event-t-{u}") for u in toques},
        descobrir_gamepad=dict,
        relogio=relogio,
        auto_manutencao=False,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)
    return hub


class TestOHub:
    """MORDIDA: tire a chamada de `_reconciliar_grabs_do_toque` do `reconciliar`
    e `test_o_no_do_toque_fica_com_o_hefesto_enquanto_a_rota_anda` reprova — o dedo
    que aperta a zona moveria também o ponteiro do computador."""

    def test_o_no_do_toque_fica_com_o_hefesto_enquanto_a_rota_anda(self) -> None:
        relogio = _Relogio()
        leitor = _LeitorDoToque()
        hub = _hub({}, {_P2: leitor}, relogio)
        assert hub.toque_da_peca(_P2) is None, "a primeira pergunta abre o leitor"
        hub.reconciliar()
        leitor.estado = _toque(_DEDO_NO_CIMA)
        leitor.clique = True
        estado, clicado = hub.toque_da_peca(_P2)  # type: ignore[misc]
        assert estado.touching and clicado
        hub.reconciliar()
        assert leitor.grab_state == "held", "o nó do toque ficou com o computador"
        relogio.agora += 3.0
        hub.reconciliar()
        assert leitor.grab_state == "off", "a rota parou e o nó não voltou ao computador"

    def test_o_painel_que_so_olha_nao_graba(self) -> None:
        leitor = _LeitorDoToque()
        hub = _hub({}, {_P2: leitor})
        hub.leitura(_P2)
        hub.reconciliar()
        hub.leitura(_P2)
        hub.reconciliar()
        assert leitor.grabs == [], "a aba Controles grabou o touchpad só por olhar"

    def test_o_acelerometro_da_peca(self) -> None:
        hub = _hub({_P3: _LeitorDeMovimento(_inclinado(20.0))}, {})
        assert hub.aceleracao_do_movimento(_P3) is None
        hub.reconciliar()
        acel = hub.aceleracao_do_movimento(_P3)
        assert acel is not None and acel[2] > 0.3


# ===========================================================================
# 4 — o P1 no modo Xbox, no daemon de verdade, com o Xbox 360 da fábrica
# ===========================================================================


class _AbsInfo(NamedTuple):
    value: int
    min: int
    max: int
    fuzz: int
    flat: int
    resolution: int


class _EC:
    """Os códigos reais de `linux/input-event-codes.h` do Xbox 360."""

    EV_SYN, EV_KEY, EV_ABS, EV_FF, EV_UINPUT = 0x00, 0x01, 0x03, 0x15, 0x0101
    UI_FF_UPLOAD, UI_FF_ERASE = 1, 2
    ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ = 0x00, 0x01, 0x02, 0x03, 0x04, 0x05
    ABS_HAT0X, ABS_HAT0Y = 0x10, 0x11
    BTN_A = BTN_SOUTH = 0x130
    BTN_B = BTN_EAST = 0x131
    BTN_X = BTN_NORTH = 0x133
    BTN_Y = BTN_WEST = 0x134
    BTN_Z = 0x135
    BTN_TL, BTN_TR, BTN_TL2, BTN_TR2 = 0x136, 0x137, 0x138, 0x139
    BTN_SELECT, BTN_START, BTN_MODE = 0x13A, 0x13B, 0x13C
    BTN_THUMBL, BTN_THUMBR = 0x13D, 0x13E
    FF_RUMBLE, FF_PERIODIC, FF_SQUARE, FF_TRIANGLE, FF_SINE, FF_GAIN = (
        0x50, 0x51, 0x58, 0x59, 0x5A, 0x60)


class _NoGravado:
    """O `evdev.UInput` sem kernel: guarda o que o kernel registraria e receberia."""

    criados: ClassVar[list[_NoGravado]] = []

    def __init__(self, events: dict[int, list[Any]], **kwargs: Any) -> None:
        self.events = events
        self.kwargs = kwargs
        self.fd = -1
        self.escritas: list[tuple[int, int, int]] = []
        type(self).criados.append(self)

    def write(self, etype: int, code: int, value: int) -> None:
        self.escritas.append((etype, code, value))

    def syn(self) -> None:
        return

    def close(self) -> None:
        return

    def read_one(self) -> None:
        return None

    def ultimo(self, etype: int, code: int) -> int | None:
        valores = [v for t, c, v in self.escritas if t == etype and c == code]
        return valores[-1] if valores else None


@pytest.fixture
def _evdev_que_grava(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
        _zerar_registro_de_mascaras,
    )

    _zerar_registro_de_mascaras()
    _NoGravado.criados = []
    mod = types.ModuleType("evdev")
    mod.UInput = _NoGravado  # type: ignore[attr-defined]
    mod.AbsInfo = _AbsInfo  # type: ignore[attr-defined]
    mod.ecodes = _EC  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "evdev", mod)
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: False)


def _mesa_de_verdade(tmp_path: Path, hub: SensorHub, perfil: Profile) -> tuple[Daemon, IpcServer]:
    """O `Daemon` e o `IpcServer` do produto, com o hub injetado no servidor."""
    controle = FakeController(transport="bt")
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle,
        store=daemon.store,
        profile_manager=gerente,
        socket_path=tmp_path / "toque.sock",
        daemon=daemon,
    )
    servidor._sensor_hub = hub
    daemon._ipc_server = servidor
    gerente.apply_movimento(perfil)
    return daemon, servidor


def _estado() -> ControllerState:
    return ControllerState(
        battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="bt"  # type: ignore[arg-type]
    )


class _CursorDeMentira:
    def __init__(self) -> None:
        self.movimentos: list[tuple[float, float]] = []
        self.cliques: list[tuple[str, bool]] = []
        self.parado = False

    def mover(self, px: float, py: float) -> None:
        self.movimentos.append((px, py))

    def clicar(self, peca: str, apertado: bool) -> None:
        self.cliques.append((peca, apertado))

    def stop(self) -> None:
        self.parado = True


class TestOP1NoModoXbox:
    """O P1 no modo Xbox: o pad é o Xbox 360 da fábrica, e o jogo recebe as rotas.

    MORDIDA: tire a chamada de `aplicar_o_toque` do `dispatch_gamepad` e
    `test_a_zona_chega_ao_xbox_360` reprova; tire o `_a_inclinacao` de
    `aplicar_o_movimento` e `test_a_inclinacao_chega_ao_xbox_360` reprova.
    """

    def _tiques(
        self, monkeypatch: pytest.MonkeyPatch, daemon: Daemon, hub: SensorHub
    ) -> _NoGravado:
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
        monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
        pad = make_virtual_pad("dualsense", identity=_P1, caminho=CAMINHO_XBOX)
        assert pad is not None
        no = pad._device  # type: ignore[attr-defined]
        assert isinstance(no, _NoGravado)
        assert (int(no.kwargs["vendor"]), int(no.kwargs["product"])) == (
            XBOX360_VENDOR, XBOX360_PRODUCT), "premissa: o modo Xbox veste o Xbox 360"
        daemon._gamepad_device = pad
        gp.dispatch_gamepad(daemon, _estado(), frozenset())
        hub.reconciliar()
        gp.dispatch_gamepad(daemon, _estado(), frozenset())
        return no

    def test_a_zona_chega_ao_xbox_360(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _evdev_que_grava: None
    ) -> None:
        toque = _LeitorDoToque()
        toque.estado = _toque(_DEDO_NO_CIMA, _DEDO_NO_L2)
        hub = _hub({}, {_P1: toque})
        perfil = Profile(
            name="Zonas", match=MatchAny(type="any"),
            movimento=ProfileMovimentoConfig(toque="zonas"),
        )
        daemon, _ = _mesa_de_verdade(tmp_path, hub, perfil)
        no = self._tiques(monkeypatch, daemon, hub)
        try:
            assert no.ultimo(_EC.EV_ABS, _EC.ABS_HAT0Y) == -1, (
                "o dedo na zona de cima não apertou o direcional do Xbox 360")
            assert no.ultimo(_EC.EV_ABS, _EC.ABS_Z) == 255, (
                "o dedo na zona do L2 não levou o gatilho do Xbox 360 ao fundo")
        finally:
            daemon._gamepad_device.stop()

    def test_a_inclinacao_chega_ao_xbox_360(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _evdev_que_grava: None
    ) -> None:
        movimento = _LeitorDeMovimento(_DEITADO)
        hub = _hub({_P1: movimento}, {})
        perfil = Profile(
            name="Inclinar", match=MatchAny(type="any"),
            movimento=ProfileMovimentoConfig(acelerometro="analogico_esquerdo"),
        )
        daemon, _ = _mesa_de_verdade(tmp_path, hub, perfil)
        no = self._tiques(monkeypatch, daemon, hub)
        try:
            assert no.ultimo(_EC.EV_ABS, _EC.ABS_X) in (None, 128), (
                "o controle na mesa já andava: o neutro não é o ângulo de partida")
            movimento.acel = _inclinado(0.0, 25.0)
            gp.dispatch_gamepad(daemon, _estado(), frozenset())
            assert (no.ultimo(_EC.EV_ABS, _EC.ABS_X) or 128) > 128, (
                "inclinar o controle para a direita não moveu o analógico esquerdo")
        finally:
            daemon._gamepad_device.stop()

    def test_o_cursor_do_toque_nasce_e_sai_com_o_controle_virtual(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _evdev_que_grava: None
    ) -> None:
        """O `Daemon` real cria o cursor na primeira vez; ele sai com o pad.

        MORDIDA: tire o `soltar_o_cursor_do_toque` do `stop_gamepad_emulation`
        e o nó do cursor fica de pé sem controle virtual.
        """
        criados: list[_CursorDeMentira] = []

        def _fabrica() -> _CursorDeMentira:
            cursor = _CursorDeMentira()
            cursor.start = lambda: True  # type: ignore[attr-defined]
            criados.append(cursor)
            return cursor

        from hefesto_dualsense4unix.integrations import uinput_mouse

        monkeypatch.setattr(uinput_mouse, "CursorDoToque", _fabrica)
        toque = _LeitorDoToque()
        hub = _hub({}, {_P1: toque})
        perfil = Profile(
            name="Cursor", match=MatchAny(type="any"),
            movimento=ProfileMovimentoConfig(toque="cursor", sensibilidade=6),
        )
        daemon, _ = _mesa_de_verdade(tmp_path, hub, perfil)
        self._tiques(monkeypatch, daemon, hub)
        toque.estado = _toque((500, 500))
        gp.dispatch_gamepad(daemon, _estado(), frozenset())
        toque.estado = _toque((600, 500))
        toque.clique = True
        gp.dispatch_gamepad(daemon, _estado(), frozenset())
        assert len(criados) == 1, "o cursor do toque nasceu mais de uma vez"
        cursor = criados[0]
        assert cursor.movimentos and cursor.movimentos[-1][0] == pytest.approx(
            100 * rot.PIXELS_POR_UNIDADE_DO_TOQUE)
        assert (_P1, True) in cursor.cliques
        gp.stop_gamepad_emulation(daemon, persist=False)
        assert cursor.parado, "o cursor do toque ficou de pé sem o controle virtual"
        assert getattr(daemon, "_cursor_do_toque", None) is None


# ===========================================================================
# 5 — os jogadores 2 a 4
# ===========================================================================


class _VpadDoJogador:
    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


class _LeitorDoJogador:
    def __init__(self) -> None:
        self.grab_state = "held"

    def snapshot(self) -> Any:
        return SimpleNamespace(
            buttons_pressed=frozenset(), l2_raw=0, r2_raw=0, lx=128, ly=128, rx=128, ry=128
        )


def _mesa_dos_secundarios(
    monkeypatch: pytest.MonkeyPatch,
    arranjo: rot.ArranjoDeMovimento,
    hub: Any,
) -> dict[str, _VpadDoJogador]:
    from hefesto_dualsense4unix.daemon.subsystems import coop as co
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer

    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    rot.definir_ativo(store, arranjo)
    daemon = SimpleNamespace(
        _ipc_server=SimpleNamespace(_garantir_sensor_hub=lambda: hub), store=store,
        _mouse_device=None,
    )
    daemon._garantir_sensor_hub = MethodType(Daemon._garantir_sensor_hub, daemon)
    gerente = CoopManager.__new__(CoopManager)
    gerente._daemon = daemon  # type: ignore[attr-defined]
    gerente._players = {}  # type: ignore[attr-defined]
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)
    vpads: dict[str, _VpadDoJogador] = {}
    for n, uniq in enumerate((_P2, _P3, _P4), start=2):
        vpad = _VpadDoJogador()
        vpads[uniq] = vpad
        gerente._players[uniq] = _SecondaryPlayer(  # type: ignore[attr-defined]
            identity=uniq, evdev_path=f"/dev/input/event{n}", reader=_LeitorDoJogador(),
            player_index=n, vpad=vpad,
        )
    gerente.forward_all()
    return vpads


class TestOsJogadores2a4:
    """*«cara nenhuma solução pode ser feita só pro p1»* — vale aqui também.

    MORDIDA: tire a chamada de `aplicar_o_toque` do `coop.forward_all` e
    `test_cada_jogador_aperta_a_propria_zona` reprova.
    """

    def test_cada_jogador_aperta_a_propria_zona(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dedos = {_P2: _toque(_DEDO_NO_CIMA), _P3: _toque(), _P4: _toque(_DEDO_NO_L1)}

        class _HubDosToques:
            def toque_da_peca(self, uniq: str) -> Any:
                return dedos[uniq], False

        vpads = _mesa_dos_secundarios(
            monkeypatch, rot.montar(ProfileMovimentoConfig(toque="zonas")), _HubDosToques()
        )
        assert "dpad_up" in vpads[_P2].buttons[0]
        assert vpads[_P3].buttons[0] == frozenset(), "o P3 não tocou e apertou botão"
        assert "l1" in vpads[_P4].buttons[0]

    def test_cada_jogador_inclina_o_proprio_analogico(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        acel = {_P2: _inclinado(0.0, 25.0), _P3: _inclinado(0.0, 25.0), _P4: _DEITADO}
        monkeypatch.setattr(
            REGISTRO, "estado",
            lambda uniq: SimpleNamespace(giroscopio=True, acelerometro=uniq != _P3),
        )

        class _HubDaInclinacao:
            def aceleracao_do_movimento(self, uniq: str) -> Any:
                return acel[uniq]

        arranjo = rot.montar(ProfileMovimentoConfig(acelerometro="analogico_esquerdo"))
        # O neutro de partida é a mesa: cada peça começa deitada.
        store_de_partida: dict[str, Any] = {}
        monkeypatch.setattr(
            rot, "neutro_da_inclinacao",
            lambda dono, uniq, a, agora: store_de_partida.setdefault(uniq, _DEITADO),
        )
        vpads = _mesa_dos_secundarios(monkeypatch, arranjo, _HubDaInclinacao())
        assert vpads[_P2].analog[0]["lx"] > 128, "o P2 inclinou e não andou"
        assert vpads[_P3].analog[0]["lx"] == 128, (
            "o P3 tinha o acelerômetro DESLIGADO por ela e andou assim mesmo")
        assert vpads[_P4].analog[0]["lx"] == 128, "o P4 estava na mesa e andou"


# ===========================================================================
# 6 — o L2 da zona liga o «Só enquanto eu segurar» da Mira
# ===========================================================================


def test_o_l2_da_zona_liga_a_mira_de_quem_nao_alcanca_o_l2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O toque entra na MÃO antes da Mira: a zona do L2 é o L2 do gatilho dela.

    MORDIDA: passe ao `aplicar_o_movimento` do `dispatch_gamepad` o
    `buttons_pressed` original, em vez dos botões com as zonas, e este teste
    reprova — quem não alcança o L2 não teria como mirar «só enquanto segura».
    """

    class _Hub:
        def velocidade_do_movimento(self, uniq: str) -> Any:
            return (0.0, 150.0, 0.0)

        def angulo_do_movimento(self, uniq: str) -> Any:
            return (0.0, 0.0, 0.0)

        def toque_da_peca(self, uniq: str) -> Any:
            return _toque(_DEDO_NO_L2), False

    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(gp, "primary_identity", lambda d: _P1)
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    rot.definir_ativo(
        store,
        rot.montar(ProfileMovimentoConfig(
            destino="analogico_direito", gatilho="l2", toque="zonas", sensibilidade=12)),
    )
    vpad = _VpadDoJogador()
    hub = _Hub()
    daemon = SimpleNamespace(
        _ipc_server=SimpleNamespace(_garantir_sensor_hub=lambda: hub), store=store,
        _gamepad_device=vpad, _mouse_device=None,
    )
    daemon._garantir_sensor_hub = MethodType(Daemon._garantir_sensor_hub, daemon)
    gp.dispatch_gamepad(daemon, SimpleNamespace(
        raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=0, r2_raw=0), frozenset())
    assert vpad.analog[0]["l2"] == 255
    assert vpad.analog[0]["rx"] != 128, "a zona do L2 não ligou a Mira do gatilho L2"


# ===========================================================================
# 7 — a Navegação fica com o computador
# ===========================================================================


def test_na_navegacao_o_toque_e_o_do_computador(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem controle virtual, o dedo segue sendo o ponteiro e a inclinação não move nada.

    Decidido pelo padrão dela (o que custa menos a quem joga): o arranjo é do
    JOGO. MORDIDA: tire o `not na_navegacao` da inclinação em
    `aplicar_o_movimento` e este teste reprova — o controle torto na mão
    moveria o cursor do computador.
    """
    from hefesto_dualsense4unix.daemon.subsystems import mouse as mo

    perguntas: list[str] = []

    class _Hub:
        def velocidade_do_movimento(self, uniq: str) -> Any:
            return (0.0, 0.0, 0.0)

        def angulo_do_movimento(self, uniq: str) -> Any:
            return (0.0, 0.0, 0.0)

        def aceleracao_do_movimento(self, uniq: str) -> Any:
            perguntas.append("inclinacao")
            return _inclinado(0.0, 40.0)

        def toque_da_peca(self, uniq: str) -> Any:
            perguntas.append("toque")
            return _toque(_DEDO_NO_CIMA), False

    monkeypatch.setattr(gp, "primary_identity", lambda d: _P1)
    store = SimpleNamespace()
    rot.definir_ativo(store, rot.montar(ProfileMovimentoConfig(
        toque="zonas", acelerometro="analogico_esquerdo")))
    hub = _Hub()
    daemon = SimpleNamespace(
        _ipc_server=SimpleNamespace(_garantir_sensor_hub=lambda: hub), store=store,
        _mouse_device=SimpleNamespace(emit_gyro_move=lambda *a: None),
        identity_registry=None,
    )
    daemon._garantir_sensor_hub = MethodType(Daemon._garantir_sensor_hub, daemon)
    mo.mover_o_cursor_pelo_giro(daemon, frozenset())
    assert perguntas == [], f"a Navegação perguntou pelo {perguntas}"


# ===========================================================================
# 8 — o IPC: o `mira.set` só ganha campos
# ===========================================================================


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from hefesto_dualsense4unix.profiles import loader as loader_module

    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


def _servidor(tmp_path: Path) -> IpcServer:
    from hefesto_dualsense4unix.profiles.loader import save_profile

    perfil = Profile(name="Bancada", match=MatchAny(type="any"))
    save_profile(perfil)
    _daemon, servidor = _mesa_de_verdade(tmp_path, _hub({}, {}), perfil)
    servidor.store.set_active_profile(perfil.name)
    return servidor


def _mira_set(servidor: IpcServer, **params: Any) -> dict[str, Any]:
    return asyncio.run(servidor._handlers["mira.set"](params))


class TestOIpc:
    """MORDIDA: tire o `"toque"` de `_CAMPOS_DA_MIRA` e `test_os_dois_chips_gravam_na_peca`
    reprova com a recusa do campo desconhecido."""

    def test_os_dois_chips_gravam_na_peca(self, perfis: Path, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.profiles.loader import load_profile

        servidor = _servidor(tmp_path)
        corpo = _mira_set(servidor, uniq=_P3, inclinacao=True)
        assert corpo["status"] == "ok" and corpo["inclinacao"] is True
        assert corpo["ligada"] is False, "a inclinação acendeu a Mira"
        corpo = _mira_set(servidor, uniq=_P3, toque="zonas")
        assert corpo["toque"] == "zonas"
        dele = load_profile("Bancada").controllers["aabbcc000003"].movimento
        assert dele is not None
        assert dele.model_fields_set == {"acelerometro", "toque"}, (
            "o chip gravou campos que ela não mexeu")
        assert dele.acelerometro == "analogico_esquerdo" and dele.toque == "zonas"
        entradas: list[dict[str, Any]] = [{"uniq": _P2}, {"uniq": _P3}]
        servidor._merge_mira(entradas)
        assert entradas[1]["mira"]["toque"] == "zonas"
        assert entradas[1]["mira"]["inclinacao"] is True
        assert entradas[1]["mira"]["ligada"] is False
        assert entradas[0]["mira"]["toque"] == "nenhum"
        assert REGISTRO.toque_roteado(_P3) and not REGISTRO.toque_roteado(_P2)

    def test_o_toque_desconhecido_e_recusado(self, perfis: Path, tmp_path: Path) -> None:
        servidor = _servidor(tmp_path)
        with pytest.raises(ValueError, match="toque"):
            _mira_set(servidor, uniq=_P3, toque="gestos")
        with pytest.raises(ValueError, match="inclinacao"):
            _mira_set(servidor, uniq=_P3, inclinacao="sim")

    def test_no_nativo_os_chips_nao_gravam(
        self, perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.profiles.loader import load_profile

        servidor = _servidor(tmp_path)
        monkeypatch.setattr(servidor.daemon, "is_native_mode", lambda: True)
        for pedido in ({"toque": "cursor"}, {"inclinacao": True}):
            corpo = _mira_set(servidor, uniq=_P3, **pedido)
            assert corpo["status"] == "nativo"
        assert not (load_profile("Bancada").controllers or {})


def test_um_perfil_com_o_toque_por_peca_chega_ao_tique() -> None:
    """O perfil do jogo diz o toque de UMA peça, e só ela o leva.

    É a resposta 2 dela: por perfil de jogo. O depósito é o do gerente, como
    está (`ProfileManager.apply_movimento`).
    """
    store = SimpleNamespace()
    gerente = ProfileManager.__new__(ProfileManager)
    gerente.store = store  # type: ignore[attr-defined]
    gerente.apply_movimento(Profile(
        name="Future Knight", match=MatchAny(type="any"),
        controllers={
            "aabbcc000002": ControllerOverrides(
                movimento=ProfileMovimentoConfig(toque="zonas")),
        },
    ))
    mesa = rot.ativo(store)
    assert mesa is rot.SO_NAS_PECAS
    assert rot.da_peca(store, _P2, mesa).toque == "zonas"  # type: ignore[union-attr]
    assert rot.da_peca(store, _P3, mesa) is None
    assert REGISTRO.toque_roteado(_P2) and not REGISTRO.toque_roteado(_P3)


# ===========================================================================
# 9 — o nó do cursor: o resto sub-pixel e o clique da mesa
# ===========================================================================


class _DispositivoDeMentira:
    """O `uinput.Device` sem kernel: guarda o que o nó emitiria."""

    def __init__(self, eventos: list[Any], name: str = "") -> None:
        self.eventos_declarados = eventos
        self.name = name
        self.emitidos: list[tuple[Any, int]] = []
        self.destruido = False

    def emit(self, evento: Any, valor: int, syn: bool = True) -> None:
        self.emitidos.append((evento, valor))

    def syn(self) -> None:
        return

    def destroy(self) -> None:
        self.destruido = True


@pytest.fixture
def _uinput_que_grava(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    mod = types.ModuleType("uinput")
    mod.REL_X, mod.REL_Y, mod.BTN_LEFT = "REL_X", "REL_Y", "BTN_LEFT"  # type: ignore[attr-defined]
    mod.Device = _DispositivoDeMentira  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uinput", mod)
    return mod


class TestOCursorDoToque:
    """MORDIDA: tire o resto sub-pixel de `CursorDoToque.mover` (trunque cada
    passo) e `test_o_dedo_devagar_ainda_anda` reprova — o dedo lento nunca
    moveria o cursor."""

    def test_o_dedo_devagar_ainda_anda(self, _uinput_que_grava: types.ModuleType) -> None:
        from hefesto_dualsense4unix.integrations.uinput_mouse import CursorDoToque

        cursor = CursorDoToque()
        assert cursor.start()
        for _ in range(5):
            cursor.mover(0.4, 0.0)
        assert [v for e, v in cursor._device.emitidos if e == "REL_X"] == [1, 1]

    def test_o_clique_e_da_mesa(self, _uinput_que_grava: types.ModuleType) -> None:
        from hefesto_dualsense4unix.integrations.uinput_mouse import CursorDoToque

        cursor = CursorDoToque()
        cursor.start()
        cursor.clicar(_P2, True)
        cursor.clicar(_P3, True)
        cursor.clicar(_P2, False)
        cliques = [v for e, v in cursor._device.emitidos if e == "BTN_LEFT"]
        assert cliques == [1], "o botão soltou com a outra peça ainda segurando"
        no = cursor._device
        cursor.stop()
        assert [v for e, v in no.emitidos if e == "BTN_LEFT"] == [1, 0]
        assert no.destruido, "o nó do cursor ficou de pé depois do stop"
