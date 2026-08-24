"""B1 — a tela do daemon fora do ar não pode ser a de um rádio vazio.

Medido na bancada viva em 23/08/2026, com o Hefesto parado: as três barras
diziam **"Folgada"**, em verde, e **"0/1600 · derivado da especificação"** —
byte a byte a tela de um rádio de fato vazio. Quem entra na aba justamente para
diagnosticar rádio cheio lê "está folgado" e vai procurar o defeito no controle.
É o padrão que esta casa já nomeou: o produto respondendo pelo TRANSPORTE e não
pelo efeito, com ausência de notícia lida como notícia de sucesso.

A MORDIDA (23/08/2026): arranquei o ramo do não-sei de `_fileira_do_medidor`
(voltando a palavra para `ocupacao.rotulo` e a cor para `_VERDE`) e
`test_a_tela_sem_daemon_nao_e_a_tela_do_radio_vazio` reprovou com as duas telas
idênticas, seguido de mais dois nós. Devolvido, os cinco passam.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: contra o stub (`Gtk.Box = object`) nada aqui existiria.
exigir_gi_real("o medidor sem daemon")

from types import SimpleNamespace
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, Mesa
from hefesto_dualsense4unix.integrations.radio_da_mesa import Ocupacao

#: Um adaptador SINTÉTICO — `vid:pid` de bancada, nenhum endereço.
_MESA = Mesa(adaptadores=(Adaptador(interface="hci0", no="1-1", vid="2357", pid="0604"),))


def _painel() -> Any:
    """A seção montada offscreen, com a mesa injetada.

    `Gtk.OffscreenWindow` e não `Gtk.Window`: sob Xvfb não há gerenciador de
    janelas e uma `Gtk.Window` fica 1x1 para sempre.
    """
    host = SimpleNamespace(
        _maquina_pendente={}, _mesa_leitor=lambda: _MESA, _censo_leitor=None
    )
    janela = Gtk.OffscreenWindow()
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    janela.add(caixa)
    painel = secao_mesa._PainelDaMesa(host)
    painel.montar(caixa)
    janela.show_all()
    return painel


def _tela(painel: Any) -> list[str]:
    """O que a caixa de medidores DIZ — texto e cor, na ordem em que aparecem."""
    textos: list[str] = []

    def andar(widget: Any) -> None:
        if isinstance(widget, Gtk.Label):
            textos.append(widget.get_label())
        if hasattr(widget, "get_children"):
            for filho in widget.get_children():
                andar(filho)

    andar(painel._caixa_medidores)
    return textos


def _radio_vazio() -> list[str]:
    """A tela do rádio de fato vazio: o daemon respondeu, e não há ninguém."""
    painel = _painel()
    painel._daemon_respondeu = True
    painel._aplicar_estado({"controllers": []})
    return _tela(painel)


def _daemon_mudo() -> list[str]:
    """A tela do daemon fora do ar, pelo caminho de produção.

    O `_falhou` de `_pedir_o_estado` é uma closure: chega-se a ele pelo dublê do
    `call_async`, que é por onde a falha chega de verdade.
    """
    painel = _painel()
    # A guarda do retrato (`_mesa_leitor` de pé = foto, e a foto não fala com o
    # daemon) faria `_pedir_o_estado` voltar na porta. A janela de verdade não
    # tem dublê nenhum, e é a janela que se mede aqui.
    painel._host._mesa_leitor = None
    guardado: dict[str, Any] = {}

    def _call_async(
        _metodo: str, _payload: Any, _ok: Any, falhou: Any, **_kw: Any
    ) -> None:
        guardado["falhou"] = falhou

    from hefesto_dualsense4unix.app import ipc_bridge

    antigo = ipc_bridge.call_async
    ipc_bridge.call_async = _call_async  # type: ignore[assignment]
    try:
        painel._pedir_o_estado()
    finally:
        ipc_bridge.call_async = antigo  # type: ignore[assignment]
    guardado["falhou"](TimeoutError("daemon fora do ar"))
    assert painel._daemon_respondeu is False
    return _tela(painel)


def test_a_tela_sem_daemon_nao_e_a_tela_do_radio_vazio() -> None:
    vazio, mudo = _radio_vazio(), _daemon_mudo()
    assert vazio, "sem barra nenhuma o teste não mede nada"
    assert mudo != vazio, (
        "o daemon fora do ar desenha a MESMA tela de um rádio vazio — quem "
        f"abre a aba para diagnosticar rádio cheio lê {vazio!r} e vai procurar "
        "o defeito no controle"
    )


def test_sem_daemon_a_palavra_nao_e_folgada_nem_verde() -> None:
    tela = " ".join(_daemon_mudo())
    assert secao_mesa._PAINEL_DESCONHECIDO in tela
    assert "Folgada" not in tela
    assert secao_mesa._VERDE not in tela, "verde é a cor de 'está tudo bem'"
    assert secao_mesa._LARANJA in tela


def test_sem_daemon_o_selo_e_o_leitor_de_tela_calam_junto() -> None:
    """Os dois acompanhantes, senão a linha continua afirmando por baixo."""
    tela = " ".join(_daemon_mudo())
    assert "1600" not in tela, "sem daemon não há número, e '0/1600' é afirmação"
    assert secao_mesa._SELO_DE_PROCEDENCIA not in tela
    assert secao_mesa._SEM_RESPOSTA_DO_DAEMON in tela
    assert secao_mesa._texto_acessivel(Ocupacao(), sabido=False) != (
        secao_mesa._texto_acessivel(Ocupacao())
    )


def test_o_caminho_feliz_continua_letra_por_letra_o_de_hoje() -> None:
    """Com o daemon respondendo, a fileira é a de antes do conserto."""
    painel = _painel()
    painel._daemon_respondeu = True
    ocupacao = Ocupacao(slots_input=260.0)
    textos: list[str] = []

    def andar(widget: Any) -> None:
        if isinstance(widget, Gtk.Label):
            textos.append(widget.get_label())
        if hasattr(widget, "get_children"):
            for filho in widget.get_children():
                andar(filho)

    andar(painel._fileira_do_medidor("aa:bb:cc:00:00:11", ocupacao))
    assert f'<span foreground="{secao_mesa._VERDE}">Folgada</span>' in textos
    assert "260/1600 · derivado da especificação" in textos


def test_a_varredura_que_falhou_e_nao_medi() -> None:
    """A segunda porta: `_ocupacoes` engolindo exceção marca "não medi"."""
    painel = _painel()
    painel._daemon_respondeu = True
    painel._controles = [{"transport": "bt"}]

    def _explode(*_a: Any, **_kw: Any) -> dict[str, Ocupacao]:
        raise OSError("/sys mudo")

    antigo = secao_mesa.ocupacao_por_adaptador
    secao_mesa.ocupacao_por_adaptador = _explode  # type: ignore[assignment]
    try:
        assert painel._ocupacoes() == {}
    finally:
        secao_mesa.ocupacao_por_adaptador = antigo  # type: ignore[assignment]
    assert painel._daemon_respondeu is False, (
        "varredura que falhou virou 'medi zero', e zero pinta verde"
    )
