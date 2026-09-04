#!/usr/bin/env python3
"""A coluna SEM controle da aba Vibração não pode mostrar o desenho como dado.

POR QUE ELE EXISTE, e a razão é uma FOTO — 03/09/2026, janela oculta, a mesa
dela com **um** controle (White · USB):

    coluna 1  P1 · White · USB   Balanceado aceso   trilho 100%   "— /255"
    coluna 2  —                  nenhum aceso       trilho  35%   "— /255"
    coluna 3  P3 · Desconectado  (lugar vazio)
    coluna 4  P4 · Desconectado  (lugar vazio)

A coluna 2 é o caso que ninguém desenhou: o mockup a fez CONECTADA
(``monta.MESA`` traz ``p1`` e ``p2`` com ``conectado: True``), então ela não é
um "lugar vazio" — e o controle dela não está na mesa de hoje, então
``app/telas/vibracao.pacote_da_mesa`` não a monta. O que sobra na tela é a CENA:
a barra do motor com a largura que o desenho cravou, ao lado de um número que
já diz "não sei".

**Largura sem número é a mentira mais barata desta tela**: o olho lê a barra,
não o travessão.

O QUE ELE MEDE, e é só isto: para cada um dos quatro lugares, o que o DOM VIVO
mostra depois de o piloto pintar — o texto da identidade, o número do
multiplicador, o número de cada motor e a LARGURA de cada trilho. Reprova
quando um lugar afirma largura sem ter número.

Uso (a janela é OCULTA; ela tem UMA tela)::

    scripts/ensaios/a_coluna_sem_controle_da_vibracao.py
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
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.interface import hefesto_vivo

ABA = "05-vibracao.html"

#: O TRAVESSÃO É DO PRODUTO, e não se digita aqui: ``app/telas/vibracao.NAO_SEI``
#: é o dono de "não sei" nesta aba, e o pintor usa o mesmo caractere.
from hefesto_dualsense4unix.app.telas.vibracao import NAO_SEI

import monta

#: OS LUGARES OCUPADOS DO DESENHO, na ordem — perguntados a quem os desenha.
#: ``monta.CONECTADOS`` é a fonte da cena do mockup; uma lista ``("p1", "p2")``
#: digitada aqui envelheceria no dia em que ela mudasse a cena.
LUGARES = tuple(c["pref"] for c in monta.CONECTADOS)

#: O PAR NÚMERO → TRILHO. É o contrato desta tela: toda largura tem um número ao
#: lado, e é o número que diz se a largura pode ser afirmada.
PARES = (("mult", "forca-pct"), ("motor-e", "motor-e-pct"),
         ("motor-d", "motor-d-pct"))

#: A LEITURA É POR ORDEM, e não pelo ``data-controle`` — e a diferença custou
#: uma medição errada, registrada porque a próxima pessoa vai tentar o mesmo.
#:
#: Nesta aba a grade é por LINHA: cada linha é um rótulo e uma célula por
#: coluna, e o ``data-controle="pN"`` está só na célula do DESENHO. O número do
#: motor e a largura do trilho moram em OUTRA linha, fora daquela célula — um
#: ``el.closest('[data-controle]')`` a partir deles devolve ``null`` (ou pior:
#: ``"dualsense"``, que é o ``data-controle`` de dentro do SVG). A primeira
#: versão desta régua leu o DOM assim e deu VERDE sobre quatro colunas vazias.
#:
#: O que casa coluna e campo é a ORDEM: a página emite um elemento por coluna
#: OCUPADA, na ordem da mesa. A i-ésima ocorrência de ``motor-e`` é o i-ésimo
#: lugar ocupado do desenho — e quem diz quais são esses lugares é
#: ``monta.CONECTADOS``, não uma lista digitada aqui.
LER = r"""
(function(){
  const fora = [];
  const largura = (el) => el.style.width || '';
  const pega = (i) => { while(fora.length <= i){ fora.push({campos:{}, larguras:{}, degraus:[]}); } return fora[i]; };
  const conta = {};
  for(const el of document.querySelectorAll('[data-campo]')){
    const campo = el.getAttribute('data-campo');
    if(campo === 'degrau'){
      // Os degraus vêm de quatro em quatro, um grupo por coluna ocupada.
      const i = Math.floor((conta['degrau'] = (conta['degrau'] || 0) + 1, conta['degrau'] - 1) / 4);
      if(el.classList.contains('on')){
        pega(i).degraus.push(el.getAttribute('data-hef-quando') || el.textContent.trim());
      }
      continue;
    }
    const i = (conta[campo] = (conta[campo] || 0) + 1) - 1;
    if(campo.endsWith('-pct')) pega(i).larguras[campo] = largura(el);
    else pega(i).campos[campo] = el.textContent.trim();
  }
  // A identidade viaja por `data-hef`, não por `data-campo` — é o rótulo da
  // coluna, e o pintor a alcança pelo mesmo fecho de endereços.
  let j = 0;
  for(const el of document.querySelectorAll('[data-hef="identidade"]')){
    pega(j++).campos['identidade'] = el.textContent.trim().replace(/\s+/g, ' ');
  }
  return JSON.stringify({lugares: fora, achei: document.querySelectorAll('[data-campo]').length,
                         url: location.pathname.split('/').pop()});
})()
"""

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def _largura_afirmada(w: str | None) -> bool:
    """`True` quando o trilho AFIRMA um comprimento — 0% e vazio não afirmam."""
    if not w:
        return False
    try:
        return float(w.rstrip("%")) > 0.0
    except ValueError:
        return False


def main() -> int:
    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    medida: list[dict] = []

    #: A PÁGINA SE ESCOLHE E SE CONFERE — e as duas metades custaram uma medição.
    #: `--abre` não bastou: a primeira versão perguntou 4 s depois de o piloto
    #: subir e leu a **01-jogar**, dando VERDE sobre uma aba que não é esta. Por
    #: isso o `_ir` explícito (como o `os_quatro_lugares_no_dom.py` faz) E o
    #: nome da página vindo de volta na resposta, conferido antes de julgar.
    def ir() -> bool:
        if not piloto.pronto:
            return True
        piloto._ir(ABA)
        GLib.timeout_add(2500, depois)
        return False

    def depois() -> bool:
        def respondeu(texto: str | None, erro: Exception | None) -> None:
            if erro or not texto:
                print(f"[dom] a ponte não respondeu: {erro}")
                Gtk.main_quit()
                return
            bruto = json.loads(texto)
            pagina.append(str(bruto["url"]))
            print(f"[dom] página {bruto['url']!r} · "
                  f"{bruto['achei']} elementos com data-campo")
            medida.extend(bruto["lugares"])
            Gtk.main_quit()

        piloto.ponte.perguntar(LER, respondeu)
        return False

    pagina: list[str] = []
    GLib.timeout_add(600, ir)
    GLib.timeout_add(40000, Gtk.main_quit)
    Gtk.main()

    if pagina and pagina[0] != ABA:
        print(f"REPROVA: li a página {pagina[0]!r}, e esta régua é da {ABA!r}.")
        return 1

    if not medida:
        print("REPROVA: não li o DOM — a janela não respondeu.")
        return 1

    print(f"{'lugar':6} {'identidade':26} "
          + " ".join(f"{n:>8}/{w:<11}" for n, w in PARES) + " degraus")
    print("-" * 112)
    culpados = []
    for i, lugar in enumerate(LUGARES):
        if i >= len(medida):
            print(f"{lugar:6} (a página não emitiu campo para este lugar)")
            continue
        d = medida[i]
        campos, larguras = d["campos"], d["larguras"]
        celas = " ".join(
            f"{campos.get(n)!s:>8}/{larguras.get(w)!s:<11}" for n, w in PARES)
        ident = f"{campos.get('identidade')}"[:26]
        print(f"{lugar:6} {ident:26} {celas} {d['degraus']}")
        # A REGRA, e ela é uma só: um número que diz "não sei" ao lado de um
        # trilho que AFIRMA comprimento. O olho lê a barra, não o travessão.
        for num, larg in PARES:
            if campos.get(num) == NAO_SEI and _largura_afirmada(larguras.get(larg)):
                culpados.append(
                    f"{lugar}: {num} diz {NAO_SEI!r} e o trilho {larg} afirma "
                    f"{larguras.get(larg)}")

    print()
    if culpados:
        print(f"REPROVA: {len(culpados)} trilho(s) afirmando largura sem número:")
        for c in culpados:
            print(f"  {c}")
        return 1
    print("OK: nenhum trilho desta aba afirma comprimento sem ter número.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
