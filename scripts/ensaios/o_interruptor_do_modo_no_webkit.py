#!/usr/bin/env python3
"""Clica DUAS VEZES no "Status do Modo" dentro do WebKit dela, e mede o que sai.

O QUE ELE PROVA, e por que o teste de unidade não bastava: a régua
``test_a_06_o_segundo_clique_nao_e_engolido`` chama ``modo()`` como função, com
um ``ctx`` de mentira. Isso prova a CONTA. O que prova o PRODUTO é o caminho
inteiro — ``<label>`` no DOM → ouvinte do piloto (``manda_do_alvo``) → thread de
``trabalhar`` → o gesto — dentro do mesmo ``WebKit2.WebView`` que ela usa, com o
estado do daemon dela sendo lido de verdade.

**A PONTE É INTERCEPTADA, E ISSO NÃO É COMODIDADE — É REGRA DA CASA.** O par
``("06-navegacao.html", "modo")`` está na lista de PERIGOSOS do piloto
(``hefesto_vivo.py:1033``), com a razão escrita: *"O CURSOR É DELA. Ligar a
emulação de mouse move o ponteiro na tela em que ela está trabalhando"*. E há um
segundo custo, medido aqui: o interruptor é dos DOIS (decisão dela, 27/08), então
dois cliques a partir de *mouse desligado · teclado ligado* deixariam o **teclado
desligado** ao fim — mudança na configuração dela que ninguém pediu.

Então ``pacotes.ponte.resultado`` é trocado por um gravador, que responde
``{"status": "ok"}`` e **não fala com o daemon**. O que continua REAL: a página,
o clique, o ouvinte, a thread, o gesto, e o ``ctx`` lido do daemon dela.

**O PORTÃO DE MODO É NEUTRALIZADO, E ISSO VAI ESCRITO NA SAÍDA.** O daemon dela
publica ``mode: None`` (medido em 03/09/2026), e o gesto recusa TODO clique nesse
estado — com razão, e nos dois lados: a GTK faz ``blocked = mode != MODE_DESKTOP``
(``mouse_actions.py:299``) e desliga o interruptor igual. Esse portão funciona e
**não é o que este ensaio mede**; ele fica no caminho do que é. Então
``mode_of_state`` é trocado por um que devolve ``desktop``, o modo REAL é impresso
antes, e a troca é dita na saída — uma neutralização calada seria o instrumento
medindo com a régua adulterada e sem avisar.

Ele mede quatro coisas:

1. o que os dois cliques MANDARAM (o defeito: ``enabled=True`` duas vezes);
2. o que o "Status do Modo" MOSTRA — a palavra e a classe ``ligado`` —, que
   desde 03/09 vem do daemon e não do desenho;
3. que o clique chega ao gesto pelo caminho do produto (DOM → ouvinte → thread);
4. que nada foi escrito no daemon dela: o gravador é a única saída.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/o_interruptor_do_modo_no_webkit.py
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

# A janela deste instrumento NÃO nasce na tela dela (TELA-DELA-02).
# Ela pediu duas vezes em 04/09/2026; o `park` do workspace chega tarde,
# porque move a janela DEPOIS de ela existir. Escape: HEFESTO_NA_TELA=1.
_RAIZ_TELA = str(pathlib.Path(__file__).resolve().parents[2] / 'src')
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk  # noqa: E402

# PELO NOME DO PACOTE, e não pelo nome curto. Custou uma medição falsa em
# 03/09/2026: `from pacotes import ponte` cria um módulo DIFERENTE de
# `hefesto_dualsense4unix.interface.pacotes.ponte`, que é o que o piloto importa
# (`hefesto_vivo.py:69`). O `ponte.resultado` trocado ficava num objeto que o
# produto nunca olha — o instrumento medindo contra a biblioteca errada, que é a
# primeira das armadilhas de `COMO-OLHAR-A-TELA.md`.
from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva  # noqa: E402
from hefesto_dualsense4unix.interface.pacotes import (  # noqa: E402
    a06_navegacao as aba,
)
from hefesto_dualsense4unix.interface.pacotes import ponte  # noqa: E402

ABA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

#: OS DOIS CLIQUES, NUM JS SÓ — para que nenhum tique caia entre eles. É a
#: condição do defeito: o `ctx` do segundo clique tem de ser o MESMO do primeiro.
#: O `setTimeout` de 60 ms é folga para o ouvinte despachar o primeiro, e cabe
#: com sobra dentro do tique de 500 ms.
DOIS_CLIQUES = r"""
(function(){
  const el = document.querySelector('[data-gesto="modo"]');
  if(!el){ return JSON.stringify({erro: 'NAO ACHEI O INTERRUPTOR'}); }
  const txt = el.querySelector('[data-campo="rato-ligado"]');
  const antes = {palavra: (txt ? txt.textContent : null),
                 ligado: el.classList.contains('ligado')};
  el.click();
  setTimeout(function(){ el.click(); }, 60);
  return JSON.stringify({antes: antes});
})()
"""

LER_O_INTERRUPTOR = r"""
(function(){
  const el = document.querySelector('[data-gesto="modo"]');
  const txt = el && el.querySelector('[data-campo="rato-ligado"]');
  return JSON.stringify({palavra: (txt ? txt.textContent : null),
                         ligado: !!(el && el.classList.contains('ligado'))});
})()
"""

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


class _Gravador:
    """O daemon de mentira. Ele existe para o daemon DELA não ser tocado."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict]] = []

    def __call__(self, metodo: str, timeout: float | None = None,
                 **params: object) -> dict:
        self.chamadas.append((metodo, dict(params)))
        return {"status": "ok"}


def main() -> int:
    gravador = _Gravador()
    ponte.resultado = gravador  # type: ignore[assignment]

    modo_de_verdade = aba.mode_of_state
    print(f"  o modo REAL do daemon dela: "
          f"{modo_de_verdade(mesa_viva.estado_do_daemon() or {})!r}")
    print(f"  NEUTRALIZADO para {aba.MODE_DESKTOP!r} — o portão de modo funciona "
          "e não é o que este ensaio mede.")
    aba.mode_of_state = lambda _st: aba.MODE_DESKTOP  # type: ignore[assignment]

    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    saida: dict[str, object] = {}

    def clicar() -> bool:
        if not piloto.pronto:
            return True

        def anotou(texto: str | None, erro: Exception | None) -> None:
            saida["clique"] = json.loads(texto) if texto and not erro else None
            saida["erro"] = str(erro) if erro else ""

        piloto.ponte.perguntar(DOIS_CLIQUES, anotou)
        return False

    def medir() -> bool:
        def leu(texto: str | None, erro: Exception | None) -> None:
            saida["depois"] = json.loads(texto) if texto and not erro else None
            Gtk.main_quit()

        piloto.ponte.perguntar(LER_O_INTERRUPTOR, leu)
        return False

    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(3000, clicar)
    # DEPOIS DOS DOIS CLIQUES E DE PELO MENOS UM TIQUE: o segundo clique sai aos
    # 60 ms, a thread do gesto leva o que a ponte de mentira levar (nada), e a
    # pintura do interruptor só acontece no tique seguinte.
    GLib.timeout_add(5000, medir)
    GLib.timeout_add(30000, Gtk.main_quit)
    Gtk.main()

    if saida.get("clique") is None:
        print(f"REPROVA: não consegui clicar. {saida.get('erro', '')}")
        return 1
    erro_js = (saida["clique"] or {}).get("erro")  # type: ignore[union-attr]
    if erro_js:
        print(f"REPROVA: {erro_js}")
        return 1

    antes = (saida["clique"] or {}).get("antes")  # type: ignore[union-attr]
    depois = saida.get("depois")
    print(f"  a tela ANTES   {antes}")
    print(f"  a tela DEPOIS  {depois}")
    print("  o que os dois cliques mandaram:")
    for metodo, params in gravador.chamadas:
        print(f"    {metodo:28s} {params}")

    mouse = [p.get("enabled") for m, p in gravador.chamadas
             if m == "mouse.emulation.set"]
    if len(mouse) != 2:
        print(f"\nREPROVA: o interruptor mandou {len(mouse)} pedido(s) de mouse, "
              "esperava 2 — o clique não chegou ao gesto pelo caminho do produto.")
        return 1
    if mouse == [True, True] or mouse == [False, False]:
        print(f"\nREPROVA: os dois cliques mandaram {mouse} — o segundo foi "
              "engolido. É o defeito de 03/09, vivo no WebKit.")
        return 1
    if mouse[0] == mouse[1]:
        print(f"\nREPROVA: os dois cliques mandaram {mouse}.")
        return 1

    # A GUARDA QUE IMPEDE ESTE ENSAIO DE MENTIR: se a palavra da tela não vier
    # do daemon, o `antes` seria o `—` do desenho para sempre, e o ensaio daria
    # verde sobre um interruptor que ninguém pinta.
    palavra = (antes or {}).get("palavra")
    if palavra in (None, "", "—"):
        print(f"\nREPROVA: o 'Status do Modo' mostrava {palavra!r} — o daemon "
              "não pintou o interruptor, e este ensaio não prova nada assim.")
        return 1

    print(f"\nOK: os dois cliques no mesmo tique mandaram {mouse} — o segundo "
          f"DESFEZ o primeiro. A tela dizia {palavra!r}, pintado do daemon.")
    print("     E o daemon dela não foi tocado: a ponte estava interceptada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
