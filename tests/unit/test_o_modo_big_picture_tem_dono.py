"""O Modo Big Picture na Steam tem dono no daemon e leva o controle ao Big Picture.

A-ABA-NAVEGACAO-FAZ-O-QUE-DIZ-E-O-MODO-STEAM-NAVEGA-O-BIG-PICTURE-01 (08/10/2026).
A lista «Modo Big Picture na Steam» da aba Navegação era `SEM_GESTO` («não há método
de Modo Steam no daemon»). Agora o `navegacao.big_picture.set` é o dono, e o
direcional, a Cruz e o Círculo viram setas, Enter e Esc quando a Steam está na frente
e o controle é do Hefesto (Sony DualSense, Xbox, Navegação). No Nativo e no Steam
Input a Steam lê o físico, e o Hefesto não entra.

Sem `/dev/uinput`: o teclado virtual é um dublê injetado pela fábrica do dono.
"""
from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import remapeamento_de_botao as remap
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import big_picture as dono
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.testing import FakeController

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"

STEAM = "steam"
NAVEGAM = frozenset({"dpad_up", "dpad_down", "dpad_left", "dpad_right", "cross", "circle"})


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _Teclado:
    """O teclado virtual de mentira: guarda o que o dono mandou apertar."""

    def __init__(self, abre: bool = True) -> None:
        self.abre = abre
        self.parado = False
        self.entregas: list[frozenset[str]] = []

    def start(self) -> bool:
        return self.abre

    def stop(self) -> None:
        self.parado = True

    def dispatch(self, botoes: frozenset[str]) -> None:
        self.entregas.append(frozenset(botoes))


def _dono(teclado: _Teclado | None = None, relogio: _Relogio | None = None,
          ligado: bool = True) -> tuple[dono.BigPicture, _Teclado, _Relogio]:
    t = teclado or _Teclado()
    r = relogio or _Relogio()
    return dono.BigPicture(ligado=ligado, teclado=lambda: t, relogio=r), t, r


def _daemon(modo: str, classe: str | None = STEAM) -> Any:
    """Um daemon de mentira: o modo vivo vem de `hotkey.modo_vigente` (trocado abaixo)."""
    return SimpleNamespace(
        store=SimpleNamespace(window_detect_current_class=classe), _modo_de_mentira=modo)


@pytest.fixture(autouse=True)
def _o_modo_vivo_e_o_do_duble(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        hotkey, "modo_vigente", lambda d: getattr(d, "_modo_de_mentira", hotkey.MODO_NATIVO))


# 1 ─ Quem lê o controle em cada um dos cinco modos ─────────────────────────


@pytest.mark.parametrize("modo,quem", [
    (hotkey.MODO_NATIVO, hotkey.LE_A_STEAM),
    (hotkey.MODO_STEAM_INPUT, hotkey.LE_A_STEAM),
    (hotkey.PONTE_DUALSENSE, hotkey.LE_O_HEFESTO),
    (hotkey.PONTE_XBOX, hotkey.LE_O_HEFESTO),
    (hotkey.PONTE_MOUSE_TECLADO, hotkey.LE_O_HEFESTO),
])
def test_1_cada_um_dos_cinco_modos_tem_quem_lhe_le_o_controle(modo: str, quem: str) -> None:
    assert hotkey.quem_le_o_controle(_daemon(modo)) == quem
    assert set(hotkey.QUEM_LE_O_CONTROLE) == {
        hotkey.MODO_NATIVO, hotkey.MODO_STEAM_INPUT, hotkey.PONTE_DUALSENSE,
        hotkey.PONTE_XBOX, hotkey.PONTE_MOUSE_TECLADO}, "a tabela não cobre os cinco modos"


def test_1_na_duvida_o_controle_e_do_hefesto() -> None:
    assert hotkey.quem_le_o_controle(_daemon("modo que não existe")) == hotkey.LE_O_HEFESTO


@pytest.mark.parametrize("modo,age", [
    (hotkey.MODO_NATIVO, False),
    (hotkey.MODO_STEAM_INPUT, False),
    (hotkey.PONTE_DUALSENSE, True),
    (hotkey.PONTE_XBOX, True),
    (hotkey.PONTE_MOUSE_TECLADO, True),
])
def test_1_o_hefesto_so_entra_onde_o_controle_e_dele(modo: str, age: bool) -> None:
    # A decisão D-0810-O-MODO-BIG-PICTURE-NASCE-DESLIGADO.
    bp, teclado, _ = _dono()
    d = _daemon(modo)
    ficam, _ = bp.rotear(d, None, frozenset({"dpad_down", "cross", "square"}))
    if age:
        assert ficam == frozenset({"square"}), f"no {modo} os botões de navegar não saíram"
        assert teclado.entregas[-1] == frozenset({"dpad_down", "cross"})
    else:
        assert ficam == frozenset({"dpad_down", "cross", "square"}), (
            f"no {modo} a Steam lê o físico, e o Hefesto roubou botão")
        assert teclado.entregas == []


# 2 ─ O foco da Steam e o interruptor decidem ───────────────────────────────


def test_2_so_com_a_steam_na_frente() -> None:
    bp, teclado, _ = _dono()
    sozinho = frozenset({"dpad_up", "square"})
    fora = _daemon(hotkey.PONTE_DUALSENSE, classe="firefox")
    assert bp.rotear(fora, None, sozinho) == (sozinho, frozenset())
    sem_janela = _daemon(hotkey.PONTE_DUALSENSE, classe=None)
    assert bp.rotear(sem_janela, None, sozinho) == (sozinho, frozenset())
    jogo = _daemon(hotkey.PONTE_DUALSENSE, classe="steam_app_1234")
    assert bp.rotear(jogo, None, sozinho) == (sozinho, frozenset()), (
        "dentro de um jogo da Steam o Big Picture não está na frente")
    assert teclado.entregas == []
    for classe in ("steam", "steamwebhelper"):
        d = _daemon(hotkey.PONTE_DUALSENSE, classe=classe)
        assert bp.rotear(d, None, sozinho)[0] == frozenset({"square"}), classe


def test_2_desligado_nao_faz_nada_e_nao_abre_teclado() -> None:
    bp, teclado, _ = _dono(ligado=False)
    d = _daemon(hotkey.PONTE_XBOX)
    botoes = frozenset({"dpad_up", "cross"})
    assert bp.rotear(d, None, botoes) == (botoes, frozenset())
    assert teclado.entregas == [] and bp._teclado is None


def test_2_sair_da_steam_solta_a_tecla_e_devolve_os_botoes() -> None:
    bp, teclado, _ = _dono()
    na_steam = _daemon(hotkey.PONTE_DUALSENSE)
    bp.rotear(na_steam, None, frozenset({"dpad_down"}))
    assert teclado.entregas[-1] == frozenset({"dpad_down"})
    fora = _daemon(hotkey.PONTE_DUALSENSE, classe="firefox")
    ficam, _ = bp.rotear(fora, None, frozenset({"dpad_down"}))
    assert ficam == frozenset({"dpad_down"}), "fora da Steam o direcional tem de voltar ao pad"
    assert teclado.entregas[-1] == frozenset(), "a tecla ficou presa ao sair da Steam"


def test_2_desligar_solta_tudo_e_fecha_o_teclado() -> None:
    bp, teclado, _ = _dono()
    bp.rotear(_daemon(hotkey.PONTE_DUALSENSE), None, frozenset({"cross"}))
    bp.definir(False)
    assert teclado.parado and bp._teclado is None
    assert bp.ligado is False


# 3 ─ Um caminho só, e o toque curto ────────────────────────────────────────


def test_3_so_o_direcional_a_cruz_e_o_circulo_viram_tecla() -> None:
    # A decisão D-0810-O-MODO-BIG-PICTURE-NASCE-DESLIGADO.
    from hefesto_dualsense4unix.integrations.uinput_keyboard import SUPPORTED_KEYS

    assert dono.BOTOES_QUE_NAVEGAM == NAVEGAM
    assert dono.TECLAS == {
        "dpad_up": ("KEY_UP",), "dpad_down": ("KEY_DOWN",), "dpad_left": ("KEY_LEFT",),
        "dpad_right": ("KEY_RIGHT",), "cross": ("KEY_ENTER",), "circle": ("KEY_ESC",)}
    for teclas in dono.TECLAS.values():
        assert set(teclas) <= set(SUPPORTED_KEYS), "o teclado virtual não tem a tecla"
    bp, _, _ = _dono()
    resto = frozenset({"square", "triangle", "r1", "l1", "r2_btn", "l2_btn", "start"})
    ficam, _ = bp.rotear(_daemon(hotkey.PONTE_DUALSENSE), None, NAVEGAM | resto)
    assert ficam == resto, "um botão que não navega saiu do pad"


def test_3_o_toque_curto_vira_aperto_e_solta() -> None:
    bp, teclado, _ = _dono()
    d = _daemon(hotkey.PONTE_XBOX)
    ficam, soltos = bp.rotear(d, None, frozenset(), frozenset({"cross", "square"}))
    assert soltos == frozenset({"square"}), "o toque da Cruz tem de sair da lista de soltos"
    assert ficam == frozenset()
    assert teclado.entregas == [frozenset({"cross"}), frozenset()], teclado.entregas


# 4 ─ P1 a P4: a tecla é a união das fontes ─────────────────────────────────


def test_4_o_p2_e_o_p3_navegam_o_big_picture() -> None:
    bp, teclado, _ = _dono()
    d = _daemon(hotkey.PONTE_DUALSENSE)
    bp.rotear(d, None, frozenset({"dpad_up"}))
    bp.rotear(d, P2, frozenset({"cross"}))
    assert teclado.entregas[-1] == frozenset({"dpad_up", "cross"})
    bp.rotear(d, P3, frozenset({"circle", "dpad_up"}))
    assert teclado.entregas[-1] == frozenset({"dpad_up", "cross", "circle"})
    bp.rotear(d, P2, frozenset())
    assert teclado.entregas[-1] == frozenset({"dpad_up", "circle"}), (
        "soltar a Cruz do P2 não podia soltar a seta que o P1 e o P3 seguram")


def test_4_a_fonte_que_some_nao_deixa_a_tecla_presa() -> None:
    bp, teclado, relogio = _dono()
    d = _daemon(hotkey.PONTE_DUALSENSE)
    bp.rotear(d, P2, frozenset({"dpad_down"}))
    relogio.agora += dono.VALIDADE_DA_FONTE_S + 0.1
    bp.rotear(d, None, frozenset())
    assert teclado.entregas[-1] == frozenset(), "o P2 saiu e a seta ficou apertada"


# 5 ─ Sem teclado virtual, nada é roubado ───────────────────────────────────


def test_5_sem_uinput_o_hefesto_nao_rouba_botao_nenhum() -> None:
    bp, _, _ = _dono(teclado=_Teclado(abre=False))
    d = _daemon(hotkey.PONTE_DUALSENSE)
    botoes = frozenset({"dpad_up", "cross"})
    assert bp.rotear(d, None, botoes) == (botoes, frozenset()), (
        "sem teclado para entregar, o botão sumiu do pad e não foi a lugar nenhum")
    assert bp._falhou is True


# 6 ─ O bloco que a tela lê ────────────────────────────────────────────────


def test_6_o_bloco_diz_ligado_agindo_e_quem_le() -> None:
    bp, _, _ = _dono()
    assert bp.bloco(_daemon(hotkey.PONTE_DUALSENSE)) == {
        "ligado": True, "agindo": True, "quem_le": "hefesto"}
    assert bp.bloco(_daemon(hotkey.MODO_NATIVO)) == {
        "ligado": True, "agindo": False, "quem_le": "steam"}
    assert bp.bloco(_daemon(hotkey.PONTE_XBOX, classe="firefox"))["agindo"] is False
    apagado, _, _ = _dono(ligado=False)
    assert apagado.bloco(_daemon(hotkey.PONTE_XBOX)) == {
        "ligado": False, "agindo": False, "quem_le": None}


# 7 ─ A escolha é da máquina, e vive entre sessões ──────────────────────────


def test_7_a_escolha_e_guardada_e_nasce_desligada() -> None:
    # A decisão D-0810-O-MODO-BIG-PICTURE-NASCE-DESLIGADO.
    from hefesto_dualsense4unix.utils.session import load_big_picture

    assert load_big_picture() is False, "sem arquivo, o Modo Big Picture nasce desligado"
    assert dono.BigPicture.da_sessao().ligado is False
    bp, _, _ = _dono(ligado=False)
    bp.definir(True)
    assert load_big_picture() is True
    assert dono.BigPicture.da_sessao().ligado is True
    bp.definir(False)
    assert load_big_picture() is False


def test_7_o_daemon_define_e_devolve_o_bloco() -> None:
    d = Daemon(controller=FakeController(transport="bt"), config=DaemonConfig())
    antes = d.config.mouse_emulation_enabled
    bloco = d.definir_o_big_picture(True)
    assert bloco["ligado"] is True and set(bloco) == {"ligado", "agindo", "quem_le"}
    assert d.config.mouse_emulation_enabled == antes, "ligar o Big Picture mexeu no mouse"
    from hefesto_dualsense4unix.utils.session import load_big_picture

    assert load_big_picture() is True
    assert d.definir_o_big_picture(False)["ligado"] is False
    assert load_big_picture() is False


# 8 ─ O gesto da aba chama o dono, e a lista não está mais entre os sem dono ─


class _PonteQueAnota:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **kw: Any) -> dict[str, Any]:
        self.chamadas.append((metodo, kw))
        return {"status": "ok"}


def test_8_quem_navega_liga_e_desliga_pelo_daemon() -> None:
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06

    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    ponte = _PonteQueAnota()
    for gesto, valor in (("quem-navega", a06.QUEM_STEAM), ("quem-navega", a06.QUEM_HEFESTO),
                         ("na-steam", a06.NA_STEAM_BIG_PICTURE)):
        fn = pacotes.gesto_da_pagina("06-navegacao.html", gesto)
        assert fn is not None, f"o gesto «{gesto}» da 06 continua sem atendente"
        fn(ctx, {"valor": valor}, ponte)
    assert ponte.chamadas == [
        ("navegacao.big_picture.set", {"ligado": True, "origin": "manual"}),
        ("navegacao.big_picture.set", {"ligado": False, "origin": "manual"}),
        ("navegacao.big_picture.set", {"ligado": True, "origin": "manual"})]
    quem = pacotes.gesto_da_pagina("06-navegacao.html", "quem-navega")
    with pytest.raises(ValueError):
        quem(ctx, {"valor": "Talvez"}, ponte)


def test_8_a_tela_pinta_o_que_o_daemon_diz_e_nao_afirma_sem_ele() -> None:
    from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06

    ligado = {"navegacao": {"interna_ligada": False, "tipo": "interna", "foco": False,
                            "big_picture": {"ligado": True, "agindo": False,
                                            "quem_le": "hefesto"}}}
    desligado = {"navegacao": {"interna_ligada": False, "tipo": "interna", "foco": False,
                               "big_picture": {"ligado": False}}}
    assert a06.big_picture_ligado(ligado) is True
    assert a06.big_picture_ligado(desligado) is False
    assert a06.big_picture_ligado({}) is None, "sem o bloco do daemon a tela afirmou um lado"
    assert a06.big_picture_ligado({"navegacao": {"tipo": "interna"}}) is None


def test_8_o_big_picture_esta_no_metodo_e_na_prova_da_aba() -> None:
    from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06

    assert "navegacao.big_picture.set" in a06.METODOS
    provas = [p for p in a06.PROVAS if p["gesto"] == "quem-navega"]
    assert {p["chama"][0][2]["ligado"] for p in provas} == {True, False}


# 9 ─ O IPC: handler, despacho e estado ─────────────────────────────────────


def test_9_o_metodo_esta_no_despacho_e_o_handler_valida() -> None:
    from hefesto_dualsense4unix.daemon import ipc_server
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    fonte = inspect.getsource(ipc_server)
    assert '"navegacao.big_picture.set": self._handle_navegacao_big_picture_set' in fonte
    handler = IpcHandlersMixin._handle_navegacao_big_picture_set

    class _Eu:
        daemon = Daemon(controller=FakeController(transport="bt"), config=DaemonConfig())

    ok = asyncio.run(handler(_Eu(), {"ligado": True, "origin": "manual"}))  # type: ignore[arg-type]
    assert ok["status"] == "ok" and ok["big_picture"]["ligado"] is True
    for ruim in ({}, {"ligado": "sim"}, {"ligado": 1}):
        with pytest.raises(ValueError):
            asyncio.run(handler(_Eu(), ruim))  # type: ignore[arg-type]
    sem_dono = type("_SemDono", (), {"daemon": SimpleNamespace()})()
    with pytest.raises(ValueError):
        asyncio.run(handler(sem_dono, {"ligado": True}))


def test_9_o_state_full_traz_o_bloco_dentro_do_navegacao() -> None:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    d = Daemon(controller=FakeController(transport="bt"), config=DaemonConfig())
    d.definir_a_navegacao_interna(ligada=False)
    d.definir_o_big_picture(True)

    class _Eu:
        daemon = d
        _navegacao_payload = IpcHandlersMixin._navegacao_payload

    bloco = _Eu()._navegacao_payload()  # type: ignore[no-untyped-call]
    assert bloco is not None and bloco["big_picture"]["ligado"] is True


# 10 ─ Os três lugares onde o botão sai do controle chamam o dono ────────────


class _Pad:
    def __init__(self) -> None:
        self.buttons: list[frozenset[str]] = []

    def forward_analog(self, **kw: int) -> None:
        pass

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


def _ligado_no_daemon(teclado: _Teclado) -> dono.BigPicture:
    return dono.BigPicture(ligado=True, teclado=lambda: teclado)


def test_10_o_primario_com_o_pad_virtual_nao_manda_a_seta_ao_pad(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0), window_detect_current_class=STEAM)
    remap.definir_ativo(store, None)
    pad = _Pad()
    teclado = _Teclado()
    estado = SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=0, r2_raw=0)
    daemon = SimpleNamespace(store=store, _gamepad_device=pad, _big_picture=_ligado_no_daemon(
        teclado), _modo_de_mentira=hotkey.PONTE_DUALSENSE)
    gp.dispatch_gamepad(daemon, estado, frozenset({"dpad_down", "r2_btn"}))
    assert pad.buttons == [frozenset({"r2_btn"})], f"o primário mandou {pad.buttons} ao pad"
    assert teclado.entregas[-1] == frozenset({"dpad_down"})


def test_10_o_secundario_navega_o_big_picture_e_o_analogico_segue() -> None:
    store = SimpleNamespace(window_detect_current_class=STEAM)
    remap.definir_ativo(store, None)
    teclado = _Teclado()
    daemon = SimpleNamespace(
        store=store, controller=SimpleNamespace(), identity_registry=None,
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(), _coop_manager=None, _navegacao_interna=None,
        _big_picture=_ligado_no_daemon(teclado), _modo_de_mentira=hotkey.PONTE_XBOX)
    mgr = CoopManager(daemon)
    snap = SimpleNamespace(lx=200, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                           buttons_pressed=frozenset({"cross", "l2_btn"}))
    pad = _Pad()
    mgr._players[P2] = _SecondaryPlayer(
        identity=P2, evdev_path="/dev/input/event9",
        reader=SimpleNamespace(grab_state="held", snapshot=lambda: snap),
        player_index=2, vpad=pad)  # type: ignore[arg-type]
    mgr.forward_all()
    assert pad.buttons == [frozenset({"l2_btn"})], f"o P2 mandou {pad.buttons} ao pad"
    assert teclado.entregas[-1] == frozenset({"cross"}), "a Cruz do P2 não virou Enter"


def test_10_o_laco_do_mouse_passa_os_botoes_pelo_dono_antes_do_despacho() -> None:
    fonte = inspect.getsource(Daemon._poll_loop)
    levar = fonte.find("levar_o_big_picture(self, None, emu_buttons)")
    despacho = fonte.find("_dispatch_mouse_emulation(state, emu_buttons)")
    assert levar != -1 and despacho != -1 and levar < despacho, (
        "o mouse virtual (Navegação) recebe a seta antes de o Big Picture ficar com ela")
    assert "levar_o_big_picture(self, None, frozenset())" in fonte, (
        "o controle que cai com a seta apertada deixa a tecla presa")


def test_10_o_daemon_nasce_com_o_dono() -> None:
    assert "_big_picture" in Daemon.__dataclass_fields__ or hasattr(Daemon, "_big_picture")
    fonte = inspect.getsource(Daemon)
    assert "BigPicture.da_sessao()" in fonte


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_10_a_parada_do_daemon_fecha_o_teclado_do_dono(transporte: str) -> None:
    """Pelo cabo e pelo rádio: o daemon que para fecha o teclado do Big Picture.

    O teclado é device privado do dono, como os dois da tabela que age com o jogo, e
    a parada os fecha no mesmo `finally` do `Daemon.run`.
    MORDIDA: tirar o `parar()` do `finally` do `Daemon.run` deixa o teclado aberto.
    """
    from unittest.mock import MagicMock

    bp, teclado, _ = _dono()
    bp.rotear(_daemon(hotkey.PONTE_DUALSENSE), None, frozenset({"cross"}))
    assert bp._teclado is teclado and not teclado.parado
    d = Daemon(
        controller=FakeController(transport=transporte),
        config=DaemonConfig(
            poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    d._gamepad_device = MagicMock()
    d._dispatch_gamepad_emulation = lambda estado, botoes: None  # type: ignore[method-assign]
    d._big_picture = bp

    async def _rodar_e_parar() -> None:
        tarefa = asyncio.create_task(d.run())
        for _ in range(500):
            if d._stop_event is not None:
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        d.stop()
        await asyncio.wait_for(tarefa, 10)

    asyncio.run(_rodar_e_parar())
    assert teclado.parado and bp._teclado is None, (
        f"pelo {transporte}, a parada do daemon deixou o teclado do Big Picture aberto")
