"""ONDA5-06-01 — o botão PS digita, e CONTINUA sendo a saída.

A DECISÃO É DELA (06-Q3, 05/09/2026), e ela escolheu a opção cujo próprio texto
declara um custo:

    *"O PS ganha a mesma lista das outras 21 linhas; se você der uma tecla a ele,
    ele passa a digitar SEM parar de abrir a Steam, e a tabela não avisa isso."*

As duas metades são requisito, e a ORDEM entre elas também: *digita* **e** *sem
parar de abrir a Steam*. Esta régua mede as duas, e mede a ordem.

O QUE ELA COBRE, e por que num arquivo só: as quatro peças respondem à mesma
pergunta — *este toque no PS vira o quê?* — e separá-las faria a próxima pessoa
curar uma e esquecer as outras.

    §1  o PS é botão DO PRODUTO      `core/acoes_de_botao.BOTOES`
    §2  e não é órfão                `core/acoes_de_botao.resolver`
    §3  a escolha chega a quem atende `profiles/manager.apply_button_actions`
    §4  o toque faz as duas coisas    `daemon/subsystems/hotkey._on_ps_solo`
    §5  e a tecla sai ANTES da Steam  (a Steam rouba o foco)

O DUBLÊ DO TECLADO É O DEVICE DE VERDADE. `UinputKeyboardDevice` com um módulo
`uinput` de mentira no lugar do real: o caminho de emissão exercitado é o do
produto, inclusive o `_delegate_virtual_tokens`. A casa já pagou por dublê mais
frouxo que a função real três vezes — este não é um deles.
"""
from __future__ import annotations

import dataclasses
import typing
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import steam_launcher
from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_COMBO_NEXT,
    HotkeyConfig,
    HotkeyManager,
)
from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import Profile

# ===========================================================================
# O aparato — um teclado virtual que emite de verdade, e um daemon de mentira
# ===========================================================================


class _UinputDeMentira:
    """O módulo `uinput` visto pelo device: cada `KEY_*` é um evento próprio.

    O device faz `getattr(u, key_name, None)` e desiste do que não achar
    (`keyboard_key_unknown`), então um objeto que devolve qualquer nome
    imitaria um teclado que sabe tudo. Este só conhece o que um teclado conhece:
    nomes que começam com `KEY_`.
    """

    def __getattr__(self, nome: str) -> Any:
        if not nome.startswith("KEY_"):
            raise AttributeError(nome)
        return ("evento", nome)


class _DeviceDeMentira:
    """O `/dev/uinput` do outro lado: guarda (tecla, valor) na ordem."""

    def __init__(self) -> None:
        self.emitidos: list[tuple[str, int]] = []
        self.syns = 0

    def emit(self, ev: Any, valor: int, syn: bool = True) -> None:
        self.emitidos.append((ev[1], valor))

    def syn(self) -> None:
        self.syns += 1


def _teclado() -> tuple[UinputKeyboardDevice, _DeviceDeMentira]:
    """Um `UinputKeyboardDevice` DE VERDADE, com o uinput dublado."""
    dev = _DeviceDeMentira()
    teclado = UinputKeyboardDevice()
    teclado._device = dev
    teclado._uinput_mod = _UinputDeMentira()
    return teclado, dev


def _daemon(
    *,
    acao_da_maquina: str = "steam",
    comando: Any = None,
    suprimido: bool = False,
    nativo: bool = False,
    teclado: Any = None,
    escolha_do_perfil: str | None = None,
) -> Any:
    d = SimpleNamespace(
        config=SimpleNamespace(
            ps_button_action=acao_da_maquina, ps_button_command=comando or []
        ),
        _emulation_suppressed=suprimido,
        store=SimpleNamespace(native_mode_active=nativo),
        _keyboard_device=teclado,
    )
    hotkey.definir_acao_do_ps(d, escolha_do_perfil)
    return d


@pytest.fixture
def steam(monkeypatch) -> list[str]:
    """A Steam de mentira — e ela anota NA MESMA LISTA que as teclas.

    Uma lista só é o que torna a ORDEM mensurável (§5). Duas listas paralelas
    diriam que as duas coisas aconteceram e nunca qual veio primeiro.
    """
    abriu: list[str] = []
    monkeypatch.setattr(
        steam_launcher, "open_or_focus_steam", lambda: abriu.append("steam") or True
    )
    return abriu


def _perfil(**campos: Any) -> Profile:
    """Um `Profile` DE VERDADE — é ele que prova que o validador seguiu o dono."""
    return Profile(name="regua", match={"type": "manual"}, **campos)


class _Gerente(ProfileManager):
    """`ProfileManager` sem controller — `apply_button_actions` não o toca."""


def _gerente(**campos: Any) -> ProfileManager:
    return _Gerente(controller=None, **campos)  # type: ignore[arg-type]


# ===========================================================================
# §1 — O PS É BOTÃO DO PRODUTO
# ===========================================================================


def test_o_ps_entrou_na_lista_do_produto_no_lugar_do_aparelho():
    """Depois do `create`, antes das três regiões do touchpad.

    A ORDEM É A DO APARELHO, e é a ordem em que a tela mostra as linhas.

    A MORDIDA: tire `BOTAO_PS` da tupla `BOTOES` — este caso reprova, e com ele
    reprovam os cinco casos seguintes.
    """
    assert acoes.BOTAO_PS in acoes.BOTOES, (
        "o `ps` saiu da lista do produto: a decisão dela na 06-Q3 é que ele "
        "ganha a mesma lista das outras 21 linhas.")
    assert len(acoes.BOTOES) == 22, (
        f"a lista tem {len(acoes.BOTOES)} linhas e devia ter 22 — as 21 de "
        f"sempre mais o PS.")
    posicao = acoes.BOTOES.index(acoes.BOTAO_PS)
    assert acoes.BOTOES[posicao - 1] == "create"
    assert acoes.BOTOES[posicao + 1] == "touchpad_left_press"


def test_o_perfil_aceita_o_ps_sem_ninguem_editar_o_validador():
    """`profiles/schema.py` NÃO foi tocado, e passou a aceitar o PS.

    É o que prova que o validador é DERIVADO: ele lê
    `core/acoes_de_botao.BOTOES` em vez de guardar uma quarta cópia da lista.
    Se alguém digitar uma lista lá, esta sprint fracassou no que ela tem de
    mais barato.

    A MORDIDA: tire o `ps` de `BOTOES` — o `Profile` volta a recusar, com a
    mesma frase que `schema.py` levanta.
    """
    perfil = _perfil(button_actions={"ps": "KEY_F11"})
    assert perfil.button_actions == {"ps": "KEY_F11"}

    # E a régua sabe RECUSAR: as duas metades do validador continuam de pé.
    with pytest.raises(ValueError, match="não é uma ação conhecida"):
        _perfil(button_actions={"ps": "__NAO_EXISTE__"})
    with pytest.raises(ValueError, match="não é um dos botões da tela"):
        _perfil(button_actions={"botao_que_nao_existe": "KEY_F11"})


def test_o_de_fabrica_do_ps_e_o_que_ele_faz_e_nao_um_travessao():
    """O PS não está em nenhum dos quatro mapas — o de fábrica dele vem do dono.

    Sem isto o laço de `acoes.padrao()` o deixaria em `__NADA__`, e a tela diria
    que o botão que abre a Steam há meses não faz nada.

    A MORDIDA: apague a linha `fora[BOTAO_PS] = ...` do fim de
    `acoes.padrao()` — o PS volta a `— Nada —` e este caso reprova nomeando o
    rótulo.
    """
    assert acoes.padrao()["ps"] == acoes.TOKEN_STEAM, (
        f"o de fábrica do PS saiu "
        f"{acoes.rotulo(acoes.padrao()['ps'])!r}, e a máquina de fábrica abre "
        f"a Steam.")
    assert acoes.padrao("none")["ps"] == acoes.TOKEN_NADA
    assert acoes.padrao("custom")["ps"] == acoes.TOKEN_PROGRAMA
    # E o rótulo é o que ela lê na tela, não o token cru.
    assert acoes.rotulo(acoes.padrao()["ps"]) == "Abrir a Steam"


def test_a_regua_pergunta_ao_dono_qual_e_o_degrau_da_maquina():
    """O de fábrica do PS tem DONO, e o dono é `DaemonConfig.ps_button_action`.

    `core/acoes_de_botao` é importável SEM DAEMON por contrato — é o que o
    mantém no `core/` e o que impede o gerador da tela de arrastar o daemon
    inteiro. Então a cópia fica lá e a pergunta fica aqui.

    A MORDIDA: troque `PS_DA_MAQUINA_DE_FABRICA` para `"none"` — este caso
    reprova dizendo que a cópia e o dono discordam.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

    campo = {c.name: c for c in dataclasses.fields(DaemonConfig)}["ps_button_action"]
    assert campo.default == acoes.PS_DA_MAQUINA_DE_FABRICA, (
        f"`acoes_de_botao` diz que a máquina faz "
        f"{acoes.PS_DA_MAQUINA_DE_FABRICA!r} de fábrica e o dono "
        f"(`DaemonConfig.ps_button_action`) diz {campo.default!r}.")

    # E o mapa cobre TODOS os valores que o dono aceita: um valor novo no
    # `Literal` sem token aqui faria a linha do PS mentir na tela.
    aceitos = set(typing.get_args(
        typing.get_type_hints(DaemonConfig)["ps_button_action"]))
    assert aceitos == set(acoes.ACAO_DA_MAQUINA_PARA_TOKEN), (
        f"o dono aceita {sorted(aceitos)} e a tradução para a tela cobre "
        f"{sorted(acoes.ACAO_DA_MAQUINA_PARA_TOKEN)}.")


# ===========================================================================
# §2 — E ELE NÃO É ÓRFÃO
# ===========================================================================


def test_o_ps_nao_cai_na_terceira_sacola():
    """O de fábrica do PS é `__STEAM__`, que está em `SEM_ATENDENTE`.

    Sem a saída própria, o PS cairia em `sem_dono` — e a tira da aba escreveria
    na tela dela que o botão que abre a Steam "não acende nada hoje", enquanto
    `profiles/manager.py` registraria o mesmo no journal como
    `button_actions_sem_atendente`.

    A MORDIDA: apague o `tabela.pop(BOTAO_PS, None)` de `resolver()` — este
    caso reprova com o PS listado como sem dono.
    """
    for escolhas in (None, {"ps": acoes.TOKEN_STEAM}, {"ps": "KEY_F11"}):
        do_mouse, do_teclado, sem_dono = acoes.resolver(escolhas)
        assert "ps" not in sem_dono, (
            f"com {escolhas!r} o PS foi listado como sem dono — ele TEM dono, "
            f"e o dono é o callback do `ps_solo`.")
        assert "ps" not in do_mouse
        assert "ps" not in do_teclado, (
            "o PS entrou na sacola do teclado: o device de teclado emitiria a "
            "tecla no `dispatch()` também, e o toque digitaria duas vezes no "
            "dia em que o latch do combo deixar o PS passar.")


def test_as_outras_vinte_e_uma_linhas_continuam_como_eram():
    """`SEM_ATENDENTE` continua valendo para todo mundo menos o PS.

    O PS é uma sacola nova, não uma regra nova sobre as antigas — mudar isso
    seria a segunda cura escondida dentro da primeira.
    """
    _m, _t, sem_dono = acoes.resolver({"cross": acoes.TOKEN_STEAM})
    assert "cross" in sem_dono, (
        "o `__STEAM__` escolhido para o X deixou de ir para a terceira sacola: "
        "a saída do PS vazou para os outros vinte e um.")
    # E os dois eixos e os dois gatilhos seguem com o tratamento de sempre.
    _m, _t, gatilho = acoes.resolver({"l2": "KEY_ESC"})
    assert "l2" in gatilho


def test_a_porta_do_ps_distingue_o_calado_do_nada():
    """`None` não é `__NADA__`, e a diferença decide quem manda no botão."""
    assert acoes.acao_do_ps(None) is None
    assert acoes.acao_do_ps({}) is None
    assert acoes.acao_do_ps({"cross": "KEY_ESC"}) is None
    assert acoes.acao_do_ps({"ps": acoes.TOKEN_NADA}) == acoes.TOKEN_NADA
    assert acoes.acao_do_ps({"ps": "KEY_F11"}) == "KEY_F11"


# ===========================================================================
# §3 — A ESCOLHA CHEGA A QUEM A ATENDE
# ===========================================================================


def test_o_perfil_empurra_a_escolha_do_ps():
    """`apply_button_actions` entrega o token ao canal do PS.

    A MORDIDA: apague a chamada `self._empurrar_o_ps(profile)` — este caso
    reprova nomeando o token que o perfil guardava e que ninguém recebeu.
    """
    recebidos: list[str | None] = []
    gerente = _gerente(ps_action_sink=recebidos.append)
    gerente.apply_button_actions(_perfil(button_actions={"ps": "KEY_F11"}))
    assert recebidos == ["KEY_F11"], (
        f"o perfil guardava `KEY_F11` no PS e o canal recebeu {recebidos!r} — "
        f"a escolha ficou no disco e não chegou a quem a atende.")


def test_o_perfil_sem_opiniao_apaga_a_escolha_de_ontem():
    """`button_actions=None` empurra `None`, e o `None` é metade do contrato.

    Sem esta chamada, trocar do perfil que deu `F11` ao PS para um perfil que
    não opina deixaria o `F11` digitando no perfil de hoje — a escolha de ontem
    sobrevivendo à troca, em silêncio.

    A MORDIDA: mova o `self._empurrar_o_ps(profile)` para DEPOIS do
    `if profile.button_actions is None: return` — este caso reprova.
    """
    recebidos: list[str | None] = []
    gerente = _gerente(ps_action_sink=recebidos.append)
    gerente.apply_button_actions(_perfil(button_actions={"ps": "KEY_F11"}))
    gerente.apply_button_actions(_perfil())
    assert recebidos == ["KEY_F11", None], (
        f"o canal recebeu {recebidos!r}: o perfil sem opinião não devolveu o "
        f"PS ao degrau da máquina.")


def test_o_empurrao_do_ps_nao_espera_device_de_mouse():
    """Sem emulação de mouse o PS continua digitando — ele não passa por device.

    `apply_button_actions` sai antes quando não há device de mouse, e é certo
    que saia: as duas primeiras sacolas vão para devices. O PS não.

    A MORDIDA: mova o `self._empurrar_o_ps(profile)` para depois do
    `if device is None: return` — este caso reprova com o canal vazio.
    """
    recebidos: list[str | None] = []
    relatorio: dict[str, str] = {}
    gerente = _gerente(ps_action_sink=recebidos.append, mouse_device_provider=lambda: None)
    gerente.apply_button_actions(
        _perfil(button_actions={"ps": "KEY_F11"}), relatorio=relatorio)
    assert relatorio["button_actions"] == "ignorado_sem_device"
    assert recebidos == ["KEY_F11"], (
        "o mouse virtual estava de pé? Não — e mesmo assim o PS tinha de "
        "receber a escolha, porque quem o atende é o `ps_solo`.")


def test_o_canal_quebrado_nao_derruba_a_ativacao():
    """O PS é um botão entre vinte e dois; uma exceção aqui levaria o perfil todo.

    A MORDIDA: tire o `try/except` de `_empurrar_o_ps` — este caso reprova com
    a exceção subindo.
    """
    def _explode(_token: str | None) -> None:
        raise RuntimeError("o canal caiu")

    gerente = _gerente(ps_action_sink=_explode)
    gerente.apply_button_actions(_perfil(button_actions={"ps": "KEY_F11"}))


def test_o_canal_do_ps_chega_pela_fabrica_do_gerente():
    """`gerente_do_daemon` injeta o canal — sem ele nada disto liga.

    É a lição do `mouse_device_provider`: o campo existir e a fábrica não o
    preencher é "a cura escrita e nunca ligada", o defeito mais caro desta casa.

    A MORDIDA: apague a linha `"ps_action_sink": _canal_do_ps(daemon)` da
    fábrica — este caso reprova, e o PS volta a não digitar nunca.
    """
    from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

    daemon = _daemon()
    gerente = gerente_do_daemon(
        daemon, controller=SimpleNamespace(), store=SimpleNamespace())
    assert gerente.ps_action_sink is not None
    gerente.ps_action_sink("KEY_F11")
    assert hotkey.acao_do_ps_do_perfil(daemon) == "KEY_F11", (
        "a fábrica entregou um canal que não chega ao subsistema de hotkey.")


# ===========================================================================
# §4 — O TOQUE FAZ AS DUAS COISAS
# ===========================================================================


def test_o_ps_digita_de_verdade_pelo_teclado_virtual(steam):
    """A tecla sai pelo device, press e release, com o `syn` de cada metade."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    hotkey.build_ps_solo_callback(daemon)()
    assert dev.emitidos == [("KEY_F11", 1), ("KEY_F11", 0)], (
        f"o device recebeu {dev.emitidos!r} — o toque no PS tinha de emitir "
        f"F11 e soltá-lo.")
    assert steam == ["steam"], "e sem parar de abrir a Steam — a palavra dela."


def test_o_ps_digita_combo(steam):
    """Um combo colado com `+` sai inteiro, e solta em ordem reversa."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_LEFTALT+KEY_TAB")
    hotkey.build_ps_solo_callback(daemon)()
    assert dev.emitidos == [
        ("KEY_LEFTALT", 1), ("KEY_TAB", 1), ("KEY_TAB", 0), ("KEY_LEFTALT", 0)]


def test_o_perfil_vence_a_maquina_calada(steam):
    """A ARMADILHA QUE A SPRINT NOMEIA, e ela é a razão da ordem do código.

    Com `ps_button_action = "none"` como PRIMEIRA porta, um perfil que escolheu
    uma tecla para o PS ficaria mudo por causa de uma config de máquina que ela
    nunca viu.

    A MORDIDA: ponha `if cfg.ps_button_action == "none": return` de volta como
    primeira linha de `_on_ps_solo` — este caso reprova com o device vazio.
    """
    teclado, dev = _teclado()
    daemon = _daemon(
        acao_da_maquina="none", teclado=teclado, escolha_do_perfil="KEY_F11")
    hotkey.build_ps_solo_callback(daemon)()
    assert dev.emitidos == [("KEY_F11", 1), ("KEY_F11", 0)], (
        "a máquina calada calou o perfil: a escolha dela na linha do PS não "
        "chegou ao teclado.")
    assert steam == [], "e a máquina em `none` continua sem abrir a Steam."


def test_a_maquina_calada_continua_calando_o_ps_sem_perfil(steam):
    """O que já funcionava continua: `none` + perfil calado = nada."""
    teclado, dev = _teclado()
    daemon = _daemon(acao_da_maquina="none", teclado=teclado)
    hotkey.build_ps_solo_callback(daemon)()
    assert dev.emitidos == []
    assert steam == []


def test_o_nada_do_perfil_cala_as_duas_metades(steam):
    """`— Nada —` na linha do PS é ela dizendo que o botão não faz nada.

    É o espelho exato do `ps_button_action = "none"`: um fato, dois donos, e a
    precedência escrita. A tabela mostrando `— Nada —` e o botão abrindo a
    Steam seria a janela mentindo.
    """
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil=acoes.TOKEN_NADA)
    hotkey.build_ps_solo_callback(daemon)()
    assert dev.emitidos == []
    assert steam == []


def test_o_steam_do_perfil_vence_a_maquina_calada(steam):
    """E o contrário também: `Abrir a Steam` no perfil abre, com a máquina em `none`."""
    daemon = _daemon(acao_da_maquina="none", escolha_do_perfil=acoes.TOKEN_STEAM)
    hotkey.build_ps_solo_callback(daemon)()
    assert steam == ["steam"]


def test_a_escolha_sem_atendente_nao_digita_e_nao_cala_a_maquina(steam):
    """`Escolher um programa…` no PS: dívida declarada, não silêncio.

    O caminho do programa EXISTE (`DaemonConfig.ps_button_command`), mas mora na
    máquina e não no perfil. Enquanto o perfil não tiver campo de caminho, a
    escolha não dispara — e o degrau da máquina segue valendo, em vez de o
    botão morrer.
    """
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil=acoes.TOKEN_PROGRAMA)
    hotkey.build_ps_solo_callback(daemon)()
    assert dev.emitidos == [], "`__PROGRAMA__` não é tecla e não pode ir ao device."
    assert steam == ["steam"], "e o degrau da máquina continua de pé."


def test_o_modo_jogo_pula_as_duas_metades(steam):
    """Com o controle dedicado a um jogo, digitar é pior que abrir a Steam.

    A MORDIDA: apague a guarda do `_emulation_suppressed` — este caso reprova
    com a tecla emitida dentro da partida dela.
    """
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11", suprimido=True)
    hotkey.build_ps_solo_callback(daemon)()
    assert dev.emitidos == []
    assert steam == []


def test_o_modo_nativo_pula_as_duas_metades(steam):
    """A MORDIDA: apague a guarda do `native_mode_active`."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11", nativo=True)
    hotkey.build_ps_solo_callback(daemon)()
    assert dev.emitidos == []
    assert steam == []


def test_o_combo_continua_ganhando_do_solo(steam):
    """PS+↑ troca de perfil e NÃO digita — o latch do combo fica inteiro.

    Aqui não há dublê de `HotkeyManager`: é o detector de verdade, com o combo
    de fábrica (`DEFAULT_COMBO_NEXT`), porque quem suprime o solo é ele
    (`_ps_combo_fired`) e não o callback.
    """
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    trocou: list[str] = []
    mgr = HotkeyManager(
        on_next=lambda: trocou.append("next"),
        on_ps_solo=hotkey.build_ps_solo_callback(daemon),
        config=HotkeyConfig(buffer_ms=0),
    )
    mgr.observe(list(DEFAULT_COMBO_NEXT), now=0.0)
    mgr.observe([], now=0.20)
    assert trocou == ["next"], "o combo PS+↑ tinha de trocar de perfil."
    assert dev.emitidos == [], (
        "o PS+↑ DIGITOU: o combo passou a digitar a tecla do PS além de trocar "
        "de perfil.")
    assert steam == []


def test_segurar_para_religar_continua_nao_digitando(steam):
    """PS-TOQUE-CURTO-01: acima do teto o release não é toque, e não digita.

    O gesto de religar o controle no rádio (segurar ~5 s) atravessa este mesmo
    caminho, e o teto é anterior a tudo.
    """
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    mgr = HotkeyManager(
        on_ps_solo=hotkey.build_ps_solo_callback(daemon),
        config=HotkeyConfig(buffer_ms=0, ps_toque_curto_teto_ms=1000),
    )
    mgr.observe(["ps"], now=0.0)
    mgr.observe([], now=5.0382)
    assert dev.emitidos == []
    assert steam == []


def test_sem_teclado_virtual_o_ps_nao_digita_e_a_steam_continua(steam):
    """"Sem device" não é "aplicou" nem "falhou" — e não pode custar a Steam."""
    daemon = _daemon(teclado=None, escolha_do_perfil="KEY_F11")
    hotkey.build_ps_solo_callback(daemon)()
    assert steam == ["steam"]


def test_o_teclado_parado_nao_conta_como_digitado(steam):
    """Device criado e depois parado: o produto não pode dizer que emitiu."""
    teclado, dev = _teclado()
    teclado._device = None
    teclado._uinput_mod = None
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    assert hotkey._digitar_o_ps(daemon, "KEY_F11") is False
    assert dev.emitidos == []


# ===========================================================================
# §5 — A ORDEM, E O QUE O TOQUE NÃO PODE ESTRAGAR
# ===========================================================================


def test_a_tecla_sai_antes_da_steam(steam, monkeypatch):
    """`open_or_focus_steam()` muda o foco: o que vier depois chega à Steam.

    A MORDIDA: inverta as duas metades em `_on_ps_solo` — este caso reprova
    imprimindo a ordem medida. Um teste que passasse nas duas ordens não mediria
    a decisão.
    """
    teclado, _dev = _teclado()
    ordem = steam  # a MESMA lista: é o que torna a ordem mensurável

    def _anota_press(botao: str) -> None:
        ordem.append("tecla")

    monkeypatch.setattr(
        UinputKeyboardDevice, "_emit_sequence_press", lambda _self, b: _anota_press(b))
    monkeypatch.setattr(
        UinputKeyboardDevice, "_emit_sequence_release", lambda _self, b: None)

    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    hotkey.build_ps_solo_callback(daemon)()
    assert ordem == ["tecla", "steam"], (
        f"a ordem medida foi {ordem!r}: a Steam roubou o foco antes de a tecla "
        f"sair, e a tecla chegou à Steam em vez de chegar ao que estava na "
        f"frente dela.")


def test_o_toque_nao_solta_o_que_estava_segurado(steam):
    """O toque no PS não pode mexer no rastreador de bordas do `dispatch`.

    `dispatch()` é SNAPSHOT: chamá-lo com `{"ps"}` faria
    `newly_released = _pressed_buttons - {"ps"}` soltar toda tecla segurada, e
    o tique seguinte a pressionaria de novo — um caractere dobrado no meio do
    que ela estivesse digitando.

    A MORDIDA: troque o par `_emit_sequence_press`/`_release` de `_digitar_o_ps`
    por dois `dispatch()` — este caso reprova mostrando o `circle` solto.
    """
    teclado, dev = _teclado()
    teclado.bindings = {"circle": ("KEY_ENTER",)}
    teclado.dispatch(frozenset({"circle"}))
    assert dev.emitidos == [("KEY_ENTER", 1)]

    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    hotkey.build_ps_solo_callback(daemon)()

    assert dev.emitidos == [
        ("KEY_ENTER", 1), ("KEY_F11", 1), ("KEY_F11", 0)], (
        f"o device recebeu {dev.emitidos!r}: o toque no PS mexeu no que estava "
        f"segurado.")
    assert teclado._pressed_buttons == frozenset({"circle"})


def test_o_binding_do_ps_nao_fica_no_device(steam):
    """Depois do toque, o mapa do device volta ao que era.

    Deixar `"ps"` no mapa faria o `dispatch()` do poll loop emitir a tecla uma
    SEGUNDA vez no dia em que o latch do combo deixasse o PS passar para
    `emu_buttons` — e o produto não pode depender do latch para não digitar
    duas vezes.

    A MORDIDA: apague o `finally: teclado.bindings = antes` — este caso reprova.
    """
    teclado, _dev = _teclado()
    antes = dict(teclado.bindings)
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    hotkey.build_ps_solo_callback(daemon)()
    assert "ps" not in teclado.bindings
    assert teclado.bindings == antes
