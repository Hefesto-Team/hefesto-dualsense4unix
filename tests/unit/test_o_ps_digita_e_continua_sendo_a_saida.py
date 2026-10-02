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


class _UinputDeMentira:
    """O módulo `uinput` visto pelo device: cada `KEY_*` é um evento próprio."""

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
    """A Steam de mentira — e ela anota NA MESMA LISTA que as teclas."""
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

    with pytest.raises(ValueError, match="não é uma ação conhecida"):
        _perfil(button_actions={"ps": "__NAO_EXISTE__"})
    with pytest.raises(ValueError, match="não é um dos botões da tela"):
        _perfil(button_actions={"botao_que_nao_existe": "KEY_F11"})


def test_o_de_fabrica_da_linha_do_ps_e_nenhuma_tecla():
    """A linha do PS só digita (01/10/2026): o de fábrica dela é «— Sem tecla —».

    O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01, `D-0110-A-LINHA-DO-PS-SO-DIGITA`
    (por delegação, a validar por ela). Até ali o de fábrica dela era o degrau
    da máquina (`DaemonConfig.ps_button_action`, «Abrir a Steam»), e o PS tinha
    dois donos para o mesmo ato. O que o toque no PS faz no computador é o ⑥ da
    tabela dos gestos; a linha não lê mais o degrau.

    A MORDIDA: devolva `fora[BOTAO_PS] = TOKEN_STEAM` ao fim de `acoes.padrao()`
    e este caso reprova nomeando o rótulo.
    """
    assert acoes.padrao()["ps"] == acoes.TOKEN_SEM_TECLA, (
        f"o de fábrica da linha do PS saiu {acoes.rotulo(acoes.padrao()['ps'])!r}")
    assert acoes.rotulo(acoes.padrao()["ps"]) == "— Sem tecla —"


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
    """`SEM_ATENDENTE` continua valendo para todo mundo menos o PS."""
    _m, _t, sem_dono = acoes.resolver({"cross": acoes.TOKEN_STEAM})
    assert "cross" in sem_dono, (
        "o `__STEAM__` escolhido para o X deixou de ir para a terceira sacola: "
        "a saída do PS vazou para os outros vinte e um.")
    _m, _t, gatilho = acoes.resolver({"l2": "KEY_ESC"})
    assert "l2" in gatilho


def test_a_porta_do_ps_distingue_o_calado_do_nada():
    """`None` não é `__NADA__`, e a diferença decide quem manda no botão."""
    assert acoes.acao_do_ps(None) is None
    assert acoes.acao_do_ps({}) is None
    assert acoes.acao_do_ps({"cross": "KEY_ESC"}) is None
    assert acoes.acao_do_ps({"ps": acoes.TOKEN_NADA}) == acoes.TOKEN_NADA
    assert acoes.acao_do_ps({"ps": "KEY_F11"}) == "KEY_F11"


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
    """O PS é um botão entre vinte e dois; uma exceção aqui levaria o perfil todo."""
    def _explode(_token: str | None) -> None:
        raise RuntimeError("o canal caiu")

    gerente = _gerente(ps_action_sink=_explode)
    gerente.apply_button_actions(_perfil(button_actions={"ps": "KEY_F11"}))


def test_o_canal_do_ps_chega_pela_fabrica_do_gerente():
    """`gerente_do_daemon` injeta o canal — sem ele nada disto liga."""
    from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

    daemon = _daemon()
    gerente = gerente_do_daemon(
        daemon, controller=SimpleNamespace(), store=SimpleNamespace())
    assert gerente.ps_action_sink is not None
    gerente.ps_action_sink("KEY_F11")
    assert hotkey.acao_do_ps_do_perfil(daemon) == "KEY_F11", (
        "a fábrica entregou um canal que não chega ao subsistema de hotkey.")


def test_o_ps_digita_de_verdade_pelo_teclado_virtual(steam):
    """A tecla sai pelo device, press e release, com o `syn` de cada metade."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert dev.emitidos == [("KEY_F11", 1), ("KEY_F11", 0)], (
        f"o device recebeu {dev.emitidos!r} — o toque no PS tinha de emitir "
        f"F11 e soltá-lo.")
    assert steam == ["steam"], "e sem parar de abrir a Steam — a palavra dela."


def test_o_ps_digita_combo(steam):
    """Um combo colado com `+` sai inteiro, e solta em ordem reversa."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_LEFTALT+KEY_TAB")
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert dev.emitidos == [
        ("KEY_LEFTALT", 1), ("KEY_TAB", 1), ("KEY_TAB", 0), ("KEY_LEFTALT", 0)]


def test_o_perfil_vence_a_maquina_calada(steam):
    """A ARMADILHA QUE A SPRINT NOMEIA, e ela é a razão da ordem do código."""
    teclado, dev = _teclado()
    daemon = _daemon(
        acao_da_maquina="none", teclado=teclado, escolha_do_perfil="KEY_F11")
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert dev.emitidos == [("KEY_F11", 1), ("KEY_F11", 0)], (
        "a máquina calada calou o perfil: a escolha dela na linha do PS não "
        "chegou ao teclado.")
    assert steam == [], "e a máquina em `none` continua sem abrir a Steam."


def test_a_maquina_calada_continua_calando_o_ps_sem_perfil(steam):
    """O que já funcionava continua: `none` + perfil calado = nada."""
    teclado, dev = _teclado()
    daemon = _daemon(acao_da_maquina="none", teclado=teclado)
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert dev.emitidos == []
    assert steam == []


def test_o_nada_antigo_do_perfil_nao_cala_o_sexto(steam):
    """O `— Nada —` que um perfil antigo guarde na linha do PS não cala mais nada."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil=acoes.TOKEN_NADA)
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert dev.emitidos == []
    assert steam == ["steam"]


def test_o_steam_antigo_do_perfil_nao_vence_o_sexto(steam):
    """E o contrário: o `Abrir a Steam` antigo da linha não abre com o ⑥ em «Nada»."""
    daemon = _daemon(acao_da_maquina="none", escolha_do_perfil=acoes.TOKEN_STEAM)
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert steam == []


def test_a_escolha_sem_atendente_nao_digita_e_nao_cala_a_maquina(steam):
    """`Escolher um programa…` no PS: dívida declarada, não silêncio."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil=acoes.TOKEN_PROGRAMA)
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert dev.emitidos == [], "`__PROGRAMA__` não é tecla e não pode ir ao device."
    assert steam == ["steam"], "e o degrau da máquina continua de pé."


def test_o_modo_jogo_pula_as_duas_metades(steam):
    """Com o controle dedicado a um jogo, digitar é pior que abrir a Steam."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11", suprimido=True)
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert dev.emitidos == []
    assert steam == []


def test_o_modo_nativo_pula_as_duas_metades(steam):
    """A MORDIDA: apague a guarda do `native_mode_active`."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11", nativo=True)
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert dev.emitidos == []
    assert steam == []


def test_o_combo_continua_ganhando_do_solo(steam):
    """PS+↑ troca de perfil e NÃO digita — o latch do combo fica inteiro."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    trocou: list[str] = []
    gesto = hotkey.build_ps_solo_callback(daemon)
    mgr = HotkeyManager(
        on_next=lambda: trocou.append("next"),
        on_ps_solo=gesto,
        config=HotkeyConfig(buffer_ms=0),
    )
    mgr.observe(list(DEFAULT_COMBO_NEXT), now=0.0)
    mgr.observe([], now=0.20)
    assert gesto.esperar(5.0)
    assert trocou == ["next"], "o combo PS+↑ tinha de trocar de perfil."
    assert dev.emitidos == [], (
        "o PS+↑ DIGITOU: o combo passou a digitar a tecla do PS além de trocar "
        "de perfil.")
    assert steam == []


def test_segurar_para_religar_continua_nao_digitando(steam):
    """PS-TOQUE-CURTO-01: acima do teto o release não é toque, e não digita."""
    teclado, dev = _teclado()
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    gesto = hotkey.build_ps_solo_callback(daemon)
    mgr = HotkeyManager(
        on_ps_solo=gesto,
        config=HotkeyConfig(buffer_ms=0, ps_toque_curto_teto_ms=1000),
    )
    mgr.observe(["ps"], now=0.0)
    mgr.observe([], now=5.0382)
    assert gesto.esperar(5.0)
    assert dev.emitidos == []
    assert steam == []


def test_sem_teclado_virtual_o_ps_nao_digita_e_a_steam_continua(steam):
    """"Sem device" não é "aplicou" nem "falhou" — e não pode custar a Steam."""
    daemon = _daemon(teclado=None, escolha_do_perfil="KEY_F11")
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert steam == ["steam"]


def test_o_teclado_parado_nao_conta_como_digitado(steam):
    """Device criado e depois parado: o produto não pode dizer que emitiu."""
    teclado, dev = _teclado()
    teclado._device = None
    teclado._uinput_mod = None
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    assert hotkey._digitar_o_ps(daemon, "KEY_F11") is False
    assert dev.emitidos == []


def test_a_tecla_sai_antes_da_steam(steam, monkeypatch):
    """`open_or_focus_steam()` muda o foco: o que vier depois chega à Steam."""
    teclado, _dev = _teclado()
    ordem = steam

    def _anota_press(botao: str) -> None:
        ordem.append("tecla")

    monkeypatch.setattr(
        UinputKeyboardDevice, "_emit_sequence_press", lambda _self, b: _anota_press(b))
    monkeypatch.setattr(
        UinputKeyboardDevice, "_emit_sequence_release", lambda _self, b: None)

    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert ordem == ["tecla", "steam"], (
        f"a ordem medida foi {ordem!r}: a Steam roubou o foco antes de a tecla "
        f"sair, e a tecla chegou à Steam em vez de chegar ao que estava na "
        f"frente dela.")


def test_o_toque_nao_solta_o_que_estava_segurado(steam):
    """O toque no PS não pode mexer no rastreador de bordas do `dispatch`."""
    teclado, dev = _teclado()
    teclado.bindings = {"circle": ("KEY_ENTER",)}
    teclado.dispatch(frozenset({"circle"}))
    assert dev.emitidos == [("KEY_ENTER", 1)]

    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)

    assert dev.emitidos == [
        ("KEY_ENTER", 1), ("KEY_F11", 1), ("KEY_F11", 0)], (
        f"o device recebeu {dev.emitidos!r}: o toque no PS mexeu no que estava "
        f"segurado.")
    assert teclado._pressed_buttons == frozenset({"circle"})


def test_o_binding_do_ps_nao_fica_no_device(steam):
    """Depois do toque, o mapa do device volta ao que era."""
    teclado, _dev = _teclado()
    antes = dict(teclado.bindings)
    daemon = _daemon(teclado=teclado, escolha_do_perfil="KEY_F11")
    gesto = hotkey.build_ps_solo_callback(daemon)
    gesto()
    assert gesto.esperar(5.0)
    assert "ps" not in teclado.bindings
    assert teclado.bindings == antes
