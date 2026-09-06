"""O `— Nada —` cala as VINTE E DUAS, e o atalho dela sobrevive ao Guardar.

ONDA3-MOTOR-01, 06/09/2026. Os dois defeitos são de MOTOR, foram medidos pela
frente da aba 06 em 04/09 e relatados em vez de curados — os arquivos estavam no
`nao_toca` dela, e ela fez certo.

**O QUE ESTA RÉGUA MEDE É O APARELHO, NÃO A TELA.** A tela já dizia a verdade
sobre os dois: a tira da aba 06 nomeia as seis linhas que o `— Nada —` não cala,
e a linha 213 do CSV de paridade registra que só a metade DITA fechou. Uma régua
que lesse a tela daria VERDE sobre defeito vivo — que é a família de instrumento
falso que esta casa mais paga. Por isso aqui se emite evento num device com o
`uinput` dublado, e se lê o que saiu.

Os dois casos, pelo nome que a sprint lhes deu:

1. **o `— Nada —` que não calava seis linhas** — `set_button_actions`
   reconstruía `_mapa_dpad` e `_mapa_tap` do DE FÁBRICA menos `do_mouse`, e um
   botão calado nunca entra em `do_mouse`. Escapavam as quatro direções do
   d-pad, o Círculo e o Quadrado.
2. **o `resolver()` que não herdava `key_bindings`** — `apply_button_actions`
   roda DEPOIS do `apply_keyboard` e reescreve o conjunto INTEIRO do teclado
   virtual. Todo atalho que ela escreveu na janela antiga morria na ativação
   seguinte de qualquer perfil com `button_actions`.
"""
from __future__ import annotations

import types
from typing import Any

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    BUTTON_TO_UINPUT,
    DPAD_TO_KEY,
    EDGE_KEY_MAP,
    UinputMouseDevice,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import Profile

#: AS SEIS QUE ESCAPAVAM, derivadas dos mapas do dono e não digitadas: são
#: exatamente os botões que o device de mouse atende por tecla, e por isso os
#: únicos que a subtração por `do_mouse` não alcançava.
AS_SEIS: frozenset[str] = frozenset(DPAD_TO_KEY) | frozenset(EDGE_KEY_MAP)


class _UinputDeMentira:
    """O módulo `uinput`, e ele só conhece nomes que existem de verdade.

    Um objeto que respondesse a qualquer atributo imitaria um device que sabe
    tudo — e esta casa já pagou três vezes por dublê mais frouxo que a função
    real.
    """

    class _Ev:
        def __init__(self, nome: str) -> None:
            self.nome = nome

    def __getattr__(self, nome: str) -> Any:
        if nome.startswith(("KEY_", "BTN_", "REL_")):
            return _UinputDeMentira._Ev(nome)
        raise AttributeError(nome)


class _DeviceDeMentira:
    def __init__(self) -> None:
        self.saiu: list[tuple[str, int]] = []

    def emit(self, ev: Any, valor: int, syn: bool = True) -> None:
        self.saiu.append((ev.nome, valor))

    def syn(self) -> None:
        pass

    def destroy(self) -> None:
        pass


def _mouse_de_pe() -> tuple[UinputMouseDevice, _DeviceDeMentira]:
    """Um `UinputMouseDevice` que emite de verdade, sem tocar `/dev/uinput`."""
    d = UinputMouseDevice()
    fake = _DeviceDeMentira()
    d._device = fake
    d._uinput_mod = _UinputDeMentira()
    return d, fake


def _apertar(d: UinputMouseDevice, botao: str) -> None:
    """Uma borda de subida e uma de descida naquele botão, e nada mais.

    Os sticks vão no centro (128) e os gatilhos em zero de propósito: um valor
    fora disso injetaria `cross`/`triangle` por `_resolve_emulated_set` e
    sujaria a leitura com evento que não é do botão medido.
    """
    comum = dict(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0)
    d.dispatch(buttons=frozenset({botao}), now=1.0, **comum)  # type: ignore[arg-type]
    d.dispatch(buttons=frozenset(), now=2.0, **comum)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 1. o `— Nada —` cala — e quem responde é o que SAIU do device
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("botao", sorted(AS_SEIS))
def test_o_nada_cala_as_seis_que_escapavam(botao: str) -> None:
    """Ela põe `— Nada —`, e o botão para de emitir. Medido no evento.

    A MORDIDA: tire o `and b not in mudos` das duas compreensões de
    `uinput_mouse.set_button_actions` — este caso reprova nomeando o botão e a
    tecla que continuou saindo.
    """
    escolhas = {botao: acoes.TOKEN_NADA}
    do_mouse, _do_teclado, _sem = acoes.resolver(escolhas)
    calados = acoes.botoes_calados(escolhas)

    d, fake = _mouse_de_pe()
    d.set_button_actions(do_mouse, calados)
    _apertar(d, botao)

    assert fake.saiu == [], (
        f"{botao} está em “— Nada —” e o device emitiu {fake.saiu}: a escolha "
        f"dela foi confirmada na tela e o botão continuou fazendo o que fazia")


def test_as_vinte_e_duas_calam_e_nenhuma_sobra() -> None:
    """A conta fechada: `— Nada —` em TODAS, e o device fica sem mapa nenhum.

    Ela mede o conjunto, e não seis casos soltos, porque o defeito era de
    COBERTURA: dezesseis calavam e seis não, e o que se perdeu era a diferença.
    """
    escolhas = {b: acoes.TOKEN_NADA for b in acoes.BOTOES}
    do_mouse, do_teclado, _sem = acoes.resolver(escolhas)
    calados = acoes.botoes_calados(escolhas)

    d, _fake = _mouse_de_pe()
    d.set_button_actions(do_mouse, calados)

    ainda_falam = sorted(
        set(d._mapa_botoes) | set(d._mapa_dpad) | set(d._mapa_tap)
        | set(do_teclado))
    assert ainda_falam == [], (
        f"com as vinte e duas linhas em “— Nada —”, estes continuam com "
        f"endereço em algum mapa efetivo: {ainda_falam}")


def test_o_que_ja_calava_continua_calando() -> None:
    """A cura tem de EXPLICAR o que já funcionava — e não pode quebrá-lo.

    Os dezesseis que já calavam calavam por outra via: `_mapa_botoes` e o
    `set_bindings` do teclado virtual são SUBSTITUÍDOS inteiros. Se a cura
    tivesse mexido nessa via, isto reprovaria.
    """
    for botao in ("cross", "triangle", "r3"):
        escolhas = {botao: acoes.TOKEN_NADA}
        do_mouse, _t, _s = acoes.resolver(escolhas)
        d, fake = _mouse_de_pe()
        d.set_button_actions(do_mouse, acoes.botoes_calados(escolhas))
        _apertar(d, botao)
        assert fake.saiu == [], f"{botao} já calava antes e passou a emitir"

    for botao in ("options", "create", "l1", "r1"):
        escolhas = {botao: acoes.TOKEN_NADA}
        _m, do_teclado, _s = acoes.resolver(escolhas)
        assert botao not in do_teclado, (
            f"{botao} já calava pelo teclado virtual e voltou a ter binding")


def test_sem_a_sacola_o_device_e_o_de_antes_byte_a_byte() -> None:
    """`calados=None` é o contrato de antes — nenhum chamador antigo muda.

    O `interface/pacotes/a06_navegacao.py` e a régua da aba 06 chamam
    `set_button_actions(do_mouse)` com um argumento só, e continuam a valer.
    """
    do_mouse, _t, _s = acoes.resolver({"dpad_up": "BTN_LEFT"})
    velho = types.SimpleNamespace()
    UinputMouseDevice.set_button_actions(velho, do_mouse)
    novo = types.SimpleNamespace()
    UinputMouseDevice.set_button_actions(novo, do_mouse, None)
    assert velho._mapa_dpad == novo._mapa_dpad
    assert velho._mapa_tap == novo._mapa_tap
    assert velho._mapa_botoes == novo._mapa_botoes
    assert "dpad_up" not in velho._mapa_dpad, (
        "o botão que virou `BTN_LEFT` tem de sair do d-pad — é a subtração "
        "que já existia, e ela não pode ter sido perdida na cura")


def test_o_de_fabrica_nao_cala_ninguem() -> None:
    """Perfil sem escolha nenhuma: nada calado, e o device fica de fábrica."""
    assert acoes.botoes_calados(None) == frozenset()
    assert acoes.botoes_calados({}) == frozenset()
    d, _fake = _mouse_de_pe()
    d.set_button_actions(None)
    assert d._mapa_dpad == DPAD_TO_KEY
    assert d._mapa_tap == EDGE_KEY_MAP
    assert d._mapa_botoes == BUTTON_TO_UINPUT


# ---------------------------------------------------------------------------
# 2. o atalho dela sobrevive ao Guardar da tela nova
# ---------------------------------------------------------------------------
def test_o_resolver_herda_os_atalhos_dela() -> None:
    """O que ela escreveu na janela antiga chega ao teclado virtual.

    A MORDIDA: apague o bloco `if key_bindings is not None:` de
    `_tabela_efetiva` — este caso reprova mostrando o `KEY_LEFTMETA` de fábrica
    no lugar do `KEY_F1` dela.
    """
    dela = {"options": ["KEY_F1"], "l1": ["KEY_F2", "KEY_LEFTCTRL"]}
    _m, sem_herdar, _s = acoes.resolver({"cross": "KEY_ENTER"})
    _m, com_herdar, _s = acoes.resolver({"cross": "KEY_ENTER"}, dela)

    assert sem_herdar["options"] == ("KEY_LEFTMETA",), (
        "a linha de base mudou: sem herdar, o `options` tem de ser o de fábrica")
    assert com_herdar["options"] == ("KEY_F1",), (
        f"o atalho que ela escreveu à mão não chegou ao device: "
        f"{com_herdar.get('options')}")
    assert com_herdar["l1"] == ("KEY_F2", "KEY_LEFTCTRL"), (
        "o combo dela chegou partido ou não chegou")


def test_a_escolha_da_tela_nova_vence_o_atalho_antigo() -> None:
    """A precedência é a das três camadas, e a última é a que ela acabou de ver.

    Se o `key_bindings` vencesse, o "Guardar" da tela nova não guardaria — e o
    defeito trocaria de lado em vez de fechar.
    """
    dela = {"options": ["KEY_F1"]}
    _m, do_teclado, _s = acoes.resolver({"options": "KEY_ESC"}, dela)
    assert do_teclado["options"] == ("KEY_ESC",), (
        f"a escolha da tela nova não venceu o atalho antigo: "
        f"{do_teclado.get('options')}")


def test_o_r3_fica_fora_da_camada_e_continua_botao_do_meio() -> None:
    """A colisão escrita continua escrita — o `r3` não é do domínio do teclado.

    O `r3` está nos DOIS lados (`BUTTON_TO_UINPUT` diz `BTN_MIDDLE`,
    `DEFAULT_BUTTON_BINDINGS` diz "fechar o teclado na tela") e o produto faz os
    dois. Uma camada que digitasse a lista em vez de perguntar ao de fábrica
    apagaria o Botão do meio dele — regressão em botão que ela usa.
    """
    assert "r3" not in acoes.DOMINIO_DO_TECLADO
    assert frozenset(DEFAULT_BUTTON_BINDINGS) - {"r3"} == acoes.DOMINIO_DO_TECLADO
    do_mouse, _t, _s = acoes.resolver({"cross": "KEY_ENTER"}, {"options": ["KEY_F1"]})
    assert do_mouse.get("r3") == "BTN_MIDDLE", (
        "a camada de atalhos comeu o Botão do meio do R3")


def test_o_dict_vazio_e_o_none_sao_coisas_diferentes() -> None:
    """`None` HERDA e `{}` ESVAZIA — o mesmo contrato de `resolve_key_bindings`.

    O `{}` é ela tendo removido tudo na janela antiga, e o `apply_keyboard` já
    entrega um teclado mudo nesse caso. Se esta camada mesclasse com o de
    fábrica, os dois appliers voltariam a discordar — que é o defeito inteiro.
    """
    _m, herdando, _s = acoes.resolver({"cross": "KEY_ENTER"}, None)
    assert herdando["options"] == ("KEY_LEFTMETA",)
    _m, esvaziado, _s = acoes.resolver({"cross": "KEY_ENTER"}, {})
    assert not (set(esvaziado) & acoes.DOMINIO_DO_TECLADO), (
        f"ela esvaziou o teclado na janela antiga e o `button_actions` "
        f"ressuscitou {sorted(set(esvaziado) & acoes.DOMINIO_DO_TECLADO)}")


def test_a_ativacao_inteira_nao_apaga_mais_o_atalho_dela() -> None:
    """O CAMINHO DE VERDADE: `apply_keyboard` escreve, `apply_button_actions` NÃO apaga.

    É a forma em que o defeito se manifestava para ela: os dois campos no
    arquivo, o perfil ativando, e o atalho morrendo em silêncio no segundo
    applier.

    A MORDIDA: tire o `profile.key_bindings` da chamada a `resolver()` em
    `apply_button_actions` — este caso reprova mostrando o de fábrica onde
    estava o atalho dela.
    """
    class _Teclado:
        def __init__(self) -> None:
            self.tem: dict[str, tuple[str, ...]] = {}

        def set_bindings(self, b: dict[str, tuple[str, ...]]) -> None:
            self.tem = dict(b)

    class _Mouse:
        def __init__(self) -> None:
            self.recebeu: dict[str, str] | None = None
            self.calados: frozenset[str] | None = None

        def set_button_actions(
            self, do_mouse: dict[str, str] | None,
            calados: frozenset[str] | None = None,
        ) -> None:
            self.recebeu = do_mouse
            self.calados = calados

    teclado, mouse = _Teclado(), _Mouse()
    m = ProfileManager(
        controller=None,
        mouse_device_provider=lambda: mouse,
        keyboard_device_provider=lambda: teclado,
    )
    perfil = Profile(
        name="t", match={"type": "any"},
        key_bindings={"options": ["KEY_F1"], "l1": ["KEY_F2"]},
        button_actions={"dpad_up": acoes.TOKEN_NADA},
    )
    m.apply_keyboard(perfil)
    assert teclado.tem["options"] == ("KEY_F1",), "a linha de base já falhou"
    m.apply_button_actions(perfil)

    assert teclado.tem.get("options") == ("KEY_F1",), (
        f"o `apply_button_actions` apagou o atalho que ela escreveu à mão: "
        f"options virou {teclado.tem.get('options')}")
    assert teclado.tem.get("l1") == ("KEY_F2",), (
        f"o combo dela não sobreviveu: l1 virou {teclado.tem.get('l1')}")
    assert mouse.calados is not None and "dpad_up" in mouse.calados, (
        "o device de mouse não soube que o `dpad_up` foi calado — a sacola não "
        "chegou pelo caminho de verdade")
