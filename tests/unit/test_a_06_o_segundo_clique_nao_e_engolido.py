#!/usr/bin/env python3
"""OS TRÊS BURACOS DA MEMÓRIA DO CLIQUE DA NAVEGAÇÃO — medidos em 03/09/2026.

A aba 06 lê o estado do ÚLTIMO TIQUE (500 ms, `hefesto_vivo.TIQUE_MS`), e não o
widget. Isso é a escolha certa — a tela nunca vira uma segunda verdade sobre o
daemon —, e ela cobra um preço: entre o clique dela e o tique seguinte, o pacote
não sabe o que acabou de acontecer. A memória `_PEDIDO` existe para pagar esse
preço, e em 02/09 ela cobriu só o `+`/`-` das velocidades. Faltavam três coisas.

**1. O INTERRUPTOR "Status do Modo" NÃO TINHA A CURA.** Ele é o único caminho do
HTML para ligar/desligar o mouse, e desde 03/09 a tela só o acende quando o
daemon diz (`pacote()`) — logo ele leva até meio segundo para responder ao olho.
Dois cliques nessa janela liam o MESMO `enabled` e mandavam `enabled=True` duas
vezes; o segundo era engolido, e ela ficava com o mouse ligado sem ter querido.
Medido antes da cura::

    mouse.emulation.set enabled=True
    mouse.emulation.set enabled=True     <- o segundo clique não desfez nada

**2. A MEMÓRIA GUARDAVA O QUE O HEFESTO RECUSOU.** `_de_onde_partir` escrevia o
alvo ANTES da chamada. Um clique recusado (`sem_device`, `modo_jogo`…) levantava
`RuntimeError` — e deixava o alvo na memória. O clique seguinte partia de um
número que nunca existiu. Medido antes da cura, com o daemon em 6::

    clique 1 (recusado)  pediu 7   ·  _PEDIDO = {"speed": (6, 7, 1)}
    clique 2             pediu 8   <- pulou o 7, que é o que ela quer

**3. A MEMÓRIA ATRAVESSAVA UMA VOLTA INTEIRA**, e o docstring dela prometia o
contrário: *"não há caminho em que ela sobreviva a uma discordância"*. Havia um
— concordar POR ACASO. Ela clica `+` aqui (6 → 7), põe o número de volta em 6
pela janela GTK, e o `+` seguinte via o daemon dizendo 6 outra vez, o mesmo
sentido, e partia de 7: pedia 8.

AS CINCO MORDIDAS (arranque a cura, veja reprovar, devolva) — as cinco foram
rodadas em 03/09/2026, e o que cada uma derruba está ao lado:

* em `modo()`, troque a partida por `novo = not atual`  →  2 reprovam: o segundo
  clique no interruptor volta a ser engolido;
* tire o `try`/`_largar_a_reserva` de `vel_cursor` e deixe só o `_reservar`  →
  2 reprovam: a recusa e o silêncio voltam a envenenar o clique seguinte;
* apague a guarda de `MEMORIA_DE_UM_CLIQUE` em `_partir_de`  →  1 reprova: a
  memória volta a atravessar a volta pela janela GTK;
* mova o `_reservar` para DEPOIS do `_mandar`  →  1 reprova: a corrida entre as
  duas threads de dois cliques rápidos reabre;
* faça `_largar_a_reserva` sempre esvaziar (em vez de devolver o anterior)  →
  1 reprova: a recusa apaga um pedido que TINHA acontecido.

E há uma sexta, na tela: `scripts/ensaios/o_interruptor_do_modo_no_webkit.py`
clica duas vezes no `<label>` dentro do `WebKit2.WebView` dela, com a ponte
interceptada — sem a primeira mordida ele imprime `[True, True]` e reprova.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.integrations.uinput_mouse import (
    DEFAULT_MOUSE_SPEED,
)

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
         "battery_pct": 90, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "cosmic-red", "mascara": "DualSense"}]

MOUSE = "mouse.emulation.set"


class _Ponte:
    """Um daemon de mentira que responde o CORPO. Sem `chamar`, de propósito.

    Um gesto que volte ao caminho que perde o motivo da recusa levanta
    `AttributeError` aqui, e a régua o nomeia.
    """

    def __init__(self, corpo: dict | None = None) -> None:
        self.corpo = corpo if corpo is not None else {"status": "ok"}
        self.chamadas: list[tuple[str, dict]] = []

    def resultado(self, metodo: str, **params: object) -> dict:
        self.chamadas.append((metodo, dict(params)))
        return dict(self.corpo)

    def pedidos(self, metodo: str, campo: str) -> list[object]:
        return [p.get(campo) for m, p in self.chamadas if m == metodo]


def _ctx(**mouse: object):
    from pacotes import Contexto

    estado: dict = {"active_profile": "regua", "controllers": [FALSO],
                    "mode": "desktop"}
    if mouse:
        estado["mouse_emulation"] = dict(mouse)
    return Contexto(state=estado, mesa=MESA, conectados=[FALSO])


@pytest.fixture(autouse=True)
def _memoria_limpa():
    """A memória é de MÓDULO — cada régua parte do zero.

    Sem isto a ordem dos testes decidiria o resultado, que é a forma de régua
    que dá verde por acidente.
    """
    from pacotes import a06_navegacao as mod

    mod._PEDIDO.clear()
    yield
    mod._PEDIDO.clear()


class _Relogio:
    """Um `time` de mentira, para a expiração ser medida e não esperada.

    Só `monotonic` é substituído; é o único membro que `_partir_de` usa.
    """

    def __init__(self) -> None:
        self.agora = 1000.0

    def monotonic(self) -> float:
        return self.agora


# ---------------------------------------------------------------------------
# 1. O INTERRUPTOR NÃO ENGOLE O SEGUNDO CLIQUE
# ---------------------------------------------------------------------------
def test_dois_cliques_no_interruptor_no_mesmo_tique_desfazem() -> None:
    """O `ctx` não muda entre eles — é exatamente o caso medido.

    O segundo clique é *desfaça*, e não *ande mais*: um interruptor tem UM
    gesto, e repetir o pedido é o que fazia a tela ficar dizendo "Ligado" sem
    ela ter querido.
    """
    from pacotes import a06_navegacao as mod

    ctx, ponte = _ctx(enabled=False, speed=6, scroll_speed=1), _Ponte()
    mod.modo(ctx, {"gesto": "modo"}, ponte)
    mod.modo(ctx, {"gesto": "modo"}, ponte)
    assert ponte.pedidos(MOUSE, "enabled") == [True, False], (
        f"dois cliques no 'Status do Modo' dentro do mesmo tique mandaram "
        f"{ponte.pedidos(MOUSE, 'enabled')} — o segundo foi engolido.")


def test_o_teclado_acompanha_o_interruptor_nos_dois_cliques() -> None:
    """O interruptor é dos DOIS (decisão dela, 27/08) — desfazer é dos dois."""
    from pacotes import a06_navegacao as mod

    ctx, ponte = _ctx(enabled=False), _Ponte()
    mod.modo(ctx, {"gesto": "modo"}, ponte)
    mod.modo(ctx, {"gesto": "modo"}, ponte)
    assert ponte.pedidos("keyboard.emulation.set", "enabled") == [True, False]


def test_quando_o_tique_chega_o_interruptor_parte_do_daemon() -> None:
    """A memória é largada assim que o daemon publica o valor novo."""
    from pacotes import a06_navegacao as mod

    ponte = _Ponte()
    mod.modo(_ctx(enabled=False), {"gesto": "modo"}, ponte)
    # O daemon aplicou e o tique trouxe `True`: o clique seguinte desliga.
    mod.modo(_ctx(enabled=True), {"gesto": "modo"}, ponte)
    assert ponte.pedidos(MOUSE, "enabled") == [True, False]
    # E de novo, com o tique acompanhando: liga.
    mod.modo(_ctx(enabled=False), {"gesto": "modo"}, ponte)
    assert ponte.pedidos(MOUSE, "enabled") == [True, False, True]


def test_o_interruptor_recusado_nao_deixa_rastro() -> None:
    """Recusa não é confirmação: o clique seguinte volta a pedir a mesma coisa.

    Era o pior lado do defeito, porque a recusa do mouse já PARA o gesto antes
    do teclado — guardar o pedido faria o clique seguinte pedir o contrário do
    que ela quis.
    """
    from pacotes import a06_navegacao as mod

    ctx = _ctx(enabled=False)
    negou = _Ponte({"status": "failed", "bloqueio": "sem_device"})
    with pytest.raises(RuntimeError):
        mod.modo(ctx, {"gesto": "modo"}, negou)
    assert not mod._PEDIDO, f"a recusa deixou rastro: {mod._PEDIDO}"

    aceitou = _Ponte()
    mod.modo(ctx, {"gesto": "modo"}, aceitou)
    assert aceitou.pedidos(MOUSE, "enabled") == [True], (
        "depois de uma recusa, o clique seguinte pediu o contrário do que ela "
        "quis — a memória guardou um pedido que não aconteceu.")


# ---------------------------------------------------------------------------
# 2. A MEMÓRIA SÓ GUARDA O QUE O HEFESTO CONFIRMOU
# ---------------------------------------------------------------------------
def test_a_velocidade_recusada_nao_envenena_o_clique_seguinte() -> None:
    """Com o daemon em 6, um `+` recusado e outro `+` pedem 7 — nunca 8.

    O alvo que ele NÃO aceitou não pode ficar no caminho: pular o 7 é a tela
    decidindo por ela um número que ninguém pediu.
    """
    from pacotes import a06_navegacao as mod

    ctx = _ctx(speed=DEFAULT_MOUSE_SPEED)
    negou = _Ponte({"status": "failed", "bloqueio": "sem_device"})
    with pytest.raises(RuntimeError):
        mod.vel_cursor(ctx, {"gesto": "vel-cursor-mais"}, negou)
    assert not mod._PEDIDO, f"a recusa deixou rastro: {mod._PEDIDO}"

    aceitou = _Ponte()
    mod.vel_cursor(ctx, {"gesto": "vel-cursor-mais"}, aceitou)
    assert aceitou.pedidos(MOUSE, "speed") == [DEFAULT_MOUSE_SPEED + 1], (
        "o clique depois da recusa partiu de um número que nunca existiu")


def test_o_silencio_do_hefesto_tambem_nao_e_confirmacao() -> None:
    """`_mandar` levanta quando ninguém responde — e nada é guardado.

    Silêncio e recusa são dois desfechos, e nenhum dos dois é "o valor mudou".
    """
    from pacotes import a06_navegacao as mod

    class _Muda(_Ponte):
        def resultado(self, metodo: str, **params: object) -> dict:
            self.chamadas.append((metodo, dict(params)))
            raise RuntimeError("ninguém respondeu")

    with pytest.raises(RuntimeError):
        mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor-mais"}, _Muda())
    assert not mod._PEDIDO, f"o silêncio deixou rastro: {mod._PEDIDO}"


def test_a_reserva_ja_esta_de_pe_durante_a_chamada() -> None:
    """Os gestos rodam em THREAD — anotar só na volta reabre o buraco.

    `hefesto_vivo.trabalhar` (`:1384`) dispara uma thread por clique, *"um gesto
    síncrono congelaria a janela inteira por nove segundos e meio"*. Se a
    memória só fosse escrita DEPOIS da resposta, um segundo clique chegado
    dentro do tempo de ida e volta do IPC leria a memória vazia e repetiria o
    pedido do primeiro — que é exatamente a janela em que ela clica duas vezes.

    A ponte olha `_PEDIDO` de dentro da chamada: é o único jeito de medir
    "antes" sem depender de escalonamento de thread.
    """
    from pacotes import a06_navegacao as mod

    visto: dict = {}

    class _Espia(_Ponte):
        def resultado(self, metodo: str, **params: object) -> dict:
            visto["durante"] = dict(mod._PEDIDO)
            return super().resultado(metodo, **params)

    mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor-mais"}, _Espia())
    assert "speed" in visto.get("durante", {}), (
        "durante a chamada a memória estava vazia — dois cliques em duas "
        "threads pedem o mesmo número")
    assert visto["durante"]["speed"][1] == 7


def test_a_recusa_nao_apaga_o_pedido_anterior() -> None:
    """Largar a reserva devolve o que estava lá — não esvazia a memória.

    Um `+` aceito seguido de um `+` recusado tem de deixar o primeiro alvo de
    pé: apagá-lo faria o clique seguinte pedir de novo o 7 que já aconteceu.
    """
    from pacotes import a06_navegacao as mod

    ctx = _ctx(speed=6)
    aceitou = _Ponte()
    mod.vel_cursor(ctx, {"gesto": "vel-cursor-mais"}, aceitou)      # 6 -> 7
    negou = _Ponte({"status": "failed", "bloqueio": "sem_device"})
    with pytest.raises(RuntimeError):
        mod.vel_cursor(ctx, {"gesto": "vel-cursor-mais"}, negou)    # 7 -> 8, não
    de_novo = _Ponte()
    mod.vel_cursor(ctx, {"gesto": "vel-cursor-mais"}, de_novo)
    assert de_novo.pedidos(MOUSE, "speed") == [8], (
        "a recusa apagou o pedido que TINHA acontecido, e o clique seguinte "
        "voltou a pedir um número que o daemon já tem")


def test_o_clique_aceito_continua_andando() -> None:
    """A guarda de vacuidade: mover a anotação não pode matar a cura de 02/09.

    Três `+` dentro do mesmo tique andam três — que é o defeito que a memória
    nasceu para curar, e que continua curado depois de ela virar confirmação.
    """
    from pacotes import a06_navegacao as mod

    ctx, ponte = _ctx(speed=DEFAULT_MOUSE_SPEED), _Ponte()
    for _ in range(3):
        mod.vel_cursor(ctx, {"gesto": "vel-cursor-mais"}, ponte)
    assert ponte.pedidos(MOUSE, "speed") == [
        DEFAULT_MOUSE_SPEED + 1, DEFAULT_MOUSE_SPEED + 2, DEFAULT_MOUSE_SPEED + 3]


# ---------------------------------------------------------------------------
# 3. A MEMÓRIA NÃO ATRAVESSA UMA VOLTA INTEIRA
# ---------------------------------------------------------------------------
def test_a_memoria_expira_e_a_volta_pela_janela_gtk_nao_pula_numero(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Concordar POR ACASO não é concordar.

    Ela clica `+` aqui (6 → 7), volta o número para 6 pela janela GTK, e clica
    `+` de novo. O daemon diz 6 outra vez e o sentido é o mesmo — as duas
    condições de 02/09 casavam, e o clique pedia 8. O relógio é a terceira.
    """
    from pacotes import a06_navegacao as mod

    relogio = _Relogio()
    monkeypatch.setattr(mod, "time", relogio)

    ponte = _Ponte()
    mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor-mais"}, ponte)
    # Ela foi à janela GTK e pôs de volta em 6. Isso leva mais que a janela do
    # tique — é um gesto humano, noutra janela.
    relogio.agora += mod.MEMORIA_DE_UM_CLIQUE + 1.0
    mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor-mais"}, ponte)
    assert ponte.pedidos(MOUSE, "speed") == [7, 7], (
        f"a memória atravessou a volta pela janela GTK: {ponte.pedidos(MOUSE, 'speed')}")


def test_dentro_da_janela_do_tique_a_memoria_vale(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A outra ponta: expirar cedo demais devolveria o defeito de 02/09.

    Um daemon lento não pode fazer o segundo clique parar de andar — a janela é
    de quatro tiques justamente por isso.
    """
    from pacotes import a06_navegacao as mod

    relogio = _Relogio()
    monkeypatch.setattr(mod, "time", relogio)

    ponte = _Ponte()
    mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor-mais"}, ponte)
    relogio.agora += mod.MEMORIA_DE_UM_CLIQUE / 2
    mod.vel_cursor(_ctx(speed=6), {"gesto": "vel-cursor-mais"}, ponte)
    assert ponte.pedidos(MOUSE, "speed") == [7, 8]


def test_a_janela_da_memoria_cobre_mais_de_um_tique() -> None:
    """O número não é digitado à toa: ele tem de valer mais que UM tique.

    O tique da pintura é de 100 ms (`hefesto_vivo.TIQUE_MS`, não importável
    daqui — o piloto puxa GTK no topo). Uma janela menor que um tique tornaria a
    memória inútil no caso exato para o qual ela existe.

    O PISO CONTINUA 1 s, e ele não é o tique: o que a memória atravessa não é o
    intervalo da pintura, é a viagem inteira do pedido — clique, IPC, o daemon
    aplicar, e o tique seguinte LER de volta o que mudou. Baixar o tique de 500
    para 100 ms em 04/09/2026 encurtou só a última perna. O piso de 1 s dá dez
    tiques de folga onde antes dava dois; frouxo de propósito, porque quem paga
    o erro é ela, com um clique engolido.
    """
    from pacotes import a06_navegacao as mod

    assert mod.MEMORIA_DE_UM_CLIQUE >= 1.0, (
        f"a memória vale {mod.MEMORIA_DE_UM_CLIQUE}s — menos que o segundo que "
        "a viagem do pedido leva para voltar lida pelo tique")


# "O homem é a medida de todas as coisas." — Protágoras
