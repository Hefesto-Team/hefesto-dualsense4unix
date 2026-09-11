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
* e QUEM estourou — o primeiro elemento cujo conteúdo passa da caixa;
* **e quanta tela sobra ABAIXO da `.janela`** — ver `--vista`, logo abaixo.

REPROVA nomeando a aba e os dois números em pixel.

    scripts/ensaios/a_janela_cabe_no_que_ela_ve.py             # as dez
    scripts/ensaios/a_janela_cabe_no_que_ela_ve.py 03 07       # só duas
    scripts/ensaios/a_janela_cabe_no_que_ela_ve.py --vista=840 # a TV dela

A VISTA DELA NÃO É A VISTA PADRÃO — 10/09/2026, ALTURA-DA-VISTA-01
-------------------------------------------------------------------

Esta régua rodava numa vista só: a do `ponte_da_tela.TAMANHO_OCULTA`, que é o
PISO (`1212x809`). **Enquanto a altura da `.janela` era um pixel fixo isso não
importava** — 809 e 840 devolviam os mesmos números, porque a `.janela` não
olhava para a vista.

Com a altura fluida é a diferença inteira, e medido: na vista de 840 px da TV
dela a `.janela` vai a 808 e o `.miolo` a 666; no piso, a 777 e 634. *Uma régua
presa ao piso responderia sobre outra JANELA que não a dela* — a assinatura dos
seis instrumentos falsos de 05/09, um nível acima.

Por isso `--vista=N` existe e o padrão deixou de ser o único caso. As duas
pontas que esta sprint mede:

    --vista=809   o PISO: nenhuma aba pode ficar pior do que já era
    --vista=840   a TELA DELA: é onde a barra que ela reclamou nasce ou morre

E A TELA QUE SOBRA EMBAIXO DA `.janela` PASSOU A CONTAR. Nenhuma régua desta
casa olhava para lá: todas mediam DENTRO da `.janela`, e a `.janela` parava
antes do fim da tela. Na vista dela sobravam **47 px** — 16 de recuo do `body`
e **31 mortos**, a faixa escura entre o rodapé e a moldura da janela, que é o
*"tem espaço vertical pra aproveitar aqui"* da queixa dela. A conta é uma
linha, e agora ela tem dono:

    window.innerHeight - document.querySelector('.janela').getBoundingClientRect().bottom

Com `--vista`, o que sobra tem de ser exatamente o recuo do `body`; qualquer
pixel a mais é tela que a página recusou, e REPROVA — **exceto quando a
`.janela` parou no teto que ela promete parar** (`--teto-da-vista`). Aí a sobra
é decisão, não desperdício, e sai no relato como `TETO`. A primeira volta desta
régua não sabia disso e reprovou as dez numa vista 4K; a razão está na nota do
`no_teto`, no corpo.
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

#: A LARGURA EM QUE SE MEDE COM `--vista`, e ela é a da janela MAXIMIZADA dela.
#:
#: A TV dela tem 1920 px a 100% (`cosmic-randr`), e a janela maximizada deixa
#: 1918 de vista depois das duas bordas. Medir a altura numa largura estreita
#: mentiria por cima: coluna estreita é coluna ALTA, e o `.miolo` pediria mais
#: do que pede na tela dela. O teto de 1600 da `.janela` cuida do resto — acima
#: dele o desenho para de esticar, por decisão dela de 08/09.
LARGURA_MAXIMIZADA = 1918

#: AS CAIXAS QUE ROLAM POR DESENHO, com a razão de cada uma — o molde do
#: `_NAO_E_PROMESSA` do `casa-sabe`: *a lista se lê, a razão se escreve*.
#:
#: Nem toda barra é defeito. A `10-perfis` tem uma lista que rola desde que
#: nasceu, e a §1 da ROLAGEM-01 já a mediu assim em 08/09 (*"Só a 10 (`div.rolo`,
#: 475/383 px), por desenho"*). Reprová-la seria a régua chamando de dívida o
#: desenho que ela aprovou; deixá-la fora do relato seria a régua ficando cega.
#: Ela fica DECLARADA: sai na tabela, não conta no vermelho, e uma caixa nova
#: que role sem estar aqui reprova.
POR_DESENHO: dict[str, tuple[str, str]] = {
    "10-perfis.html": ("DIV.rolo", "a lista de perfis rola por desenho — quantos "
                                   "perfis ela tem é dela, e a caixa não pode "
                                   "crescer com eles (§1 da ROLAGEM-01, 08/09)"),
    #: AS DUAS DE 09/09, e as duas pela MESMA frase da linha de cima — o que
    #: entra na caixa é dela ou do daemon, e a caixa não pode crescer com isso.
    "07-lancadores.html": ("DIV.lancadores",
                           "a grade de cartões rola por desenho — quantos "
                           "lançadores ela tem, e quantos jogos com pendência, é "
                           "dela: medido, a grade foi de 493 a 534px sozinha "
                           "numa sessão, quando o cartão da Steam ganhou um jogo "
                           "pendente (ROLAGEM-01 §8, 09/09)"),
    "09-sistema.html": ("DIV.log",
                        "o registro técnico rola por desenho — quantas linhas o "
                        "daemon escreveu não é assunto da aba, e o "
                        "`data-hef-rolar=\"fim\"` do HTML já dizia isso desde que "
                        "nasceu (ROLAGEM-01 §8, 09/09)"),
}

#: A PERGUNTA AO DOM. Ela mede a `.janela` e o documento, e nomeia o primeiro
#: estouro — sem o culpado, o relato diz "rolou" e ninguém sabe onde mexer.
#:
#: O `+2` DE FOLGA não é frouxidão: o WebKit arredonda alturas de linha, e um
#: pixel de diferença aparece em página que não rola. Dois pixels não fazem
#: barra aparecer; medido em 09/09/2026 nas dez.
LER = """(function(){
  var j = document.querySelector('.janela');
  var d = document.documentElement;
  var culpado = null, cortado = null;
  if (j) {
    var todos = j.querySelectorAll('*');
    for (var i = 0; i < todos.length; i++) {
      var e = todos[i];
      if (e.scrollHeight <= e.clientHeight + 2) continue;
      var ov = getComputedStyle(e).overflowY;
      if (ov === 'visible') continue;
      var ficha = e.tagName + '.' + String(e.className).slice(0, 30) +
                  ' ' + e.scrollHeight + '>' + e.clientHeight;
      // SÓ `auto` E `scroll` DESENHAM BARRA. `hidden` CORTA, em silêncio — e
      // as duas coisas pedem conserto diferente, então o relato as separa.
      if (ov === 'auto' || ov === 'scroll') { culpado = ficha; break; }
      if (!cortado) cortado = ficha;
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
    cortado: cortado,
    janela_alt: j ? j.scrollHeight : 0,
    janela_caixa: j ? j.clientHeight : 0,
    doc_alt: d.scrollHeight,
    doc_caixa: d.clientHeight,
    vista: window.innerHeight,
    // O QUE SOBRA EMBAIXO DA `.janela`, em pixel. Tem de ser o recuo do
    // `body` e nada mais; o que passar disso é tela que a página recusou.
    sobra: j ? Math.round(window.innerHeight -
                          j.getBoundingClientRect().bottom) : -1,
    // O RECUO DO `body` NÃO SE DIGITA AQUI: quem o conhece é o CSS
    // (`--recuo-do-corpo`), e perguntar a ele é o que impede esta régua de
    // ficar velha no dia em que o recuo mudar.
    recuo: (function(){
      var v = getComputedStyle(document.documentElement)
                .getPropertyValue('--recuo-do-corpo').trim();
      var n = parseInt(v, 10);
      return isNaN(n) ? -1 : n; })(),
    // O TETO DA `.janela`, e ele é o que separa tela MORTA de vão DECIDIDO.
    teto: (function(){
      var v = getComputedStyle(document.documentElement)
                .getPropertyValue('--teto-da-vista').trim();
      var n = parseInt(v, 10);
      return isNaN(n) ? -1 : n; })(),
    culpado: culpado
  });
})()"""


def _e_por_desenho(aba: str, culpado: str) -> bool:
    """A caixa declarada em `POR_DESENHO` rola porque alguém quis."""
    declarada = POR_DESENHO.get(aba)
    return bool(declarada and culpado.startswith(declarada[0]))


def _vista_pedida(argv: list[str]) -> int:
    """A altura da vista em que medir, ou 0 para o padrão do piloto.

    O PADRÃO É O PISO (`ponte_da_tela.TAMANHO_OCULTA`, 809 px de vista). Ele
    continua sendo o caso que diz *"nenhuma aba ficou pior do que era"*; o que
    ele NÃO diz é o que acontece na tela dela, e é por isso que ele deixou de
    ser o único.
    """
    for arg in argv:
        if arg.startswith("--vista="):
            bruto = arg.split("=", 1)[1]
            if not bruto.isdigit() or int(bruto) < 200:
                raise SystemExit(
                    f"ERRO: `--vista={bruto}` não é uma altura de tela. "
                    "Ela é um inteiro de pixels, e a da TV dela é 840.")
            return int(bruto)
    return 0


def main() -> int:
    pedidas = [a for a in sys.argv[1:] if not a.startswith("-")]
    alvos = ([a for a in ABAS if any(a.startswith(p) for p in pedidas)]
             if pedidas else list(ABAS))
    if not alvos:
        print(f"REPROVA: nenhuma aba casa com {pedidas}. As dez estão em `ABAS`.")
        return 1
    vista = _vista_pedida(sys.argv[1:])

    args = argparse.Namespace(**BANDEIRAS, abre=alvos[0])
    piloto = hefesto_vivo.Piloto(args)
    lidas: list[dict] = []
    fila = list(alvos)

    def esticar() -> None:
        """Põe a vista na altura pedida, e a largura da janela maximizada dela.

        É O `view` QUE RECEBE O PEDIDO, e não a janela. Medido em 10/09/2026:
        `Gtk.OffscreenWindow.resize()` depois do `show_all()` não move um pixel
        — a janela oculta se dimensiona pelo que o filho PEDE. Um `resize()`
        aqui devolveria teimosamente os 809 do padrão, e a régua diria ter
        medido a tela dela sem nunca ter saído do piso.
        """
        if vista:
            piloto.tela.view.set_size_request(LARGURA_MAXIMIZADA, vista)

    esticar()

    def proxima() -> bool:
        if not piloto.pronto:
            return True
        if not fila:
            Gtk.main_quit()
            return False
        esticar()
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

    print(f"{'aba':18} {'janela':>14} {'documento':>14} {'vista':>13}  quem estourou")
    print("-" * 106)
    culpados, cortes, mortos, tetos = [], [], [], []


    for d in lidas:
        if d.get("erro"):
            print(f"{d['url']:18} (sem resposta: {d['erro']})")
            continue
        ja, jc = d["janela_alt"], d["janela_caixa"]
        da, dc = d["doc_alt"], d["doc_caixa"]
        rola_d = da > dc + 2
        #: O RAMO `rola_j` MORREU AQUI — 10/09/2026, §4.2 da ALTURA-DA-VISTA-01,
        #: e ele sai NOMEADO em vez de sumir calado.
        #:
        #: Ele comparava a `.janela` com a própria caixa (`ja > jc + 2`). Com a
        #: altura em pixel isso ainda podia acontecer; com a altura seguindo a
        #: vista, **uma `.janela` que segue a vista jamais transborda de si
        #: mesma** — o ramo passaria a dar verde sobre nada, que é exatamente o
        #: que ele já fez uma vez: em 09/09 ele dava PASSA (`775/775` nas dez)
        #: com a barra de rolagem na tela dela.
        #:
        #: Quem reprova continua sendo o ramo do CULPADO — o `.miolo` —, que
        #: nasceu por causa daquele verde falso. Os dois números da `.janela`
        #: continuam SAINDO no relato: eles dizem se a altura pegou.
        sobra, recuo = d.get("sobra", -1), d.get("recuo", -1)
        teto = d.get("teto", -1)
        #: A TELA QUE A PÁGINA RECUSA. Tem de ser o recuo do `body` e nada mais.
        #: O `+2` é a mesma folga de arredondamento do WebKit usada acima.
        sobrou = sobra >= 0 and recuo >= 0 and sobra > recuo + 2
        #: O TETO NÃO É TELA MORTA, E ESTA LINHA NASCEU DE UM VERMELHO FALSO.
        #:
        #: Medido em 10/09/2026, na primeira volta desta régua: numa vista de
        #: 2160 px — a TV dela tem o modo 3840x2160 — ela reprovou as DEZ com
        #: *"1289px de tela que a página não usou"*. E estava errada: a
        #: `.janela` tinha parado no teto que ela PROMETE parar
        #: (`--teto-da-vista`), porque vão vazio é queixa dela e o teto existe
        #: para capá-lo. *Uma régua que reprova o desenho aprovado ensina
        #: errado* — é a mesma lição do corte, doze linhas abaixo.
        #:
        #: O TETO SE PERGUNTA AO CSS, nunca se digita aqui: quem o conhece é o
        #: `:root` do `topo.html`, e uma segunda cópia dele aqui seria a régua
        #: medindo o mundo de ontem no dia em que ele mudasse.
        no_teto = teto > 0 and jc >= teto - 2
        morre = sobrou and not no_teto
        marca = ("ROLA" if rola_d else "MORRE" if morre
                 else "teto" if sobrou else "ok")
        print(f"{d['url']:18} {ja:6}/{jc:<7} {da:6}/{dc:<7} "
              f"{d.get('vista', 0):6}-{sobra:<6} "
              f"{marca:5} {d.get('culpado') or ''}"
              f"{('  (corta: ' + d['cortado'] + ')') if d.get('cortado') and not d.get('culpado') else ''}")
        if d.get("dentro"):
            print(f"{'':18}   dentro: {' '.join(d['dentro'])}")
        if morre:
            mortos.append(
                f"{d['url']}: sobram {sobra}px embaixo da `.janela` numa vista "
                f"de {d.get('vista', 0)}px, e o recuo do `body` é {recuo} — "
                f"{sobra - recuo}px de tela que a página não usou")
        elif sobrou:
            tetos.append(
                f"{d['url']}: a `.janela` parou no teto de {teto}px e sobram "
                f"{sobra - recuo}px de tela. É o teto fazendo o serviço dele — "
                f"acima dele o que sobra viraria vão dentro do quadro")
        if d.get("culpado") and not _e_por_desenho(d["url"], d["culpado"]):
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
        if d.get("cortado") and not d.get("culpado"):
            cortes.append(f"{d['url']}: {d['cortado']}")

    #: O CORTE NÃO É BARRA, E POR ISSO NÃO REPROVA — 09/09/2026, ROLAGEM-01.
    #: `overflow:hidden` esconde em silêncio: nenhuma barra nasce dali. A régua
    #: reprovava os dois juntos e ficava VERMELHA em quatro abas por causa de
    #: caixa **fechada de propósito** — o corpo do acordeão da `02-controles`
    #: (`DIV.corpo-cx 267>0`), o da `03-gatilhos` que esta sprint criou
    #: (`DIV.rot-l2-3 16>0`) e o `DIV.desfecho 15>0` da `10-perfis`. Régua que
    #: reprova sempre não ensina nada, e a que reprova o desenho aprovado ensina
    #: errado. O corte fica no relato porque ele PODE ser dívida — a
    #: `DIV.moldura 153>144` da `04` esconde 9px de desenho —, mas quem decide
    #: o vermelho é a barra.
    print()
    #: O TETO SAI NO RELATO E NÃO NO VERMELHO — ver a nota do `no_teto`, acima.
    #: Ele fica VISÍVEL porque é o número que diz quanto de tela o desenho está
    #: deixando de lado por decisão; calá-lo faria a próxima pessoa remedir.
    if tetos:
        print(f"TETO (não é tela morta, é o limite decidido): {len(tetos)}")
        for t_ in tetos:
            print(f"  {t_}")
        print()
    if cortes:
        print(f"CORTE (não é barra, `overflow:hidden` esconde calado): "
              f"{len(cortes)}")
        for c in cortes:
            print(f"  {c}")
        print()
    if culpados:
        print(f"REPROVA: {len(culpados)} aba(s) com barra de rolagem:")
        for c in culpados:
            print(f"  {c}")
        return 1
    #: A TELA QUE MORRE REPROVA DEPOIS DA BARRA, e a ordem é escolha: a barra
    #: corta o que ela quer ler, e a faixa morta só desperdiça. Quando as duas
    #: aparecem juntas, a que se conserta primeiro é a barra.
    if mortos:
        print(f"REPROVA: {len(mortos)} aba(s) deixam tela morta embaixo da "
              f"`.janela`:")
        for m in mortos:
            print(f"  {m}")
        return 1
    print(f"PASSA: as {len(lidas)} abas cabem na janela e usam a vista "
          f"inteira, com o dado vivo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
