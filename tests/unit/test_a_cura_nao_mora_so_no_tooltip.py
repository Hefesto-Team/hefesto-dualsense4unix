"""A cura sai do tooltip e vira card — com as três linhas e o selo de cada uma.

O QUE ESTE ARQUIVO TRAVA
-------------------------

O produto sabe achar cinco problemas na mesa, tem a cura escrita de quatro
deles, e até 25/08/2026 a cura só chegava à tela dentro de um
``set_tooltip_text`` (`secao_exame._dica_do_item`, e não havia um segundo
caminho). Quem não passasse o mouse por cima da palavra certa **nunca descobria
o que fazer**. Ao lado disso, `integrations/ordens_da_mesa.py` — 1261 linhas,
seis regras, bateria verde — não tinha um único consumidor.

Este arquivo é a régua de que os dois defeitos fecharam juntos:

1. o imperativo de uma ordem e as **três** linhas de porquê aparecem no texto de
   um ``Gtk.Label``, **fora de qualquer tooltip**;
2. a **terceira** linha aparece inclusive quando ela confessa que o ganho não
   foi medido. É ela que impede raciocínio de se vestir de medição: uma ordem
   que manda mover sem dizer quanto se ganha é honesta; a mesma com o ganho
   escondido é palpite com cara de laudo;
3. cada linha carrega o **selo de procedência** na tela — sem ele, "USB 3.0
   emite ruído em 2,4 GHz" (especificação de terceiro) e "não medi o ganho nesta
   máquina" (conta) leem igual;
4. a cura de uma conferência SEM ordem também sai do tooltip;
5. **nenhum serial chega ao markup.** A exigência nasceu quando a tela desta
   aba virava PNG versionado pelo retratista da janela GTK — que saiu com ela
   em 06/09/2026 (`D-0609-GTK-LEVA-INTEIRA`), e o retratista de hoje
   (`src/hefesto_dualsense4unix/interface/olhar.py`) fotografa as páginas HTML,
   não este painel. **A exigência fica**, e não depende de quem fotografa:
   nenhum portão de anonimato varre imagem, e `scripts/check_anonymity.sh` diz
   por escrito que o serial identifica a unidade dela tão bem quanto o MAC.

POR QUE ``Gtk.OffscreenWindow``, E NUNCA ``Gtk.Window``
--------------------------------------------------------

Sob Xvfb não há gerenciador de janelas, e uma ``Gtk.Window`` fica 1x1 para
sempre: os filhos nunca ganham tamanho e o teste passa a medir o servidor X em
vez do produto. É a armadilha nº 2 de `docs/method/COMO-OLHAR-A-TELA.md`.

A BANCADA NÃO É ESTA MÁQUINA
------------------------------

`bancada_das_ordens.py` monta o `Censo` e os `NoDeEntrada` à mão, com caminhos
``/mentira`` e seriais sintéticos, e os cinco caminhos do exame apontam para uma
raiz que não existe. Nada aqui abre ``/sys``, ``/proc`` ou o rádio.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a cura fora do tooltip")

import re
from pathlib import Path
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.integrations import exame_da_mesa as exame_mod
from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens
from tests.unit import bancada_das_ordens as bancada

SERIAL = re.compile(
    "(?<![0-9A-Fa-f])[0-9A-Fa-f]{"
    f"{ordens._TAMANHO_DO_SERIAL_DE_ENDERECO}"
    "}(?![0-9A-Fa-f])"
)

SEM_BANCADA = Path("/bancada/nao-existe")


def _leitura() -> ordens.Leitura:
    """A bancada de 24/08 como `Leitura` — sem desenho de gabinete nenhum."""
    return ordens.Leitura(censo=bancada.censo(), entradas=bancada.entradas())


def _itens(**extra: Any) -> list[exame_mod.Item]:
    """As cinco conferências no pior caso, mais o que o teste pedir por cima."""
    argumentos: dict[str, Any] = {
        "parametro_do_radio": SEM_BANCADA,
        "conf_do_radio": SEM_BANCADA,
        "raiz_usb": SEM_BANCADA,
        "modulos": SEM_BANCADA,  # (noqa-acento): nome de argumento
        "diretorio_do_modulo": SEM_BANCADA,
        "executar_busctl": lambda _argumentos: None,
        "leitura_da_vizinhanca": list,
        "leitura_das_ordens": _leitura,
    }
    argumentos.update(extra)
    return exame_mod.exame(**argumentos)


def _textos_visiveis(raiz: Any) -> list[str]:
    """O texto de todo ``Gtk.Label`` da árvore — e **nenhum tooltip**."""
    achados: list[str] = []
    for widget in _arvore(raiz):
        if isinstance(widget, Gtk.Label) and widget.get_text():
            achados.append(widget.get_text())
    return achados


def _markups(raiz: Any) -> list[str]:
    """O markup Pango cru de cada rótulo — é o que vira pixel e vira PNG."""
    achados: list[str] = []
    for widget in _arvore(raiz):
        if isinstance(widget, Gtk.Label):
            bruto = widget.get_label()
            if bruto:
                achados.append(bruto)
    return achados


def _arvore(raiz: Any) -> list[Any]:
    achados: list[Any] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        achados.append(widget)
        filhos = getattr(widget, "get_children", None)
        if filhos is not None:
            pilha.extend(filhos())
    return achados


def test_sem_pedir_o_exame_nao_traz_ordem_nenhuma() -> None:
    """O default de `leitura_das_ordens` é desligado, e isso é a foto."""
    itens = _itens(leitura_das_ordens=None)

    assert [item.ordem for item in itens] == [None] * 5


def test_leitura_que_explode_vira_nao_sei_e_nunca_silencio() -> None:
    """Falha de leitura não pode virar "não recomendei nada"."""

    def _quebrada() -> ordens.Leitura:
        raise OSError("o barramento sumiu no meio da leitura")

    itens = _itens(leitura_das_ordens=_quebrada)

    das_ordens = [item for item in itens if item.chave == exame_mod.CHAVE_DAS_ORDENS]
    assert len(das_ordens) == 1
    assert das_ordens[0].estado == exame_mod.ESTADO_NAO_SEI
    assert exame_mod.veredito(itens) != exame_mod.ESTADO_CERTO
