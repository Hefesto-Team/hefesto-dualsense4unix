"""POINT-AND-CLICK-01 — o chip da tela e o PS + R3 pela MESMA porta."""
from __future__ import annotations

from typing import Any, Literal

from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    plan_mode_transition,
)
from hefesto_dualsense4unix.daemon.subsystems import hotkey


class _DaemonDoGesto:
    """Dublê do daemon para o gesto. Anota o que foi PEDIDO, e nada mais."""

    def __init__(self, *, com_arranjo: bool = True) -> None:
        self.recebeu: list[tuple[str, dict[str, Any]]] = []
        if not com_arranjo:
            self.aplicar_o_arranjo_do_desktop = None  # type: ignore[assignment]

    def set_gamepad_emulation(
        self,
        enabled: bool,
        flavor: str | None = None,
        *,
        origin: Literal["manual", "profile"],
        caminho: str | None = None,
        grava_o_modo: Literal[False, "ipc", "controle"] = False,
    ) -> bool:
        self.recebeu.append(
            ("gamepad", {"enabled": enabled, "origin": origin, "caminho": caminho,
                         "grava_o_modo": grava_o_modo})
        )
        return True

    def aplicar_o_arranjo_do_desktop(
        self,
        *,
        origin: str = "manual",
        grava_o_modo: Literal[False, "ipc", "controle"] = False,
    ) -> dict[str, str]:
        self.recebeu.append(
            ("arranjo", {"origin": origin, "grava_o_modo": grava_o_modo})
        )
        return {"mouse": "aplicado"}

    def efeitos(self) -> list[str]:
        return [nome for nome, _p in self.recebeu]


def _efeitos_do_chip() -> list[str]:
    """O que o CLIQUE no chip Navegação pede, traduzido para o mesmo vocabulário."""
    traducao = {
        "gamepad.emulation.set": "gamepad",
        "desktop.arranjo.apply": "arranjo",
        "native.mode.set": "nativo",
        "mouse.emulation.restore": "flag_da_sessao",
    }
    return [traducao.get(m, m) for m, _p in plan_mode_transition(MODE_DESKTOP)]


def test_os_dois_caminhos_terminam_no_mesmo_arranjo() -> None:
    """O gesto e o clique pedem o MESMO carregamento de perfil."""
    d = _DaemonDoGesto()
    assert hotkey._aplicar_ponte(d, hotkey.PONTE_MOUSE_TECLADO) is True

    do_gesto = set(d.efeitos())
    do_chip = set(_efeitos_do_chip())

    assert "arranjo" in do_gesto, (
        "o PS + R3 não passa pelo arranjo do desktop — ele voltou a escrever a "
        f"própria sequência de chamadas à mão. Pediu: {d.efeitos()}"
    )
    assert "arranjo" in do_chip, (
        f"o clique no chip não passa pelo arranjo: {_efeitos_do_chip()}"
    )
    comum = {"gamepad", "arranjo"}
    assert comum <= do_gesto, f"o gesto perdeu um efeito: {sorted(do_gesto)}"
    assert comum <= do_chip, f"o chip perdeu um efeito: {sorted(do_chip)}"
    assert "nativo" not in do_gesto, (
        "o gesto passou a sair do Modo Nativo — o ciclo do PS + R3 já saiu dele, "
        "e repetir o passo é o segundo dono voltando pelo outro lado."
    )


def test_o_gesto_e_o_chip_pedem_o_mesmo_arranjo() -> None:
    """Nenhum parâmetro só do gesto: as duas portas pedem o MESMO arranjo."""
    d = _DaemonDoGesto()
    hotkey._aplicar_ponte(d, hotkey.PONTE_MOUSE_TECLADO)

    arranjos = [p for nome, p in d.recebeu if nome == "arranjo"]
    assert arranjos, f"o gesto não chamou o arranjo: {d.efeitos()}"
    assert arranjos[0] == {"origin": "manual", "grava_o_modo": "controle"}, (
        f"o gesto pediu um arranjo diferente do chip: {arranjos[0]}")

    passos = dict(plan_mode_transition(MODE_DESKTOP))
    assert passos["desktop.arranjo.apply"] == {"origin": "manual"}, (
        "o CLIQUE no chip passou a mandar um parâmetro que o gesto não manda: "
        f"{passos['desktop.arranjo.apply']}")


def test_o_gesto_derruba_o_vpad_antes_de_carregar_o_arranjo() -> None:
    """A ordem é a mesma do plano, e pelo mesmo motivo (HARM-06)."""
    d = _DaemonDoGesto()
    hotkey._aplicar_ponte(d, hotkey.PONTE_MOUSE_TECLADO)

    ordem = d.efeitos()
    assert ordem.index("gamepad") < ordem.index("arranjo"), (
        f"o arranjo veio antes de o vpad cair: {ordem}"
    )
    gamepad = next(p for nome, p in d.recebeu if nome == "gamepad")
    assert gamepad["enabled"] is False


def test_daemon_sem_arranjo_ainda_sobe_a_ponte_e_deixa_rastro() -> None:
    """Daemon enxuto (CLI, dublê antigo) não pode derrubar o gesto."""
    d = _DaemonDoGesto(com_arranjo=False)
    assert hotkey._aplicar_ponte(d, hotkey.PONTE_MOUSE_TECLADO) is True
    assert d.efeitos() == ["gamepad"]
