"""Silêncio não é gesto dela: o `origin` viaja explícito, sem default."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon import lifecycle, protocols
from hefesto_dualsense4unix.daemon.ipc_handlers import origem_do_pedido
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

RAIZ = Path(__file__).resolve().parents[2]

SETTERS = (
    "set_gamepad_emulation",
    "set_native_mode",
    "set_mouse_emulation",
    "set_coop_enabled",
)


def test_silencio_nao_e_gesto_dela() -> None:
    """Sem `origin` no pedido, a origem é automática."""
    assert origem_do_pedido(None) == "profile"
    assert origem_do_pedido({}) == "profile"
    assert origem_do_pedido({"enabled": True}) == "profile"


def test_o_cliente_declara_e_e_respeitado() -> None:
    """Quem diz "manual" continua sendo tratado como gesto dela."""
    assert origem_do_pedido({"origin": "manual"}) == "manual"
    assert origem_do_pedido({"origin": "profile"}) == "profile"


@pytest.mark.parametrize("lixo", ["auto", "autoswitch", "", 1, True, []])
def test_origem_invalida_e_recusada_em_voz_alta(lixo: object) -> None:
    """Valor desconhecido levanta, em vez de virar "manual" por engano."""
    with pytest.raises(ValueError, match="origin"):
        origem_do_pedido({"origin": lixo})


@pytest.mark.parametrize("nome", SETTERS)
def test_o_setter_nao_tem_default_de_origem(nome: str) -> None:
    """`origin` é obrigatório: o `mypy` obriga cada chamador a declarar."""
    sig = inspect.signature(getattr(lifecycle.Daemon, nome))
    p = sig.parameters.get("origin")
    assert p is not None, f"`{nome}` perdeu o parâmetro `origin`"
    assert p.default is inspect.Parameter.empty, (
        f"`{nome}` voltou a ter default de `origin`. Silêncio vira gesto dela, e "
        "um cliente distraído fura o portão JOGO-01 com o jogo aberto."
    )
    assert p.kind is inspect.Parameter.KEYWORD_ONLY, (
        f"`{nome}.origin` deixou de ser keyword-only — passar por posição esconde "
        "a decisão de quem lê a chamada."
    )


def test_o_start_do_gamepad_tambem_exige_a_origem() -> None:
    """É ele que carrega o portão JOGO-01 (`if origin != "manual"`)."""
    p = inspect.signature(gp.start_gamepad_emulation).parameters.get("origin")
    assert p is not None and p.default is inspect.Parameter.empty, (
        "`start_gamepad_emulation` voltou a ter default de `origin` — é a função "
        "onde o portão da allowlist decide, e o default era a porta dos fundos."
    )


@pytest.mark.parametrize("nome", SETTERS)
def test_o_protocolo_declara_a_origem(nome: str) -> None:
    """A armadilha morava no CONTRATO, não só na implementação."""
    sig = inspect.signature(getattr(protocols.DaemonProtocol, nome))
    p = sig.parameters.get("origin")
    assert p is not None, (
        f"`DaemonProtocol.{nome}` não declara `origin`. Sem isso o `mypy` não "
        "fecha o cerco e a próxima implementação volta a assumir um default."
    )
    assert p.default is inspect.Parameter.empty, (
        f"`DaemonProtocol.{nome}` ganhou default de `origin` — o contrato voltou "
        "a permitir o silêncio."
    )


def test_nenhum_handler_ipc_chama_sem_declarar() -> None:
    """Os quatro handlers IPC declaram a origem a partir do pedido."""
    texto = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "ipc_handlers.py"
    ).read_text(encoding="utf-8")

    for nome in SETTERS:
        for trecho in texto.split(f"self.daemon.{nome}(")[1:]:
            chamada = trecho[: trecho.index(")")]
            assert "origin=" in chamada, (
                f"há uma chamada a `{nome}` nos handlers IPC sem `origin=`. "
                "Silêncio vira gesto dela, e o portão JOGO-01 deixa passar."
            )

    assert "origem_do_pedido" in texto, (
        "sumiu a função que traduz o pedido em origem — sem ela cada handler "
        "decide por conta própria, e a regra deixa de ter um dono só."
    )


METODOS_DE_MODO = ("gamepad.emulation.set", "native.mode.set", "mouse.emulation.set")

TELAS = (
    "app/actions/mode_transition.py",
    "app/actions/home_actions.py",
    "app/actions/mouse_actions.py",
)


@pytest.mark.parametrize("arquivo", TELAS)
def test_a_janela_declara_o_gesto_dela(arquivo: str) -> None:
    """Todo pedido de modo saído da janela leva `origin: "manual"`."""
    texto = (RAIZ / "src" / "hefesto_dualsense4unix" / arquivo).read_text(
        encoding="utf-8"
    )
    for metodo in METODOS_DE_MODO:
        for trecho in texto.split(f'"{metodo}",')[1:]:
            fecha = trecho.index("}")
            if "{" not in trecho[:fecha]:
                continue
            bloco = trecho[: fecha + 1]
            assert '"origin": "manual"' in bloco, (
                f"em `{arquivo}` há um pedido a `{metodo}` sem "
                '`"origin": "manual"`. Dentro de um jogo marcado, o daemon vai '
                "recusar o clique dela — foi assim que o botão 'Jogar pelo "
                "Hefesto' parou de funcionar em 08/08."
            )


def test_o_restore_do_mouse_nao_finge_ser_gesto() -> None:
    """O contrapeso: reconciliação continua sendo reconciliação.

    `mouse.emulation.restore` devolve a preferência que o daemon persistiu — não
    há dedo dela nisso. Se ele passasse a viajar como "manual", a cura viraria
    "tudo é gesto dela", que é exatamente o defeito de origem, agora escrito de
    propósito.

    ONDE ELE MORA HOJE. Em 17/09/2026 (POINT-AND-CLICK-01) ele saiu do plano
    da transição, que passou a chamar o `desktop.arranjo.apply` (lê o PERFIL);
    em 29/09 (O-MOUSE-SEGUE-A-NAVEGACAO-01) o arranjo parou de recuar para ele
    (sem a seção no perfil, lê da flag só as velocidades). Sobrou o método IPC,
    cujo corpo é `Daemon.restore_mouse_preference`, e a pergunta é a mesma —
    aquele caminho continua carimbando `origin="profile"`.
    """
    texto = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "daemon/lifecycle.py"
    ).read_text(encoding="utf-8")
    inicio = texto.index("def restore_mouse_preference")
    bloco = texto[inicio : texto.index("\n    def ", inicio)]
    assert 'origin="profile"' in bloco, (
        "o `restore_mouse_preference` deixou de se declarar reconciliação. Ele "
        "restaura preferência persistida, e chamá-lo de gesto dela reabre o "
        "defeito pelo outro lado."
    )
    assert 'origin="manual"' not in bloco, (
        "a restauração da flag de sessão passou a viajar como gesto manual."
    )


def test_o_arranjo_do_desktop_declara_a_origem() -> None:
    """E o passo que É gesto dela declara — a outra metade da mesma cura."""
    texto = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "app/actions/mode_transition.py"
    ).read_text(encoding="utf-8")
    trecho = texto[texto.index('"desktop.arranjo.apply"') :]
    bloco = trecho[: trecho.index("}") + 1]
    assert '"origin": "manual"' in bloco, (
        "o arranjo do desktop parou de declarar a origem. O silêncio é lido "
        "como automático, e o gesto dela perde a única porta que atravessa o "
        "lock manual."
    )
