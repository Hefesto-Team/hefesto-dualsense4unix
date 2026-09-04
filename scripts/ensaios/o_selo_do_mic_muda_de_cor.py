#!/usr/bin/env python3
"""O selo do microfone MUDA DE COR quando o mudo chega pelo tique.

POR QUE ELE EXISTE, e é a armadilha desta frente: o gerador escreve
``class="selo-ativo off"`` na PRIMEIRA montagem, e um teste que leia o HTML no
disco passa. O que ela vê é outra coisa — a repintura do tique escreve TEXTO
(``escrever()`` cai no alvo padrão, ``el.textContent = t``), e **um elemento
aceita UM alvo de pintura**. O card que nasceu ATIVO e ficou mudo mostrava a
palavra ``MUDO`` sobre o fundo VERDE.

DECISÃO DELA, 03/09/2026: *"Cor + ícone. Redundante de propósito — quem lê
rápido pega pela cor, quem não distingue cor pega pelo risco."*

Ele NÃO TOCA O APARELHO DELA: não clica no 🎙, que faria ``mic.set`` no
firmware do DualSense que está no cabo agora. Ele injeta a carga que o TIQUE
injetaria — ``window.__hef.pintar`` com ``mic-selo`` valendo cada um dos três
estados — e lê o DOM na MESMA avaliação de JS, para que o tique de 500 ms não
caia no meio da medição.

MEDE PIXEL, NÃO CLASSE: a cor sai de ``getComputedStyle``, e o risco sai do
``content`` do ``::after``. Uma régua sobre ``className`` daria verde no dia em
que o CSS trocasse de nome de classe — e o que ela vê é a cor.

Uso (a janela é OCULTA; ela tem UMA tela)::

    scripts/ensaios/o_selo_do_mic_muda_de_cor.py
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

from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva

ABA = "02-controles.html"

#: OS TRÊS ESTADOS, PERGUNTADOS AO DONO — `mesa_viva.selo_do_mic`, o mesmo que
#: o pacote emite a cada tique e o mesmo que o gerador crava em
#: `data-hef-quando`. Digitar "MUDO" aqui faria a régua reprovar a MELHORA no
#: dia em que a palavra mudar — é a lição que esta casa pagou seis vezes.
SELO_MUDO = mesa_viva.selo_do_mic(True, True)
SELO_ATIVO = mesa_viva.selo_do_mic(False, True)
SELO_SEM_LEITURA = mesa_viva.selo_do_mic(False, False)
ESTADOS = (SELO_MUDO, SELO_ATIVO, SELO_SEM_LEITURA)

#: PINTA E LÊ NUMA AVALIAÇÃO SÓ. O `%s` recebe o selo a pintar.
PINTA_E_LE = r"""
(function(){
  const selo = %s;
  const carga = {colunas: {}};
  for(const p of ['p1','p2','p3','p4']) carga.colunas[p] = {'mic-selo': selo};
  const pintou = (window.__hef && window.__hef.pintar)
                 ? window.__hef.pintar(carga) : -1;
  const fora = [], vistos = [];
  for(const el of document.querySelectorAll('[data-campo="mic-selo"]')){
    // O DONO DA COR é quem carrega a classe `selo-ativo`; com o <span>
    // aninhado, quem tem o TEXTO é o filho. Sobe até achar quem pinta.
    let pinta = el;
    while(pinta && !pinta.classList.contains('selo-ativo')) pinta = pinta.parentElement;
    pinta = pinta || el;
    const card = el.closest('[data-controle]');
    const glifo = pinta.querySelector('.mic-glifo');
    if(vistos.indexOf(pinta) >= 0) continue;   // três endereços, UM selo
    vistos.push(pinta);
    fora.push({
      controle: card ? (card.dataset.controle || '') : '',
      texto: (pinta.textContent || '').trim(),
      classe: pinta.className,
      fundo: getComputedStyle(pinta).backgroundColor,
      // O RISCO É DO GLIFO, não do selo: ele cruza o microfone, não a palavra.
      risco: glifo ? getComputedStyle(glifo, '::after').content : 'sem glifo',
      icone: !!glifo,
      // A ARMADILHA MEDIDA, e este número é ela: com UM endereço no selo, o
      // piloto alcança um alvo só — e o que ele alcança é o texto, porque é o
      // padrão. A cor fica na que o gerador desenhou, para sempre.
      enderecos: 1 + pinta.querySelectorAll('[data-campo="mic-selo"]').length,
      // O ÍCONE CUSTA LARGURA, e a linha do rótulo do microfone já era
      // apertada — o card mede 328px e o comentário do `luz-hex` registra que
      // "a frase inteira do rótulo não cabe". Se o selo empurrar o vizinho para
      // fora da linha, a régua tem de dizer, e não a foto.
      transbordou: (function(){
        const linha = pinta.parentElement;
        if(!linha) return false;
        return linha.scrollWidth - linha.clientWidth > 1;
      })(),
      largura: Math.round(pinta.getBoundingClientRect().width * 10) / 10,
    });
  }
  return JSON.stringify({pintou: pintou, selos: fora});
})()
"""

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def main() -> int:
    linha = argparse.ArgumentParser(description=__doc__)
    linha.add_argument("--bancada", action="store_true",
                       help="medir o DESENHO (`mockup/`) em vez do publicado. "
                            "É onde a cura vive até ela dar o OK.")
    linha.add_argument("--foto", default="",
                       help="retratar a página no fim da medição. A janela é "
                            "OCULTA: ela tem UMA tela.")
    linha.add_argument("--selo", default="",
                       help="deixar o selo NESTE estado antes da foto "
                            "(ATIVO/MUDO/—). Sem isto a foto sai no último "
                            "estado medido, que é o travessão.")
    dela = linha.parse_args()

    from hefesto_dualsense4unix.interface import onde

    alvo = onde.pagina(ABA, publicado=not dela.bancada)
    print(f"[medindo] {alvo}")

    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    medidas: dict[str, dict] = {}
    fila = list(ESTADOS)

    # A NAVEGAÇÃO É DO `main()` DO PILOTO, não do `__init__` — quem constrói o
    # `Piloto` à mão nasce na `01-jogar` e mediria a aba errada. Foi o que a
    # primeira execução deste ensaio fez: zero `mic-selo` no DOM, com os quatro
    # endereços vivos na página publicada.
    #
    # E A URI É MONTADA AQUI, não pelo `_ir`, que é fixo em `publicado=True`. É
    # o que permite medir a BANCADA com o mesmo motor e o mesmo daemon: o
    # `_carregou` do piloto reinstala a ponte por NOME DE ARQUIVO, e os dois
    # arquivos se chamam `02-controles.html`.
    def ir() -> bool:
        if not piloto.pronto:
            return True
        piloto.view.load_uri(alvo.as_uri())
        GLib.timeout_add(2500, proxima)
        return False

    def proxima() -> bool:
        if not piloto.pronto:
            return True
        if not fila:
            if dela.foto:
                GLib.timeout_add(300, retratar)
            else:
                Gtk.main_quit()
            return False
        estado = fila.pop(0)

        def leu(texto: str | None, erro: Exception | None) -> None:
            medidas[estado] = (json.loads(texto) if texto and not erro
                               else {"erro": str(erro), "selos": []})
            GLib.timeout_add(250, proxima)

        piloto.ponte.perguntar(PINTA_E_LE % json.dumps(estado), leu)
        return False

    def retratar() -> bool:
        """A foto, DEPOIS da medição — e com o selo no estado pedido.

        O TIQUE DE 500 ms REPINTA POR CIMA, e a primeira versão desta função
        pagou por isso: ela injetava e fotografava na MESMA passagem, com
        `run_javascript` sendo assíncrono — o obturador batia antes de o JS
        correr, e a foto saía no estado que o daemon diz agora. Aqui a foto é
        agendada pelo RETORNO da injeção, e o piloto é parado antes, para que
        o tique seguinte não desfaça o que se quer mostrar a ela.
        """
        piloto.pronto = False          # cala o tique: ele repintaria por cima
        if not dela.selo:
            return bater()

        def injetou(_v: object, _e: object) -> None:
            GLib.timeout_add(200, bater)

        piloto.ponte.perguntar(PINTA_E_LE % json.dumps(dela.selo), injetou)
        return False

    def bater() -> bool:
        piloto.tela.fotografar(dela.foto)
        print(f"foto: {dela.foto}"
              + (f" (selo forçado em {dela.selo!r})" if dela.selo else ""))
        Gtk.main_quit()
        return False

    GLib.timeout_add(800, ir)
    GLib.timeout_add(60000, Gtk.main_quit)
    Gtk.main()

    print(json.dumps(medidas, ensure_ascii=False, indent=2))
    print()

    if not any(m.get("selos") for m in medidas.values()):
        print("REPROVA: não achei um só `mic-selo` no DOM vivo.")
        return 1

    # O CONTRATO, e ele é o da decisão dela: VERDE quer dizer uma coisa só —
    # ATIVO. Tudo o que não é ATIVO fica apagado, e o RISCO separa o MUDO do
    # travessão. Ver a tabela em `aba02.selo_do_microfone`.
    mau: list[str] = []
    for estado in ESTADOS:
        for s in medidas.get(estado, {}).get("selos", []):
            lugar = f"{estado}/{s['controle'] or '?'}"
            if s["texto"] != estado:
                mau.append(f"{lugar}: o texto ficou {s['texto']!r}")
            quer_verde = estado == SELO_ATIVO
            if ("on" in s["classe"].split()) is not quer_verde:
                mau.append(f"{lugar}: classe={s['classe']!r} (queria "
                           f"{'com' if quer_verde else 'sem'} `on`)")
            if not s["icone"]:
                mau.append(f"{lugar}: SEM o ícone do microfone (`.mic-glifo`)")
            tem_risco = s["risco"] not in ("none", "normal")
            if tem_risco is not (estado == SELO_MUDO):
                mau.append(f"{lugar}: risco={s['risco']!r} (queria "
                           f"{'um risco' if estado == SELO_MUDO else 'nenhum'})")
            if s["enderecos"] < 3:
                mau.append(f"{lugar}: o selo tem {s['enderecos']} endereço(s) e "
                           "precisa de 3 — a cor, o risco e a palavra são três "
                           "alvos de pintura, e um elemento aceita UM")
            if s["transbordou"]:
                mau.append(f"{lugar}: o selo ({s['largura']}px) empurrou a linha "
                           "do rótulo para fora — o ícone custou largura demais")

    fundos = {e: {s["fundo"] for s in medidas.get(e, {}).get("selos", [])}
              for e in ESTADOS}
    if fundos[SELO_MUDO] and fundos[SELO_MUDO] == fundos[SELO_ATIVO]:
        mau.append(f"{SELO_MUDO} e {SELO_ATIVO} têm O MESMO FUNDO: "
                   f"{fundos[SELO_MUDO]} — a cor não segue o estado")

    if mau:
        print(f"REPROVA: {len(mau)} defeito(s) no selo do microfone:")
        for linha in mau:
            print("  " + linha)
        return 1
    print("OK — o selo muda de cor E de risco nos três estados, e o ícone fica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
