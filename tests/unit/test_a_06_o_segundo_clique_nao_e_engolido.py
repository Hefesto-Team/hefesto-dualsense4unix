#!/usr/bin/env python3
"""OS TRÊS BURACOS DA MEMÓRIA DO CLIQUE DA NAVEGAÇÃO — medidos em 03/09/2026.

A aba 06 lê o estado do ÚLTIMO TIQUE (500 ms, `hefesto_vivo.TIQUE_MS`), e não o
widget. Isso é a escolha certa — a tela nunca vira uma segunda verdade sobre o
daemon —, e ela cobra um preço: entre o clique do usuário e o tique seguinte, o pacote
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

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
         "battery_pct": 90, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "cosmic-red", "mascara": "DualSense"}]

#: o «Status do Modo» manda `desktop.status.set` uma vez, e o daemon liga o
STATUS = "desktop.status.set"


class _Ponte:
    """Um daemon de mentira que responde o CORPO. Sem `chamar`, de propósito."""

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
    """A memória é de MÓDULO — cada régua parte do zero."""
    from pacotes import a06_navegacao as mod

    mod._PEDIDO.clear()
    yield
    mod._PEDIDO.clear()


class _Relogio:
    """Um `time` de mentira, para a expiração ser medida e não esperada."""

    def __init__(self) -> None:
        self.agora = 1000.0

    def monotonic(self) -> float:
        return self.agora


def test_dois_cliques_no_interruptor_no_mesmo_tique_desfazem() -> None:
    """O `ctx` não muda entre eles — é exatamente o caso medido."""
    from pacotes import a06_navegacao as mod

    ctx, ponte = _ctx(enabled=False, speed=6, scroll_speed=1), _Ponte()
    mod.modo(ctx, {"gesto": "modo"}, ponte)
    mod.modo(ctx, {"gesto": "modo"}, ponte)
    assert ponte.pedidos(STATUS, "enabled") == [True, False], (
        f"dois cliques no 'Status do Modo' dentro do mesmo tique mandaram "
        f"{ponte.pedidos(STATUS, 'enabled')} — o segundo foi engolido.")


def test_o_teclado_acompanha_o_interruptor_nos_dois_cliques() -> None:
    """O interruptor é dos DOIS (decisão, 27/08) — desfazer é dos dois.

    Desde 29/09/2026 os dois vão no MESMO pedido (`desktop.status.set`), e o
    daemon liga o teclado depois do mouse: a janela não manda um segundo
    método que pudesse chegar sem o primeiro.
    """
    from pacotes import a06_navegacao as mod

    ctx, ponte = _ctx(enabled=False), _Ponte()
    mod.modo(ctx, {"gesto": "modo"}, ponte)
    mod.modo(ctx, {"gesto": "modo"}, ponte)
    assert ponte.pedidos(STATUS, "enabled") == [True, False]
    assert ponte.pedidos("keyboard.emulation.set", "enabled") == [], (
        "a janela voltou a mandar o teclado por conta própria")


def test_quando_o_tique_chega_o_interruptor_parte_do_daemon() -> None:
    """A memória é largada assim que o daemon publica o valor novo."""
    from pacotes import a06_navegacao as mod

    ponte = _Ponte()
    mod.modo(_ctx(enabled=False), {"gesto": "modo"}, ponte)
    mod.modo(_ctx(enabled=True), {"gesto": "modo"}, ponte)
    assert ponte.pedidos(STATUS, "enabled") == [True, False]
    mod.modo(_ctx(enabled=False), {"gesto": "modo"}, ponte)
    assert ponte.pedidos(STATUS, "enabled") == [True, False, True]


def test_o_interruptor_recusado_nao_deixa_rastro() -> None:
    """Recusa não é confirmação: o clique seguinte volta a pedir a mesma coisa."""
    from pacotes import a06_navegacao as mod

    ctx = _ctx(enabled=False)
    negou = _Ponte({"status": "failed", "bloqueio": "sem_device"})
    with pytest.raises(RuntimeError):
        mod.modo(ctx, {"gesto": "modo"}, negou)
    assert not mod._PEDIDO, f"a recusa deixou rastro: {mod._PEDIDO}"

    aceitou = _Ponte()
    mod.modo(ctx, {"gesto": "modo"}, aceitou)
    assert aceitou.pedidos(STATUS, "enabled") == [True], (
        "depois de uma recusa, o clique seguinte pediu o contrário do que ela "
        "quis — a memória guardou um pedido que não aconteceu.")


def test_o_silencio_do_hefesto_tambem_nao_e_confirmacao() -> None:
    """Silêncio e recusa são dois desfechos, e nenhum é "o valor mudou"."""
    from pacotes import a06_navegacao as mod

    class _Muda(_Ponte):
        def resultado(self, metodo: str, **params: object) -> dict:
            self.chamadas.append((metodo, dict(params)))
            raise RuntimeError("ninguém respondeu")

    muda = _Muda()
    with pytest.raises(RuntimeError, match="não respondeu"):
        mod.modo(_ctx(enabled=False), {"gesto": "modo"}, muda)
    assert muda.chamadas, (
        "o gesto nem chegou a falar com o daemon — o silêncio que se mede aqui "
        "não chegou a acontecer, e o resto deste teste não vale nada")
    assert not mod._PEDIDO, f"o silêncio deixou rastro: {mod._PEDIDO}"


def test_a_reserva_ja_esta_de_pe_durante_a_chamada() -> None:
    """Os gestos rodam em THREAD — anotar só na volta reabre o buraco."""
    from pacotes import a06_navegacao as mod

    visto: dict = {}

    class _Espia(_Ponte):
        def resultado(self, metodo: str, **params: object) -> dict:
            visto.setdefault("durante", dict(mod._PEDIDO))
            return super().resultado(metodo, **params)

    mod.modo(_ctx(enabled=False), {"gesto": "modo"}, _Espia())
    assert "modo" in visto.get("durante", {}), (
        "durante a chamada a memória estava vazia — dois cliques em duas "
        "threads pedem a mesma coisa")
    assert visto["durante"]["modo"][1] == 1, (
        "a reserva não guardou o alvo do clique: o segundo clique partiria do "
        "estado velho")


def test_a_recusa_nao_apaga_o_pedido_anterior() -> None:
    """Largar a reserva devolve o que estava lá — não esvazia a memória."""
    from pacotes import a06_navegacao as mod

    ctx = _ctx(enabled=False)
    aceitou = _Ponte()
    mod.modo(ctx, {"gesto": "modo"}, aceitou)
    negou = _Ponte({"status": "failed", "bloqueio": "sem_device"})
    with pytest.raises(RuntimeError):
        mod.modo(ctx, {"gesto": "modo"}, negou)
    de_novo = _Ponte()
    mod.modo(ctx, {"gesto": "modo"}, de_novo)
    assert de_novo.pedidos(STATUS, "enabled") == [False], (
        "a recusa apagou o pedido que TINHA acontecido, e o clique seguinte "
        "voltou a pedir o que o daemon já tem")


def test_o_clique_aceito_continua_andando() -> None:
    """A guarda de vacuidade: mover a anotação não pode matar a cura de 02/09."""
    from pacotes import a06_navegacao as mod

    ctx, ponte = _ctx(enabled=False), _Ponte()
    for _ in range(3):
        mod.modo(ctx, {"gesto": "modo"}, ponte)
    assert ponte.pedidos(STATUS, "enabled") == [True, False, True]


def test_a_memoria_expira_e_a_volta_pela_janela_gtk_nao_pula_numero(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Concordar POR ACASO não é concordar."""
    from pacotes import a06_navegacao as mod

    relogio = _Relogio()
    monkeypatch.setattr(mod, "time", relogio)

    ponte = _Ponte()
    mod.modo(_ctx(enabled=False), {"gesto": "modo"}, ponte)
    relogio.agora += mod.MEMORIA_DE_UM_CLIQUE + 1.0
    mod.modo(_ctx(enabled=False), {"gesto": "modo"}, ponte)
    assert ponte.pedidos(STATUS, "enabled") == [True, True], (
        f"a memória atravessou a volta pela janela GTK: "
        f"{ponte.pedidos(STATUS, 'enabled')}")


def test_dentro_da_janela_do_tique_a_memoria_vale(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A outra ponta: expirar cedo demais devolveria o defeito de 02/09."""
    from pacotes import a06_navegacao as mod

    relogio = _Relogio()
    monkeypatch.setattr(mod, "time", relogio)

    ponte = _Ponte()
    mod.modo(_ctx(enabled=False), {"gesto": "modo"}, ponte)
    relogio.agora += mod.MEMORIA_DE_UM_CLIQUE / 2
    mod.modo(_ctx(enabled=False), {"gesto": "modo"}, ponte)
    assert ponte.pedidos(STATUS, "enabled") == [True, False]


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


