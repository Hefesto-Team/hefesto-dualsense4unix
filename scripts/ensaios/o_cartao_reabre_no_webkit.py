#!/usr/bin/env python3
"""Fecha o cartão do P2 no DOM VIVO, manda o controle de volta, e mede a altura.

POR QUE ELE EXISTE, e é a regra desta casa: o teste de unidade
``test_o_cartao_do_controle_que_chega_reabre`` roda o passo `1b`/`1c` do piloto
no ``node``, contra um DOM de mentira. Isso prova a CONTA. O que prova o
PRODUTO é o mesmo passo dentro do ``WebKit2.WebView`` que ela usa, com a folha
de estilo real aplicando o `off` — porque o que ela via não era um atributo, era
um cartão de 24 px.

O ensaio faz o caminho dela, em três tempos:

1. lê a altura do cartão do P2 como está;
2. manda ``window.__hef.pintar({vazios:['p2']})`` — o controle SAIU;
3. manda ``window.__hef.pintar({ocupados:['p2']})`` — o controle VOLTOU.

Reprova se o terceiro tempo não devolver a altura do primeiro.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/o_cartao_reabre_no_webkit.py
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.interface import hefesto_vivo

#: A ABA ESCOLHIDA é a Controles: é a que tem os quatro cartões grandes, e é
#: onde a frente 1 mediu os 64% de bateria num assento vazio.
ABA = "02-controles.html"
LUGAR = "p2"

#: OS TRÊS TEMPOS, num JS só — para que nada aconteça ENTRE eles. Cada um
#: devolve a altura do cartão e o que a folha está vestindo.
ROTEIRO = r"""
(function(){
  const sel = '[data-controle="__LUGAR__"]';
  function medir(){
    const el = document.querySelector(sel);
    if(!el){ return null; }
    const r = el.getBoundingClientRect();
    return {altura: Math.round(r.height), largura: Math.round(r.width),
            conectado: el.dataset.conectado || null,
            off: el.classList.contains('off')};
  }
  // A ORDEM COMEÇA ABRINDO, e isso foi medido: com um controle só na mesa o
  // cartão do P2 já nasce fechado, e um ensaio que começasse medindo "antes"
  // compararia dois estados fechados e daria verde sem provar nada.
  window.__hef.pintar({ocupados: ['__LUGAR__'], colunas: {}});
  const aberto = medir();
  window.__hef.pintar({vazios: ['__LUGAR__'], colunas: {}});
  const fechado = medir();
  window.__hef.pintar({ocupados: ['__LUGAR__'], colunas: {}});
  const reaberto = medir();
  // E DEVOLVE A MESA COMO ESTAVA: o piloto repinta do daemon no tique
  // seguinte, mas deixar a tela mentindo entre um e outro não é jeito de medir.
  window.__hef.pintar({vazios: ['__LUGAR__'], colunas: {}});
  return JSON.stringify({aberto: aberto, fechado: fechado, reaberto: reaberto});
})()
""".replace("__LUGAR__", LUGAR)

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def main() -> int:
    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    saida: dict[str, object] = {"medidas": None}

    def perguntar() -> bool:
        if not piloto.pronto:
            return True

        def respondeu(texto: str | None, erro: Exception | None) -> None:
            saida["medidas"] = json.loads(texto) if texto and not erro else None
            saida["erro"] = str(erro) if erro else ""
            Gtk.main_quit()

        piloto.ponte.perguntar(ROTEIRO, respondeu)
        return False

    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(3000, perguntar)
    GLib.timeout_add(30000, Gtk.main_quit)
    Gtk.main()

    m = saida.get("medidas")
    if not m:
        print(f"REPROVA: não li o cartão do {LUGAR.upper()} no DOM vivo. "
              f"{saida.get('erro', '')}")
        return 1

    for tempo in ("aberto", "fechado", "reaberto"):
        d = m[tempo]
        if not d:
            print(f"REPROVA: o cartão sumiu no tempo `{tempo}`.")
            return 1
        print(f"  {tempo:7s} altura {d['altura']:4d} px · largura {d['largura']:4d} px"
              f" · data-conectado={d['conectado']!r:8s} · off={d['off']}")

    # A GUARDA DE VACUIDADE: se fechar não encolhe, os três números são iguais
    # e a comparação de baixo passa sem medir nada.
    if m["fechado"]["altura"] >= m["aberto"]["altura"]:
        print("\nATENÇÃO: fechar o cartão não mudou a altura — ou a folha desta "
              "aba não encolhe o `off`, ou o passo `1b` do piloto não pegou. O "
              "ensaio não prova nada assim.")
        return 1

    if m["reaberto"] != m["aberto"]:
        print(f"\nREPROVA: o cartão do {LUGAR.upper()} não voltou ao que era — "
              f"{m['aberto']} contra {m['reaberto']}. O dado dela chega "
              "invisível, e só recarregar a página desfaz.")
        return 1

    print(f"\nOK: o cartão fecha ({m['aberto']['altura']} -> "
          f"{m['fechado']['altura']} px) e REABRE inteiro "
          f"({m['reaberto']['altura']} px, `off` de volta a False).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
