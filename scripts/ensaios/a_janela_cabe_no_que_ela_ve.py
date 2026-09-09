#!/usr/bin/env python3
"""ROLAGEM-01 — a barra vertical, medida no WebKit VIVO e não no Chrome.

**Achado por ELA em 08/09/2026, com o produto instalado e maximizado:**

    "outro bo desde que alteramos a altura e largura geral. duas paginas  (noqa-acento: citação dela)
     ficaram com barra de navegação vertical. tipo a gatilhos e lançadores."

**O QUE JÁ TINHA SIDO EXCLUÍDO, e por medição:** as dez páginas PUBLICADAS,
lidas em Chrome headless a 1180, 1600 e 1900 de largura, não trazem nenhum
elemento com `overflow` estourado dentro da `.janela`, e o conteúdo dela fecha
em 775 px nas dez. Se a legenda (`div.nota`, que vive FORA da `.janela`) fosse
a causa, as dez rolariam — a `02-controles` mais que todas, com 3093 px — e ela
viu **duas**.

**O QUE SOBRAVA, e é o que este instrumento mede:** WebKit + **dado vivo** + a
janela GTK. Com quatro controles na mesa, a `03-gatilhos` desenha quatro
colunas com o bloco do L2, o do R2 e a linha «Guardar / Todos»; a
`07-lancadores` desenha seis cartões com a biblioteca de cada um. O publicado
tem as quatro colunas — mas com o DESENHO, não com o que o aparelho dela diz.

*Um instrumento que mede a página estática responde sobre outra coisa que não o
produto.* É a assinatura dos seis instrumentos falsos de 05/09.

O QUE ELE FAZ
-------------

Abre o piloto OCULTO (TELA-DELA-02: a janela não nasce na tela dela), visita
cada aba, espera o tique pintar com o dado do daemon vivo, e pergunta ao DOM:

* a altura do conteúdo da `.janela` contra a caixa que ela tem;
* o mesmo para o documento inteiro;
* e QUEM estourou — o primeiro elemento cujo conteúdo passa da caixa.

REPROVA nomeando a aba e os dois números em pixel.

    scripts/ensaios/a_janela_cabe_no_que_ela_ve.py             # as dez
    scripts/ensaios/a_janela_cabe_no_que_ela_ve.py 03 07       # só duas
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src/hefesto_dualsense4unix/interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# A janela deste instrumento NÃO nasce na tela dela (TELA-DELA-02).
# Escape declarado: HEFESTO_NA_TELA=1.
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.interface import hefesto_vivo

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)

ABAS = ["01-jogar.html", "02-controles.html", "03-gatilhos.html",
        "04-iluminacao.html", "05-vibracao.html", "06-navegacao.html",
        "07-lancadores.html", "08-conexoes.html", "09-sistema.html",
        "10-perfis.html"]

#: A PERGUNTA AO DOM. Ela mede a `.janela` e o documento, e nomeia o primeiro
#: estouro — sem o culpado, o relato diz "rolou" e ninguém sabe onde mexer.
#:
#: O `+2` DE FOLGA não é frouxidão: o WebKit arredonda alturas de linha, e um
#: pixel de diferença aparece em página que não rola. Dois pixels não fazem
#: barra aparecer; medido em 09/09/2026 nas dez.
LER = """(function(){
  var j = document.querySelector('.janela');
  var d = document.documentElement;
  var culpado = null;
  if (j) {
    var todos = j.querySelectorAll('*');
    for (var i = 0; i < todos.length; i++) {
      var e = todos[i];
      if (e.scrollHeight > e.clientHeight + 2) {
        var ov = getComputedStyle(e).overflowY;
        if (ov === 'visible') continue;
        culpado = e.tagName + '.' + String(e.className).slice(0, 30) +
                  ' ' + e.scrollHeight + '>' + e.clientHeight;
        break;
      }
    }
  }
  // E QUEM SÃO OS FILHOS DA PRIMEIRA COLUNA, com altura — sem isso o relato
  // diz "estourou 299px" e ninguém sabe qual bloco dobrar. `--dentro` liga.
  var dentro = [];
  if (window.__hef_dentro && j) {
    var alvo = j.querySelector('.ctrl') || j.querySelector('.miolo');
    if (alvo) {
      for (var k = 0; k < alvo.children.length; k++) {
        var f = alvo.children[k];
        dentro.push((String(f.className) || f.tagName).slice(0, 22) + ':' +
                    Math.round(f.getBoundingClientRect().height));
      }
    }
  }
  return JSON.stringify({
    url: (location.pathname.split('/').pop() || ''),
    dentro: dentro,
    janela_alt: j ? j.scrollHeight : 0,
    janela_caixa: j ? j.clientHeight : 0,
    doc_alt: d.scrollHeight,
    doc_caixa: d.clientHeight,
    vista: window.innerHeight,
    culpado: culpado
  });
})()"""


def main() -> int:
    pedidas = [a for a in sys.argv[1:] if not a.startswith("-")]
    alvos = ([a for a in ABAS if any(a.startswith(p) for p in pedidas)]
             if pedidas else list(ABAS))
    if not alvos:
        print(f"REPROVA: nenhuma aba casa com {pedidas}. As dez estão em `ABAS`.")
        return 1

    args = argparse.Namespace(**BANDEIRAS, abre=alvos[0])
    piloto = hefesto_vivo.Piloto(args)
    lidas: list[dict] = []
    fila = list(alvos)

    def proxima() -> bool:
        if not piloto.pronto:
            return True
        if not fila:
            Gtk.main_quit()
            return False
        piloto._ir(fila[0])
        #: ESPERA O TIQUE PINTAR, e não só a página carregar: o que faz a
        #: caixa crescer é o DADO, e ele chega no tique seguinte ao carregar.
        #: Medir antes disso responde sobre o desenho, que é justamente o que
        #: o Chrome já respondeu.
        GLib.timeout_add(2600, medir)
        return False

    def medir() -> bool:
        if "--dentro" in sys.argv:
            alvo = next((x.split("=", 1)[1] for x in sys.argv
                         if x.startswith("--alvo=")), ".ctrl")
            piloto.ponte.perguntar(
                f'window.__hef_dentro = 1; window.__hef_alvo = "{alvo}";',
                lambda *_: None)
        def respondeu(texto: str | None, erro: Exception | None) -> None:
            if erro or not texto:
                print(f"[dom] a ponte não respondeu em {fila[0]}: {erro}")
                lidas.append({"url": fila[0], "erro": str(erro)})
            else:
                lidas.append(json.loads(texto))
            fila.pop(0)
            GLib.timeout_add(200, proxima)

        piloto.ponte.perguntar(LER, respondeu)
        return False

    GLib.timeout_add(900, proxima)
    GLib.timeout_add(15000 + 4000 * len(alvos), Gtk.main_quit)
    Gtk.main()

    if not lidas:
        print("REPROVA: não li o DOM — a janela não respondeu.")
        return 1

    print(f"{'aba':18} {'janela':>14} {'documento':>14}  quem estourou")
    print("-" * 92)
    culpados = []
    for d in lidas:
        if d.get("erro"):
            print(f"{d['url']:18} (sem resposta: {d['erro']})")
            continue
        ja, jc = d["janela_alt"], d["janela_caixa"]
        da, dc = d["doc_alt"], d["doc_caixa"]
        rola_j = ja > jc + 2
        rola_d = da > dc + 2
        marca = "ROLA" if (rola_j or rola_d) else "ok"
        print(f"{d['url']:18} {ja:6}/{jc:<7} {da:6}/{dc:<7}  "
              f"{marca:5} {d.get('culpado') or ''}")
        if d.get("dentro"):
            print(f"{'':18}   dentro: {' '.join(d['dentro'])}")
        if rola_j:
            culpados.append(
                f"{d['url']}: a `.janela` tem {ja}px de conteúdo numa caixa de "
                f"{jc}px — {ja - jc}px de sobra. {d.get('culpado') or ''}")
        elif d.get("culpado"):
            #: **O CULPADO SOZINHO JÁ REPROVA — e a primeira volta desta régua
            #: não sabia disso.** Ela olhava só a `.janela` e o documento, e os
            #: dois FECHAM: `775/775` e `809/809` nas dez. Deu **PASSA** com a
            #: barra na tela dela.
            #:
            #: A `.janela` é `overflow:hidden` — ela nunca rola, por desenho.
            #: Quem rola é o filho: medido em 09/09/2026, com quatro controles
            #: vivos, `DIV.miolo` da `03-gatilhos` tem **863px de conteúdo numa
            #: caixa de 564** (299 de sobra) e o da `07-lancadores`, 627 em 564
            #: — **as duas abas que ela nomeou**.
            #:
            #: *Uma régua que mede o continente dá verde sobre o conteúdo que
            #: transborda dentro dele.*
            culpados.append(
                f"{d['url']}: {d['culpado']} — a caixa não cabe no que ela vê, "
                f"e é aí que a barra nasce")
        elif rola_d:
            culpados.append(
                f"{d['url']}: o DOCUMENTO tem {da}px numa vista de {dc}px "
                f"({da - dc}px). A `.janela` cabe — o que sobra está FORA dela.")

    print()
    if culpados:
        print(f"REPROVA: {len(culpados)} aba(s) com barra de rolagem:")
        for c in culpados:
            print(f"  {c}")
        return 1
    print(f"PASSA: as {len(lidas)} abas cabem na janela, com o dado vivo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
