#!/usr/bin/env python3
"""As quatro linhas da tabela «Ajuste próprio» cabem — inclusive com a tira acesa."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba
from hefesto_dualsense4unix.interface import onde

ABA = "10-perfis.html"  # (noqa-acento) nome de arquivo
TITULO = "Hefesto — aba PERFIS"

ESPALHAMENTO_TOLERADO = 2.0

ROTEIRO = r"""
(function () {
  function comoOProdutoPinta() {
    var linhas = document.querySelectorAll('.guarda tbody tr');
    for (var i = 0; i < linhas.length; i++) {
      var id = linhas[i].querySelector('.gd-id');
      if (i >= 2) {
        linhas[i].className = 'fora';
        if (id) { id.textContent = '—'; }
      } else if (id) {
        id.textContent = i === 0 ? 'AA:BB:CC:00:00:01' : 'AA:BB:CC:00:00:02';
      }
    }
  }

  // A CAIXA DO TEXTO DE VERDADE, e não a do elemento: um `<td>` estica com a
  // linha, e comparar caixas de `<td>` diria que tudo alinha mesmo quando o
  // glifo não alinha. `Range` devolve onde o desenho POUSA.
  function caixaDoTexto(el) {
    if (!el) { return null; }
    var r = document.createRange();
    r.selectNodeContents(el);
    var c = r.getBoundingClientRect();
    if (!c.height && !c.width) { c = el.getBoundingClientRect(); }
    return c;
  }

  function medir() {
    var g = document.querySelector('.guarda');
    var t = g ? g.querySelector('table') : null;
    var linhas = g ? g.querySelectorAll('tbody tr') : [];
    var espalhamentos = [];
    for (var i = 0; i < linhas.length; i++) {
      var rl = linhas[i].getBoundingClientRect();
      var alvos = [
        caixaDoTexto(linhas[i].querySelector('.gd-nome span:last-child')),
        caixaDoTexto(linhas[i].querySelector('.gd-pecas .gls')),
        caixaDoTexto(linhas[i].querySelector('.gd-id'))
      ];
      var c = [];
      for (var k = 0; k < alvos.length; k++) {
        if (alvos[k]) {
          c.push(alvos[k].top + alvos[k].height / 2 - rl.top);
        }
      }
      espalhamentos.push(c.length
        ? Math.round((Math.max.apply(null, c) - Math.min.apply(null, c)) * 100) / 100
        : null);
    }
    // `quarta` É O NOME, e é mais exato que o ordinal genérico: o desenho tem
    // QUATRO lugares, sempre. O ordinal em português levaria acento e um
    // identificador de JavaScript não leva — o portão de acentuação reprova a
    // forma sem ele, e ESTE comentário seria a primeira ocorrência do defeito
    // que descreve. A armadilha é conhecida nesta casa; ela mordeu de novo aqui.
    var quarta = linhas.length ? linhas[linhas.length - 1] : null;
    var visivel = null;
    var rg = g ? g.getBoundingClientRect() : null;
    if (quarta && rg) {
      var ru = quarta.getBoundingClientRect();
      visivel = Math.round(
        (Math.min(rg.bottom, ru.bottom) - Math.max(rg.top, ru.top)) * 100) / 100;
    }
    var pedida = null;
    if (t) {
      var antes = t.style.height;
      t.style.height = 'auto';
      void t.offsetHeight;
      pedida = Math.ceil(t.getBoundingClientRect().height);
      t.style.height = antes;
      void t.offsetHeight;
    }
    return {
      disponivel: g ? g.clientHeight : null,
      pedida: pedida,
      sobra: (g && pedida !== null) ? g.clientHeight - pedida : null,
      rola: g ? (g.scrollHeight - g.clientHeight) : null,
      linhas: linhas.length,
      altura_da_linha: linhas.length
        ? Math.round(linhas[0].getBoundingClientRect().height * 100) / 100 : null,
      quarta_linha_visivel: visivel,
      espalhamento_por_linha: espalhamentos
    };
  }

  function tira(liga) {
    var d = document.querySelector('.desfecho');
    if (!d) { return false; }
    if (liga) {
      d.className = 'desfecho on';
      var s = d.querySelector('span') || d;
      s.textContent = 'Perfil salvo: Mortal Kombat';
    } else {
      d.className = 'desfecho';
    }
    void document.body.offsetHeight;
    return true;
  }

  comoOProdutoPinta();
  var achou_a_tira = tira(false);
  var sem = medir();
  tira(true);
  var com = medir();
  tira(false);

  return JSON.stringify({
    janela: {largura: window.innerWidth, altura: window.innerHeight},
    achou_a_tira: achou_a_tira,
    tem_quadro_de_modo: !!document.querySelector('.campo.modo'),
    sem_a_tira: sem,
    com_a_tira: com
  });
})()
"""


def medir(pagina: pathlib.Path) -> dict:
    """Abre a página no WebKit OCULTO e devolve o que o roteiro mediu."""
    saida: dict = {}

    def carregou() -> None:
        def veio(valor, erro):
            if erro is not None:
                saida["erro"] = str(erro)
            else:
                try:
                    saida.update(json.loads(valor))
                except Exception as e:
                    saida["erro"] = f"{e}: {valor!r}"
            Gtk.main_quit()

        GLib.timeout_add(400, lambda: (janela.ponte.perguntar(ROTEIRO, veio), False)[1])

    janela = JanelaDaAba(arquivo=pagina, titulo_esperado=TITULO,
                         ao_carregar=carregou, oculta=True)
    GLib.timeout_add_seconds(30, Gtk.main_quit)
    Gtk.main()
    return saida


def _queixas(medida: dict) -> list[str]:
    """O que reprova, com o número ao lado. Lista vazia é o verde."""
    fora: list[str] = []
    if "erro" in medida:
        return [f"a página não respondeu: {medida['erro']}"]
    if not medida.get("achou_a_tira"):
        fora.append(
            "a tira do desfecho (`.desfecho`) não está na página — sem ela este "
            "ensaio mediria os dois estados IGUAIS e daria verde por vacuidade")
    if medida.get("tem_quadro_de_modo"):
        fora.append(
            "o quadro «Modo» voltou ao editor — ele saiu por ordem dela em "
            "11/09/2026, e era a fileira dele (36px) que tirava a linha do P4 "
            "do quadro sempre que a tira acendia")
    for nome, estado in (("sem a tira", medida.get("sem_a_tira") or {}),
                         ("com a tira acesa", medida.get("com_a_tira") or {})):
        if estado.get("linhas") != 4:
            fora.append(f"{nome}: a tabela tem {estado.get('linhas')} linhas, "
                        f"e o desenho tem quatro lugares")
            continue
        sobra = estado.get("sobra")
        if sobra is None or sobra < 0:
            fora.append(
                f"{nome}: o quadro tem {estado.get('disponivel')}px e as quatro "
                f"linhas pedem {estado.get('pedida')}px — faltam {-(sobra or 0)}px")
        if estado.get("rola"):
            fora.append(
                f"{nome}: a tabela rola {estado['rola']}px dentro do quadro, e a "
                f"última linha aparece {estado.get('quarta_linha_visivel')}px")
        maior = max((e for e in (estado.get("espalhamento_por_linha") or [])
                     if e is not None), default=0.0)
        if maior > ESPALHAMENTO_TOLERADO:
            fora.append(
                f"{nome}: as três colunas de uma linha desalinham {maior}px "
                f"(o teto é {ESPALHAMENTO_TOLERADO}) — é a linha «quebrada» que "
                f"ela fotografou")
    return fora


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--publicado", action="store_true",
                   help="mede a página que o produto renderiza, e não a bancada")
    p.add_argument("--json", action="store_true", help="a medida crua")
    args = p.parse_args()

    pagina = onde.pagina(ABA, publicado=args.publicado)
    if not pagina.exists():
        print(f"ERRO: {pagina} não existe", file=sys.stderr)
        return 2

    medida = medir(pagina)
    if args.json:
        print(json.dumps(medida, ensure_ascii=False, indent=2))

    onde_esta = "publicada" if args.publicado else "bancada"
    for nome, estado in (("sem a tira ", medida.get("sem_a_tira") or {}),
                         ("com a tira ", medida.get("com_a_tira") or {})):
        print(f"{onde_esta} · {nome}: quadro {estado.get('disponivel')}px · "
              f"quatro linhas pedem {estado.get('pedida')}px · "
              f"sobra {estado.get('sobra')} · rola {estado.get('rola')} · "
              f"linha {estado.get('altura_da_linha')}px · "
              f"desalinho {estado.get('espalhamento_por_linha')}")

    queixas = _queixas(medida)
    if queixas:
        print("\nREPROVA:", file=sys.stderr)
        for q in queixas:
            print(f"  - {q}", file=sys.stderr)
        return 1
    print("\nOK: as quatro linhas cabem nos dois estados, e as três colunas "
          "alinham.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
