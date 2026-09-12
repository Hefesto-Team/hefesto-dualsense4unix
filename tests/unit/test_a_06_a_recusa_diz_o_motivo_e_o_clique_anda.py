#!/usr/bin/env python3
"""OS DOIS DEFEITOS DE CLIQUE DA NAVEGAÇÃO, e nenhum deles era de tela.

**1. A RECUSA VOLTAVA COMO SUCESSO.** Os gestos desta aba chamavam
`ponte.chamar`, que devolve `bool` e joga fora o corpo. Um
`{"status": "failed", "bloqueio": "sem_device"}` — que o daemon manda desde
25/08 (`ipc_handlers._handle_mouse_emulation_set`) — voltava `True`, o gesto
seguia adiante, e ela não via uma palavra. Pior no `modo`: com o mouse recusado,
o gesto ainda mandava LIGAR o teclado.

O produto já tinha as duas peças e ninguém as chamava:

    ponte.resultado                          traz o corpo (`ponte.py:152`)
    mouse_actions.frase_da_recusa_do_mouse   traduz cinco motivos, desde 25/08
    emulation_actions.descrever_teclado_emulado   idem, do lado do teclado

FATO DERRUBADO — 03/09/2026. O próprio `_mandar` declarava que *"a ponte não
expõe o `_call_checked_detalhado`, que é o único que entrega o corpo"*. A ponte
entrega o corpo desde 01/09; era caminho existente que esta aba não chamava.

**2. O SEGUNDO CLIQUE NO `+` NÃO ANDAVA.** O número de partida sai do `ctx`, que
é o estado do último tique (500 ms). Dois cliques dentro do mesmo tique liam o
MESMO número e pediam o MESMO alvo. É o defeito que quem clica rápido sente
primeiro, e a GTK não o tem porque o `Gtk.Scale` dela lê o widget.

AS MORDIDAS:

* troque `p.resultado` por `p.chamar` em `_mandar` — as recusas voltam mudas;
* tire a memória de `_de_onde_partir` (devolva sempre `atual + passo`) — o
  segundo clique para de andar;
* tire a aparação de `_de_onde_partir` (o `max`/`min` com a faixa do
  produto) — o clique fica preso no teto.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.actions.mouse_actions import (
    BLOQUEIO_DO_MOUSE_EM_PORTUGUES,
    frase_da_recusa_do_mouse,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    DEFAULT_MOUSE_SPEED,
    MOUSE_SPEED_MAX,
    MOUSE_SPEED_MIN,
    SCROLL_SPEED_MIN,
)

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
         "battery_pct": 90, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "cosmic-red", "mascara": "DualSense"}]


class _Ponte:
    """Um daemon de mentira que responde o CORPO — recusando ou não.

    Ele não expõe `chamar` de propósito: um gesto que volte ao caminho que perde
    o motivo levanta `AttributeError` aqui, e a régua o nomeia.
    """

    def __init__(self, corpo: dict | None = None, muda: bool = False) -> None:
        self.corpo = corpo if corpo is not None else {"status": "ok"}
        self.muda = muda
        self.chamadas: list[tuple[str, dict]] = []

    def resultado(self, metodo: str, **params: object) -> dict:
        self.chamadas.append((metodo, dict(params)))
        if self.muda:
            raise RuntimeError(f"o daemon não respondeu a {metodo}")
        return dict(self.corpo)


def _ctx(**mouse: object):
    from pacotes import Contexto

    estado: dict = {"active_profile": "regua", "controllers": [FALSO],
                    "mode": "desktop"}
    if mouse:
        estado["mouse_emulation"] = dict(mouse)
    return Contexto(state=estado, mesa=MESA, conectados=[FALSO])


@pytest.fixture(autouse=True)
def _memoria_limpa():
    """A memória do último alvo é de MÓDULO — cada régua parte do zero.

    Sem isto, a ordem dos testes decidiria o resultado, que é a forma de régua
    que dá verde por acidente.
    """
    from pacotes import a06_navegacao as mod

    mod._PEDIDO.clear()
    yield
    mod._PEDIDO.clear()


# ---------------------------------------------------------------------------
# 1. A RECUSA DIZ O MOTIVO
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bloqueio", sorted(BLOQUEIO_DO_MOUSE_EM_PORTUGUES))
def test_a_velocidade_recusada_diz_por_que(bloqueio: str) -> None:
    """A frase é a do produto, inteira — e ela chega ao cartão dela.

    `RuntimeError` é o contrato: `hefesto_vivo._recusou_dizendo` leva ao cartão
    a frase de um `RuntimeError` e NÃO a de um `ValueError`, que fala com quem
    programa.
    """
    from pacotes import a06_navegacao as mod

    ponte = _Ponte({"status": "failed", "bloqueio": bloqueio})
    with pytest.raises(RuntimeError) as caiu:
        mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor", "valor": "7"}, ponte)
    assert str(caiu.value) == frase_da_recusa_do_mouse({"bloqueio": bloqueio}), (
        f"a tela diria {caiu.value!r}, e o produto traduz esse motivo como "
        f"{frase_da_recusa_do_mouse({'bloqueio': bloqueio})!r}")


def test_a_recusa_sem_motivo_nao_vira_queda_de_linha() -> None:
    """"Recusou e não disse por quê" é outra coisa de "ninguém respondeu".

    Culpar a rede quando o daemon respondeu é a ELO-MUDO-01 ao contrário, e a
    GTK já separava os dois em `RECUSA_SEM_MOTIVO`.
    """
    from pacotes import a06_navegacao as mod

    ponte = _Ponte({"status": "failed"})
    with pytest.raises(RuntimeError) as caiu:
        mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor", "valor": "7"}, ponte)
    assert str(caiu.value) == frase_da_recusa_do_mouse({}), caiu.value


def test_sem_resposta_continua_sendo_sem_resposta() -> None:
    """O outro desfecho não pode virar "o Hefesto recusou"."""
    from pacotes import a06_navegacao as mod

    with pytest.raises(RuntimeError, match="não respondeu"):
        mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor", "valor": "7"},
                       _Ponte(muda=True))


def test_o_ok_nao_reclama_de_nada() -> None:
    """Uma régua que só provasse o NÃO reprovaria a cura junto com o defeito."""
    from pacotes import a06_navegacao as mod

    ponte = _Ponte({"status": "ok", "enabled": True})
    mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor", "valor": "7"}, ponte)
    assert ponte.chamadas == [
        ("mouse.emulation.set", {"speed": 7, "origin": "manual"})]


def test_o_modo_para_quando_o_mouse_recusa() -> None:
    """Com o mouse recusado, o teclado NÃO é ligado sozinho.

    Era o pior lado do defeito: o `chamar` devolvia `True` e o gesto seguia,
    deixando o teclado ligado num modo que não é dele — que é exatamente o
    estado que o `keyboard.emulation.set` nasceu para curar.
    """
    from pacotes import a06_navegacao as mod

    ponte = _Ponte({"status": "failed", "bloqueio": "sem_device"})
    with pytest.raises(RuntimeError) as caiu:
        mod.modo(_ctx(enabled=False), {}, ponte)
    assert [m for m, _ in ponte.chamadas] == ["mouse.emulation.set"], (
        f"o gesto seguiu adiante depois da recusa: {ponte.chamadas}")
    assert BLOQUEIO_DO_MOUSE_EM_PORTUGUES["sem_device"].split(" — ")[0] in str(
        caiu.value), caiu.value


def test_o_teclado_recusado_diz_o_estado_que_o_daemon_devolveu() -> None:
    """O handler manda o bloco inteiro justamente para a janela não perguntar duas vezes.

    Quem o traduz é `descrever_teclado_emulado`, o mesmo dono da linha de estado
    desta aba — a frase da recusa e a do estado não podem ser duas.
    """
    from pacotes import a06_navegacao as mod

    ponte = _Ponte({"status": "failed", "enabled": False,
                    "keyboard_emulation": {"enabled": True,
                                           "bloqueio": "modo_jogo"}})
    with pytest.raises(RuntimeError) as caiu:
        mod.teclado(_ctx(), {"valor": mod.TECLADO_DESATIVADO}, ponte)
    assert "modo jogo" in str(caiu.value), caiu.value


def test_o_teclado_recusado_sem_bloco_nao_culpa_o_hefesto_de_estar_morto() -> None:
    """A frase de "não sei" da GTK fala do daemon, e aqui ele respondeu.

    `TECLADO_SEM_ESTADO` diz *"o Hefesto pode estar desligado"*. Usá-la numa
    recusa seria acusar de queda de linha um daemon que disse não.
    """
    from pacotes import a06_navegacao as mod

    ponte = _Ponte({"status": "failed"})
    with pytest.raises(RuntimeError) as caiu:
        mod.teclado(_ctx(), {"valor": mod.TECLADO_DESATIVADO}, ponte)
    assert "pode estar desligado" not in str(caiu.value), caiu.value
    assert "não disse por quê" in str(caiu.value), caiu.value


# ---------------------------------------------------------------------------
# 2. A BARRA MANDA O NÚMERO INTEIRO — e o que a memória curava não existe mais
# ---------------------------------------------------------------------------
# **A SEÇÃO INTEIRA FOI REESCRITA EM 05/09/2026, e a razão é uma decisão dela:**
# *"velocidade do cursor e da rolagem coloca um slicer pra cada"*. Até aqui as
# duas linhas eram um par de botões `-`/`+`, e os gestos `vel-cursor-menos` e
# `vel-cursor-mais` somavam ±1 ao número do ÚLTIMO TIQUE (500 ms). Daí vinha
# tudo o que esta seção mede: a memória `_PEDIDO`, o `_partir_de`, o
# `_reservar`, as três condições que a desligam.
#
# **UMA BARRA NÃO TEM DE ONDE PARTIR.** Ela manda o número inteiro, e a partida
# é o polegar dela — não há passo engolido a curar. Os quatro testes que
# mediam a memória da VELOCIDADE não medem mais nada: o produto que eles
# guardavam saiu com os botões.
#
# A MEMÓRIA CONTINUA VIVA E CONTINUA COBRADA — pelo interruptor "Status do
# Modo", que tem UM gesto e por isso depende dela para o segundo clique ser
# *desfaça*. As cinco mordidas do `test_a_06_o_segundo_clique_nao_e_engolido.py`
# continuam de pé para ele.
#
# O QUE ENTRA NO LUGAR são as três coisas que a barra pode errar, e nenhuma
# delas existia antes: mandar sem número, mandar fora da faixa, e consultar o
# tique em vez do polegar.


def test_a_barra_sem_numero_reprova_e_nao_manda_nada() -> None:
    """Clicar no rótulo ao lado da barra não pode virar um pedido em branco.

    O `data-hef-alvo="valor"` do `<input type=range>` faz o ouvinte mandar
    `valor: alvo.value`. Um clique que NÃO nasce da barra chega sem `valor` —
    e mandar `speed` vazio ao daemon seria pedir que ele adivinhasse.
    """
    from pacotes import a06_navegacao as mod

    ponte = _Ponte()
    # O RECORTE MUDOU DE METADE — 11/09/2026, A5-028, aprovada por ela. A frase
    # abria com *"a barra não mandou número nenhum, e …"*, que é o que o CÓDIGO
    # viu; a de hoje abre pelo que ela precisa — *"{campo} ficou como estava"* —
    # e ensina o gesto na segunda oração. A régua passa a cobrar as DUAS coisas
    # que a recusa tem de dizer: que nada mudou, e o que fazer em vez disso.
    with pytest.raises(RuntimeError, match="ficou como estava"):
        mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor"}, ponte)
    with pytest.raises(RuntimeError, match="Arraste o cursor da barra"):
        mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor"}, ponte)
    assert ponte.chamadas == [], (
        "a barra sem número chegou a falar com o daemon — o pedido em branco "
        f"virou uma chamada: {ponte.chamadas}")


def test_dois_arrastes_mandam_os_dois_numeros() -> None:
    """Cada arraste é absoluto: o `ctx` não muda entre eles e não precisa mudar.

    É o mesmo caso que os `+`/`-` erravam — dois gestos dentro do mesmo tique —,
    e com a barra ele é trivial por construção. A régua fica porque o caso é o
    mesmo, e porque uma volta a `_partir_de` faria o segundo número sumir.
    """
    from pacotes import a06_navegacao as mod

    ctx, ponte = _ctx(speed=DEFAULT_MOUSE_SPEED), _Ponte()
    for numero in (9, 4, 11):
        mod.vel_cursor(ctx, {"gesto": "vel-cursor", "valor": str(numero)}, ponte)
    assert [p["speed"] for _m, p in ponte.chamadas] == [9, 4, 11]


def test_a_barra_nao_consulta_o_tique() -> None:
    """O número vem do polegar dela, e o estado do daemon não entra na conta.

    A MORDIDA: some o valor ao `ctx` em `_velocidade` e esta régua reprova —
    é o retorno da partida-pelo-tique que a barra existe para não ter.
    """
    from pacotes import a06_navegacao as mod

    ponte = _Ponte()
    # O daemon diz 3; o polegar dela diz 10. Vale o polegar.
    mod.vel_cursor(_ctx(speed=3), {"gesto": "vel-cursor", "valor": "10"}, ponte)
    assert ponte.chamadas[0][1]["speed"] == 10


def test_a_barra_apara_na_faixa_e_a_faixa_tem_dono() -> None:
    """Número fora do `min`/`max` é aparado aqui, e a faixa não é digitada.

    `MOUSE_SPEED_MIN`/`MAX` vêm de `integrations/uinput_mouse.py`, o mesmo
    módulo de onde o `set_speed` do daemon tira a sua — aparar aqui é a rede
    para o dia em que alguém publicar a página sem regerar o desenho, não uma
    segunda verdade.
    """
    from pacotes import a06_navegacao as mod

    ponte = _Ponte()
    mod.vel_cursor(_ctx(), {"gesto": "vel-cursor",
                           "valor": str(MOUSE_SPEED_MAX + 5)}, ponte)
    mod.vel_cursor(_ctx(), {"gesto": "vel-cursor",
                           "valor": str(MOUSE_SPEED_MIN - 5)}, ponte)
    assert [p["speed"] for _m, p in ponte.chamadas] == [
        MOUSE_SPEED_MAX, MOUSE_SPEED_MIN]


def test_a_rolagem_tem_a_faixa_dela() -> None:
    """Duas barras, dois donos, e nenhum dos dois digitado aqui."""
    from pacotes import a06_navegacao as mod

    ponte = _Ponte()
    mod.vel_rolagem(_ctx(), {"gesto": "vel-rolagem",
                            "valor": str(SCROLL_SPEED_MIN - 3)}, ponte)
    assert ponte.chamadas[0][1]["scroll_speed"] == SCROLL_SPEED_MIN


# "O homem é a medida de todas as coisas." — Protágoras
