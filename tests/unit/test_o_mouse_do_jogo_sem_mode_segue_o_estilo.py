"""O mouse do jogo sem `mode` segue o estilo dele, como o modo.

O-MOUSE-DO-JOGO-SEM-MODE-SEGUE-O-ESTILO-01 (14/11/2026). O sem-arme fez o modo do perfil de jogo
sem `mode` sair do estilo (`o_modo_do_jogo_sem_mode`), mas o liga do mouse lia o `mode` cru, no
`ProfileManager.apply_emulation` e no `Daemon.apply_profile_mouse`: o Point and click ou a
Visual novel aberto vindo do gamepad desligava o pad e não ligava o mouse, e o controle ficava
sem saída. A cura faz os três perguntarem ao mesmo dono.

A régua passa pela ativação inteira (`apply_emulation` com os appliers do daemon). O modo e o
mouse são do daemon, um só para os quatro controles: nenhum dos appliers recebe o jogador, e o
que vale para um vale de P1 a P4.

MORDIDAS: devolva o `getattr(profile, "mode")` cru ao `apply_emulation` e o mouse não é
chamado; devolva-o ao `Daemon.apply_profile_mouse` e o mouse «não opina»; tire dele o
`_o_jogo_sem_mode_ganha_o_estilo` e o Nativo que o usuário ligou ganha o mouse por baixo.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.gamepad import EMU_APLICADO, EMU_DESLIGADO
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import Profile, ProfileModeConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController

APPID_FORJADO = 9942229
CLASSE_DO_JOGO = f"steam_app_{APPID_FORJADO}"
TRANSPORTES = ("usb", "bt")
MASCARAS = ("dualsense", "xbox")
ESTILOS_DO_MOUSE = ("point_and_click", "visual_novel")


def _perfil_do_jogo(
    estilo: str | None, *, mouse: bool = False, mode: dict[str, Any] | None = None
) -> Profile:
    dados: dict[str, Any] = {
        "name": f"Jogo forjado {estilo}",
        "match": {"type": "criteria", "window_class": [CLASSE_DO_JOGO]},
        "priority": 80,
    }
    if estilo is not None:
        dados["estilo"] = estilo
    if mouse:
        dados["mouse"] = {"enabled": True, "speed": 6, "scroll_speed": 1}
    if mode is not None:
        dados["mode"] = mode
    return Profile.model_validate(dados)


class _Vpad:
    def __init__(self, flavor: str) -> None:
        self.flavor = flavor


class _Mouse:
    acoes: dict[str, str] | None = None

    def set_speed(self, *, mouse_speed: int, scroll_speed: int) -> None:
        self.velocidades = (mouse_speed, scroll_speed)

    def set_button_actions(
        self, do_mouse: dict[str, str] | None, calados: frozenset[str] | None = None
    ) -> None:
        self.acoes = do_mouse


def _daemon(monkeypatch: pytest.MonkeyPatch, *, transporte: str, mascara: str) -> Daemon:
    """O daemon de verdade com o pad e o mouse virtuais em dublê, na mesma exclusão mútua."""
    d = Daemon(controller=FakeController(transport=transporte), config=DaemonConfig())  # type: ignore[arg-type]
    monkeypatch.setattr(lifecycle, "_mascara_da_maquina", lambda: mascara)

    def mouse(enabled: bool, speed: int | None = None, scroll_speed: int | None = None, *,
              origin: str = "manual") -> bool:
        if enabled and d._gamepad_device is not None:
            pad(False)
        d.config.mouse_emulation_enabled = enabled
        d._mouse_device = _Mouse() if enabled else None
        return True

    def pad(enabled: bool, flavor: str | None = None, *, origin: str = "manual",
            **_k: Any) -> str:
        if enabled and d._mouse_device is not None:
            d.config.mouse_emulation_enabled = False
            d._mouse_device = None
        d.config.gamepad_emulation_enabled = enabled
        d._gamepad_device = _Vpad(flavor or mascara) if enabled else None
        return EMU_APLICADO if enabled else EMU_DESLIGADO

    def pad_bool(enabled: bool, flavor: str | None = None, *, origin: str = "manual",
                 **_k: Any) -> bool:
        pad(enabled, flavor, origin=origin)
        return True

    def nativo(enabled: bool, *, reapply: bool = True, restore_stash: bool = False,
               origin: str = "manual") -> bool:
        d._native_mode = enabled
        d.store.set_native_mode_active(enabled, origin=origin)
        return enabled

    monkeypatch.setattr(d, "set_mouse_emulation", mouse)
    monkeypatch.setattr(d, "set_gamepad_emulation_desfecho", pad)
    monkeypatch.setattr(d, "set_gamepad_emulation", pad_bool)
    monkeypatch.setattr(d, "set_native_mode", nativo)
    monkeypatch.setattr(lifecycle, "_velocidades_ou_as_da_sessao", lambda s, r: (s, r))
    return d


def _manager(d: Daemon) -> ProfileManager:
    return ProfileManager(
        controller=d.controller,
        store=d.store,
        mouse_applier=d.apply_profile_mouse,
        mode_applier=d.apply_profile_mode,
    )


def _abre(d: Daemon, perfil: Profile) -> dict[str, str]:
    d.store.record_window_detect_read("teste", CLASSE_DO_JOGO)
    return _manager(d).apply_emulation(perfil, origin="autoswitch")


def _no_gamepad(d: Daemon, mascara: str) -> None:
    _abre(d, _perfil_do_jogo("fps", mode={"kind": "gamepad", "gamepad_flavor": mascara}))
    assert d._gamepad_device is not None and d._mouse_device is None


@pytest.mark.parametrize("transporte", TRANSPORTES)
@pytest.mark.parametrize("mascara", MASCARAS)
@pytest.mark.parametrize("estilo", ESTILOS_DO_MOUSE)
@pytest.mark.parametrize("com_secao_mouse", [False, True])
def test_do_gamepad_para_o_jogo_de_mouse_sem_mode_o_mouse_liga_e_o_fps_devolve_o_pad(
    monkeypatch: pytest.MonkeyPatch, transporte: str, mascara: str, estilo: str,
    com_secao_mouse: bool,
) -> None:
    d = _daemon(monkeypatch, transporte=transporte, mascara=mascara)
    _no_gamepad(d, mascara)

    _abre(d, _perfil_do_jogo(estilo, mouse=com_secao_mouse))

    assert d._gamepad_device is None
    assert d.config.mouse_emulation_enabled is True and d._mouse_device is not None
    if estilo == "point_and_click":
        assert d._mouse_device.acoes, "os botões do Point and click não chegaram ao mouse"

    _abre(d, _perfil_do_jogo("fps", mouse=com_secao_mouse))

    assert d._mouse_device is None and d.config.mouse_emulation_enabled is False
    assert d._gamepad_device is not None and d._gamepad_device.flavor == mascara


@pytest.mark.parametrize("estilo", [None, "fps", "terror"])
def test_o_jogo_de_pad_sem_mode_nao_liga_o_mouse(
    monkeypatch: pytest.MonkeyPatch, estilo: str | None
) -> None:
    d = _daemon(monkeypatch, transporte="bt", mascara="xbox")
    _no_gamepad(d, "xbox")

    _abre(d, _perfil_do_jogo(estilo, mouse=True))

    assert d._mouse_device is None
    assert d._gamepad_device is not None


def test_o_nativo_que_o_usuario_ligou_nao_ganha_o_mouse_pelo_jogo_sem_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d = _daemon(monkeypatch, transporte="usb", mascara="dualsense")
    d.set_native_mode(True, origin="manual")

    _abre(d, _perfil_do_jogo("point_and_click", mouse=True))

    assert d._native_mode is True
    assert d._mouse_device is None


@pytest.mark.parametrize("transporte", TRANSPORTES)
def test_o_nativo_que_um_perfil_ligou_cede_o_mouse_ao_jogo_de_mouse_sem_mode(
    monkeypatch: pytest.MonkeyPatch, transporte: str
) -> None:
    d = _daemon(monkeypatch, transporte=transporte, mascara="dualsense")
    _abre(d, _perfil_do_jogo("fps", mode={"kind": "native"}))
    assert d._native_mode is True

    _abre(d, _perfil_do_jogo("visual_novel"))

    assert d._native_mode is False
    assert d.config.mouse_emulation_enabled is True and d._mouse_device is not None


@pytest.mark.parametrize("transporte", TRANSPORTES)
def test_a_secao_mouse_desligada_do_jogo_de_mouse_sem_mode_vale_como_no_mode_escrito(
    monkeypatch: pytest.MonkeyPatch, transporte: str
) -> None:
    resultados = []
    for mode in (None, {"kind": "desktop", "arranjo": "point_and_click"}):
        d = _daemon(monkeypatch, transporte=transporte, mascara="xbox")
        _abre(d, _perfil_do_jogo("visual_novel"))
        assert d._mouse_device is not None
        dados = _perfil_do_jogo("point_and_click", mode=mode).model_dump(exclude_unset=True)
        _abre(d, Profile.model_validate({**dados, "mouse": {"enabled": False}}))
        resultados.append((d._mouse_device is None, d._gamepad_device is None))

    assert resultados == [(True, True), (True, True)]


def test_o_mode_escrito_vale_acima_do_estilo(monkeypatch: pytest.MonkeyPatch) -> None:
    d = _daemon(monkeypatch, transporte="usb", mascara="dualsense")
    _no_gamepad(d, "dualsense")

    _abre(d, _perfil_do_jogo("point_and_click", mode={"kind": "gamepad"}))

    assert d._mouse_device is None
    assert d._gamepad_device is not None


def test_o_dono_e_um_so() -> None:
    from hefesto_dualsense4unix.profiles.manager import o_modo_do_jogo_sem_mode

    perfil = _perfil_do_jogo("visual_novel")
    assert o_modo_do_jogo_sem_mode(perfil, None) == ProfileModeConfig(
        kind="desktop", arranjo="navegacao"
    )
    assert o_modo_do_jogo_sem_mode(_perfil_do_jogo("fps"), None, lambda: "xbox") == (
        ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
    )
    assert lifecycle._o_modo_do_jogo_sem_arme(perfil, None) == o_modo_do_jogo_sem_mode(
        perfil, None
    )
