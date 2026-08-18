"""Silêncio não é gesto dela: o `origin` viaja explícito, sem default.

ORIGEM-QUE-MENTE-01 (08/08/2026). Os setters do daemon tinham
`origin: Literal["manual", "profile"] = "manual"`, e o protocolo IPC **não
expunha o campo**. Consequência: o daemon lia a AUSÊNCIA de informação como a
mão dela, e qualquer cliente que apenas reconciliasse estado era promovido a
gesto humano.

O CUSTO, MEDIDO
===============
Com o Sackboy aberto e marcado na allowlist do Steam Input, um cliente chamou
`gamepad.emulation.set` sem `origin`. O portão JOGO-01 (`gamepad.py`,
`if origin != "manual"`) deixou passar, o gamepad virtual voltou com o grab e o
esconde-esconde pulados, e o jogo passou a ver o controle físico E o virtual.
Ela fotografou um **"Jogador 3"** fantasma no Sackboy.

E o ramo `origin == "manual"` ainda carimba `_emu_manual_ts`, que cala o perfil
por 30 s: o cliente distraído não só furava o portão como silenciava o
autoswitch depois.

A REGRA, E ELA É ASSIMÉTRICA DE PROPÓSITO
=========================================
**"manual" só quando o cliente DIZ que é manual.** É a inversão do default
antigo, e a assimetria é escolhida:

- errar para ``"profile"`` custa, no pior caso, um gesto dela que não fura o
  portão — e o produto lhe diz por quê;
- errar para ``"manual"``, como antes, custa **o controle dela no meio da
  partida**.

O caso inteiro está em
`docs/process/sprints/2026-08-08-JOGADOR-3-FANTASMA-01-a-cura-certa-no-momento-errado.md`.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon import lifecycle, protocols
from hefesto_dualsense4unix.daemon.ipc_handlers import origem_do_pedido
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

RAIZ = Path(__file__).resolve().parents[2]

#: Os setters que decidem quem manda no controle. Todos passam pelo portão
#: JOGO-01 ou carimbam `_emu_manual_ts`.
SETTERS = (
    "set_gamepad_emulation",
    "set_native_mode",
    "set_mouse_emulation",
    "set_coop_enabled",
)


# --- a função pura: silêncio é automático -------------------------------------


def test_silencio_nao_e_gesto_dela() -> None:
    """Sem `origin` no pedido, a origem é automática.

    ARRANQUE A CURA (volte a devolver "manual" no silêncio) e este teste
    REPROVA. É o defeito exato: um cliente reconciliando estado fura o portão
    JOGO-01 e devolve o gamepad virtual com o jogo da allowlist aberto.
    """
    assert origem_do_pedido(None) == "profile"
    assert origem_do_pedido({}) == "profile"
    assert origem_do_pedido({"enabled": True}) == "profile"


def test_o_cliente_declara_e_e_respeitado() -> None:
    """Quem diz "manual" continua sendo tratado como gesto dela.

    O contrapeso: a cura não pode virar "nada é manual", senão o botão dela na
    janela deixaria de funcionar dentro de um jogo marcado — e aí o produto
    passaria a recusar o gesto legítimo, que é o oposto do que ela pediu.
    """
    assert origem_do_pedido({"origin": "manual"}) == "manual"
    assert origem_do_pedido({"origin": "profile"}) == "profile"


@pytest.mark.parametrize("lixo", ["auto", "autoswitch", "", 1, True, []])
def test_origem_invalida_e_recusada_em_voz_alta(lixo: object) -> None:
    """Valor desconhecido levanta, em vez de virar "manual" por engano.

    Cair no default silencioso é o que criou este defeito. Um cliente que
    invente um valor achando que existe merece um erro, não uma promoção.
    """
    with pytest.raises(ValueError, match="origin"):
        origem_do_pedido({"origin": lixo})


# --- as assinaturas: sem default, keyword-only --------------------------------


@pytest.mark.parametrize("nome", SETTERS)
def test_o_setter_nao_tem_default_de_origem(nome: str) -> None:
    """`origin` é obrigatório: o `mypy` obriga cada chamador a declarar.

    ARRANQUE A CURA (devolva `= "manual"`) e este teste REPROVA. É o portão que
    impede a mina de voltar por descuido, num setter novo ou num refactor.
    """
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
    """A armadilha morava no CONTRATO, não só na implementação.

    Antes, `daemon/protocols.py` nem mencionava `origin`: quem programasse
    contra o protocolo não tinha como saber que existia essa decisão a tomar. Um
    protocolo que esconde a decisão obriga a implementação a chutar.
    """
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


# --- nenhum chamador do produto ficou mudo ------------------------------------


def test_nenhum_handler_ipc_chama_sem_declarar() -> None:
    """Os quatro handlers IPC declaram a origem a partir do pedido.

    É o teste que amarra a ponta: sem ele, alguém acrescenta um handler novo
    chamando o setter sem `origin` e o `mypy` reclama — mas um `# type: ignore`
    apressado reabriria o buraco em silêncio.
    """
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


def test_o_porque_esta_escrito_no_codigo() -> None:
    """Quem for pôr um default de volta encontra o custo medido primeiro."""
    for arquivo in ("daemon/ipc_handlers.py", "daemon/lifecycle.py", "daemon/protocols.py"):
        texto = (RAIZ / "src" / "hefesto_dualsense4unix" / arquivo).read_text(
            encoding="utf-8"
        )
        assert "ORIGEM-QUE-MENTE-01" in texto, (
            f"o registro do defeito saiu de `{arquivo}`. Sem o porquê, "
            "`origin` sem default parece rigor gratuito e volta a ter default."
        )


# --- a janela DECLARA que o clique é dela -------------------------------------


#: Os métodos IPC cujo pedido, vindo da janela, é gesto dela — e que o daemon
#: recusa dentro de um jogo marcado se chegarem sem `origin`.
METODOS_DE_MODO = ("gamepad.emulation.set", "native.mode.set", "mouse.emulation.set")

#: Os arquivos da janela que disparam esses métodos por clique dela.
TELAS = (
    "app/actions/mode_transition.py",
    "app/actions/home_actions.py",
    "app/actions/mouse_actions.py",
)


@pytest.mark.parametrize("arquivo", TELAS)
def test_a_janela_declara_o_gesto_dela(arquivo: str) -> None:
    """Todo pedido de modo saído da janela leva `origin: "manual"`.

    ARRANQUE A CURA e este teste REPROVA — e o defeito que ele descreve foi
    MEDIDO na máquina dela: com o Sackboy marcado na allowlist, o botão "Jogar
    pelo Hefesto" **parou de funcionar**. O clique chegava sem `origin`, era
    lido como reconciliação, e o daemon o recusava com
    `gamepad_start_recusado_steam_input`.

    É a metade que faltava da ORIGEM-QUE-MENTE-01: inverter o default protegeu o
    daemon de clientes distraídos, mas a janela também era um deles. Curar só um
    lado troca um defeito por outro — antes qualquer coisa virava gesto dela;
    depois, nem o gesto dela era gesto dela.
    """
    texto = (RAIZ / "src" / "hefesto_dualsense4unix" / arquivo).read_text(
        encoding="utf-8"
    )
    for metodo in METODOS_DE_MODO:
        for trecho in texto.split(f'"{metodo}",')[1:]:
            # o dicionário de params do pedido vem logo depois do método. Um
            # trecho que NÃO abre `{` antes de fechar não é um pedido — é o
            # método citado numa lista/conjunto (`_MODE_DEFINING_METHODS`), e
            # esses não têm params para declarar.
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
    """
    texto = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "app/actions/mode_transition.py"
    ).read_text(encoding="utf-8")
    trecho = texto[texto.index('"mouse.emulation.restore"') :]
    bloco = trecho[: trecho.index("}") + 1]
    assert '"origin"' not in bloco, (
        "o `mouse.emulation.restore` passou a declarar origem. Ele restaura "
        "preferência persistida: é reconciliação por definição, e chamá-lo de "
        "gesto dela reabre o defeito pelo outro lado."
    )
