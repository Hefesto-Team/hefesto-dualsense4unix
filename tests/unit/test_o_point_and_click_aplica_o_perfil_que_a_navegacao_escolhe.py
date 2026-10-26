"""O-POINT-AND-CLICK-APLICA-O-PERFIL-QUE-A-NAVEGACAO-ESCOLHE-01 (21/10/2026).

O «Point and click» (Ligado) e a «Navegação» (Desligado) são o mesmo modo `desktop` com tabelas de
botões diferentes (D-2010-O-POINT-AND-CLICK-APLICA-O-PERFIL-ESCOLHIDO, por delegação, a validar
pelo usuário). A Navegação aplica as linhas da aba Navegação do perfil ativo; o Point and click,
a tabela do «Perfil jogo - navegação» (`mouse.point_and_click`: um molde ou um perfil salvo).

O que a régua lê é o que os devices RECEBERAM, pela subclasse do `Daemon` real. O perfil ativo
põe o «quadrado» em KEY_SPACE; o molde Visual novel, em KEY_LEFTCTRL; o de fábrica, em KEY_ESC.
Três valores diferentes, para que nenhum recuo passe por acerto.

A MORDIDA: tire o `**_o_arranjo(arranjo)` do plano em `mode_transition` ou devolva ``base`` no
começo de `Daemon._tabelas_do_arranjo`, e o caso do Point and click recebe KEY_SPACE.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    plan_mode_transition,
)
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.session import (
    ARRANJO_NAVEGACAO,
    ARRANJO_POINT_AND_CLICK,
    config_dir,
    load_arranjo_do_desktop,
)

PERFIL_ATIVO: dict[str, Any] = {
    "name": "Perfil Ativo",
    "match": {"type": "any"},
    "mouse": {"enabled": True, "speed": 9, "scroll_speed": 2,
              "point_and_click": "molde:visual_novel"},
    "button_actions": {"cross": "KEY_ENTER", "square": "KEY_SPACE"},
}

PERFIL_DO_JOGO: dict[str, Any] = {
    "name": "Jogo Navegacao",
    "match": {"type": "any"},
    "button_actions": {"cross": "BTN_LEFT", "square": "KEY_TAB"},
}


class _Teclado:
    def __init__(self) -> None:
        self.bindings: list[dict[str, Any]] = []

    def set_bindings(self, mapping: Any) -> None:
        self.bindings.append(dict(mapping))


class _Mouse:
    def __init__(self) -> None:
        self.acoes: list[dict[str, str] | None] = []

    def set_button_actions(self, do_mouse: Any, calados: Any = None) -> None:
        self.acoes.append(None if do_mouse is None else dict(do_mouse))


class _DaemonQueAnota(Daemon):
    """SUBCLASSE do daemon real: os devices só anotam, o mouse emulado não toca o aparelho."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._keyboard_device = _Teclado()
        self._mouse_device = _Mouse()

    def set_mouse_emulation(self, enabled: bool, speed: int | None = None,
                            scroll_speed: int | None = None, *,
                            origin: Literal["manual", "profile"]) -> bool:
        self.config.mouse_emulation_enabled = bool(enabled)
        return True

    def set_mouse_speed(self, speed: int | None = None, scroll_speed: int | None = None) -> bool:
        return True

    def set_keyboard_emulation(self, enabled: bool, *, persist: bool = True) -> bool:
        return True

    def set_emulation_suppressed(self, value: bool | None = None, *,
                                 origin: Literal["manual", "profile"] = "manual") -> bool:
        return bool(value)

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:  # type: ignore[override]
        return fn(*args)

    def quadrado(self) -> tuple[str, ...] | None:
        """O que o «quadrado» digita no teclado, pela última tabela que chegou."""
        ultima = self._keyboard_device.bindings[-1]
        valor = ultima.get("square")
        return tuple(valor) if valor is not None else None


def _gravar(nome: str, corpo: dict[str, Any]) -> None:
    pasta = Path(config_dir()) / "profiles"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome}.json").write_text(json.dumps(corpo, ensure_ascii=False), encoding="utf-8")


def _daemon(perfil: dict[str, Any] = PERFIL_ATIVO) -> _DaemonQueAnota:
    d = _DaemonQueAnota(controller=FakeController(transport="usb"),
                        config=DaemonConfig(mouse_speed=6, mouse_scroll_speed=1))
    _gravar("perfil-ativo", perfil)
    _gravar("jogo-navegacao", PERFIL_DO_JOGO)
    d.store.set_active_profile("perfil-ativo")
    return d


def _arranjo_do_chip(arranjo: str) -> dict[str, Any]:
    """Os params do passo `desktop.arranjo.apply` do plano do chip."""
    metodo, params = plan_mode_transition(MODE_DESKTOP, arranjo=arranjo)[-1]
    assert metodo == "desktop.arranjo.apply"
    return params


def _pelo_ipc(d: Daemon, params: dict[str, Any]) -> dict[str, Any]:
    """O handler de verdade do `desktop.arranjo.apply`, com este daemon atrás."""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    casca = SimpleNamespace(daemon=d)
    resposta: dict[str, Any] = asyncio.run(
        IpcHandlersMixin._handle_desktop_arranjo_apply(casca, params))  # type: ignore[arg-type]
    return resposta


def test_o_point_and_click_aplica_o_molde_que_a_navegacao_escolheu() -> None:
    """A prova da D-2010-O-POINT-AND-CLICK-APLICA-O-PERFIL-ESCOLHIDO."""
    d = _daemon()
    _pelo_ipc(d, _arranjo_do_chip(ARRANJO_POINT_AND_CLICK))
    assert d.quadrado() == ("KEY_LEFTCTRL",), (
        "o Point and click aplicou outra tabela que não a do molde Visual novel: "
        f"o quadrado digita {d.quadrado()!r}")
    mouse = d._mouse_device.acoes[-1] or {}
    assert (mouse.get("cross"), mouse.get("circle")) == ("BTN_LEFT", "BTN_RIGHT")


def test_a_navegacao_aplica_as_linhas_do_perfil_ativo() -> None:
    d = _daemon()
    _pelo_ipc(d, _arranjo_do_chip(ARRANJO_NAVEGACAO))
    assert d.quadrado() == ("KEY_SPACE",)


def test_um_perfil_salvo_como_perfil_jogo_navegacao_da_a_tabela_dele() -> None:
    d = _daemon({**PERFIL_ATIVO, "mouse": {**PERFIL_ATIVO["mouse"],
                                           "point_and_click": "perfil:jogo-navegacao"}})
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    assert d.quadrado() == ("KEY_TAB",)


def test_sem_escolha_vale_o_molde_point_and_click() -> None:
    sem_escolha = {**PERFIL_ATIVO, "mouse": {"enabled": True, "speed": 9, "scroll_speed": 2}}
    d = _daemon(sem_escolha)
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    tabela = d._keyboard_device.bindings[-1]
    assert tuple(tabela["triangle"]) == ("KEY_ESC",)
    assert d.quadrado() != ("KEY_SPACE",)


def test_o_mouse_e_as_velocidades_seguem_o_perfil_ativo_nos_dois() -> None:
    d = _daemon()
    relatorio = d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    assert relatorio.get("button_actions") == "aplicado"
    assert relatorio.get("keyboard") not in ("falhou", "ignorado_sem_perfil")


def test_o_arranjo_se_guarda_e_o_ps_r3_sem_escolha_usa_o_guardado() -> None:
    d = _daemon()
    _pelo_ipc(d, _arranjo_do_chip(ARRANJO_NAVEGACAO))
    assert load_arranjo_do_desktop() == ARRANJO_NAVEGACAO
    d.aplicar_o_arranjo_do_desktop(origin="profile")
    assert d.quadrado() == ("KEY_SPACE",)


def test_um_valor_fora_da_lista_nao_muda_o_guardado() -> None:
    d = _daemon()
    _pelo_ipc(d, {"origin": "manual", "arranjo": "qualquer"})
    assert d.arranjo_do_desktop == ARRANJO_POINT_AND_CLICK
    with pytest.raises(ValueError):
        plan_mode_transition(MODE_DESKTOP, arranjo="qualquer")


def test_sem_arquivo_vale_o_ultimo_clique_da_janela() -> None:
    from hefesto_dualsense4unix.app.gui_prefs import set_pref

    assert load_arranjo_do_desktop() == ARRANJO_POINT_AND_CLICK
    set_pref("jogar_navegacao_no_desligado", True)
    assert load_arranjo_do_desktop() == ARRANJO_NAVEGACAO


def test_o_estado_publica_o_arranjo() -> None:
    d = _daemon()
    _pelo_ipc(d, _arranjo_do_chip(ARRANJO_NAVEGACAO))
    from hefesto_dualsense4unix.daemon import ipc_handlers

    fonte = Path(ipc_handlers.__file__).read_text(encoding="utf-8")
    assert '"desktop_arranjo": _as_str_or_none(getattr(self.daemon, "arranjo_do_desktop"' in fonte
    assert d.arranjo_do_desktop == ARRANJO_NAVEGACAO


def test_o_servico_reiniciado_volta_no_point_and_click() -> None:
    _pelo_ipc(_daemon(), _arranjo_do_chip(ARRANJO_POINT_AND_CLICK))
    novo = _daemon()
    assert novo.arranjo_do_desktop == ARRANJO_POINT_AND_CLICK
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.utils.session import gravar_a_escolha

    gravar_a_escolha("perfil-ativo")
    novo.store.set_active_profile("")
    asyncio.run(restore_last_profile(novo))
    assert novo.quadrado() == ("KEY_LEFTCTRL",), (
        "o boot ativou o perfil e deixou as tabelas da Navegação no Point and click")


def test_a_ativacao_de_um_perfil_no_desktop_repoe_o_point_and_click() -> None:
    d = _daemon()
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    d._aplicar_as_tabelas(d._perfil_do_arranjo(), None)
    assert d.quadrado() == ("KEY_SPACE",)
    d.apply_profile_mode(None, profile=d._perfil_do_arranjo(), origin="autoswitch")
    assert d.quadrado() == ("KEY_LEFTCTRL",)


def test_sair_para_o_gamepad_devolve_a_tabela_do_perfil(monkeypatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    d = _daemon()
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    assert d.quadrado() == ("KEY_LEFTCTRL",)
    monkeypatch.setattr(gamepad, "start_gamepad_emulation_desfecho",
                        lambda *a, **k: gamepad.EMU_APLICADO)
    d.set_gamepad_emulation_desfecho(True, origin="manual")
    assert d.quadrado() == ("KEY_SPACE",), (
        "o teclado do desktop digita com o jogo aberto, e a tabela do Point and click ficou nele")
