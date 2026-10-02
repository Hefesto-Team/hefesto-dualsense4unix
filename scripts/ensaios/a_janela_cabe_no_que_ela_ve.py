#!/usr/bin/env python3
"""ROLAGEM-01 — a barra vertical, medida no WebKit VIVO e não no Chrome."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src/hefesto_dualsense4unix/interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

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

LARGURA_MAXIMIZADA = 1918

POR_DESENHO: dict[str, tuple[str, str]] = {
    "10-perfis.html": ("DIV.rolo", "a lista de perfis rola por desenho — quantos "
                                   "perfis ela tem é dela, e a caixa não pode "
                                   "crescer com eles (§1 da ROLAGEM-01, 08/09)"),
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
    """A altura da vista em que medir, ou 0 para o padrão do piloto."""
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
        """Põe a vista na altura pedida, e a largura da janela maximizada dela."""
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
        sobra, recuo = d.get("sobra", -1), d.get("recuo", -1)
        teto = d.get("teto", -1)
        sobrou = sobra >= 0 and recuo >= 0 and sobra > recuo + 2
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
            culpados.append(
                f"{d['url']}: {d['culpado']} — a caixa não cabe no que ela vê, "
                f"e é aí que a barra nasce")
        elif rola_d:
            culpados.append(
                f"{d['url']}: o DOCUMENTO tem {da}px numa vista de {dc}px "
                f"({da - dc}px). A `.janela` cabe — o que sobra está FORA dela.")
        if d.get("cortado") and not d.get("culpado"):
            cortes.append(f"{d['url']}: {d['cortado']}")

    print()
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
