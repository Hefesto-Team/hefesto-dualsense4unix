"""O botão chega ao jogo como ele é (O-BOTAO-CHEGA-AO-JOGO-COMO-ELE-E-01, entrada 1).

Nasceu de um relatório do Forja que dizia «o mapa dos botões está trocado» e
que a medida de 01/10 derrubou: os bits que o Hefesto escreve são os que o
driver e o SDL leem. O que a medida achou no caminho é o que estas réguas
trancam:

- **a ida e volta pelo DRIVER** (réguas 1 a 3): o código evdev que o físico
  manda entra no `EvdevReader` de verdade, passa pelo caminho de verdade do P1
  (`gamepad.dispatch_gamepad`) e dos jogadores 2 a 4
  (`coop.CoopManager.forward_all`) até o pad virtual, e volta pelo decodificador
  que este arquivo monta LENDO o `hid-playstation.c` desta árvore. O lado
  esperado nunca importa uma tabela do Hefesto (a régua 3 confere pela árvore
  sintática);
- **o aperto que cabe entre dois tiques chega** (réguas 4, 5 e 8): medido com o
  leitor de verdade, um aperto de 10 ms sumia em 4 de 10 fases e um de 5 ms em 7
  de 10 (`o_aperto_entre_dois_tiques.py` do estudo de 01/10). O leitor conta as
  bordas, quem entrega ao jogo compara, e o pad `uhid` guarda o aperto até ele
  sair num report.

O QUE A MEDIDA DERRUBOU NA RÉGUA 2 DA SPRINT: ela dizia que, no `uinput`, «o
código escrito é o que o físico mandou». Não é, e não deve ser, na máscara
Xbox: o SDL lê o X da Xbox no `BTN_X` (o mesmo número do `BTN_NORTH`), e o
quadrado do físico chega como `BTN_WEST`. O lado esperado da régua 2 é o botão
que o JOGO lê, pela regra do SDL para o VID que o pad mostra
(`_esperado_codigo_que_o_jogo_le`). E pela mesma regra a máscara DualSense do
`uinput` (VID da Sony) troca o quadrado e o triângulo: o defeito fica escrito
no xfail estrito da régua 2b, fora da posse desta sprint
(`uinput_gamepad.py` é `nao_toca`).

A MEDIDA ANTES DA CURA, com este arquivo sobre o `src/` do `c3db67ca6`: 46
reprovavam (as 40 da régua 4, as 4 do grace da régua 8 e as 2 da contagem), e
as réguas 1, 2, 3 e 5 já passavam: o mapa nunca esteve trocado.

AS MORDIDAS, provadas em 02/10/2026 (aplicadas, rodadas, devolvidas, md5
conferido): ver a docstring de cada régua.
"""

from __future__ import annotations

import ast
import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, fields
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core.evdev_reader import EvdevReader, EvdevSnapshot
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.poll import evdev_buttons_once
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from tests.unit import test_o_report_de_entrada_bate_com_o_driver as o_report

# ─────────────────────────────────────────────────────────────────────────────
# O LADO ESPERADO: lido do driver, nunca de uma tabela do Hefesto
# ─────────────────────────────────────────────────────────────────────────────
#
# Toda função do lado esperado começa com `_esperado_`, e a régua 3 confere pela
# árvore sintática deste arquivo que nenhuma delas cita um nome de tabela do
# produto. O leitor dos `#define` e do struct já tem dono e é importado:
# `o_report._mascaras_de_botao` e `o_report._campos_do_struct`, que leem o
# `DRIVER` do módulo deles (a régua 3 o aponta para uma cópia).


@dataclass(frozen=True)
class _EsperadoDriver:
    """O que o `dualsense_parse_report` faz com um report, lido do fonte."""

    #: (BTN_*, índice em `buttons[]`, máscara), na ordem do fonte.
    pares: tuple[tuple[str, int, int], ...]
    #: O byte de `buttons[]` e a máscara do hat.
    hat_byte: int
    hat_mascara: int
    #: `ps_gamepad_hat_mapping`: índice -> (x, y).
    hat_vetores: tuple[tuple[int, int], ...]
    #: O índice que o driver usa quando o valor passa da tabela (o centro).
    hat_centro: int
    #: O offset de `buttons` dentro do `struct dualsense_input_report`.
    offset_dos_botoes: int
    #: Onde o struct começa no report do cabo (`&data[N]`) e no do rádio.
    inicio_no_cabo: int
    inicio_no_radio: int
    #: Quantas vezes o corpo da leitura atribui `ds_report` (uma por transporte).
    atribuicoes: int


def _esperado_corpo_da_leitura(fonte: str) -> str:
    """O corpo do `dualsense_parse_report`, a leitura única do cabo e do rádio."""
    inicio = fonte.index("static int dualsense_parse_report")
    corpo = fonte[inicio:]
    return corpo[: corpo.index("\n}\n")]


def _esperado_driver_lido() -> _EsperadoDriver:
    fonte = o_report.DRIVER.read_text(encoding="utf-8")
    mascaras = o_report._mascaras_de_botao()
    corpo = _esperado_corpo_da_leitura(fonte)
    pares = tuple(
        (btn, int(byte), mascaras[nome])
        for btn, byte, nome in re.findall(
            r"input_report_key\(ds->gamepad,\s*(BTN_\w+),\s*"
            r"ds_report->buttons\[(\d)\]\s*&\s*(DS_BUTTONS\d_\w+)\)",
            corpo,
        )
    )
    hat = re.search(r"value = ds_report->buttons\[(\d)\] & (DS_BUTTONS\d_HAT_SWITCH);", corpo)
    centro = re.search(r"value = (\d+); /\* center \*/", corpo)
    tabela = re.search(r"ps_gamepad_hat_mapping\[\] = \{(.*?)\};", fonte, re.S)
    cabo = re.search(
        r"report->id == DS_INPUT_REPORT_USB.*?ds_report = "
        r"\(struct dualsense_input_report \*\)&data\[(\d)\];",
        corpo,
        re.S,
    )
    radio = re.search(
        r"report->id == DS_INPUT_REPORT_BT.*?ds_report = "
        r"\(struct dualsense_input_report \*\)&data\[(\d)\];",
        corpo,
        re.S,
    )
    assert hat and centro and tabela and cabo and radio, "a leitura do driver mudou de forma"
    vetores = tuple(
        (int(x), int(y)) for x, y in re.findall(r"\{(-?\d+),\s*(-?\d+)\}", tabela.group(1))
    )
    return _EsperadoDriver(
        pares=pares,
        hat_byte=int(hat.group(1)),
        hat_mascara=mascaras[hat.group(2)],
        hat_vetores=vetores,
        hat_centro=int(centro.group(1)),
        offset_dos_botoes=dict(o_report._campos_do_struct())["buttons"],
        inicio_no_cabo=int(cabo.group(1)),
        inicio_no_radio=int(radio.group(1)),
        atribuicoes=len(re.findall(r"\bds_report = ", corpo)),
    )


def _esperado_le_o_report(
    driver: _EsperadoDriver, report: bytes
) -> tuple[frozenset[str], tuple[int, int]]:
    """O que o `hid-playstation` publicaria no nó do pad: os BTN_* e o hat.

    O pad `uhid` escreve o report do CABO (`0x01`), e o struct começa em
    `data[inicio_no_cabo]`.
    """
    corpo = report[driver.inicio_no_cabo :]
    botoes = corpo[driver.offset_dos_botoes : driver.offset_dos_botoes + 4]
    apertados = frozenset(btn for btn, byte, mascara in driver.pares if botoes[byte] & mascara)
    valor = botoes[driver.hat_byte] & driver.hat_mascara
    if valor >= len(driver.hat_vetores):
        valor = driver.hat_centro
    return apertados, driver.hat_vetores[valor]


#: O VID da Sony e o da Nintendo, como o pad virtual os mostra ao jogo.
_VID_SONY = 0x054C
_VID_NINTENDO = 0x057E


def _esperado_codigo_que_o_jogo_le(vid: int, codigo_do_fisico: int) -> int:
    """O código que, num pad sem hidraw de VID `vid`, o jogo lê como este botão.

    Lido no fonte do SDL 3.4.14 (a cópia do Forja,
    `src/joystick/linux/SDL_sysjoystick.c:2377-2408`): com o VID da Sony, o X
    do jogo é o `BTN_WEST` e o Y é o `BTN_NORTH` (a POSIÇÃO, como o físico
    manda); com outro VID, o X é o `BTN_X` e o Y é o `BTN_Y` (a convenção do
    `xpad`: o X da Xbox fica à esquerda e se chama `BTN_X`, que tem o número do
    `BTN_NORTH`). O Nintendo segue a posição porque a casa crava
    `SDL_GAMECONTROLLER_USE_BUTTON_LABELS=0` em todo jogo (`launch_env`, medido
    em 07/09/2026). Os outros botões têm o mesmo código nas duas regras.
    """
    if vid in (_VID_SONY, _VID_NINTENDO):
        return codigo_do_fisico
    xpad = {ecodes.BTN_WEST: ecodes.BTN_X, ecodes.BTN_NORTH: ecodes.BTN_Y}
    return xpad.get(codigo_do_fisico, codigo_do_fisico)


#: O gatilho do físico manda o eixo junto com o bit: o `z`/`rz` do report vira
#: `ABS_Z`/`ABS_RZ` (`input_report_abs` do mesmo `dualsense_parse_report`).
_EIXO_DO_GATILHO = {"BTN_TL2": "ABS_Z", "BTN_TR2": "ABS_RZ"}


@dataclass(frozen=True)
class _Caso:
    """Um botão do físico: os eventos que ele manda e o que o pad tem de dizer."""

    rotulo: str
    aperta: tuple[tuple[int, int, int], ...]
    solta: tuple[tuple[int, int, int], ...]
    #: O BTN_* que o físico mandou (vazio no hat).
    codigo: int | None
    #: O vetor do hat (o centro nos botões).
    vetor: tuple[int, int]
    #: O eixo do gatilho, quando é L2 ou R2.
    eixo: int | None = None


def _esperado_casos(driver: _EsperadoDriver) -> list[_Caso]:
    """Os 13 pares do driver (o PS entre eles) e as 8 direções do hat."""
    centro = driver.hat_vetores[driver.hat_centro]
    casos = []
    for btn, _byte, _mascara in driver.pares:
        codigo = getattr(ecodes, btn)
        aperta = [(ecodes.EV_KEY, codigo, 1)]
        solta = [(ecodes.EV_KEY, codigo, 0)]
        eixo = None
        if btn in _EIXO_DO_GATILHO:
            eixo = getattr(ecodes, _EIXO_DO_GATILHO[btn])
            aperta.insert(0, (ecodes.EV_ABS, eixo, 255))
            solta.append((ecodes.EV_ABS, eixo, 0))
        casos.append(_Caso(btn, tuple(aperta), tuple(solta), codigo, centro, eixo))
    for vetor in driver.hat_vetores:
        if vetor == centro:
            continue
        x, y = vetor
        aperta = ((ecodes.EV_ABS, ecodes.ABS_HAT0X, x), (ecodes.EV_ABS, ecodes.ABS_HAT0Y, y))
        solta = ((ecodes.EV_ABS, ecodes.ABS_HAT0X, 0), (ecodes.EV_ABS, ecodes.ABS_HAT0Y, 0))
        casos.append(_Caso(f"hat{vetor}", aperta, solta, None, vetor))
    return casos


# ─────────────────────────────────────────────────────────────────────────────
# A bancada: os quatro jogadores pelo caminho de verdade
# ─────────────────────────────────────────────────────────────────────────────

#: Os jogadores 2 a 4, na faixa forjada da casa.
_UNIQ = {2: "aa:bb:cc:00:00:02", 3: "aa:bb:cc:00:00:03", 4: "aa:bb:cc:00:00:04"}

_SYN = (-1, -1, -1)


@dataclass
class _Evento:
    type: int
    code: int
    value: int


class _NoDoUinput:
    """O nó `uinput` de mentira: guarda cada `write`, e o `syn` como marca."""

    def __init__(self) -> None:
        self.escritas: list[tuple[int, int, int]] = []

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        self.escritas.append((tipo, codigo, valor))

    def syn(self) -> None:
        self.escritas.append(_SYN)


class _Mesa:
    """Os quatro leitores de verdade, o P1 pelo `dispatch_gamepad`, o resto pelo co-op."""

    def __init__(self, pads: dict[int, Any]) -> None:
        self.leitores = {
            n: EvdevReader(device_path=Path(f"/nao/existe/event-do-p{n}")) for n in range(1, 5)
        }
        self.pads = pads
        self.daemon = SimpleNamespace(
            controller=SimpleNamespace(_evdev=self.leitores[1]),
            store=SimpleNamespace(udp_trigger_thresholds=(0, 0)),
            _gamepad_device=pads[1],
            _mouse_device=None,
            _input_ready_at=0.0,
        )
        gerente = co.CoopManager.__new__(co.CoopManager)
        gerente._daemon = self.daemon
        gerente._players = {}
        for n in (2, 3, 4):
            gerente._players[_UNIQ[n]] = co._SecondaryPlayer(
                identity=_UNIQ[n],
                evdev_path=f"/dev/input/event-do-p{n}",
                reader=self.leitores[n],
                player_index=n,
                vpad=pads[n],
            )
        self.coop = gerente

    def mandar(self, n: int, *eventos: tuple[int, int, int]) -> None:
        """O nó do físico do jogador `n` entregou estes eventos ao leitor dele."""
        for tipo, codigo, valor in eventos:
            self.leitores[n]._handle_event(_Evento(tipo, codigo, valor), ecodes)

    def trocar_o_pad(self, n: int, pad: Any) -> None:
        self.pads[n] = pad
        if n == 1:
            self.daemon._gamepad_device = pad
        else:
            self.coop._players[_UNIQ[n]].vpad = pad

    def tique(self) -> None:
        """Um tique do `_poll_loop` depois do grace: o P1 e o co-op."""
        botoes = evdev_buttons_once(self.daemon)
        if self.daemon._gamepad_device is not None:
            r = self.leitores[1].snapshot()
            estado = SimpleNamespace(
                raw_lx=r.lx, raw_ly=r.ly, raw_rx=r.rx, raw_ry=r.ry, l2_raw=r.l2_raw, r2_raw=r.r2_raw
            )
            gp.dispatch_gamepad(cast(Any, self.daemon), estado, botoes)
        self.coop.forward_all()


@pytest.fixture(autouse=True)
def _o_laco_so_do_botao(monkeypatch: pytest.MonkeyPatch) -> None:
    """O que o tique faz e não é o caminho do botão: o aviso de modo na luz, a
    reconciliação do lançamento e a mesa do co-op (quem cedeu, quem espera o
    grab). Os quatro moram fora do trecho medido aqui."""
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)


@pytest.fixture
def fazer_uhid() -> Iterator[Callable[[int], tuple[UhidDualSense, list[bytes]]]]:
    """O `UhidDualSense` de verdade com o fd no `/dev/null` e os reports gravados."""
    abertos: list[UhidDualSense] = []

    def fazer(n: int) -> tuple[UhidDualSense, list[bytes]]:
        pad = UhidDualSense(player=n, blueprint=None)
        pad._fd = os.open(os.devnull, os.O_WRONLY)
        reports: list[bytes] = []
        enviar = pad.send_report

        def gravar(report: bytes) -> bool:
            reports.append(bytes(report))
            return enviar(report)

        pad.send_report = gravar  # type: ignore[method-assign]
        abertos.append(pad)
        return pad, reports

    yield fazer
    for pad in abertos:
        fd, pad._fd = pad._fd, None
        if fd is not None:
            os.close(fd)


def _fazer_uinput(mascara: str) -> tuple[UinputGamepad, list[tuple[int, int, int]]]:
    pad = UinputGamepad.for_flavor(mascara)
    no = _NoDoUinput()
    pad._device = no
    pad._ecodes = ecodes
    return pad, no.escritas


def _mesa_uhid(
    fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]],
) -> tuple[_Mesa, dict[int, list[bytes]]]:
    pads, reports = {}, {}
    for n in range(1, 5):
        pads[n], reports[n] = fazer_uhid(n)
    return _Mesa(pads), reports


def _mesa_uinput(mascara: str) -> tuple[_Mesa, dict[int, list[tuple[int, int, int]]]]:
    pads, escritas = {}, {}
    for n in range(1, 5):
        pads[n], escritas[n] = _fazer_uinput(mascara)
    return _Mesa(pads), escritas


# ─────────────────────────────────────────────────────────────────────────────
# Régua 1: a ida e volta pelo driver, pad `uhid`, P1 a P4
# ─────────────────────────────────────────────────────────────────────────────


def _ida_e_volta_no_uhid(
    mesa: _Mesa, reports: dict[int, list[bytes]], jogador: int, driver: _EsperadoDriver
) -> list[str]:
    """Cada caso do driver entra no leitor do `jogador` e volta pelo report."""
    erros: list[str] = []
    centro = driver.hat_vetores[driver.hat_centro]
    mesa.tique()
    for caso in _esperado_casos(driver):
        antes = {n: len(r) for n, r in reports.items()}
        mesa.mandar(jogador, *caso.aperta)
        mesa.tique()
        visto = _esperado_le_o_report(driver, reports[jogador][-1])
        pedido = (frozenset({caso.rotulo}) if caso.codigo is not None else frozenset(), caso.vetor)
        if visto != pedido:
            erros.append(f"P{jogador} {caso.rotulo}: pedia {pedido}, chegava {visto}")
        for outro, quantos in antes.items():
            if outro != jogador and len(reports[outro]) != quantos:
                erros.append(f"P{jogador} {caso.rotulo}: o pad do P{outro} também mudou")
        mesa.mandar(jogador, *caso.solta)
        mesa.tique()
        visto = _esperado_le_o_report(driver, reports[jogador][-1])
        if visto != (frozenset(), centro):
            erros.append(f"P{jogador} {caso.rotulo} solto: chegava {visto}")
    return erros


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_regua_1_ida_e_volta_pelo_driver_no_uhid(
    jogador: int, fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]]
) -> None:
    """Os 13 pares do driver e as 8 direções do hat, P1 a P4, ida igual à volta.

    Mordidas: trocar `l3` e `create` em `_BUTTONS1_BITS` reprova nos quatro;
    `_HAT_BY_VECTOR[(1, 0)]` apontando para 6 reprova a seta → nos quatro;
    trocar `BTN_THUMBL` e `BTN_THUMBR` no `BUTTON_MAP` reprova nos quatro."""
    driver = _esperado_driver_lido()
    assert len(driver.pares) == 13 and len(driver.hat_vetores) == 9
    mesa, reports = _mesa_uhid(fazer_uhid)
    erros = _ida_e_volta_no_uhid(mesa, reports, jogador, driver)
    assert not erros, "\n".join(erros)


def test_o_cabo_e_o_radio_passam_pela_mesma_leitura() -> None:
    """O driver lê o `0x01` do cabo e o `0x31` do rádio numa função só: os dois
    transportes atribuem o mesmo `ds_report` (em `data[1]` e `data[2]`) e os
    pares vêm depois, uma vez cada. Logo o código que o leitor recebe é o mesmo
    nos dois, e a régua 1 vale para cabo e rádio."""
    driver = _esperado_driver_lido()
    assert driver.atribuicoes == 2
    assert (driver.inicio_no_cabo, driver.inicio_no_radio) == (1, 2)
    nomes = [btn for btn, _b, _m in driver.pares]
    assert len(nomes) == len(set(nomes)), "um BTN_* lido duas vezes"


# ─────────────────────────────────────────────────────────────────────────────
# Régua 2: as máscaras do `uinput`
# ─────────────────────────────────────────────────────────────────────────────


def _o_que_o_jogo_ve_no_uinput(
    escritas: list[tuple[int, int, int]],
) -> tuple[frozenset[int], tuple[int, int], dict[int, int]]:
    """Dobra as escritas do nó: as teclas apertadas, o hat e os eixos."""
    teclas: dict[int, int] = {}
    eixos: dict[int, int] = {}
    for tipo, codigo, valor in escritas:
        if tipo == ecodes.EV_KEY:
            teclas[codigo] = valor
        elif tipo == ecodes.EV_ABS:
            eixos[codigo] = valor
    apertadas = frozenset(c for c, v in teclas.items() if v)
    return apertadas, (eixos.get(ecodes.ABS_HAT0X, 0), eixos.get(ecodes.ABS_HAT0Y, 0)), eixos


#: Os dois botões da frente que, na máscara DualSense do `uinput`, chegam
#: trocados (régua 2b, xfail estrito).
_A_FRENTE_QUE_O_VID_DECIDE = frozenset({"BTN_WEST", "BTN_NORTH"})


def _ida_e_volta_no_uinput(
    mesa: _Mesa,
    escritas: dict[int, list[tuple[int, int, int]]],
    jogador: int,
    driver: _EsperadoDriver,
    *,
    so: frozenset[str] | None = None,
    menos: frozenset[str] = frozenset(),
) -> list[str]:
    erros: list[str] = []
    vid = mesa.pads[jogador].vendor
    mesa.tique()
    for caso in _esperado_casos(driver):
        if (so is not None and caso.rotulo not in so) or caso.rotulo in menos:
            continue
        mesa.mandar(jogador, *caso.aperta)
        mesa.tique()
        teclas, hat, eixos = _o_que_o_jogo_ve_no_uinput(escritas[jogador])
        if caso.codigo is None:
            ok = teclas == frozenset() and hat == caso.vetor
        elif caso.eixo is not None:
            # O gatilho chega por um dos dois códigos que o físico manda para ele.
            ok = hat == (0, 0) and (
                teclas == {caso.codigo} or (teclas == frozenset() and eixos.get(caso.eixo) == 255)
            )
        else:
            ok = hat == (0, 0) and teclas == {_esperado_codigo_que_o_jogo_le(vid, caso.codigo)}
        if not ok:
            nomes = sorted(hex(c) for c in teclas)
            erros.append(f"P{jogador} {caso.rotulo}: chegava teclas={nomes} hat={hat}")
        mesa.mandar(jogador, *caso.solta)
        mesa.tique()
        teclas, hat, eixos = _o_que_o_jogo_ve_no_uinput(escritas[jogador])
        if teclas or hat != (0, 0) or (caso.eixo is not None and eixos.get(caso.eixo, 0) != 0):
            erros.append(f"P{jogador} {caso.rotulo} solto: teclas={sorted(teclas)} hat={hat}")
    return erros


def test_as_mascaras_desta_regua_sao_as_do_produto() -> None:
    """Uma máscara nova no `uinput` sem caso aqui reprova (lado do produto)."""
    from hefesto_dualsense4unix.integrations.uinput_gamepad import BOTOES_POR_FLAVOR

    assert set(BOTOES_POR_FLAVOR) == {"dualsense", "xbox", "nintendo"}


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
@pytest.mark.parametrize("mascara", ["dualsense", "xbox", "nintendo"])
def test_regua_2_ida_e_volta_nas_mascaras_do_uinput(mascara: str, jogador: int) -> None:
    """Cada botão chega como o botão que o jogo lê, pelo VID da máscara.

    Fica de fora só o par da frente na máscara DualSense (a régua 2b).
    Mordidas: trocar `l3` e `r3` em `BUTTON_TO_UINPUT` reprova a DualSense e a
    Xbox e não a Nintendo; o mesmo em `BOTOES_PROCON` reprova só a Nintendo."""
    driver = _esperado_driver_lido()
    mesa, escritas = _mesa_uinput(mascara)
    menos = _A_FRENTE_QUE_O_VID_DECIDE if mascara == "dualsense" else frozenset()
    erros = _ida_e_volta_no_uinput(mesa, escritas, jogador, driver, menos=menos)
    assert not erros, "\n".join(erros)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Defeito lido no fonte, fora da posse desta sprint: a máscara DualSense do "
        "uinput mostra o VID da Sony e escreve o quadrado como BTN_X (o número do "
        "BTN_NORTH); o SDL lê o X da Sony no BTN_WEST, e o quadrado chega como "
        "triângulo. Curado o uinput_gamepad.py, este xfail vira vermelho e sai."
    ),
)
def test_regua_2b_a_frente_na_mascara_dualsense_do_uinput() -> None:
    driver = _esperado_driver_lido()
    mesa, escritas = _mesa_uinput("dualsense")
    erros = _ida_e_volta_no_uinput(mesa, escritas, 1, driver, so=_A_FRENTE_QUE_O_VID_DECIDE)
    assert not erros, "\n".join(erros)


# ─────────────────────────────────────────────────────────────────────────────
# Régua 3: o esperado vem do driver, e não da saída
# ─────────────────────────────────────────────────────────────────────────────


def test_regua_3_o_driver_trocado_reprova_a_regua_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]],
) -> None:
    """Uma cópia do `hid-playstation.c` com `DS_BUTTONS1_L3` e `DS_BUTTONS1_R3`
    trocados faz a régua 1 reprovar com o codificador intacto: o lado esperado
    lê o driver, e não a saída do produto."""
    fonte = o_report.DRIVER.read_text(encoding="utf-8")
    l3 = re.search(r"#define DS_BUTTONS1_L3\s+(BIT\(\d+\))", fonte)
    r3 = re.search(r"#define DS_BUTTONS1_R3\s+(BIT\(\d+\))", fonte)
    assert l3 and r3
    trocado = re.sub(
        r"(#define DS_BUTTONS1_(L3|R3)\s+)BIT\(\d+\)",
        lambda m: m.group(1) + (r3.group(1) if m.group(2) == "L3" else l3.group(1)),
        fonte,
    )
    copia = tmp_path / "hid-playstation.c"
    copia.write_text(trocado, encoding="utf-8")
    monkeypatch.setattr(o_report, "DRIVER", copia)
    mesa, reports = _mesa_uhid(fazer_uhid)
    erros = _ida_e_volta_no_uhid(mesa, reports, 1, _esperado_driver_lido())
    assert any("BTN_THUMBL" in e for e in erros) and any("BTN_THUMBR" in e for e in erros)
    assert all("THUMB" in e for e in erros), erros


#: Os nomes de tabela do produto que o lado esperado nunca pode citar.
_TABELAS_DO_PRODUTO = frozenset({
    "_BUTTONS0_BITS",
    "_BUTTONS1_BITS",
    "_BUTTONS2_BITS",
    "_HAT_BY_VECTOR",
    "BUTTON_MAP",
    "BUTTON_TO_UINPUT",
    "BOTOES_PROCON",
    "BOTOES_POR_FLAVOR",
})


def test_regua_3_o_lado_esperado_nao_cita_tabela_do_produto() -> None:
    """Pela árvore sintática deste arquivo: nenhuma função `_esperado_*` (nem a
    classe do driver lido) cita uma tabela do produto, e nenhum import do topo
    a traz. Mordida: importar `_BUTTONS1_BITS` no lado esperado reprova."""
    arvore = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    citados: set[str] = set()
    for no in arvore.body:
        if isinstance(no, ast.ImportFrom):
            citados.update(a.name for a in no.names if a.name in _TABELAS_DO_PRODUTO)
        if isinstance(no, ast.FunctionDef | ast.ClassDef) and no.name.startswith(
            ("_esperado_", "_Esperado")
        ):
            for filho in ast.walk(no):
                if isinstance(filho, ast.Name) and filho.id in _TABELAS_DO_PRODUTO:
                    citados.add(filho.id)
                elif isinstance(filho, ast.Attribute) and filho.attr in _TABELAS_DO_PRODUTO:
                    citados.add(filho.attr)
                elif isinstance(filho, ast.alias) and filho.name in _TABELAS_DO_PRODUTO:
                    citados.add(filho.name)
    assert not citados, f"o lado esperado cita tabela do produto: {sorted(citados)}"


# ─────────────────────────────────────────────────────────────────────────────
# Régua 4: o aperto de 10 ms entre dois tiques chega
# ─────────────────────────────────────────────────────────────────────────────

#: O aperto curto: o R3 (o botão do relatório do Forja) e a seta → (o hat, que
#: conta pelo `_refresh_dpad_buttons` e não pelo `_handle_key`).
_APERTOS_CURTOS = {
    "r3": (
        ((ecodes.EV_KEY, ecodes.BTN_THUMBR, 1),),
        ((ecodes.EV_KEY, ecodes.BTN_THUMBR, 0),),
    ),
    "dpad_right": (
        ((ecodes.EV_ABS, ecodes.ABS_HAT0X, 1),),
        ((ecodes.EV_ABS, ecodes.ABS_HAT0X, 0),),
    ),
}


def _o_aperto_curto(mesa: _Mesa, jogador: int, nome: str) -> None:
    """Aperta e solta entre dois tiques: nenhum retrato o vê apertado."""
    aperta, solta = _APERTOS_CURTOS[nome]
    mesa.mandar(jogador, *aperta)
    mesa.mandar(jogador, *solta)
    assert nome not in mesa.leitores[jogador].snapshot().buttons_pressed


def _o_report_tem(nome: str, report: bytes) -> bool:
    """O nome está apertado no report, pela leitura do driver."""
    driver = _esperado_driver_lido()
    apertados, vetor = _esperado_le_o_report(driver, report)
    if nome == "r3":
        return "BTN_THUMBR" in apertados
    return vetor == (1, 0)


def _janela(n: int) -> bytes:
    return bytes([n & 0xFF, (n >> 8) & 0xFF]) + bytes(uhid_gamepad._MOTION_WINDOW_LEN - 2)


@pytest.mark.parametrize("nome", sorted(_APERTOS_CURTOS))
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_regua_4_o_aperto_curto_chega_no_uhid_sem_espelho(
    jogador: int, nome: str, fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]]
) -> None:
    """Sem o espelho, quem emite é o tique: um report com o bit e depois um sem.

    Mordidas: tirar a comparação do `dispatch_gamepad` reprova só o P1; tirar a
    do `forward_all` reprova só P2 a P4; contar por leitura do retrato em vez
    da borda reprova os quatro."""
    mesa, reports = _mesa_uhid(fazer_uhid)
    mesa.tique()
    mesa.tique()
    inicio = len(reports[jogador])
    _o_aperto_curto(mesa, jogador, nome)
    mesa.tique()
    novos = [_o_report_tem(nome, r) for r in reports[jogador][inicio:]]
    assert novos == [True, False], novos


@pytest.mark.parametrize("nome", sorted(_APERTOS_CURTOS))
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_regua_4_o_aperto_curto_chega_no_uhid_com_o_espelho(
    jogador: int, nome: str, fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]]
) -> None:
    """Com o espelho ligado, o tique só guarda: o aperto pega carona no report
    seguinte do leitor de movimento, e o seguinte já sai sem ele.

    Mordida: sem os `_pendentes` do `UhidDualSense`, só este caso reprova (o
    tique entrega `apertados | soltos` e logo `apertados`, e o leitor só emite
    depois)."""
    mesa, reports = _mesa_uhid(fazer_uhid)
    for pad in mesa.pads.values():
        pad._motion_streaming = True
    mesa.tique()
    mesa.pads[jogador].forward_motion(_janela(1))
    inicio = len(reports[jogador])
    _o_aperto_curto(mesa, jogador, nome)
    mesa.tique()
    assert len(reports[jogador]) == inicio, "o tique não emite com o espelho ligado"
    mesa.pads[jogador].forward_motion(_janela(2))
    mesa.pads[jogador].forward_motion(_janela(3))
    novos = [_o_report_tem(nome, r) for r in reports[jogador][inicio:]]
    assert novos == [True, False], novos


@pytest.mark.parametrize("nome", sorted(_APERTOS_CURTOS))
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
@pytest.mark.parametrize("mascara", ["dualsense", "xbox", "nintendo"])
def test_regua_4_o_aperto_curto_chega_no_uinput(mascara: str, jogador: int, nome: str) -> None:
    """No `uinput`, o aperto e a soltura saem no mesmo tique, cada um com o seu
    SYN: o jogo lê dois quadros de evento."""
    mesa, escritas = _mesa_uinput(mascara)
    mesa.tique()
    inicio = len(escritas[jogador])
    _o_aperto_curto(mesa, jogador, nome)
    mesa.tique()
    novas = escritas[jogador][inicio:]
    alvo = (ecodes.EV_KEY, ecodes.BTN_THUMBR) if nome == "r3" else (ecodes.EV_ABS, ecodes.ABS_HAT0X)
    quadros: list[list[int]] = [[]]
    for escrita in novas:
        if escrita == _SYN:
            quadros.append([])
        elif escrita[:2] == alvo:
            quadros[-1].append(escrita[2])
    assert [q for q in quadros if q] == [[1], [0]], novas


# ─────────────────────────────────────────────────────────────────────────────
# Régua 5: nenhum report a mais com o espelho ligado
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("jogador", [1, 2])
def test_regua_5_nenhum_report_a_mais_com_o_espelho(
    jogador: int, fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]]
) -> None:
    """Vinte janelas de movimento, com tiques e apertos curtos no meio: sai um
    report por janela, e nenhum a mais.

    Mordida: emitir no `forward_buttons` com o espelho ligado reprova."""
    mesa, reports = _mesa_uhid(fazer_uhid)
    for pad in mesa.pads.values():
        pad._motion_streaming = True
    mesa.tique()
    inicio = len(reports[jogador])
    for n in range(20):
        if n % 3 == 0:
            _o_aperto_curto(mesa, jogador, "r3")
        if n % 5 == 0:
            mesa.mandar(jogador, (ecodes.EV_KEY, ecodes.BTN_SOUTH, n % 2))
        mesa.tique()
        mesa.pads[jogador].forward_motion(_janela(10 + n))
    assert len(reports[jogador]) - inicio == 20


# ─────────────────────────────────────────────────────────────────────────────
# Régua 8: o aperto do assentamento não vira fantasma, e o contador é um só
# ─────────────────────────────────────────────────────────────────────────────


def _algum_report_tem(nome: str, reports: list[bytes]) -> bool:
    return any(_o_report_tem(nome, r) for r in reports)


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_regua_8_o_aperto_dentro_do_grace_nao_chega(
    jogador: int, fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]]
) -> None:
    """A conexão arma o grace (`_input_ready_at` muda), e o laço não despacha
    até ele passar. O aperto feito ali dentro não chega no primeiro tique
    depois; o aperto curto feito depois chega.

    Mordidas: tirar o rebase pelo `_input_ready_at` reprova a primeira metade;
    rebasear a cada tique reprova a segunda."""
    mesa, reports = _mesa_uhid(fazer_uhid)
    mesa.tique()
    mesa.tique()
    mesa.daemon._input_ready_at = 1_000.0  # a borda da conexão arma o grace
    _o_aperto_curto(mesa, jogador, "r3")  # dentro do grace: nenhum tique despacha
    inicio = len(reports[jogador])
    mesa.tique()  # o grace passou
    mesa.tique()
    assert not _algum_report_tem("r3", reports[jogador][inicio:]), "entrada fantasma"
    inicio = len(reports[jogador])
    _o_aperto_curto(mesa, jogador, "r3")
    mesa.tique()
    assert [_o_report_tem("r3", r) for r in reports[jogador][inicio:]] == [True, False]


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_regua_8_o_aperto_sem_pad_nao_chega_ao_pad_novo(
    jogador: int, fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]]
) -> None:
    """O pad do jogador morre (o grab que volta a pendente, o arming que
    recria), o aperto acontece sem pad, e o pad novo nasce: ele não recebe o
    aperto de antes de existir.

    Mordida: tirar o rebase pelo pad novo reprova."""
    mesa, _reports = _mesa_uhid(fazer_uhid)
    mesa.tique()
    mesa.tique()
    mesa.trocar_o_pad(jogador, None)
    mesa.tique()
    _o_aperto_curto(mesa, jogador, "r3")
    mesa.tique()
    novo, reports_do_novo = fazer_uhid(jogador)
    mesa.trocar_o_pad(jogador, novo)
    mesa.tique()
    mesa.tique()
    assert reports_do_novo, "o pad novo nasce com um report"
    assert not _algum_report_tem("r3", reports_do_novo), "entrada fantasma no pad novo"


def test_regua_8_o_contador_de_bordas_e_um_so() -> None:
    """O `EvdevSnapshot` tem UM campo de contagem por borda (a NAVEGACAO lê o
    mesmo). Mordida: um segundo contador ao lado reprova."""
    contadores = [f.name for f in fields(EvdevSnapshot) if str(f.type) == "dict[str, int]"]
    assert contadores == ["apertos"]


def test_a_contagem_e_na_borda_e_sobrevive_a_queda() -> None:
    """R3 segurado por três leituras conta 1; a queda do nó solta tudo sem
    zerar a contagem; o hat conta a direção que entra."""
    leitor = EvdevReader(device_path=Path("/nao/existe/event-da-contagem"))
    leitor._handle_event(_Evento(ecodes.EV_KEY, ecodes.BTN_THUMBR, 1), ecodes)
    for _ in range(3):
        assert leitor.snapshot().apertos == {"r3": 1}
    leitor._handle_event(_Evento(ecodes.EV_KEY, ecodes.BTN_THUMBR, 2), ecodes)  # autorepeat
    leitor._reset_on_disconnect()
    assert leitor.snapshot().buttons_pressed == frozenset()
    assert leitor.snapshot().apertos == {"r3": 1}
    leitor._handle_event(_Evento(ecodes.EV_KEY, ecodes.BTN_THUMBR, 1), ecodes)
    leitor._handle_event(_Evento(ecodes.EV_ABS, ecodes.ABS_HAT0X, 1), ecodes)
    leitor._handle_event(_Evento(ecodes.EV_ABS, ecodes.ABS_HAT0Y, -1), ecodes)
    assert leitor.snapshot().apertos == {"r3": 2, "dpad_right": 1, "dpad_up": 1}


# ─────────────────────────────────────────────────────────────────────────────
# Régua 4c: o aperto curto passa pela troca do perfil (conferência de 02/10)
# ─────────────────────────────────────────────────────────────────────────────


def _o_report_tem_o_btn(btn: str, report: bytes) -> bool:
    """O BTN_* está apertado no report, pela leitura do driver."""
    apertados, _vetor = _esperado_le_o_report(_esperado_driver_lido(), report)
    return btn in apertados


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_regua_4c_o_aperto_curto_chega_com_a_troca_do_perfil(
    jogador: int, fazer_uhid: Callable[[int], tuple[UhidDualSense, list[bytes]]]
) -> None:
    """Com a troca L3 ↔ R3 no perfil, o R3 de 10 ms entre dois tiques chega ao
    jogo como L3, e o R3 nunca aparece: a troca vale para o aperto que já
    soltou como para os outros (a sprint, «A ordem no tique»).

    Mordidas (conferência de 02/10): tirar a troca do quadro dos soltos no
    `dispatch_gamepad` reprova só o P1; no `forward_all`, só P2 a P4."""
    from hefesto_dualsense4unix.core.remapeamento_de_botao import definir_ativo

    mesa, reports = _mesa_uhid(fazer_uhid)
    definir_ativo(mesa.daemon.store, {"l3": "r3", "r3": "l3"})
    mesa.tique()
    mesa.tique()
    inicio = len(reports[jogador])
    _o_aperto_curto(mesa, jogador, "r3")
    mesa.tique()
    novos = reports[jogador][inicio:]
    assert [_o_report_tem_o_btn("BTN_THUMBL", r) for r in novos] == [True, False]
    assert not any(_o_report_tem_o_btn("BTN_THUMBR", r) for r in novos), "o R3 cru chegou"
