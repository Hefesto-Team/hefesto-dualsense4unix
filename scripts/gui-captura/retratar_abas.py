#!/usr/bin/env python3
"""Retrata as NOVE abas da janela, com o card do controle vivo dentro.

É o script que a documentação e o Claude Code usam. Uma execução, nenhum
clique, nenhuma janela na frente: ele monta a interface numa janela offscreen
do tamanho da tela maximizada dela e salva um PNG por aba.

    scripts/gui-captura/retratar_abas.py                 # atualiza as imagens
                                                         # da documentação
    scripts/gui-captura/retratar_abas.py /tmp/olhar      # só olhar, sem tocar
                                                         # no repositório

POR QUE ELE EXISTE, e por que é ele o certo entre os três desta pasta
--------------------------------------------------------------------

Esta pasta tem outros dois, e os dois têm limite conhecido:

* ``capturar_verificado.sh`` percorre as abas por teclado e fotografa a tela
  DE VERDADE. Precisa da janela aberta, maximizada e em foco — e o COSMIC
  recusou maximizar por atalho, por duplo clique e por F11. Serve para prova
  final com o olho dela, não para rotina;
* ``retrato_offscreen.py`` renderiza o ``.glade`` CRU. Rápido e sem
  dependência, mas mostra a janela VAZIA: combos sem itens, listas sem linhas
  e — o pior — a aba Status sem o card do controle, que é montado em código e
  é justamente a aba mais densa da janela.

Este aqui monta o glade E injeta o card do controle com dados de verdade. É a
única das três que produz uma foto onde dá para entender a tela.

O QUE ELE **NÃO** É
-------------------

Ele não substitui o olho dela. Um `OffscreenWindow` não passa pelo compositor:
não há sombra, arredondamento de canto nem o tema de janela do COSMIC. Para
"ficou bonito?" a resposta continua sendo a tela real. Para "o que tem nesta
aba, e onde?", esta foto é fiel — e é para isso que ela serve.

ARMADILHAS QUE ESTE ARQUIVO JÁ PAGOU (não as repita)
-----------------------------------------------------

1. **Sob Xvfb não há gerenciador de janelas.** Uma ``Gtk.Window`` de verdade
   nunca é mapeada e o filho fica 1x1 para sempre, por mais que o laço de
   eventos rode. Por isso aqui é ``OffscreenWindow``, que se auto-aloca.
2. **Widget sem alocação mede 1x1**, e qualquer medida tirada dele passa com
   qualquer desenho. O ``_assentar()`` abaixo drena o laço mais de uma vez de
   propósito.
3. **A aba Status sem o card é uma foto de tela vazia.** Foi o que fez uma leva
   inteira ser fotografada sem o objeto que ela mudava.
4. **O tema tem de ser aplicado**, senão as cores saem do tema do sistema e a
   foto não é o produto.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(os.environ.get("HEFESTO_RAIZ", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("GDK_BACKEND", "x11")

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

GLADE = RAIZ / "src/hefesto_dualsense4unix/gui/main.glade"

#: O destino padrão é onde a documentação já aponta. Rodar sem argumento
#: ATUALIZA as imagens do README e do guia da interface — é o comportamento
#: pedido: uma execução e a documentação deixa de mentir.
DESTINO_DOC = RAIZ / "docs/usage/assets"

#: A tela dela maximizada. Não é número inventado: é a resolução em que as
#: bancadas de layout desta casa medem, e a mesma do `retrato_offscreen.py`.
LARGURA, ALTURA = 1920, 1080

#: Os nomes que a documentação referencia. A ORDEM é a das abas no notebook.
#: O `interface.md` cita os nove; mudar um nome aqui quebra a documentação, então
#: o script confere no fim e avisa.
NOMES = (
    "readme_inicio",
    "readme_status",
    "readme_gatilhos",
    "readme_lightbar",
    "readme_rumble",
    "readme_perfis",
    "readme_sistema",
    "readme_emulacao",
    "readme_navegacao_dsx",
)


def _assentar(vezes: int = 8) -> None:
    """Drena o laço de eventos até o GTK parar de ter o que fazer.

    Mais de uma passada de propósito: a primeira monta, as seguintes deixam o
    tema, os `SizeGroup` e as elipses assentarem. Widget medido antes disso
    reporta 1x1.
    """
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


def _aplicar_tema(janela) -> str:  # type: ignore[no-untyped-def]
    """Aplica o tema do produto. A assinatura mudou entre versões; tenta as duas."""
    try:
        from hefesto_dualsense4unix.app.theme import apply_theme
    except Exception as exc:  # tema indisponível não impede a foto
        return f"tema indisponível ({exc})"
    for tentativa in (lambda: apply_theme(janela), lambda: apply_theme()):
        try:
            tentativa()
            return "tema aplicado"
        except TypeError:
            continue
        except Exception as exc:
            return f"tema falhou ({exc})"
    return "tema não aplicado"


def _injetar_card(builder) -> str:  # type: ignore[no-untyped-def]
    """Põe um card de controle vivo na aba Status.

    É o que separa este script do `retrato_offscreen.py`. Sem isto, a aba mais
    densa da janela sai vazia e a foto não serve para entender nada.

    Os dados vêm dos dublês da suíte (`test_status_faixa_blocos`) de propósito:
    eles já são a entrada canônica de um controle completo — sensores,
    touchpad, bateria — e são mantidos junto com o card. Inventar um payload
    aqui seria criar um segundo dono do formato.
    """
    try:
        from hefesto_dualsense4unix.app.mic_monitor import LeituraMic
        from hefesto_dualsense4unix.app.widgets.controller_card import (
            ControllerCard,
        )
        from tests.unit.test_status_faixa_blocos import _ENTRY, _ESTADO
    except Exception as exc:
        return f"card não injetado ({exc}) — a aba Status sai vazia"

    slot = builder.get_object("status_players_slot")
    if slot is None:
        return "card não injetado (slot ausente no glade)"

    card = ControllerCard(compact=False)
    card.set_hexpand(True)
    card.set_valign(Gtk.Align.START)
    slot.attach(card, 0, 0, 1, 1)
    card.show_all()

    # O botão da rota de som é REPARENTADO em tempo de execução pela
    # `status_actions._alojar_botao_da_rota`; sem repetir isso aqui, a foto
    # mostraria o botão no berço dele (o frame Estado) e não na casa.
    botao = builder.get_object("btn_som_no_controle")
    destino = getattr(card, "_speaker_rota_slot", None)
    if botao is not None and destino is not None:
        pai = botao.get_parent()
        if pai is not None:
            pai.remove(botao)
        destino.pack_start(botao, True, True, 0)
        destino.show_all()

    card.update(_ENTRY, _ESTADO, LeituraMic(nivel=0.6, muted=False))
    # Um volume conhecido, para o bloco do alto-falante não sair no estado
    # "sem dado" — que é o menos informativo dos possíveis.
    card.update(
        {**_ENTRY, "audio": {"speaker": {"volume": 180, "muted": False}}},
        _ESTADO,
        LeituraMic(nivel=0.6, muted=False),
    )
    return "card do controle injetado na aba Status"


def main(destino: str | None = None) -> int:
    saida = Path(destino) if destino else DESTINO_DOC
    saida.mkdir(parents=True, exist_ok=True)

    builder = Gtk.Builder()
    builder.add_from_file(str(GLADE))
    notebook = builder.get_object("main_notebook")
    if notebook is None:
        print("ERRO: `main_notebook` não existe no glade", file=sys.stderr)
        return 1

    janela = Gtk.OffscreenWindow()
    pai = notebook.get_parent()
    if pai is not None:
        pai.remove(notebook)
    janela.add(notebook)
    janela.set_size_request(LARGURA, ALTURA)
    print(f"  {_aplicar_tema(janela)}")
    janela.show_all()
    _assentar()
    print(f"  {_injetar_card(builder)}")
    _assentar()

    total = notebook.get_n_pages()
    if total != len(NOMES):
        print(
            f"AVISO: o notebook tem {total} abas e este script conhece "
            f"{len(NOMES)} nomes. A documentação cita os nomes de "
            "`NOMES` — acrescente o da aba nova ali, ou a foto dela ficará "
            "sem lugar.",
            file=sys.stderr,
        )

    print(f"\n  {'aba':<22} {'arquivo':<26} tamanho")
    print("  " + "-" * 58)
    for indice in range(total):
        notebook.set_current_page(indice)
        _assentar()
        pagina = notebook.get_nth_page(indice)
        rotulo = notebook.get_tab_label_text(pagina) or f"aba {indice}"
        nome = NOMES[indice] if indice < len(NOMES) else f"aba_{indice:02d}"
        arquivo = saida / f"{nome}.png"
        janela.get_pixbuf().savev(str(arquivo), "png", [], [])
        kb = arquivo.stat().st_size // 1024
        print(f"  {rotulo:<22} {arquivo.name:<26} {kb:>4} KB")

    print(f"\n  {total} aba(s) em {saida}")
    if saida == DESTINO_DOC:
        print("  as imagens do README e de docs/usage/interface.md estão em dia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
