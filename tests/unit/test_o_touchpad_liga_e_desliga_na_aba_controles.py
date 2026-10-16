"""A-ABA-CONTROLES-DO-TODO-01 (15/10/2026): o touchpad liga e desliga em CADA controle, e a aba
sai sem «?», sem a linha do Ganho e com as três rotas do alto-falante, como o desenho do todo.

Esta régua mede seis coisas, cada uma com a sua mordida:

1. o interruptor «Ligado | Desligado» está em todo cartão, e «Cursor», «Botões» e «Sem toque» não;
2. as três terças da superfície não levam texto (quem acende é o terço onde o dedo está);
3. o gesto `touchpad` manda o OPOSTO do que o daemon leu, só daquele controle, e recusa sem leitura;
4. `regiao_do_toque` parte a superfície em terços;
5. a aba não tem «?» nem `class="ajuda"`, nem a linha do Ganho, nem o botão «junto»;
6. o alto-falante tem as três rotas, com os nomes do todo.

A MORDIDA: escreva «Meio» dentro de `<span class="todo-terca">` em `aba02.py` e o caso 2 reprova;
troque `"desligado" if agora else "ligado"` por `"ligado"` no gesto e o caso 3 reprova; ponha o
`ponto_de_interrogacao` de volta no cabeçalho do microfone e o caso 5 reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

import pacotes
import pacotes.a02_controles as a02

UNIQ = "aa:bb:cc:00:00:01"
OUTRO = "aa:bb:cc:00:00:02"


def _pagina() -> str:
    return (INTERFACE.parent.parent.parent / "mockup" / "02-controles.html").read_text(
        encoding="utf-8")


class Ponte:
    """Um dublê da ponte que guarda os pedidos e devolve o corpo `ok` do daemon."""

    def __init__(self, corpo: dict[str, Any] | None = None) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []
        self.corpo = {"status": "ok"} if corpo is None else corpo

    def sensor_set_detalhado(self, **kwargs: Any) -> dict[str, Any]:
        self.chamadas.append(("sensor_set_detalhado", kwargs))
        return self.corpo

    def mira_set_detalhado(self, **kwargs: Any) -> dict[str, Any]:
        self.chamadas.append(("mira_set_detalhado", kwargs))
        return self.corpo


def _ctx(**sensores: Any) -> Any:
    entrada: dict[str, Any] = {"uniq": UNIQ, "transport": "usb", "connected": True}
    if sensores:
        entrada["sensores"] = dict(sensores)
    outro = {"uniq": OUTRO, "transport": "bt", "connected": True,
             "sensores": {"touchpad": "ligado"}}
    return pacotes.Contexto(state={}, mesa=[], conectados=[entrada, outro], estados={})


def _gesto(nome: str) -> Any:
    fn = pacotes.gesto_da_pagina("02-controles.html", nome)
    assert fn is not None, f"02-controles.html:{nome} não tem dono"
    return fn


# 1. O INTERRUPTOR -------------------------------------------------------------------------------

def test_o_interruptor_esta_em_todo_cartao_e_o_cursor_e_os_botoes_saíram() -> None:
    doc = _pagina()
    cartoes = doc.count('data-gesto="touchpad"')
    assert cartoes >= 2, "o interruptor do touchpad sumiu dos cartões"
    doc = re.sub(r"<style>.*?</style>|<!--.*?-->", "", doc, flags=re.S)  # só o que se vê
    assert cartoes == len(re.findall(r'class="sw todo-sw-toque"', doc)), (
        "há interruptor sem a classe do desenho, ou o contrário")
    for velho in ("Cursor", "Botões", "Sem toque", 'data-campo="touch-estado"'):
        assert velho not in doc, f"{velho!r} voltou à tela: saiu no todo de 15/10/2026"
    assert doc.count(">Ligado<") >= cartoes and doc.count(">Desligado<") >= cartoes


# 2. AS TERÇAS -----------------------------------------------------------------------------------

def test_as_tres_tercas_acendem_sem_texto() -> None:
    doc = _pagina()
    tercas = re.findall(r'<span class="todo-terca[^"]*"[^>]*>([^<]*)</span>', doc)
    assert len(tercas) == 3 * doc.count('data-gesto="touchpad"')
    assert set(tercas) == {""}, f"uma terça ganhou texto: {sorted(set(tercas))}"


# 3. O GESTO -------------------------------------------------------------------------------------

def test_o_gesto_manda_o_oposto_so_daquele_controle() -> None:
    for agora, vai in (("ligado", "desligado"), ("desligado", "ligado")):
        p = Ponte()
        _gesto("touchpad")(_ctx(touchpad=agora), {"uniq": UNIQ}, p)
        assert p.chamadas == [("sensor_set_detalhado", {"touchpad": vai, "uniq": UNIQ})], (
            f"com o touchpad {agora} o gesto devia pedir {vai}, só para {UNIQ}")


def test_sem_leitura_o_gesto_recusa_dizendo_e_nao_manda_nada() -> None:
    p = Ponte()
    with pytest.raises(RuntimeError) as erro:
        _gesto("touchpad")(_ctx(), {"uniq": UNIQ}, p)
    assert str(erro.value) == a02.SEM_LEITURA_DO_TOUCHPAD
    assert p.chamadas == [], "recusou e mandou o pedido assim mesmo"


def test_sem_o_controle_no_clique_o_gesto_nao_chuta() -> None:
    with pytest.raises(ValueError):
        _gesto("touchpad")(_ctx(touchpad="ligado"), {}, Ponte())


def test_o_daemon_que_nao_confirma_vira_frase_curta() -> None:
    p = Ponte()
    p.corpo = None  # type: ignore[assignment]
    with pytest.raises(RuntimeError) as erro:
        _gesto("touchpad")(_ctx(touchpad="ligado"), {"uniq": UNIQ}, p)
    frase = str(erro.value)
    assert "não confirmou" in frase and "daemon" not in frase.lower(), frase


def test_a_ressalva_do_giro_nao_vira_erro_no_clique_do_touchpad() -> None:
    """Conferência de 15/10/2026: com o giro desligado e o nó de movimento sem grab, o
    `sensor.set` devolve `status: ok` com uma `ressalva` sobre o MOVIMENTO. O clique no
    touchpad deu certo, e o cartão não pode dizer o contrário.

    MORDIDA: volte a passar o `corpo` inteiro a `frase_do_interruptor_de_sensor` e reprova."""
    p = Ponte({"status": "ok", "touchpad": "desligado",
               "ressalva": "o nó de movimento não ficou exclusivo (grab=released)"})
    _gesto("touchpad")(_ctx(touchpad="ligado"), {"uniq": UNIQ}, p)
    assert p.chamadas == [("sensor_set_detalhado", {"touchpad": "desligado", "uniq": UNIQ})]


def test_o_daemon_que_devolve_o_touchpad_do_outro_lado_vira_erro() -> None:
    p = Ponte({"status": "ok", "touchpad": "ligado"})
    with pytest.raises(RuntimeError, match="seguiu ligado"):
        _gesto("touchpad")(_ctx(touchpad="ligado"), {"uniq": UNIQ}, p)


def test_o_pacote_pinta_o_estado_de_cada_controle() -> None:
    assert a02._toque_ligado({"sensores": {"touchpad": "ligado"}}) is True
    assert a02._toque_ligado({"sensores": {"touchpad": "desligado"}}) is False
    assert a02._toque_ligado({}) is None
    assert a02._toque_ligado({"sensores": {"touchpad": "talvez"}}) is None


# 4. OS TERÇOS -----------------------------------------------------------------------------------

@pytest.mark.parametrize(("x", "terca"), [
    (0.0, "esquerda"), (33.0, "esquerda"), (33.4, "meio"), (50.0, "meio"),
    (66.6, "meio"), (66.7, "direita"), (100.0, "direita"),
])
def test_a_superficie_parte_em_tercos(x: float, terca: str) -> None:
    assert a02.regiao_do_toque((x, 40.0)) == terca


def test_sem_dedo_nenhuma_terca_acende() -> None:
    assert a02.regiao_do_toque(None) == ""


# 5. SEM «?», SEM GANHO, SEM «JUNTO» -------------------------------------------------------------

def test_a_aba_sai_sem_ponto_de_interrogacao_nem_ganho() -> None:
    doc = _pagina()
    assert 'class="ajuda' not in doc and ">?<" not in doc and "?<span" not in doc, (
        "um «?» voltou à aba: cada explicação é uma dica curta no próprio botão")
    assert 'data-gesto="ganho-mic"' not in doc and "mic-ganho" not in doc, (
        "a linha do Ganho voltou ao microfone")
    assert 'data-rota="junto"' not in doc, "o quarto botão do alto-falante voltou"
    assert "chip-da-mira" not in doc, "o botão da mira voltou ao cabeçalho do cartão"


# 6. AS TRÊS ROTAS -------------------------------------------------------------------------------

def test_o_alto_falante_tem_as_tres_rotas_do_todo() -> None:
    doc = _pagina()
    cartoes = doc.count('class="rota trio"')
    assert cartoes >= 2
    nomes = {
        "jogo": "Canais sonoros nativos - Padrão",
        "pc": "Canais sonoros apenas no DualSense",
        "nada": "Canais sonoros apenas no PC",
    }
    for rota, nome in nomes.items():
        vistos = re.findall(rf'data-rota="{rota}"[^>]*>([^<]*)</button>', doc)
        assert vistos == [nome] * cartoes, f"a rota {rota} diz {sorted(set(vistos))}"
