"""O número que ela escreveu no gabinete chega ao texto que ela já lê hoje."""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("a coluna 'Onde está' da seção Conexões")

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
    _onde_esta_o_adaptador,
    _onde_esta_o_radio,
)
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, RadioUsb
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa, MaquinaConfig
from tests.unit.test_mapa_a_bancada_de_mentira import bancada_de_agora, mapa_dela

_NA_EXTENSAO = Adaptador(
    interface="hci1",
    no="/mentira/3-1.1.4",
    vid="2357",
    pid="0604",
    busnum=3,
    devpath="1.1.4",
    atras_de_hub=True,
)

#: O DualSense por cabo, na entrada 9 — e ele NÃO está atrás de hub na frase de
_NO_HUB = Adaptador(
    interface="hci0",
    no="/mentira/3-1.2",
    vid="2357",
    pid="0604",
    busnum=3,
    devpath="1.2",
    painel="right",
)


class _Hospedeiro:
    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None


def test_com_mapa_a_frase_traz_o_numero_dela() -> None:
    """"Entrada 9" — e nem "porta" nem "barramento" sobrevivem na frase."""
    texto, dica = _onde_esta_o_adaptador(_NO_HUB, mapa_dela())

    assert texto == "Entrada 9", f"a coluna não trouxe o número dela: {texto!r}"
    assert "porta" not in texto.lower(), (
        f"a palavra que ela recusou continua na tela: {texto!r}"
    )
    assert "barramento" not in texto.lower(), (
        f"o jargão do kernel continua na tela: {texto!r}"
    )
    assert dica is not None and "3-1.2" in dica, (
        "o caminho do sistema sumiu junto com o jargão. Ele tem de ficar na "
        f"dica: sem ele ninguém acha o aparelho num log. Dica: {dica!r}"
    )


def test_a_entrada_por_extensao_tambem_chega_na_frase() -> None:
    """``15a`` é um número de entrada como qualquer outro na coluna."""
    texto, _dica = _onde_esta_o_adaptador(_NA_EXTENSAO, mapa_dela())

    assert texto == "Entrada 15a", f"a entrada por extensão não chegou: {texto!r}"


def test_o_radio_vizinho_tambem_ganha_o_numero() -> None:
    """O Wi-Fi da traseira 3.0 é "Entrada 7", e não "Não sei"."""
    wifi = RadioUsb(
        no="/mentira/4-4", vid="2357", pid="012d", busnum=4, devpath="4", usb3=True
    )

    assert _onde_esta_o_radio(wifi, None, mapa_dela()) == "Entrada 7"
    assert _onde_esta_o_radio(wifi, ("colado no vizinho", "…"), mapa_dela()) == (
        "Entrada 7 · colado no vizinho"
    )


def test_sem_mapa_a_frase_e_a_de_hoje() -> None:
    """A frase literal de antes desta leva, palavra por palavra."""
    assert _onde_esta_o_adaptador(_NO_HUB) == (
        "Barramento 3, porta 1.2 · Direita",
        None,
    )
    assert _onde_esta_o_adaptador(_NO_HUB, MapaDaMesa()) == (
        "Barramento 3, porta 1.2 · Direita",
        None,
    )
    texto, dica = _onde_esta_o_adaptador(_NA_EXTENSAO, MapaDaMesa())
    assert texto == "Barramento 3, porta 1.1.4 · Não sei · Em hub"
    assert dica == "Lido do barramento USB: o Hefesto reconhece o hub."


def test_o_embutido_continua_dentro_da_maquina_com_ou_sem_mapa() -> None:
    """Rádio na placa-mãe não está em entrada nenhuma, e isso não muda."""
    embutido = Adaptador(interface="hci0")

    assert _onde_esta_o_adaptador(embutido, mapa_dela()) == (
        "Dentro da máquina",
        None,
    )


def test_aparelho_fora_do_mapa_fala_como_falava() -> None:
    """Ela desenhou a mesa e plugou um aparelho novo numa entrada não declarada."""
    intruso = Adaptador(
        interface="hci2", no="/mentira/2-1", vid="2357", pid="0604", busnum=2, devpath="1"
    )

    texto, _dica = _onde_esta_o_adaptador(intruso, mapa_dela())
    assert texto.startswith("Barramento 2, porta 1"), (
        f"o produto inventou uma entrada para um aparelho não declarado: {texto!r}"
    )


def test_a_tabela_montada_mostra_a_entrada_dela() -> None:
    """A seção inteira, montada, com o número dela na coluna "Onde está"."""
    bancada = bancada_de_agora()
    documento = MaquinaConfig.model_validate(
        {"version": 1, "mapa": mapa_dela().model_dump(mode="json")}
    )

    janela = Gtk.OffscreenWindow()
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    janela.add(caixa)
    painel = secao_mesa._PainelDaMesa(_Hospedeiro())
    painel._ler = lambda: bancada.mesa()  # type: ignore[method-assign]
    painel._ler_o_censo = lambda: bancada.censo()  # type: ignore[method-assign]
    painel._pedir_o_estado = lambda: None  # type: ignore[method-assign]
    original = secao_mesa.carregar_maquina
    secao_mesa.carregar_maquina = lambda: documento  # type: ignore[assignment]
    try:
        painel.montar(caixa)
    finally:
        secao_mesa.carregar_maquina = original  # type: ignore[assignment]
    janela.show_all()

    textos = _textos(caixa)
    assert "Entrada 13" in textos, (
        f"o número dela não chegou à tabela de adaptadores: {textos}"
    )
    assert "Entrada 15a" in textos, (
        f"a entrada por extensão não chegou à tabela: {textos}"
    )
    assert not any("Barramento 3" in texto for texto in textos), (
        f"o jargão do kernel continua na tela ao lado do número dela: {textos}"
    )


def _textos(raiz: Any) -> list[str]:
    achados: list[str] = []

    def _andar(widget: Any) -> None:
        if isinstance(widget, Gtk.Label):
            achados.append(widget.get_text())
        obter = getattr(widget, "get_children", None)
        if obter is not None:
            for filho in obter():
                _andar(filho)

    _andar(raiz)
    return achados
