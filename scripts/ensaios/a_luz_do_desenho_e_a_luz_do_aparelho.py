#!/usr/bin/env python3
"""O DESENHO GRANDE da aba Iluminação acende a luz do APARELHO, ou a do mockup?

POR QUE ELE EXISTE. A régua de tela conta campos escritos e a do mockup compara
o publicado com o desenho aprovado; **nenhuma das duas olha para dentro de um
SVG**. A lightbar do desenho grande e as cinco lâmpadas do indicador nunca
foram campo: o gerador CRAVA ``style="--luz:#7EB8D4"`` no ``<g>`` e a classe
``led-on`` nos ``<rect>`` que o MOCKUP escolheu, e nada no produto os alcança.

O que isso custa está fotografado em 03/09/2026, na mesa dela, com UM controle
no cabo: a coluna do P1 dizia ``#0000FF`` na caixa do hexadecimal e desenhava a
barra em ``#7EB8D4`` — a mesma célula afirmando duas cores. Quem olha a tela lê
o desenho antes de ler o número.

O QUE ELE MEDE, e ele PERGUNTA em vez de digitar:

    a luz do APARELHO   ``a04_iluminacao.pacote()`` → o ``hex`` daquela coluna,
                        que sai de ``controller_card.cor_do_swatch`` desescalado
                        por ``cor_escolhida``. É o dono do dado.
    a luz do DESENHO    ``getComputedStyle`` do ``.peca`` dentro do
                        ``[id$="-lightbar"]`` daquela coluna, no DOM VIVO.
    as lâmpadas         quais dos cinco ``[id*="-led-jogador-"]`` estão acesos,
                        pela cor computada — contra ``player_led_pattern`` do
                        número VIVO, que é a tabela que o daemon acende.

Nada aqui compara o produto com ele mesmo: os dois lados vêm de donos
diferentes, e é isso que faz a divergência aparecer em vez de se cancelar.

REPROVA quando a coluna tem controle e as duas luzes discordam. Uma coluna sem
controle não é medida — não há luz a afirmar, e é a regra dela.

Uso (a janela é OCULTA; ela tem UMA tela)::

    scripts/ensaios/a_luz_do_desenho_e_a_luz_do_aparelho.py
"""
from __future__ import annotations

import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk  # noqa: E402

from hefesto_dualsense4unix.interface import hefesto_vivo  # noqa: E402

ABA = "04-iluminacao.html"

#: O QUE SE LÊ NO DOM, e por que é a cor COMPUTADA e não o atributo: a luz pode
#: chegar por três caminhos — o `style` cravado no `<g>`, uma regra da folha viva
#: e o `fill` de apresentação do próprio `<path>`. Ler qualquer um deles isolado
#: mediria um caminho e chamaria de resultado; `getComputedStyle` responde o que
#: a TELA mostra, que é a pergunta.
LER = r"""
(function(){
  const fora = {};
  for(const p of ['p1','p2','p3','p4']){
    const raiz = document.querySelector('[data-controle="' + p + '"]');
    if(!raiz){ fora[p] = null; continue; }
    const g = raiz.querySelector('[id$="-lightbar"]');
    const peca = g ? g.querySelector('.peca') : null;
    const lampadas = [];
    for(const r of raiz.querySelectorAll('[id*="-led-jogador-"]')){
      const n = (r.id.match(/-led-jogador-(\d)$/) || [])[1];
      if(n) lampadas.push([Number(n), getComputedStyle(r).fill]);
    }
    fora[p] = {
      conectado: raiz.dataset.conectado || null,
      // O `id` DO GRUPO É A TESTEMUNHA DE QUE A ABA É ESTA. `monta.svg`
      // prefixa todo `id` com o nome do lugar (`il-p1-…` aqui, `jg-p1-…` na
      // Jogar), e sem esta linha uma medição feita na aba errada volta
      // plausível — ver o comentário de `abrir()`.
      grupo: g ? g.id : null,
      tira: peca ? getComputedStyle(peca).fill : null,
      lampadas: lampadas,
    };
  }
  return JSON.stringify(fora);
})()
"""

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def _rgb(css: str | None) -> tuple[int, int, int] | None:
    """`rgb(126, 184, 212)` → `(126, 184, 212)`; qualquer outra coisa → `None`."""
    if not css:
        return None
    n = [int(float(x)) for x in
         "".join(c if (c.isdigit() or c in ".,") else " " for c in css).split(",")
         if x.strip()]
    return (n[0], n[1], n[2]) if len(n) >= 3 else None


def _do_hex(h: str) -> tuple[int, int, int] | None:
    """`#0000FF` → `(0, 0, 255)`; o travessão e o vazio → `None`."""
    h = (h or "").strip().lstrip("#")
    if len(h) != 6:
        return None
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return None


def _acesas(lampadas: list) -> list[int]:
    """Quais das cinco lâmpadas estão ACESAS, pela cor computada de cada uma.

    NÃO SE PERGUNTA À CLASSE `led-on`: ela é o que o gerador crava a partir do
    MOCKUP, e lê-la seria perguntar ao desenho se o desenho está certo — é
    exatamente o defeito que este ensaio nasceu para achar.

    NÃO SE DIGITA UM LIMIAR TAMBÉM. A primeira escrita comparava a soma dos
    canais com `3 × 120`, um número inventado aqui: o dia em que o par de tons
    do `CSS_LUZINHAS` mudasse, esta régua reprovaria a mudança em vez do
    defeito. O par tem dono (`a04_iluminacao.token_das_luzinhas`) e é a ele que
    se pergunta — a lâmpada acesa é a que está na cor do ACESO.
    """
    from pacotes import a04_iluminacao

    alvo = _do_hex(a04_iluminacao.token_das_luzinhas("--led-aceso"))
    return sorted(n for n, css in lampadas if alvo and _rgb(css) == alvo)


def _o_que_o_aparelho_diz(piloto: hefesto_vivo.Piloto) -> dict[str, dict]:
    """Por lugar (`p1`…`p4`): a luz que o MOTOR afirma, e o número.

    QUEM RESPONDE NÃO É O PACOTE DA ABA, e é isso que faz esta medição valer:
    ``app/widgets/controller_card.rotulo_lightbar`` é o dono da pergunta *"há
    cor a afirmar neste controle?"* — o mesmo que os cards da GUI estável usam —
    e ele devolve ``(ressalva, cor base)``. Perguntar ao pacote da 04 seria
    comparar o produto com ele mesmo: ele erraria o desenho e a resposta do
    mesmo jeito, e a régua concordaria com o erro.

    A REGRA QUE SE COBRA É DELA: *"se não tá mostrando agora, não tem info pra
    mostrar no produto"*. Com ressalva, o desenho não pode acender cor nenhuma;
    sem ressalva, ele tem de acender exatamente a cor base.

    O `_ctx_de_agora` é a mesa do último tique — o piloto a guarda para resolver
    o `uniq` de um clique sem gastar um IPC. Reusá-la é o que garante que os
    dois lados desta medição falam do MESMO instante; montar um segundo contexto
    aqui compararia a tela de agora com a mesa de daqui a pouco.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import rotulo_lightbar

    ctx = getattr(piloto, "_ctx_de_agora", None)
    if ctx is None:
        return {}
    por_uniq = {str(c.get("uniq") or ""): c for c in ctx.conectados}
    fora: dict[str, dict] = {}
    for lugar in ctx.mesa:
        pref, uniq = str(lugar.get("pref") or ""), str(lugar.get("uniq") or "")
        se = por_uniq.get(uniq)
        if not pref or se is None:
            continue
        recado, base = rotulo_lightbar(se, ctx.state)
        jogador = lugar.get("jogador")
        fora[pref] = {"acesa": None if recado is not None else base,
                      "ressalva": recado or "",
                      "numero": jogador if isinstance(jogador, int) else None}
    return fora


def main() -> int:
    import argparse

    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    lido: dict = {}
    dono: dict = {}

    #: O `_ir` É OBRIGATÓRIO, e a lição custou uma medição inteira em
    #: 03/09/2026: com `abre=` e sem ele, o piloto respondeu a pergunta na
    #: **01-jogar** — os `data-controle` são `p1`…`p4` nas duas abas e há
    #: lightbar nas duas, então a leitura voltou plausível e ERRADA. O que a
    #: denunciou foi o prefixo dos `id` do SVG: `jg-p1-…` em vez de `il-p1-…`.
    #: É a armadilha que esta casa nomeia — *medir contra a coisa errada produz
    #: alarme convincente*. Ver `os_quatro_lugares_no_dom.py`, que sempre o fez.
    def abrir() -> bool:
        if not piloto.pronto:
            return True
        piloto._ir(ABA)
        GLib.timeout_add(2200, medir)
        return False

    def medir() -> bool:
        def respondeu(texto: str | None, erro: Exception | None) -> None:
            if texto and not erro:
                lido.update(json.loads(texto))
            dono.update(_o_que_o_aparelho_diz(piloto))
            Gtk.main_quit()

        piloto.ponte.perguntar(LER, respondeu)
        return False

    GLib.timeout_add(1200, abrir)
    GLib.timeout_add(60000, Gtk.main_quit)
    Gtk.main()

    if not lido:
        print("REPROVA: não consegui ler o DOM da aba Iluminação.")
        return 1

    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    from pacotes import a04_iluminacao

    #: O PREFIXO QUE ESTA ABA DÁ AOS `id` DO DESENHO. Ele não é enfeite: é o
    #: único fato do DOM que separa esta aba da 01-jogar, que tem os mesmos
    #: `data-controle` e o mesmo grupo de lightbar.
    PREFIXO = "il-"
    #: O CINZA DE UMA BARRA SEM LUZ, perguntado ao dono — nunca digitado aqui.
    APAGADA = a04_iluminacao.LUZ_APAGADA

    print(f"{'lugar':6s} {'estado':12s} {'aparelho':>16s} {'desenho':>16s} "
          f"{'lâmpadas':>12s} {'esperadas':>12s}")
    print("-" * 80)
    erros: list[str] = []
    for pref in ("p1", "p2", "p3", "p4"):
        d = lido.get(pref)
        if not d:
            print(f"{pref:6s} (sem lugar no DOM)")
            erros.append(f"{pref}: o lugar não existe na página")
            continue
        grupo = str(d.get("grupo") or "")
        if grupo and not grupo.startswith(PREFIXO):
            print(f"{pref:6s} (o desenho é de outra aba: {grupo})")
            erros.append(f"{pref}: medi a aba errada — o grupo é {grupo!r} e a "
                         f"Iluminação prefixa com {PREFIXO!r}")
            continue
        campos = dono.get(pref) or {}
        acesa = campos.get("acesa")
        quero = tuple(int(x) for x in acesa[:3]) if acesa else None
        tenho = _rgb(d.get("tira"))
        acesas = _acesas(d.get("lampadas") or [])
        numero = campos.get("numero")
        esperadas: list[int] = []
        if isinstance(numero, int):
            esperadas = [i + 1 for i, b in enumerate(player_led_pattern(numero)) if b]
        estado = d.get("conectado") or "?"
        print(f"{pref:6s} {estado:12s} "
              f"{(str(quero) if quero else 'sem cor a afirmar'):>18s} "
              f"{(str(tenho) if tenho else '—'):>16s} "
              f"{str(acesas):>12s} {str(esperadas or '—'):>12s}")
        if campos.get("ressalva"):
            print(f"{'':6s} ressalva do motor: {campos['ressalva']}")
        if estado != "sim":
            continue
        apagada = _do_hex(APAGADA)
        if quero and tenho != quero:
            erros.append(f"{pref}: o motor afirma {quero} e o desenho acende {tenho}")
        if quero is None and tenho != apagada:
            erros.append(f"{pref}: o motor NÃO afirma cor nenhuma "
                         f"({campos.get('ressalva') or 'sem ressalva'}) e o "
                         f"desenho acende {tenho} — devia ficar em {apagada}")
        if esperadas and acesas != esperadas:
            erros.append(f"{pref}: o número {numero} pede as lâmpadas {esperadas} "
                         f"e o desenho acende {acesas}")

    print()
    if erros:
        print(f"REPROVA: {len(erros)} divergência(s) entre a luz do desenho e a "
              f"do aparelho:")
        for e in erros:
            print(f"  {e}")
        return 1
    print("OK: o desenho grande acende a luz que o aparelho tem, e as cinco "
          "lâmpadas dizem o número vivo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
