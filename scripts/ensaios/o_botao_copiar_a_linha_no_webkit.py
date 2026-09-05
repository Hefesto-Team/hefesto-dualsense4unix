#!/usr/bin/env python3
"""Clica o «Copiar a linha» no DOM VIVO e prova que a linha chega à área de transferência.

POR QUE ELE EXISTE, e é a regra desta casa (dela, 29/08/2026): *"temos que ter
no nosso hook do novo dev algo que induza a construção de validações via
interface"*. O teste de unidade
``test_a_aba_07_lancadores_fecha_as_linhas`` prova a CONTA — o botão nasce só
no estado intocável, o gesto copia a constante do motor, a recusa aponta a
linha à mostra — em Python puro, com a área de transferência DUBLADA. O que
prova o PRODUTO é o mesmo caminho dentro do ``WebKit2.WebView`` que ela usa:
o botão que ela clica, a área de transferência de verdade, e a tarja que ela lê.

O ensaio faz o caminho dela, em três tempos:

1. **antes** — o cartão da Steam com um jogo de LINHA INTOCÁVEL; lê o corpo, os
   botões e o bloco da linha à mostra;
2. **o clique** — aciona o «Copiar a linha» de verdade, pelo ouvinte do piloto;
3. **a prova** — lê a área de transferência **de volta** e compara com
   ``steam_launch_options.WRAPPER_LAUNCH``, e lê a tarja no DOM.

A ÁREA DE TRANSFERÊNCIA NÃO É A DELA, e isto é o que torna o ensaio seguro: a
guarda de tela (TELA-DELA-02) aponta o GTK para um ``Xvfb`` próprio
(``DISPLAY=:NN``, sem ``WAYLAND_DISPLAY``), e a seleção X daquele servidor é
isolada da sessão dela. Nada do que ela tiver copiado é substituído.

NADA AQUI TOCA O DISCO DELA: ``a07._ler_do_disco`` é dublado, e o gesto de
copiar não escreve arquivo nenhum por construção.

A MORDIDA MORA AQUI DENTRO, com ``--sem-cura``: a leitura vai sem a
``linha``, e o ensaio tem de REPROVAR dizendo que o botão não nasceu. Um ensaio
que não sabe reprovar não mede nada.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/o_botao_copiar_a_linha_no_webkit.py [--foto X.png] [--sem-cura]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

# A janela deste instrumento NÃO nasce na tela dela (TELA-DELA-02), e aqui ela
# faz um segundo trabalho: sob o `Xvfb` a área de transferência é a DAQUELE
# servidor, não a da sessão dela. Escape: HEFESTO_NA_TELA=1 — e quem o declarar
# passa a copiar por cima do que ela tiver copiado.
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
# O `Gdk` PRECISA DE VERSÃO DECLARADA, e este ensaio pagou por descobrir: sem
# esta linha o `from gi.repository import Gdk` resolve para o **GDK 4** (é o
# mais novo instalado), o Gtk 3 já carregado recusa, e o instrumento morre com
# `Requiring namespace 'Gdk' version '3.0', but '4.0' is already loaded`. É a
# mesma armadilha do produto: `Gdk.SELECTION_CLIPBOARD` não existe no GDK 4.
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk

from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
from hefesto_dualsense4unix.interface import hefesto_vivo
from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

ABA = "07-lancadores.html"

#: O jogo intocável de mentira. O appid não existe na Steam de ninguém — é a
#: forma de o ensaio nunca casar com a biblioteca de quem o rodar.
APPID = "999000002"
ROTULO = "JOGO DE LINHA INTOCÁVEL"

#: Lê o cartão da Steam: os botões, o bloco da linha e o corpo.
LER = r"""
(function(){
  const c = document.querySelector('[data-lancador="steam"]');
  if(!c){ return JSON.stringify({achou: false}); }
  const bloco = c.querySelector('.linha-do-wrapper code');
  return JSON.stringify({
    achou: true,
    botoes: Array.from(c.querySelectorAll('button')).map(b => b.textContent.trim()),
    copiar: c.querySelectorAll('[data-gesto="copiar-a-linha"]').length,
    linha: bloco ? bloco.textContent : null,
    diz: (c.querySelector('[data-campo="steam-diz"]') || {}).textContent || null
  });
})()
"""

CLICAR = r"""
(function(){
  const bt = document.querySelector('[data-gesto="copiar-a-linha"]');
  if(!bt){ return JSON.stringify({clicou: false}); }
  bt.click();
  return JSON.stringify({clicou: true, rotulo: bt.textContent.trim()});
})()
"""

TARJA = r"""
(function(){
  const el = document.querySelector('.hef-recado');
  return JSON.stringify({tarja: el ? el.textContent.trim() : null});
})()
"""

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def _leitura_de_mentira(com_linha: bool) -> desenho.Leitura:
    """Um cartão da Steam com jogo de LINHA INTOCÁVEL — o único estado do botão."""
    a07.PORTOES = a07._Portoes(jogo_aberto=False, steam_aberta=False)
    return desenho.Leitura(
        com_wrapper=("1", "2"),
        intocaveis=((APPID, ROTULO, "linha editada à mão — não vou tocar"),),
        instalados=2,
        onde_estao=(("steam", "/usr/local/share/applications/steam.desktop"),),
        linha=slo.WRAPPER_LAUNCH if com_linha else "",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--foto", default="",
                    help="PNG do cartão com o botão (sempre oculto)")
    ap.add_argument("--sem-cura", action="store_true",
                    help="A MORDIDA: a leitura vai sem a linha, e o ensaio "
                         "tem de reprovar dizendo que o botão não nasceu")
    args_meus = ap.parse_args()

    a07._ler_do_disco = lambda: _leitura_de_mentira(not args_meus.sem_cura)

    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    visto: dict[str, object] = {}

    def _pergunta(chave: str, js: str, depois: object = None) -> object:
        def _corpo() -> bool:
            if not piloto.pronto:
                return True

            def _respondeu(texto: str | None, erro: Exception | None) -> None:
                visto[chave] = json.loads(texto) if texto and not erro else None
                if erro:
                    visto[chave + "-erro"] = str(erro)
                if depois is not None:
                    depois()

            piloto.ponte.perguntar(js, _respondeu)
            return False
        return _corpo

    def _fim() -> None:
        if args_meus.foto:
            piloto.tela.fotografar(args_meus.foto)
        Gtk.main_quit()

    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(2500, _pergunta("antes", LER))
    GLib.timeout_add(3200, _pergunta("clique", CLICAR))
    # O gesto roda em thread e a confirmação da área de transferência tem teto
    # de `a07.SEGUNDOS_PARA_COPIAR`; a tarja só pousa depois disso.
    GLib.timeout_add(6000, _pergunta("tarja", TARJA))
    GLib.timeout_add(7000, _pergunta("depois", LER, _fim))
    GLib.timeout_add(30000, Gtk.main_quit)
    Gtk.main()

    # A ÁREA DE TRANSFERÊNCIA, LIDA DE VOLTA — e é esta linha que separa este
    # ensaio do teste de unidade: lá ela é dublê, aqui é a seleção X de verdade.
    area = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()

    antes = visto.get("antes") or {}
    clique = visto.get("clique") or {}
    tarja = visto.get("tarja") or {}

    print(f"  antes    botões no cartão: {antes.get('botoes')}")
    print(f"           «Copiar a linha» no DOM: {antes.get('copiar')}")
    print(f"           bloco à mostra: {str(antes.get('linha'))[:70]!r}")
    print(f"  clique   {clique}")
    print(f"  tarja    {str(tarja.get('tarja'))[:110]!r}")
    print(f"  área     {str(area)[:70]!r}")

    if args_meus.sem_cura:
        if antes.get("copiar"):
            print("\nREPROVA (mordida): sem a linha na leitura, o botão NASCEU "
                  "mesmo assim — ele copiaria o vazio e diria 'Copiado!'.")
            return 1
        print("\nOK (mordida): sem a linha, o cartão não oferece o botão nem o "
              "bloco — o desenho cala em vez de inventar. Rode sem "
              "`--sem-cura` para ver a cura passar.")
        return 0

    if not antes.get("achou"):
        print("\nREPROVA: não achei o cartão da Steam no DOM.")
        return 1
    if not antes.get("copiar"):
        print("\nREPROVA: o cartão com jogo intocável não trouxe o «Copiar a "
              "linha» — a tela continuaria prometendo reparo manual sem "
              "oferecer caminho.")
        return 1
    if antes.get("linha") != slo.WRAPPER_LAUNCH:
        print("\nREPROVA: o bloco à mostra não traz a linha do motor.")
        return 1
    if not clique.get("clicou"):
        print("\nREPROVA: não achei o botão para clicar no DOM vivo.")
        return 1
    if area != slo.WRAPPER_LAUNCH:
        print("\nREPROVA: a área de transferência NÃO ficou com a linha. O "
              "clique chegou ao Python e o efeito não chegou ao ambiente — "
              "que é exatamente o botão que responde calado.")
        return 1
    if not tarja.get("tarja") or "Copiado" not in str(tarja.get("tarja")):
        print("\nREPROVA: copiou e não disse. Sem a tarja, o único sinal do "
              "clique é a área de transferência — que ela não vê.")
        return 1

    print("\nOK: o cartão com linha intocável ofereceu o «Copiar a linha» E o "
          "bloco à mostra, o clique pôs a linha do motor na área de "
          "transferência de verdade, e a tarja disse o que fazer com ela.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
