"""POINT-AND-CLICK-01 — o chip da tela e o PS + R3 pela MESMA porta.

O mesmo modo tinha DOIS donos e eles discordavam. É o HARM-01 outra vez, e o
próprio `a01_jogar` conta a história: *"o sprint que nasceu porque o modo tinha
DOIS donos e eles discordavam"*. A cura de então criou `plan_mode_transition`
como dono único — **e o gesto no controle nunca passou a usá-lo**.

O que cada um fazia, medido em 17/09/2026:

    | efeito                | chip da aba Jogar          | PS + R3           |
    | vpad cai              | sim                        | sim               |
    | mouse liga            | conforme a FLAG GLOBAL     | SEMPRE            |
    | teclado liga          | NUNCA                      | sempre, e grava   |
    | supressão cai         | NUNCA                      | sempre            |

*Quando a cura conhece a causa, ela cobre TODOS os chamadores.* Cobrir só o
chip deixaria o gesto no controle ligando o teclado que o clique não liga — e a
próxima pessoa remedindo o mesmo defeito, que foi o que aconteceu duas vezes num
dia em 05/09.

O FURO DESTA RÉGUA, dito porque a casa exige: ela prova que os dois chamam o
MESMO, e **não** prova que o que eles chamam está certo. Sem a
`test_o_point_and_click_ativa_o_que_a_navegacao_gravou` ao lado, ela daria verde
sobre dois caminhos igualmente errados — que é exatamente a forma do defeito que
o HARM-01 curou.
"""
from __future__ import annotations

from typing import Any

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
            # O DAEMON ENXUTO: sem o método, e o `getattr` do gesto tem de ver
            # isso. `None` no atributo de instância é o que o `callable()` do
            # produto recusa — apagar da CLASSE envenenaria as outras instâncias.
            self.aplicar_o_arranjo_do_desktop = None  # type: ignore[assignment]

    def set_gamepad_emulation(
        self,
        enabled: bool,
        flavor: str | None = None,
        *,
        origin: str = "manual",
        caminho: str | None = None,
    ) -> bool:
        self.recebeu.append(
            ("gamepad", {"enabled": enabled, "origin": origin, "caminho": caminho})
        )
        return True

    def aplicar_o_arranjo_do_desktop(
        self, *, origin: str = "manual", forcar_mouse: bool = False
    ) -> dict[str, str]:
        self.recebeu.append(
            ("arranjo", {"origin": origin, "forcar_mouse": forcar_mouse})
        )
        return {"mouse": "aplicado"}

    def efeitos(self) -> list[str]:
        return [nome for nome, _p in self.recebeu]


def _efeitos_do_chip() -> list[str]:
    """O que o CLIQUE no chip Navegação pede, traduzido para o mesmo vocabulário.

    A asserção é sobre o CONJUNTO de efeitos, não sobre a lista literal: o gesto
    não passa pelo `native.mode.set` (o ciclo já saiu do nativo), e exigir
    igualdade byte a byte faria a régua reprovar uma diferença legítima.
    """
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
    # O que os dois têm de ter em comum, e a diferença legítima fica de fora.
    comum = {"gamepad", "arranjo"}
    assert comum <= do_gesto, f"o gesto perdeu um efeito: {sorted(do_gesto)}"
    assert comum <= do_chip, f"o chip perdeu um efeito: {sorted(do_chip)}"
    assert "nativo" not in do_gesto, (
        "o gesto passou a sair do Modo Nativo — o ciclo do PS + R3 já saiu dele, "
        "e repetir o passo é o segundo dono voltando pelo outro lado."
    )


def test_o_gesto_e_socorro_e_o_chip_e_escolha() -> None:
    """`forcar_mouse` separa os dois, e é a ÚNICA diferença.

    O PS + R3 é uma das duas saídas de emergência quando o jogo não responde:
    obedecer a um perfil com `mouse.enabled: false` tiraria dela o cursor
    justamente quando ela não tem outro caminho. O clique é escolha e obedece.
    """
    d = _DaemonDoGesto()
    hotkey._aplicar_ponte(d, hotkey.PONTE_MOUSE_TECLADO)

    arranjos = [p for nome, p in d.recebeu if nome == "arranjo"]
    assert arranjos, f"o gesto não chamou o arranjo: {d.efeitos()}"
    assert arranjos[0]["forcar_mouse"] is True, (
        "o PS + R3 deixou de forçar o mouse. Com um perfil que o desliga, a "
        "saída de emergência dela passa a não devolver o cursor."
    )
    assert arranjos[0]["origin"] == "manual", (
        "o gesto tem de DECLARAR que é dela — é o único origin que atravessa o "
        "gate R-04 e o lock de 30 s do `apply_profile_mouse`."
    )

    passos = dict(plan_mode_transition(MODE_DESKTOP))
    assert "forcar_mouse" not in passos["desktop.arranjo.apply"], (
        "o CLIQUE no chip passou a forçar o mouse. O socorro virou regra e o "
        "perfil dela voltou a não ser lido — a cura com o nome novo e o "
        "comportamento velho."
    )


def test_o_gesto_derruba_o_vpad_antes_de_carregar_o_arranjo() -> None:
    """A ordem é a mesma do plano, e pelo mesmo motivo (HARM-06).

    Ligar o mouse antes de o gamepad sair faria a exclusão mútua do daemon
    derrubar o mouse recém-ligado.
    """
    d = _DaemonDoGesto()
    hotkey._aplicar_ponte(d, hotkey.PONTE_MOUSE_TECLADO)

    ordem = d.efeitos()
    assert ordem.index("gamepad") < ordem.index("arranjo"), (
        f"o arranjo veio antes de o vpad cair: {ordem}"
    )
    gamepad = next(p for nome, p in d.recebeu if nome == "gamepad")
    assert gamepad["enabled"] is False


def test_daemon_sem_arranjo_ainda_sobe_a_ponte_e_deixa_rastro() -> None:
    """Daemon enxuto (CLI, dublê antigo) não pode derrubar o gesto.

    Devolver `False` aqui seria dizer que a ponte não subiu — e ela subiu: o
    vpad já caiu. O journal é quem diz o que não foi carregado.
    """
    d = _DaemonDoGesto(com_arranjo=False)
    assert hotkey._aplicar_ponte(d, hotkey.PONTE_MOUSE_TECLADO) is True
    assert d.efeitos() == ["gamepad"]
