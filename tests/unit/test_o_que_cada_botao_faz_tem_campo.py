#!/usr/bin/env python3
"""A RÉGUA DO CAMPO NOVO: o que cada botão faz sai do perfil e CHEGA ao aparelho.

DECISÃO DELA, 01/09/2026, ao ler a medição de que doze das vinte e uma linhas da
aba Navegação aceitavam escolha e não tinham onde ser guardadas: *"ganha campo.
essa é a parte das features que precisam ou serem ajustadas ou desenvolvidas."*

A CADEIA TEM QUATRO ELOS, e esta régua morde os quatro. Faltando um, o campo
vira a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em tamanho natural: uma escolha que
grava, aparece na tela e não acende nada.

    1. o PADRÃO é derivado dos mapas do produto, e não digitado
    2. o CAMPO existe no perfil e recusa o que não conhece
    3. a RESOLUÇÃO separa quem atende cada escolha — e diz quem NÃO atende
    4. o DEVICE obedece, e volta ao de fábrica quando o perfil não opina

O ELO 1 É O QUE JUSTIFICA OS OUTROS: o padrão era digitado no gerador da tela, e
já divergia. Medido no dia: a tela dizia que as três regiões do touchpad fazem
*Botão esquerdo · Botão direito · F11*, e o produto faz *Backspace · Enter ·
Delete*. Três linhas de vinte e uma, erradas desde que foram escritas, porque
nada as comparava.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))


# --------------------------------------------------------------------------
# 1. o padrão é DERIVADO
# --------------------------------------------------------------------------
def test_o_padrao_sai_dos_mapas_do_produto() -> None:
    """Cada linha do padrão tem de casar com o mapa que a produz.

    A MORDIDA ESTÁ NA PRÓPRIA FORMA: troque um valor em `BUTTON_TO_UINPUT` e
    este caso reprova até que a tabela o acompanhe. Era exatamente isso que não
    acontecia com a cópia escrita no gerador da tela.
    """
    from hefesto_dualsense4unix.core.acoes_de_botao import padrao
    from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS
    from hefesto_dualsense4unix.integrations.uinput_mouse import (
        BUTTON_TO_UINPUT,
        DPAD_TO_KEY,
        EDGE_KEY_MAP,
    )

    p = padrao()
    for botao, token in BUTTON_TO_UINPUT.items():
        assert p[botao] == token, f"{botao}: o padrão diz {p[botao]!r}, o mouse diz {token!r}"
    for botao, tecla in DPAD_TO_KEY.items():
        assert p[botao] == tecla, f"{botao}: o padrão diz {p[botao]!r}, o d-pad diz {tecla!r}"
    for botao, tecla in EDGE_KEY_MAP.items():
        assert p[botao] == tecla, f"{botao}: o padrão diz {p[botao]!r}, o tap diz {tecla!r}"
    for botao, ligacao in DEFAULT_BUTTON_BINDINGS.items():
        if botao in BUTTON_TO_UINPUT:
            continue  # (noqa-acento) o mouse tem precedência — ver o docstring da função
        assert p[botao] == "+".join(ligacao), (
            f"{botao}: o padrão diz {p[botao]!r}, o teclado diz {'+'.join(ligacao)!r}")


def test_os_gatilhos_seguem_os_botoes_que_o_produto_injeta() -> None:
    """L2 e R2 não têm mapa próprio: o produto os injeta como cross e triangle.

    Digitar `BTN_LEFT` para o L2 daria certo hoje e mentiria no dia em que o
    `cross` mudasse — que é a forma exata do defeito que este módulo cura.
    """
    from hefesto_dualsense4unix.core.acoes_de_botao import padrao

    p = padrao()
    assert p["l2"] == p["cross"], "o L2 deixou de acompanhar o cross"
    assert p["r2"] == p["triangle"], "o R2 deixou de acompanhar o triangle"


def test_as_vinte_e_uma_linhas_tem_padrao_e_rotulo() -> None:
    """Linha sem padrão é `<select>` que abre vazio; sem rótulo, é token cru na tela.

    O NÚMERO DEIXOU DE SER DIGITADO — 06/09/2026. Estava escrito
    `assert len(BOTOES) == 21`, com a queixa *"a tela mostra 21 linhas e BOTOES
    tem N"* — e a régua **afirmava** o que a tela mostra em vez de perguntar a
    ela. Quando o PS entrou no produto (ONDA5-06-01), foi este `21` que
    reprovou, e a queixa dizia a verdade pela metade: a tela mostrava 21 porque
    ainda não tinha sido gerada, não porque 21 fosse o certo.

    **AGORA ELA PERGUNTA À TELA**, contando os `data-linha` da página publicada
    — a que o produto renderiza. É a mesma pergunta, com o dono no lugar do
    número, e ela passa a pegar o defeito nos DOIS sentidos: o produto que anda
    sem a tela, e a tela que anda sem o produto.

    A MORDIDA: tire uma linha de `aba06.BOTOES` e regere a página — este caso a
    nomeia.
    """
    from hefesto_dualsense4unix.core.acoes_de_botao import ACOES, BOTOES, padrao
    from hefesto_dualsense4unix.interface import onde

    p = padrao()
    doc = onde.pagina("06-navegacao.html", publicado=True).read_text(encoding="utf-8")
    na_tela = set(re.findall(r'<select[^>]*data-linha="([^"]+)"', doc))
    assert na_tela == set(BOTOES), (
        f"a tela e o produto contam listas diferentes — a mais na tela: "
        f"{sorted(na_tela - set(BOTOES))}; a menos: {sorted(set(BOTOES) - na_tela)}")
    faltando = [b for b in BOTOES if b not in p]
    assert not faltando, f"sem padrão: {faltando}"
    sem_rotulo = [f"{b}={p[b]}" for b in BOTOES if p[b] not in ACOES]
    assert not sem_rotulo, (
        f"o padrão destas linhas usa um token que a lista da tela não oferece: "
        f"{sem_rotulo}\nA tela não conseguiria MOSTRAR o que o produto faz — foi "
        f"assim que as três regiões do touchpad ficaram erradas.")


# --------------------------------------------------------------------------
# 2. o campo existe e recusa dizendo
# --------------------------------------------------------------------------
def test_o_perfil_guarda_a_escolha() -> None:
    from hefesto_dualsense4unix.profiles.schema import Profile

    p = Profile(name="t", match={"type": "any"}, button_actions={"cross": "KEY_ENTER"})
    assert p.button_actions == {"cross": "KEY_ENTER"}
    assert Profile(name="t", match={"type": "any"}).button_actions is None, (
        "o padrão do campo tem de ser `None` — que quer dizer HERDA o de fábrica, "
        "e é diferente de `{}`")


@pytest.mark.parametrize(
    ("ruim", "pedaco"),
    [({"nao_existe": "KEY_ENTER"}, "não é um dos botões"),
     ({"cross": "KEY_INVENTADA"}, "não é uma ação conhecida")])
def test_o_perfil_recusa_dizendo_o_que(ruim: dict[str, str], pedaco: str) -> None:
    """Um perfil de outra máquina com um nome que esta versão não conhece tem de
    dizer QUAL — senão a mensagem vira "perfil inválido" e a pessoa perde a tarde.
    """
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.schema import Profile

    with pytest.raises(ValidationError) as erro:
        Profile(name="t", match={"type": "any"}, button_actions=ruim)
    assert pedaco in str(erro.value), str(erro.value)


# --------------------------------------------------------------------------
# 3. a resolução separa quem atende — e diz quem não atende
# --------------------------------------------------------------------------
def test_a_escolha_vai_para_o_device_certo() -> None:
    """`BTN_*` é do mouse, `KEY_*` é do teclado, e um botão fica em UM só.

    Estar nos dois faria o mesmo aperto emitir duas vezes — que é a colisão que
    o `keyboard_mappings.py:47-52` já registrava para o `r3`.
    """
    from hefesto_dualsense4unix.core.acoes_de_botao import resolver

    do_mouse, do_teclado, _ = resolver({"dpad_up": "BTN_LEFT", "cross": "KEY_ENTER"})
    assert do_mouse["dpad_up"] == "BTN_LEFT", "a escolha de mouse não chegou ao mouse"
    assert do_teclado["cross"] == ("KEY_ENTER",), "a escolha de tecla não chegou ao teclado"
    nos_dois = set(do_mouse) & set(do_teclado)
    assert not nos_dois, f"estes botões ficaram nos DOIS devices: {sorted(nos_dois)}"


def test_o_que_ninguem_atende_sai_pela_terceira_sacola() -> None:
    """A tela oferece o que o produto ainda não faz — e isso não pode ser silêncio.

    "Abrir a Steam", "Sair do modo jogo" e "Escolher um programa…" estão no
    desenho que ela aprovou. Guardá-los e não acender nada, sem dizer, seria o
    botão que responde calado.
    """
    from hefesto_dualsense4unix.core.acoes_de_botao import (
        TOKEN_CURSOR,
        TOKEN_STEAM,
        resolver,
    )

    do_mouse, do_teclado, sem_dono = resolver(
        {"cross": TOKEN_STEAM, "circle": TOKEN_CURSOR})
    assert "cross" in sem_dono, "o comando sem atendente passou por atendido"
    assert "circle" in sem_dono, (
        "pedir MOVIMENTO DE CURSOR a um botão passou por atendido — um botão só "
        "sabe ir e voltar, e o produto não tem como dar-lhe um eixo")
    assert "cross" not in do_mouse and "cross" not in do_teclado


def test_sem_escolha_a_resolucao_e_o_de_fabrica() -> None:
    """`None` HERDA. É o mesmo contrato do `key_bindings`, e a régua o fixa."""
    from hefesto_dualsense4unix.core.acoes_de_botao import padrao, resolver
    from hefesto_dualsense4unix.integrations.uinput_mouse import BUTTON_TO_UINPUT

    do_mouse, _, sem_dono = resolver(None)
    assert do_mouse == dict(BUTTON_TO_UINPUT), (
        f"sem escolha, o mouse tem de ficar exatamente com o mapa de fábrica; "
        f"veio {do_mouse}")
    assert sem_dono == [], f"o de fábrica não pode ter linha sem atendente: {sem_dono}"
    assert padrao()["cross"] == "BTN_LEFT"


# --------------------------------------------------------------------------
# 4. o device obedece — e volta
# --------------------------------------------------------------------------
def test_o_device_troca_o_que_o_botao_faz() -> None:
    """O elo que faltava: sem ele o campo grava e nada acende."""
    from hefesto_dualsense4unix.core.acoes_de_botao import resolver
    from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice

    d = UinputMouseDevice()
    de_fabrica = dict(d._mapa_botoes)
    do_mouse, _, _ = resolver({"dpad_up": "BTN_LEFT"})
    d.set_button_actions(do_mouse)

    assert d._mapa_botoes.get("dpad_up") == "BTN_LEFT", (
        "o device não passou a tratar o d-pad para cima como clique esquerdo")
    assert "dpad_up" not in d._mapa_dpad, (
        "o `dpad_up` virou botão de mouse E continuou emitindo `KEY_UP` — o "
        "mesmo aperto faria duas coisas")

    d.set_button_actions(None)
    assert d._mapa_botoes == de_fabrica, (
        "o device não voltou ao de fábrica quando o perfil deixou de opinar")


def test_o_perfil_empurra_ao_ativar() -> None:
    """O ELO DE CIMA: `apply_button_actions` chega ao device pelo provider.

    Sem esta ligação o campo seria escrita pura — e o relatório diria `aplicado`
    sobre nada. É o mesmo silêncio que o `apply_keyboard` já tinha aprendido a
    distinguir em três estados, e por isso este caso cobra os três.
    """
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import Profile

    class DeviceDeMentira:
        def __init__(self) -> None:
            self.recebeu: dict[str, str] | None = None

        def set_button_actions(self, do_mouse: dict[str, str] | None) -> None:
            self.recebeu = do_mouse

    dispositivo = DeviceDeMentira()
    m = ProfileManager(controller=None,
                       mouse_device_provider=lambda: dispositivo)

    relatorio: dict[str, str] = {}
    m.apply_button_actions(
        Profile(name="t", match={"type": "any"}, button_actions={"dpad_up": "BTN_LEFT"}),
        relatorio=relatorio)
    assert dispositivo.recebeu is not None, "o device não recebeu nada"
    assert dispositivo.recebeu.get("dpad_up") == "BTN_LEFT"
    assert relatorio["button_actions"] == "aplicado"

    relatorio.clear()
    m.apply_button_actions(Profile(name="t", match={"type": "any"}), relatorio=relatorio)
    assert relatorio["button_actions"] == "de_fabrica", (
        "perfil sem `button_actions` tem de dizer que herdou, e não que aplicou")

    relatorio.clear()
    sem = ProfileManager(controller=None, mouse_device_provider=lambda: None)
    sem.apply_button_actions(
        Profile(name="t", match={"type": "any"}, button_actions={"dpad_up": "BTN_LEFT"}),
        relatorio=relatorio)
    assert relatorio["button_actions"] == "ignorado_sem_device", (
        "sem device, o relatório tem de dizer que a escolha não pousou — "
        "'sem device' não é 'aplicou' nem 'falhou'")


def test_a_fabrica_do_daemon_injeta_o_provider() -> None:
    """A cura ligada de verdade: quem monta o manager no daemon passa o mouse.

    Esta é a linha que separa a feature do inventário: sem ela, tudo acima passa
    e nada acontece na máquina dela.
    """
    import inspect

    from hefesto_dualsense4unix.profiles import manager as mod

    fonte = inspect.getsource(mod)
    assert '"mouse_device_provider": lambda: getattr(daemon, "_mouse_device", None)' in fonte, (
        "a fábrica `manager_do_daemon` parou de injetar o `mouse_device_provider`. "
        "Com ela fora, `button_actions` grava no disco e não acende nada.")
