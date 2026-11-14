"""O jogo aberto por fora do lançador, com perfil sem `mode`, não herda a Navegação.

O-JOGO-SEM-ARME-NAO-HERDA-A-NAVEGACAO-01 (14/11/2026). Com a Navegação em vigor, o perfil de
jogo sem `mode` caía no ramo «sem opinião» do applier, que com a janela do jogo em foco não
mexe em nada: o controle seguia em teclado e mouse dentro do jogo. A cura resolve, no
`Daemon.apply_profile_mode`, o modo de jogo do estilo do perfil (`estilos_de_jogo`): o estilo
com modo dá a Navegação com o arranjo dele, todo outro dá o controle de jogo com a máscara do
computador. O modo é do daemon, um só para os quatro controles e os dois transportes.

MORDIDAS: tire a linha `mode = _o_modo_do_jogo_sem_arme(...)` de `apply_profile_mode` e o
jogo volta a herdar a Navegação; troque o modo do estilo por `None` e o Point and click
deixa de abrir no arranjo dele.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.lifecycle import (
    MODO_NAVEGACAO,
    MODO_XBOX,
    Daemon,
    DaemonConfig,
    modo_do_controle,
)
from hefesto_dualsense4unix.daemon.subsystems.gamepad import EMU_APLICADO, EMU_DESLIGADO
from hefesto_dualsense4unix.profiles.schema import Profile, ProfileModeConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController

APPID_FORJADO = 9942223
CLASSE_DO_JOGO = f"steam_app_{APPID_FORJADO}"


def _perfil_do_jogo(estilo: str | None = None, mode: dict[str, Any] | None = None) -> Profile:
    dados: dict[str, Any] = {
        "name": "Jogo forjado",
        "match": {"type": "criteria", "window_class": [CLASSE_DO_JOGO]},
        "priority": 80,
    }
    if estilo is not None:
        dados["estilo"] = estilo
    if mode is not None:
        dados["mode"] = mode
    return Profile.model_validate(dados)


def _perfil_da_navegacao() -> Profile:
    return Profile.model_validate({
        "name": "Navegar no computador",
        "match": {"type": "criteria", "window_class": ["firefox"]},
        "priority": 10,
        "mode": {"kind": "desktop"},
    })


class _Vpad:
    def __init__(self, flavor: str) -> None:
        self.flavor = flavor
        self.backend = "uhid" if flavor == "dualsense" else "uinput"


def _daemon(monkeypatch: pytest.MonkeyPatch, *, transporte: str, mascara: str) -> Daemon:
    d = Daemon(controller=FakeController(transport=transporte), config=DaemonConfig())  # type: ignore[arg-type]
    monkeypatch.setattr(lifecycle, "_mascara_da_maquina", lambda: mascara)

    def pad(enabled: bool, flavor: str | None = None, *, origin: str = "manual") -> str:
        d.config.gamepad_emulation_enabled = enabled
        d._gamepad_device = _Vpad(flavor or mascara) if enabled else None
        return EMU_APLICADO if enabled else EMU_DESLIGADO

    def pad_bool(enabled: bool, flavor: str | None = None, *, origin: str = "manual") -> bool:
        pad(enabled, flavor, origin=origin)
        return True

    def nativo(enabled: bool, *, reapply: bool = True, restore_stash: bool = False,
               origin: str = "manual") -> bool:
        d._native_mode = enabled
        d.store.set_native_mode_active(enabled, origin=origin)
        return enabled

    monkeypatch.setattr(d, "set_gamepad_emulation_desfecho", pad)
    monkeypatch.setattr(d, "set_gamepad_emulation", pad_bool)
    monkeypatch.setattr(d, "set_native_mode", nativo)
    return d


def _na_navegacao(d: Daemon) -> None:
    d.store.record_window_detect_read("teste", "firefox")
    d.apply_profile_mode(_perfil_da_navegacao().mode, profile=_perfil_da_navegacao(),
                         origin="autoswitch")
    assert modo_do_controle(d, d._gamepad_device) == MODO_NAVEGACAO


def _abre_o_jogo_sem_arme(d: Daemon, perfil: Profile) -> str:
    d.store.record_window_detect_read("teste", CLASSE_DO_JOGO)
    return d.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")


TRANSPORTES = ("usb", "bt")
MASCARAS = ("dualsense", "xbox")


@pytest.mark.parametrize("transporte", TRANSPORTES)
@pytest.mark.parametrize("mascara", MASCARAS)
@pytest.mark.parametrize("estilo", [None, "fps", "nativo", "personalizado", "terror"])
def test_o_jogo_sem_mode_sai_da_navegacao_para_o_modo_de_jogo(
    monkeypatch: pytest.MonkeyPatch, transporte: str, mascara: str, estilo: str | None
) -> None:
    d = _daemon(monkeypatch, transporte=transporte, mascara=mascara)
    _na_navegacao(d)

    _abre_o_jogo_sem_arme(d, _perfil_do_jogo(estilo))

    assert d.config.gamepad_emulation_enabled is True
    assert d._gamepad_device is not None and d._gamepad_device.flavor == mascara
    assert modo_do_controle(d, d._gamepad_device) != MODO_NAVEGACAO
    assert d._mode_from_profile == "gamepad"


@pytest.mark.parametrize("transporte", TRANSPORTES)
def test_a_navegacao_vale_de_novo_quando_volta_a_ser_o_perfil_ativo(
    monkeypatch: pytest.MonkeyPatch, transporte: str
) -> None:
    d = _daemon(monkeypatch, transporte=transporte, mascara="xbox")
    _na_navegacao(d)
    _abre_o_jogo_sem_arme(d, _perfil_do_jogo())
    assert modo_do_controle(d, d._gamepad_device) == MODO_XBOX

    _na_navegacao(d)

    assert d._gamepad_device is None


@pytest.mark.parametrize("estilo, arranjo", [("point_and_click", "point_and_click"),
                                             ("visual_novel", "navegacao")])
def test_o_estilo_de_navegacao_abre_no_arranjo_dele(
    monkeypatch: pytest.MonkeyPatch, estilo: str, arranjo: str
) -> None:
    d = _daemon(monkeypatch, transporte="usb", mascara="dualsense")
    d.set_gamepad_emulation_desfecho(True, "dualsense")

    _abre_o_jogo_sem_arme(d, _perfil_do_jogo(estilo))

    assert d._gamepad_device is None
    assert d._arranjo_do_perfil == arranjo


def test_o_mode_que_o_perfil_diz_vale_acima_do_estilo(monkeypatch: pytest.MonkeyPatch) -> None:
    d = _daemon(monkeypatch, transporte="bt", mascara="dualsense")
    _na_navegacao(d)

    _abre_o_jogo_sem_arme(d, _perfil_do_jogo("fps", {"kind": "desktop"}))

    assert d._gamepad_device is None


def test_o_perfil_que_nao_e_de_jogo_segue_sem_opiniao(monkeypatch: pytest.MonkeyPatch) -> None:
    d = _daemon(monkeypatch, transporte="usb", mascara="dualsense")
    _na_navegacao(d)
    app = Profile.model_validate({
        "name": "Um app", "match": {"type": "criteria", "window_class": ["app_de_desktop"]},
    })
    d.store.record_window_detect_read("teste", "app_de_desktop")

    d.apply_profile_mode(None, profile=app, origin="autoswitch")

    assert d._gamepad_device is None


def test_o_nativo_que_o_usuario_ligou_nao_cai_pelo_jogo_sem_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d = _daemon(monkeypatch, transporte="usb", mascara="dualsense")
    d.set_native_mode(True, origin="manual")

    _abre_o_jogo_sem_arme(d, _perfil_do_jogo())

    assert d._native_mode is True
    assert d._gamepad_device is None


def test_a_secao_resolvida_e_a_do_estilo() -> None:
    assert lifecycle._o_modo_do_jogo_sem_arme(_perfil_do_jogo("point_and_click"), None) == (
        ProfileModeConfig(kind="desktop", arranjo="point_and_click")
    )
    assert lifecycle._o_modo_do_jogo_sem_arme(_perfil_da_navegacao(), None) is None


class _ConfigDoBoot:
    gamepad_emulation_enabled = False
    mouse_emulation_enabled = True


class _DaemonDoBoot:
    store = None
    appid_em_cena = APPID_FORJADO

    def __init__(self) -> None:
        self.config = _ConfigDoBoot()


@pytest.mark.parametrize("mascara", MASCARAS)
@pytest.mark.parametrize("estilo", [None, "fps", "terror"])
def test_o_boot_com_o_jogo_sem_mode_nasce_com_o_pad(
    monkeypatch: pytest.MonkeyPatch, mascara: str, estilo: str | None
) -> None:
    """O reinício com o jogo em cena (ou o último) sem `mode`: o pad nasce, na máscara da
    máquina, e o mouse não. MORDIDA: devolva o `perfil.mode` cru ao boot e ele nasce no mouse."""
    from hefesto_dualsense4unix.daemon import connection

    perfil = _perfil_do_jogo(estilo)
    monkeypatch.setattr(lifecycle, "_mascara_da_maquina", lambda: mascara)
    monkeypatch.setattr(connection, "o_jogo_que_o_boot_restaura", lambda *_a, **_k: perfil)
    monkeypatch.setattr(connection, "perfil_que_o_boot_restaura", lambda *_a, **_k: perfil)
    d = _DaemonDoBoot()

    assert lifecycle._o_pad_do_jogo_volta_no_boot(d, perfil.name) is True
    assert d.config.gamepad_emulation_enabled is True
    assert d.config.mouse_emulation_enabled is False
    assert lifecycle._o_modo_do_perfil_do_boot(None)[1:] == (mascara, perfil.name)


def test_o_boot_com_o_jogo_de_navegacao_nao_liga_o_pad(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon import connection

    perfil = _perfil_do_jogo("point_and_click")
    monkeypatch.setattr(connection, "o_jogo_que_o_boot_restaura", lambda *_a, **_k: perfil)
    monkeypatch.setattr(connection, "perfil_que_o_boot_restaura", lambda *_a, **_k: perfil)
    d = _DaemonDoBoot()

    assert lifecycle._o_pad_do_jogo_volta_no_boot(d, perfil.name) is False
    assert d.config.gamepad_emulation_enabled is False
    assert lifecycle._o_modo_do_perfil_do_boot(None) == (None, None, perfil.name)
