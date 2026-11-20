"""O-PERFIL-COM-TECLA-LIGA-O-TECLADO-01: o perfil que manda tecla liga o teclado virtual.

Duas causas, duas curas, e o instrumento é o daemon real (subclasse que só troca o
nascimento do device de teclado por um que anota, sem uinput):

1. a ativação e o `profile.reaplicar` resolvem o `teclado_emulado` do perfil pelo mesmo
   `resolver_teclado_emulado` do arranjo do desktop, e o device que nasce aí já leva as
   `key_bindings` do perfil; o arranjo liga o teclado antes de aplicar as tabelas;
2. o «Guardar» do Mapa do controle grava `teclado_emulado: true` quando alguma escolha do
   perfil é tecla e o perfil não tem opinião; quem desligou à mão continua desligado.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.xdg_paths import config_dir

NOME = "Perfil das Teclas"
COM_TECLA = {"cross": ["KEY_SPACE"]}


class _Teclado:
    """O device de teclado de mentira: anota o que recebeu, nunca toca o uinput."""

    def __init__(self) -> None:
        self.bindings: list[dict[str, Any]] = []
        self.parado = False

    def set_bindings(self, mapping: Any) -> None:
        self.bindings.append(dict(mapping))

    def set_button_actions(self, *args: Any, **kwargs: Any) -> None:
        return None

    def stop(self) -> None:
        self.parado = True


class _Daemon(Daemon):
    """O daemon real; só o nascimento e a morte do device de teclado são do dublê."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.nasceram: list[_Teclado] = []

    def _start_keyboard_emulation(self) -> bool:
        if self._keyboard_device is None and self.config.keyboard_emulation_enabled:
            teclado = _Teclado()
            self.nasceram.append(teclado)
            self._keyboard_device = teclado
        return self._keyboard_device is not None

    def _stop_keyboard_emulation(self) -> None:
        if self._keyboard_device is not None:
            self._keyboard_device.stop()
        self._keyboard_device = None

    def set_mouse_emulation(self, *args: Any, **kwargs: Any) -> bool:
        return True

    def set_emulation_suppressed(self, *args: Any, **kwargs: Any) -> bool:
        return True


def _flag_global(ligado: bool | None) -> None:
    alvo = Path(config_dir()) / "keyboard_emulation.flag"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if ligado is None:
        alvo.unlink(missing_ok=True)
    else:
        alvo.write_text(json.dumps({"enabled": ligado}), encoding="utf-8")


def _perfil(nome: str = NOME, **campos: Any) -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    corpo = {"name": nome, "match": {"type": "any"}, "key_bindings": COM_TECLA, **campos}
    loader.save_profile(Profile.model_validate(corpo))


def _daemon() -> _Daemon:
    return _Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(keyboard_emulation_enabled=False),
    )


def _reaplicar(d: _Daemon, nome: str = NOME) -> dict[str, str]:
    relatorio: dict[str, str] = {}
    gerente_do_daemon(d, mode_applier=None).reaplicar(nome, relatorio=relatorio)
    return relatorio


def test_o_reaplicar_liga_o_teclado_do_perfil_com_o_global_desligado() -> None:
    """D-2011-O-PERFIL-COM-TECLA-LIGA-O-TECLADO: o perfil com opinião vence o global."""
    _flag_global(False)
    _perfil(teclado_emulado=True)
    d = _daemon()

    _reaplicar(d)

    assert d._keyboard_device is not None, "o perfil diz teclado ligado e o device não nasceu"
    assert d._keyboard_device.bindings, "o device nasceu sem as ligações do perfil"
    assert "cross" in d._keyboard_device.bindings[-1]


def test_a_ativacao_do_lancamento_liga_o_teclado_do_perfil() -> None:
    _flag_global(False)
    _perfil(teclado_emulado=True)
    d = _daemon()

    gerente_do_daemon(d, mode_applier=None).activate(NOME, origin="launch")

    assert d._keyboard_device is not None
    assert "cross" in d._keyboard_device.bindings[-1]


def test_o_perfil_sem_opiniao_deixa_o_global_mandar_e_nao_cria_device() -> None:
    _flag_global(False)
    _perfil()
    d = _daemon()

    _reaplicar(d)

    assert d._keyboard_device is None
    assert d.nasceram == []


def test_o_perfil_com_false_derruba_o_teclado_que_o_global_deixou_ligado() -> None:
    _flag_global(True)
    _perfil(teclado_emulado=False)
    d = _daemon()
    d.config.keyboard_emulation_enabled = True
    d._start_keyboard_emulation()
    assert d._keyboard_device is not None

    _reaplicar(d)

    assert d._keyboard_device is None, "o perfil com `teclado_emulado: false` deixou o device de pé"


def test_o_perfil_seguinte_sem_opiniao_devolve_o_teclado_ao_global() -> None:
    _flag_global(False)
    _perfil("Com Tecla", teclado_emulado=True)
    _perfil("Sem Opiniao")
    d = _daemon()

    _reaplicar(d, "Com Tecla")
    assert d._keyboard_device is not None
    _reaplicar(d, "Sem Opiniao")

    assert d._keyboard_device is None, (
        "a opinião do perfil anterior ficou: o global desligado manda no perfil sem opinião")


def test_a_opiniao_do_perfil_nao_vira_a_preferencia_global() -> None:
    _flag_global(False)
    _perfil(teclado_emulado=True)
    d = _daemon()

    _reaplicar(d)

    corpo = json.loads((Path(config_dir()) / "keyboard_emulation.flag").read_text("utf-8"))
    assert corpo == {"enabled": False}


def test_o_arranjo_do_desktop_liga_o_teclado_antes_das_tabelas() -> None:
    _flag_global(False)
    _perfil(teclado_emulado=True)
    d = _daemon()
    d.store.set_active_profile(NOME)

    relatorio = d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo="navegacao")

    assert relatorio.get("keyboard") != "ignorado_sem_device", relatorio
    assert d._keyboard_device is not None
    assert "cross" in d._keyboard_device.bindings[-1]


def _ctx() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state={"active_profile": NOME}, mesa=[], conectados=[], escolhido="")


@pytest.fixture
def mapa() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13

    a13._largar()
    yield a13
    a13._largar()


def _guardar_a_cruz_em(mapa: Any, valor: str) -> Any:
    from hefesto_dualsense4unix.profiles import loader

    ctx = _ctx()
    mapa.mapa_botao(ctx, {"b": "cross"}, None)
    mapa.mapa_escolher(ctx, {"v": f"acao:{valor}"}, None)  # (noqa-acento)
    mapa.mapa_guardar(ctx, {}, MagicMock())
    return loader.load_profile(NOME)


def test_guardar_tecla_num_perfil_sem_opiniao_liga_o_teclado_do_perfil(mapa: Any) -> None:
    """D-2011-O-PERFIL-COM-TECLA-LIGA-O-TECLADO: o Guardar com tecla grava o teclado ligado."""
    _perfil(key_bindings=None)

    gravado = _guardar_a_cruz_em(mapa, "KEY_SPACE")

    assert gravado.button_actions == {"cross": "KEY_SPACE"}
    assert gravado.teclado_emulado is True


def test_guardar_o_analogico_em_wasd_liga_o_teclado_do_perfil(mapa: Any) -> None:
    _perfil(key_bindings=None)
    from hefesto_dualsense4unix.profiles import loader

    ctx = _ctx()
    mapa.mapa_botao(ctx, {"b": "l3_direcao"}, None)
    mapa.mapa_escolher(ctx, {"v": "acao:__WASD__"}, None)  # (noqa-acento)
    mapa.mapa_guardar(ctx, {}, MagicMock())

    assert loader.load_profile(NOME).teclado_emulado is True


def test_guardar_tecla_respeita_o_false_gravado_no_perfil(mapa: Any) -> None:
    _perfil(key_bindings=None, teclado_emulado=False)

    gravado = _guardar_a_cruz_em(mapa, "KEY_SPACE")

    assert gravado.button_actions == {"cross": "KEY_SPACE"}
    assert gravado.teclado_emulado is False


def test_guardar_so_mouse_nao_liga_o_teclado(mapa: Any) -> None:
    _perfil(key_bindings=None)

    gravado = _guardar_a_cruz_em(mapa, "BTN_RIGHT")

    assert gravado.button_actions == {"cross": "BTN_RIGHT"}
    assert gravado.teclado_emulado is None

