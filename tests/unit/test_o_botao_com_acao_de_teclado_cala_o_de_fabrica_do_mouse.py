"""D-2511-O-BOTAO-COM-ACAO-DE-TECLADO-CALA-O-DE-FABRICA-DO-MOUSE: uma ação de teclado, um gesto só.

Medido antes de curar (25/11/2026), com o `ProfileManager` real e os dois devices reais sobre um
`uinput` que grava o que cada um emite: o direcional, o Círculo e o Quadrado com uma ação de
teclado no perfil (tecla, «Abrir a Steam») saíam DUAS vezes, a ação escolhida e o gesto de fábrica
do mouse virtual (`dpad_up=__STEAM__` seguia emitindo `KEY_UP`; `circle=KEY_F11` saía `KEY_ENTER`
e `KEY_F11`; `dpad_down=KEY_DOWN` saía duas vezes). O caminho do perfil passava ao mouse só os
botões calados; a tabela com o jogo aberto, `calados | do_teclado`.

A pergunta «esta ação de teclado tem quem a emita agora?» tem um dono, o
`UinputMouseDevice.ceder_ao_teclado` (a tabela e a pergunta que o gerente entrega), e a resposta é
lida a cada tique: com o teclado virtual de pé E com a ação do botão na tabela dele, o de fábrica
do botão sai do mouse; sem ele (Função do teclado desligada), ou com o teclado que acabou de nascer
com o de fábrica dele, o de fábrica segue, e o teclado que liga, desliga ou recebe a tabela depois
é acompanhado sem reaplicar o perfil. O jogo aberto tem teclado privado, que sempre existe.

MORDIDAS (cada uma reprova nomeando o botão): arrancar a chamada `ceder` do
`apply_button_actions` reprova os casos com teclado; trocar a pergunta por «sempre sim»
(`calados | do_teclado` fixo) reprova os casos sem teclado e o do teclado que desliga; arrancar o
`_acompanhar_o_teclado` do `dispatch` reprova só o do teclado que liga e desliga depois; voltar a
pergunta a «há um teclado de pé?», sem olhar a tabela dele, reprova o do teclado que nasce sem a
tabela (o botão ficava mudo: o mouse cedia e o teclado novo não emitia nada).
"""
from __future__ import annotations

import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.daemon.subsystems.mouse import TabelaNoJogo
from hefesto_dualsense4unix.integrations.uinput_keyboard import DEVICE_NAME as NOME_DO_TECLADO
from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    DEVICE_NAME as NOME_DO_MOUSE,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    DPAD_TO_KEY,
    EDGE_KEY_MAP,
    UinputMouseDevice,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import Profile
from tests.unit.test_o_gatilho_vira_clique_sem_ligar_o_cursor import (
    _daemon_de_mentira,
    _estado,
    _OskDeMentira,
    _UinputPorDevice,
)

DE_FABRICA = {**DPAD_TO_KEY, **EDGE_KEY_MAP}
OS_SEIS = sorted(DE_FABRICA)
CENTRO = dict(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0)


@pytest.fixture
def uinput(monkeypatch: pytest.MonkeyPatch) -> _UinputPorDevice:
    mod = _UinputPorDevice()
    monkeypatch.setitem(sys.modules, "uinput", mod)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard._fazer_o_comando",
        lambda daemon, token: None)
    return mod


def _zerar(mod: _UinputPorDevice) -> None:
    """Esvazia o que cada device gravou, sem soltar as listas que os devices seguram."""
    for gravado in mod.saiu.values():
        gravado.clear()


def _toques(mod: _UinputPorDevice, nome: str) -> list[str]:
    """Os gestos (borda de subida) que o device gravou."""
    return [n for n, v in mod.saiu.get(nome, []) if v == 1]


def _dois_devices(mod: _UinputPorDevice, escolhas: dict[str, str], *, com_teclado: bool,
                  ) -> tuple[UinputMouseDevice, UinputKeyboardDevice, dict[str, bool]]:
    """O caminho do computador: o `ProfileManager` entrega o perfil; `de_pe` liga o teclado."""
    mouse, teclado = UinputMouseDevice(), UinputKeyboardDevice()
    assert mouse.start() and teclado.start()
    de_pe: dict[str, Any] = {"teclado": com_teclado, "qual": teclado}
    gerente = ProfileManager(
        controller=None,
        mouse_device_provider=lambda: mouse,
        keyboard_device_provider=lambda: de_pe["qual"] if de_pe["teclado"] else None)
    perfil = Profile(name="ensaio", match={"type": "any"}, button_actions=escolhas)
    if com_teclado:
        gerente.apply_keyboard(perfil)
    gerente.apply_button_actions(perfil)
    _zerar(mod)
    return mouse, teclado, de_pe


def _apertar(mouse: UinputMouseDevice, teclado: UinputKeyboardDevice, botao: str, *,
             de_pe: dict[str, Any] | None = None, volta: int = 0) -> None:
    for i, apertado in enumerate((frozenset({botao}), frozenset())):
        mouse.dispatch(buttons=apertado, now=1.0 + volta * 10 + i, **CENTRO)  # type: ignore[arg-type]
        if de_pe is None or de_pe["teclado"]:
            teclado.dispatch(apertado)


def _no_computador(mod: _UinputPorDevice, botao: str, token: str, *, com_teclado: bool,
                   ) -> tuple[list[str], list[str]]:
    mouse, teclado, de_pe = _dois_devices(mod, {botao: token}, com_teclado=com_teclado)
    _apertar(mouse, teclado, botao, de_pe=de_pe)
    return _toques(mod, NOME_DO_MOUSE), _toques(mod, NOME_DO_TECLADO)


def _com_o_jogo_aberto(mod: _UinputPorDevice, botao: str, token: str,
                       ) -> tuple[list[str], list[str]]:
    daemon = _daemon_de_mentira()
    daemon._osk_controller = _OskDeMentira()
    tabela = TabelaNoJogo({botao: token}, None, ligada=True)
    estado = _estado(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128)
    tabela.tick(daemon, estado, frozenset({botao}))
    tabela.tick(daemon, estado, frozenset())
    tabela.fechar()
    return _toques(mod, NOME_DO_MOUSE), _toques(mod, NOME_DO_TECLADO)


@pytest.mark.parametrize("botao", OS_SEIS)
def test_a_tecla_escolhida_sai_sozinha_com_o_teclado_de_pe(
    uinput: _UinputPorDevice, botao: str,
) -> None:
    mouse, teclado = _no_computador(uinput, botao, "KEY_F11", com_teclado=True)
    assert mouse == [], (
        f"{botao}=KEY_F11: o mouse virtual ainda emitiu {mouse} (de fábrica) junto da ação")
    assert teclado == ["KEY_F11"], f"{botao}=KEY_F11: o teclado emitiu {teclado}"


@pytest.mark.parametrize("botao", OS_SEIS)
def test_abrir_a_steam_nao_deixa_o_de_fabrica_sair(
    uinput: _UinputPorDevice, botao: str,
) -> None:
    mouse, _teclado = _no_computador(uinput, botao, acoes.TOKEN_STEAM, com_teclado=True)
    assert mouse == [], (
        f"{botao}=«Abrir a Steam»: o mouse virtual emitiu {mouse}, o gesto de fábrica que a "
        f"escolha devia ter calado")


@pytest.mark.parametrize("botao", OS_SEIS)
def test_a_mesma_tecla_de_fabrica_sai_uma_vez_so(
    uinput: _UinputPorDevice, botao: str,
) -> None:
    tecla = DE_FABRICA[botao]
    mouse, teclado = _no_computador(uinput, botao, tecla, com_teclado=True)
    assert mouse + teclado == [tecla], (
        f"{botao}={tecla}: saiu {mouse + teclado}, a mesma tecla de dois dispositivos")


@pytest.mark.parametrize("botao", OS_SEIS)
def test_sem_o_teclado_o_de_fabrica_segue(uinput: _UinputPorDevice, botao: str) -> None:
    for token in ("KEY_F11", acoes.TOKEN_STEAM):
        mouse, teclado = _no_computador(uinput, botao, token, com_teclado=False)
        assert mouse == [DE_FABRICA[botao]], (
            f"{botao}={token} com a Função do teclado desligada: o mouse emitiu {mouse}, e o "
            f"de fábrica {DE_FABRICA[botao]} devia seguir (ninguém emite a ação)")
        assert teclado == []


@pytest.mark.parametrize("botao", OS_SEIS)
def test_o_jogo_aberto_e_o_computador_dao_o_mesmo(
    uinput: _UinputPorDevice, botao: str,
) -> None:
    for token in ("KEY_F11", acoes.TOKEN_STEAM, DE_FABRICA[botao]):
        no_computador = _no_computador(uinput, botao, token, com_teclado=True)
        _zerar(uinput)
        no_jogo = _com_o_jogo_aberto(uinput, botao, token)
        assert no_jogo == no_computador, (
            f"{botao}={token}: o computador deu {no_computador} e o jogo aberto {no_jogo}")
        _zerar(uinput)


@pytest.mark.parametrize("botao", OS_SEIS)
def test_o_teclado_que_liga_e_desliga_depois_da_tabela_e_acompanhado(
    uinput: _UinputPorDevice, botao: str,
) -> None:
    mouse, teclado, de_pe = _dois_devices(uinput, {botao: "KEY_F11"}, com_teclado=True)
    _apertar(mouse, teclado, botao, de_pe=de_pe, volta=0)
    assert _toques(uinput, NOME_DO_MOUSE) == []

    de_pe["teclado"] = False
    _zerar(uinput)
    _apertar(mouse, teclado, botao, de_pe=de_pe, volta=1)
    assert _toques(uinput, NOME_DO_MOUSE) == [DE_FABRICA[botao]], (
        f"{botao}: o teclado desligou e o botão ficou mudo, sem ninguém para emitir F11")

    de_pe["teclado"] = True
    _zerar(uinput)
    _apertar(mouse, teclado, botao, de_pe=de_pe, volta=2)
    assert _toques(uinput, NOME_DO_MOUSE) == []
    assert _toques(uinput, NOME_DO_TECLADO) == ["KEY_F11"]


@pytest.mark.parametrize("botao", OS_SEIS)
@pytest.mark.parametrize("com_teclado", [True, False], ids=["religado", "ligado-depois"])
def test_o_teclado_que_nasce_sem_a_tabela_nao_cala_o_de_fabrica(
    uinput: _UinputPorDevice, botao: str, com_teclado: bool,
) -> None:
    """D-2511-O-BOTAO-COM-ACAO-DE-TECLADO-CALA-O-DE-FABRICA-DO-MOUSE: o mouse cede só ao teclado
    que tem a tabela. Ligar a Função do teclado cria um device novo, com o de fábrica dele e sem a
    tabela do perfil: ninguém emite a ação escolhida, e o de fábrica do mouse segue (o botão não
    fica mudo).
    """
    mouse, _velho, de_pe = _dois_devices(uinput, {botao: "KEY_F11"}, com_teclado=com_teclado)
    novo = UinputKeyboardDevice()
    assert novo.start()
    de_pe["teclado"], de_pe["qual"] = True, novo
    _apertar(mouse, novo, botao, de_pe=de_pe)
    saiu = _toques(uinput, NOME_DO_MOUSE) + _toques(uinput, NOME_DO_TECLADO)
    assert saiu == [DE_FABRICA[botao]], (
        f"{botao}=KEY_F11 com um teclado novo sem a tabela: saiu {saiu}; o mouse cedeu a quem "
        f"não emite a ação")

    novo.set_bindings({botao: ("KEY_F11",)})
    _zerar(uinput)
    _apertar(mouse, novo, botao, de_pe=de_pe, volta=1)
    saiu = _toques(uinput, NOME_DO_MOUSE) + _toques(uinput, NOME_DO_TECLADO)
    assert saiu == ["KEY_F11"], f"{botao}: a tabela chegou ao teclado novo e saiu {saiu}"


def test_o_perfil_sem_opiniao_no_direcional_nao_o_faz_sair_duas_vezes(
    uinput: _UinputPorDevice,
) -> None:
    """O de fábrica do direcional, num perfil que só opina noutra linha: uma seta por aperto."""
    mouse, teclado, de_pe = _dois_devices(uinput, {"cross": "BTN_LEFT"}, com_teclado=True)
    _apertar(mouse, teclado, "dpad_up", de_pe=de_pe)
    saiu = _toques(uinput, NOME_DO_MOUSE) + _toques(uinput, NOME_DO_TECLADO)
    assert saiu == ["KEY_UP"], f"o direcional de fábrica saiu {saiu}"


def test_o_botao_do_mouse_continua_do_mouse(uinput: _UinputPorDevice) -> None:
    """A cura cala o de fábrica por ação de TECLADO, nunca o clique que o perfil deu ao mouse."""
    mouse, teclado, de_pe = _dois_devices(uinput, {"dpad_up": "BTN_LEFT"}, com_teclado=True)
    _apertar(mouse, teclado, "dpad_up", de_pe=de_pe)
    assert _toques(uinput, NOME_DO_MOUSE) == ["BTN_LEFT"]


def test_sem_a_pergunta_o_device_e_o_de_antes() -> None:
    """Quem chama `set_button_actions(do_mouse, calados)` (a tabela do jogo) não muda."""
    do_mouse: dict[str, str] = {}
    velho, novo = UinputMouseDevice(), UinputMouseDevice()
    velho.set_button_actions(do_mouse, frozenset({"dpad_up"}))
    novo.ceder_ao_teclado((), lambda: ("dpad_up", "circle"))
    novo.set_button_actions(do_mouse, frozenset({"dpad_up"}))
    assert velho._mapa_dpad == novo._mapa_dpad == {
        b: k for b, k in DPAD_TO_KEY.items() if b != "dpad_up"}
    assert velho._mapa_tap == novo._mapa_tap == dict(EDGE_KEY_MAP)


def test_a_pergunta_que_levanta_conta_como_ninguem(uinput: _UinputPorDevice) -> None:
    def quebrada() -> frozenset[str]:
        raise RuntimeError("provider caiu")

    mouse = UinputMouseDevice()
    assert mouse.start()
    mouse.set_button_actions({}, frozenset())
    mouse.ceder_ao_teclado(("dpad_up",), quebrada)
    assert mouse._mapa_dpad == dict(DPAD_TO_KEY)


def test_o_numero_que_devolve_zero_gestos_dobrados(uinput: _UinputPorDevice) -> None:
    """A conta da sprint: os botões que emitem dois gestos por aperto, do contado para zero."""
    dobrados: list[str] = []
    for botao in OS_SEIS:
        for token in ("KEY_F11", acoes.TOKEN_STEAM, DE_FABRICA[botao]):
            mouse, teclado = _no_computador(uinput, botao, token, com_teclado=True)
            gestos = [*mouse, *teclado]
            if len(gestos) > 1 or (token == acoes.TOKEN_STEAM and mouse):
                dobrados.append(f"{botao}={token}: {gestos}")
    assert dobrados == [], f"botões com dois gestos por aperto: {dobrados}"

