#!/usr/bin/env python3
"""Clica o chip de máscara nos QUATRO cartões da Jogar, dentro do WebKit dela.

O PEDIDO É DELA, 03/09/2026: *"É uma máscara por controle. (…) Se isso não
ocorre com os 4 controles em cada aba, então temos que construir isso e garantir
isso."*

O QUE ESTE ENSAIO PROVA, e o teste de unidade não alcança: o teste conta
atributos num arquivo. Este faz o caminho DELA — o dedo no chip, o evento
subindo pelo ouvinte único do piloto, o `closest('[data-controle]')` achando de
quem é o cartão, a tradução `pref → uniq` na mesa viva, o gesto decidindo, e a
frase voltando à tela. Até 03/09 os chips do P3 e do P4 não tinham
``data-gesto``: **o clique morria no DOM** e nada — nem terminal, nem tela —
dizia uma palavra.

NADA CHEGA AO DAEMON DELA. ``pacotes.ponte.chamar`` é trocado por um gravador
antes do primeiro clique: o caminho inteiro é percorrido e a chamada
``gamepad.mask.set`` é ANOTADA em vez de despachada. Ela está usando a máquina;
um ensaio que trocasse a máscara do controle no cabo dela seria um estrago, não
uma medição.

A PÁGINA É A DA BANCADA, e isto é deliberado: o piloto abre o PUBLICADO
(`hefesto_vivo._ir`), e o publicado só recebe endereço pelo
``check_o_desenho_aprovado.py --publicar-enderecos``, que é ato de quem
coordena. Medir o publicado hoje daria **verde sobre a página congelada** — a
armadilha mais cara do `docs/process/COMO-OLHAR-A-TELA.md`. O desvio é uma cópia
num diretório temporário; a bancada dela não é tocada.

OS TRÊS DESFECHOS QUE ELE SABE SEPARAR, e a diferença é o ponto inteiro:

    aplicou ............ o gesto mandou `gamepad.mask.set` com o `uniq` daquele
                         cartão — é o que acontece num lugar COM controle;
    recusou dizendo .... o gesto respondeu com a frase ("Não há controle no
                         lugar P3…") — é o que acontece num lugar VAZIO, e é
                         resposta, não silêncio;
    SEM RESPOSTA ....... ninguém ouviu o clique. É o defeito, e era o estado do
                         P3 e do P4.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/os_quatro_cartoes_mudam_a_mascara.py
    scripts/ensaios/os_quatro_cartoes_mudam_a_mascara.py --publicado
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk  # noqa: E402

from hefesto_dualsense4unix.interface import hefesto_vivo, onde  # noqa: E402
from hefesto_dualsense4unix.interface.pacotes import ponte  # noqa: E402

ABA = "01-jogar.html"

#: O CHIP CLICADO. **Xbox 360** e não DualSense, e a escolha é medida: o cartão
#: do P1 já nasce com o DualSense aceso no desenho, então clicar nele deixaria o
#: ensaio sem como distinguir "o clique chegou" de "já estava assim".
CHIP = "Xbox 360"

#: OS LUGARES, do dono deles. `monta.MESA` é a mesa do desenho — quatro —, e
#: cravar `["p1", "p2", "p3", "p4"]` aqui seria a régua digitando o que devia
#: perguntar: no dia em que a mesa mudar de tamanho, este ensaio a segue.
def _lugares() -> list[str]:
    import monta

    return [str(c.get("uniq") or c["pref"]) for c in monta.MESA]


#: O CLIQUE, num JS só por cartão. `.click()` do DOM e não um evento sintético:
#: é o mesmo caminho do dedo dela, e é o único que passa pelo ouvinte delegado
#: do piloto (`document.addEventListener('click', …, true)`).
CLIQUE = r"""
(function(){
  const cartao = document.querySelector('[data-controle="__ONDE__"]');
  if(!cartao){ return JSON.stringify({achou: false, porque: 'sem cartao'}); }
  const chip = cartao.querySelector('[data-mascara="__CHIP__"]');
  if(!chip){ return JSON.stringify({achou: false, porque: 'sem chip'}); }
  chip.click();
  return JSON.stringify({
    achou: true,
    // O QUE O CHIP DECLARA — é isto que decide se o ouvinte o vê como gesto.
    gesto: chip.getAttribute('data-gesto'),
    campo: chip.getAttribute('data-campo'),
    conectado: cartao.getAttribute('data-conectado')
  });
})()
""".replace("__CHIP__", CHIP)

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def _desviar_para_a_bancada(pilha: list[pathlib.Path]) -> None:
    """Aponta o PUBLICADO do piloto para uma cópia da bancada, em /tmp."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="ensaio-jogar-"))
    pilha.append(tmp)
    shutil.copy2(onde.BANCADA / ABA, tmp / ABA)
    onde.PUBLICADO = tmp


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--publicado", action="store_true",
                    help="mede a página do produto em vez da bancada")
    opcoes = ap.parse_args()

    lixo: list[pathlib.Path] = []
    if not opcoes.publicado:
        _desviar_para_a_bancada(lixo)

    # O GRAVADOR, POSTO ANTES DO PRIMEIRO CLIQUE. Sem ele o gesto despacharia
    # `gamepad.mask.set` no daemon DELA, que está vivo e com controle na mesa.
    ipcs: list[tuple[str, dict]] = []
    ponte.chamar = lambda metodo, timeout=None, **params: (  # type: ignore[assignment]
        ipcs.append((metodo, dict(params))) or True)

    lugares = _lugares()
    piloto = hefesto_vivo.Piloto(argparse.Namespace(**BANDEIRAS, abre=ABA))
    achados: list[dict] = []
    fila = list(lugares)

    def proximo() -> bool:
        if not piloto.pronto or not fila:
            if not fila:
                Gtk.main_quit()
                return False
            return True
        onde_ = fila.pop(0)
        # O DESFECHO ANTERIOR SAI DA MESA antes do clique: `desfechos` é
        # `{pagina:gesto}`, e os quatro cliques são o MESMO gesto. Sem esta
        # linha o quarto cartão herdaria a resposta do terceiro, e um chip mudo
        # passaria por respondido — que é exatamente o defeito medido aqui.
        piloto.desfechos.pop(f"{ABA}:mascara", None)
        antes = len(ipcs)

        def clicou(texto: str | None, erro: Exception | None) -> None:
            dom = json.loads(texto) if texto and not erro else {"achou": False,
                                                                "porque": str(erro)}

            def colher() -> bool:
                desfecho, frase = piloto.desfechos.get(f"{ABA}:mascara",
                                                       ("SEM RESPOSTA", ""))
                achados.append({"onde": onde_, "dom": dom, "desfecho": desfecho,
                                "frase": frase, "ipcs": ipcs[antes:]})
                GLib.timeout_add(200, proximo)
                return False

            # UM SEGUNDO ANTES DE COLHER: o gesto roda em THREAD (o piloto não
            # congela a janela por um IPC), então ler `desfechos` no mesmo laço
            # do clique leria o de antes.
            GLib.timeout_add(1000, colher)

        piloto.ponte.perguntar(CLIQUE.replace("__ONDE__", onde_), clicou)
        return False

    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(3500, proximo)
    GLib.timeout_add(45000, Gtk.main_quit)
    Gtk.main()

    for t in lixo:
        shutil.rmtree(t, ignore_errors=True)

    if len(achados) != len(lugares):
        print(f"REPROVA: cliquei {len(achados)} de {len(lugares)} cartões — a "
              f"janela não respondeu a tempo.")
        return 1

    mudos = []
    print(f"  chip clicado: {CHIP} · página: "
          f"{'PUBLICADA' if opcoes.publicado else 'bancada'}\n")
    for a in achados:
        dom = a["dom"]
        if not dom.get("achou"):
            print(f"  {a['onde']:>18s}  SEM CHIP NO DOM ({dom.get('porque')})")
            mudos.append(a["onde"])
            continue
        ipc = ", ".join(m for m, _ in a["ipcs"]) or "—"
        print(f"  {a['onde']:>18s}  data-gesto={dom['gesto']!r:11s} "
              f"conectado={dom['conectado']!r:6s} → {a['desfecho']} · IPC {ipc}")
        if a["frase"]:
            print(f"                      “{a['frase'].split(': ', 1)[-1]}”")
        # O CRITÉRIO É "RESPONDEU", e não "aplicou": num lugar VAZIO a resposta
        # certa é a frase que diz que não há controle ali. Cobrar `aplicou` nos
        # quatro exigiria quatro controles na mesa dela para o ensaio passar.
        if a["desfecho"] == "SEM RESPOSTA":
            mudos.append(a["onde"])

    if mudos:
        print(f"\nREPROVA: {len(mudos)} cartão(ões) não respondeu ao clique — "
              f"{', '.join(mudos)}. O chip está desenhado e o dedo dela não "
              f"alcança nada: nem muda, nem diz por quê.")
        return 1

    print(f"\nOK: os {len(achados)} cartões respondem ao clique no chip de "
          f"máscara — cada um com o seu próprio lugar na mesa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
