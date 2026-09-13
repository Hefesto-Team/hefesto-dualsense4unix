#!/usr/bin/env python3
"""Clica o "Consertar" no DOM VIVO e prova que a vigia cumpre — CALADA no cartão.

POR QUE ELE EXISTE, e é a regra desta casa: o teste de unidade
``test_a_vigia_da_steam_repoe_sozinha_07`` prova a CONTA — arma, tique, relato
— em Python puro. O que prova o PRODUTO é o mesmo caminho dentro do
``WebKit2.WebView`` que ela usa: o botão que ela clica e o cartão que ela lê.

O ensaio faz o caminho dela, em três tempos:

1. **antes** — o cartão da Steam com um jogo pendente; lê o corpo do cartão;
2. **o clique** — aciona o `Consertar` de verdade, pelo ouvinte do piloto. A
   Steam "está aberta", então o produto RECUSA com a frase da sentinela, e é
   essa recusa que ARMA a vigia;
3. **o tempo** — espera o tique da vigia com a "Steam já fechada" e relê o
   cartão.

O CONTRATO MUDOU EM 13/09/2026 — TELA-CALADA-02. Até aqui o terceiro tempo
exigia a frase do `carona_do_wrapper` DENTRO do cartão. A palavra dela sobre as
frases de status é *"em todas as abas da interface"*, e a frase saiu do cartão:
ela vai para o diário da janela (`[relato]` no stderr). O ensaio passou a exigir
as duas metades — o relato ESCRITO e o cartão CALADO — e a vigia viva no tempo.

Reprova se o clique não chegar ao gesto, se a vigia não sobreviver ao primeiro
adiamento, se o relato não for escrito, ou se a frase aparecer no cartão.

NADA AQUI TOCA O DISCO DELA, e essa é a condição de o ensaio poder existir: os
TRÊS caminhos que escreveriam no `localconfig.vdf` são dublados neste processo
(`_ler_do_disco`, `sentinela_do_wrapper.reparar_ou_adiar` e
`carona_do_wrapper.passada`). O jogo pendente é de mentira.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/a_vigia_da_steam_no_webkit.py
"""
from __future__ import annotations

import argparse
import json
import os
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
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions import carona_do_wrapper as cdw
from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
from hefesto_dualsense4unix.interface import hefesto_vivo
from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

ABA = "07-lancadores.html"

#: O jogo pendente de mentira. O appid não existe na Steam de ninguém — é a
#: forma de o ensaio nunca casar com a biblioteca de quem o rodar.
APPID = "999000001"
ROTULO = "JOGO DE ENSAIO"

FRASE_DA_VIGIA = (
    "Reposta a Opção de Inicialização do Hefesto em 1 jogo da Steam: "
    f"{ROTULO}. As opções que você já tinha na linha foram preservadas."
)

#: O QUE NÃO PODE APARECER NO CARTÃO, antes nem depois. O rótulo do jogo não
#: serve: ele mora na LISTA do cartão (`steam-fora`), e procurar por ele no
#: corpo já deu verde sobre nada numa versão anterior deste ensaio.
MARCA = "Reposta a Opção de Inicialização do Hefesto"

#: Onde gravar o retrato do cartão DEPOIS. Vazio = não fotografa.
FOTO = ""

#: Lê o corpo do cartão da Steam. `data-campo` do desenho, não uma classe.
LER = r"""
(function(){
  const el = document.querySelector('[data-campo="steam-diz"]');
  const bt = Array.from(document.querySelectorAll('[data-gesto="consertar"]'));
  return JSON.stringify({diz: el ? el.textContent.trim() : null,
                         botoes: bt.length});
})()
"""

CLICAR = r"""
(function(){
  const bt = document.querySelector('[data-gesto="consertar"]');
  if(!bt){ return JSON.stringify({clicou: false}); }
  bt.click();
  return JSON.stringify({clicou: true, rotulo: bt.textContent.trim()});
})()
"""

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500, sem_ondas=False,
                 conta_mutacoes=0)


def _leitura_de_mentira() -> desenho.Leitura:
    """Um cartão da Steam COM pendência — e os portões que abrem o botão."""
    a07.PORTOES = a07._Portoes(jogo_aberto=False, steam_aberta=True)
    return desenho.Leitura(
        com_wrapper=("1",),
        reparaveis=((APPID, ROTULO, "tinha o atalho e perdeu"),),
        instalados=1,
        onde_estao=(("steam", "/usr/local/share/applications/steam.desktop"),),
    )


def _censo() -> sw.Censo:
    return sw.Censo(
        faltantes=[sw.JogoSemWrapper(APPID, ROTULO, None, sw.MOTIVO_REGRESSAO,
                                     "/dev/null")],
        steam_aberta=True,
    )


def _dublar() -> tuple[list[int], list[str]]:
    """Tira o disco do caminho. Devolve os tiques da vigia e os relatos."""
    tiques: list[int] = []
    relatos: list[str] = []

    def _passada(*, completa: bool = True) -> cdw.ResultadoDaCarona:
        tiques.append(1)
        if len(tiques) == 1:  # a Steam ainda está aberta
            return cdw.ResultadoDaCarona(cdw.ADIADO_SEM_OLHAR, "",
                                         frozenset(), True)
        return cdw.ResultadoDaCarona(sw.REPARO_FEITO, FRASE_DA_VIGIA,
                                     frozenset(), False)

    anotar = a07.VIGIA_DA_STEAM._anotar

    def _anotar(frase: str) -> None:
        relatos.append(frase)
        anotar(frase)

    a07._ler_do_disco = _leitura_de_mentira
    a07.VIGIA_DA_STEAM._anotar = _anotar
    sw.reparar_ou_adiar = lambda *a, **k: (sw.REPARO_ADIADO_STEAM, _censo(), None)
    cdw.passada = _passada
    cdw.INTERVALO_DA_VIGIA_S = 3
    os.environ["HEFESTO_CARONA_WRAPPER"] = "1"
    return tiques, relatos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--foto", default="",
                    help="PNG do cartão DEPOIS de a vigia repor (sempre oculto)")
    global FOTO
    FOTO = ap.parse_args().foto

    tiques, relatos = _dublar()
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

    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(2500, _pergunta("antes", LER))
    GLib.timeout_add(3200, _pergunta("clique", CLICAR))
    # A vigia tem de VIVER NO TEMPO: o clique arma em ~3,2 s, o primeiro tique
    # (≈6,2 s) ADIA e o segundo (≈9,2 s) REPÕE. A leitura vem depois disso.
    def _fim() -> None:
        if FOTO:
            piloto.tela.fotografar(FOTO)
        Gtk.main_quit()

    GLib.timeout_add(11000, _pergunta("depois", LER, _fim))
    GLib.timeout_add(30000, Gtk.main_quit)
    Gtk.main()

    antes = visto.get("antes") or {}
    clique = visto.get("clique") or {}
    depois = visto.get("depois") or {}

    print(f"  antes    botões `consertar` no DOM: {antes.get('botoes')}")
    print(f"           corpo do cartão: {str(antes.get('diz'))[:90]!r}")
    print(f"  clique   {clique}")
    print(f"  vigia    armada={a07.VIGIA_DA_STEAM.armada()} · "
          f"tiques={len(tiques)} · relatos={len(relatos)}")
    print(f"  depois   corpo do cartão: {str(depois.get('diz'))[:150]!r}")

    if not antes.get("botoes"):
        print("\nREPROVA: o cartão não ofereceu o `Consertar` — sem ele não há "
              "o que clicar, e o ensaio não prova nada.")
        return 1
    if not clique.get("clicou"):
        print("\nREPROVA: não achei o botão para clicar no DOM vivo.")
        return 1
    if len(tiques) < 2:
        print(f"\nREPROVA: a vigia deu {len(tiques)} tique(s). Ela precisa "
              "sobreviver ao primeiro adiamento para provar que espera.")
        return 1
    if FRASE_DA_VIGIA not in relatos:
        print("\nREPROVA: a vigia repôs e não escreveu o relato — o diário da "
              "janela ficaria sem saber que o Hefesto cumpriu.")
        return 1
    for quando, lido in (("antes", antes), ("depois", depois)):
        if MARCA in str(lido.get("diz") or ""):
            print(f"\nREPROVA: o cartão disse {MARCA!r} {quando} — a notícia "
                  "de fundo voltou ao corpo do cartão (TELA-CALADA-02).")
            return 1

    print("\nOK: o `Consertar` chegou ao gesto com a Steam aberta, a recusa "
          f"ARMOU a vigia, ela sobreviveu a {len(tiques) - 1} adiamento(s) e, "
          "com a Steam fechada, repôs, escreveu o relato e deixou o cartão calado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
