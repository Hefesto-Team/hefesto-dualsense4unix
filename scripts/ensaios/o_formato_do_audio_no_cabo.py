#!/usr/bin/env python3
"""o_formato_do_audio_no_cabo.py — o mesmo bloco de áudio, no controle do CABO.

A PERGUNTA, E ELA É DELA — 10/09/2026, com os dois controles na mesa:

    *"manda antes pro controle com fio. eu quero saber se o mesmo teste
     funcionaria nele, pq o audio mesmo com cabo a gnt precisa tomar o
     controle."*  # noqa-acento: citação literal dela

**O que ela desenhou é o controle positivo que faltava, e ele separa duas coisas
que esta casa vinha medindo juntas: o FORMATO e o TRANSPORTE.**

Toda passada de áudio por rádio deu silêncio — as seis de 08/09 pelo hidraw, os
seis cruzamentos de 10/09 pelos dois envelopes, e a rajada de 10/09 pelo socket
L2CAP direto com o MTU levantado a 1024. Em todas elas variou-se o CAMINHO. **O
bloco de áudio em si nunca foi posto à prova contra um aparelho que se sabe
capaz de tocar.**

O controle do CABO é esse aparelho: ele toca, e ela ouviu.

O QUE CADA RESULTADO DECIDE
----------------------------
* **saiu som no cabo** → o formato do bloco está CERTO, e o silêncio do rádio é
  de transporte. A caça continua na camada do enlace;
* **silêncio no cabo também** → o formato está ERRADO, e **o silêncio do rádio
  nunca foi de transporte**. Todas as passadas de envelope mediram a coisa
  errada, e a fila muda de lugar: o que falta descobrir é o corpo do report, não
  o cano.

O segundo resultado é o que mais move a casa, e é por isso que este ensaio é
barato e vem antes de qualquer outra ideia.

O QUE ELE MANDA — três formas, e a diferença entre elas é declarada
--------------------------------------------------------------------
O report de áudio dos arranjos é o ``0x39`` de 547 B, com CRC-32 no rabo. O CRC
é coisa de BLUETOOTH: por cabo o DualSense não usa CRC em report de saída
(``build_usb_report`` não escreve nenhum). Então há três candidatos honestos, e
o ensaio manda os três em vez de escolher um por palpite:

1. ``tal-e-qual`` — o ``0x39`` exatamente como vai pelo rádio, CRC incluído;
2. ``sem-crc`` — o mesmo, com os 4 bytes de CRC cortados;
3. ``sem-crc-64`` — o mesmo sem CRC, truncado no tamanho de report que o cabo
   usa para o estado (64 B). É o candidato mais fraco e está aqui porque custa
   nada: se o firmware exigir o tamanho do transporte, é ele que passa.

**E o `common` da condição vai junto**, com o volume que ela ouviu (85), rota só
no alto-falante e o pré-amplificador do kernel — senão um silêncio por volume
zero se leria como silêncio de formato.

QUEM MANDA NO APARELHO ENQUANTO ISSO
-------------------------------------
O daemon está vivo e é o dono da barra e do estado. Este ensaio **não assume** o
controle: ele escreve os reports de áudio e sai. É a palavra dela — *"o audio
mesmo com cabo a gnt precisa tomar o controle"* — e ela tem razão para o REGIME;
para uma rajada de 5 s o que decide é se o firmware ACEITA o corpo, e isso não
depende de posse.

ESCREVE NO APARELHO? SIM, e só com `--tocar`. Sem ele, lê e mostra o que faria.

USO
    o_formato_do_audio_no_cabo.py --listar
    o_formato_do_audio_no_cabo.py --tocar               # as três formas, todos os arranjos
    o_formato_do_audio_no_cabo.py --tocar --forma sem-crc --arranjo ds5dongle
"""

from __future__ import annotations

import argparse
import os
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import hefesto_dualsense4unix.core.ds_output_report as rep
import hefesto_dualsense4unix.integrations.alto_falante_bt as af
from a_folha_do_som_por_controle import ms_por_report, pacotes_do_tom
from comum import (
    CABO,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    descobrir_aparelhos,
    fisicos,
    resumo,
)
from escrita_pelo_broker import mascarar

#: AS TRÊS FORMAS, e cada uma é uma hipótese sobre o que o firmware exige no
#: cabo. Nenhuma é "a certa" — o ensaio existe justamente porque não se sabe.
FORMAS = {
    "tal-e-qual": "o 0x39 como vai pelo rádio, com o CRC-32 no rabo",
    "sem-crc": "o mesmo, com os 4 bytes de CRC cortados (o cabo não usa CRC)",
    "sem-crc-64": "o mesmo sem CRC, truncado em 64 B (o tamanho do 0x02)",
}


def aplicar_forma(pacote: bytes, forma: str) -> bytes:
    """O mesmo report, na forma pedida. O corte é declarado, nunca implícito."""
    if forma == "tal-e-qual":
        return pacote
    sem_crc = pacote[:-4]
    if forma == "sem-crc":
        return sem_crc
    if forma == "sem-crc-64":
        return sem_crc[: rep.USB_REPORT_LEN]
    raise ValueError(f"forma que este ensaio não conhece: {forma!r}")


def o_controle_no_cabo() -> object | None:
    """O DualSense do cabo. Um só: com dois, não se sabe de qual veio o som."""
    reais = [a for a in fisicos(descobrir_aparelhos()) if a.transporte == CABO]
    return reais[0] if len(reais) == 1 else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--listar", action="store_true", help="só lê: o alvo e o que ele faria")
    ap.add_argument("--tocar", action="store_true", help="manda os reports (ESCREVE no aparelho)")
    ap.add_argument("--forma", choices=list(FORMAS), action="append",
                    help=f"padrão: as três ({', '.join(FORMAS)})")
    ap.add_argument("--arranjo", action="append",
                    help=f"padrão: todos ({', '.join(af.ARRANJO_POR_NOME)})")
    ap.add_argument("--segundos", type=float, default=4.0, help="a duração de cada tom")
    args = ap.parse_args()

    print(cabecalho_do_instrumento(
        "o_formato_do_audio_no_cabo",
        "o mesmo bloco de áudio que o rádio recusa, o CABO aceita?",
        bibliotecas=["hefesto_dualsense4unix.integrations.alto_falante_bt"],
        escreve_no_aparelho=bool(args.tocar)))

    alvo = o_controle_no_cabo()
    if alvo is None:
        print(resumo("preciso de EXATAMENTE UM DualSense no CABO — é ele o "
                     "controle positivo, e com dois não se sabe de qual veio o som."))
        return 1
    print(f"o controle do cabo: {mascarar(alvo.mac)}  ({alvo.caminho_hidraw})\n")

    formas = args.forma or list(FORMAS)
    arranjos = args.arranjo or list(af.ARRANJO_POR_NOME)
    desconhecidos = [n for n in arranjos if n not in af.ARRANJO_POR_NOME]
    if desconhecidos:
        print(resumo(f"arranjo que o produto não conhece: {desconhecidos}"))
        return 1

    # A CONDIÇÃO É A DO PRODUTO, com o volume que ELA ouviu no cabo.
    common = af.common_de_audio(
        volume=af.VOLUME_QUE_ELA_OUVIU,
        rota=rep.SAIDA_SO_NO_ALTO_FALANTE,
        preamp=rep.SP_PREAMP_GAIN_PADRAO,
    )

    if not args.tocar:
        print("O QUE ESTE ENSAIO MANDARIA, e são as combinações:")
        for arranjo in arranjos:
            pacotes = pacotes_do_tom(arranjo, segundos=args.segundos, common=common, seq0=1)
            for forma in formas:
                exemplo = aplicar_forma(pacotes[0], forma)
                print(f"  {arranjo:20s} × {forma:12s} → {len(pacotes)} report(s) de "
                      f"{len(exemplo)} B, um a cada {ms_por_report(arranjo)} ms")
        print()
        for forma, porque in FORMAS.items():
            print(f"  {forma:12s} — {porque}")
        print(resumo("leitura pura — nenhum byte escrito. Rode com --tocar, com ela ouvindo."))
        return 0

    # O `Escritor` do broker monta o report a partir do `common` — aqui o pacote
    # já vem PRONTO do arranjo (é o corpo do 0x39, não um estado), então a porta
    # se abre direto. O broker continua sendo quem a entrega, com o daemon vivo.
    no = abrir_no_hidraw(alvo.caminho_hidraw, escrita=True)
    print(getattr(no, "linha_de_relatorio", "porta: broker"))
    total_recusas = 0
    for arranjo in arranjos:
        pacotes = pacotes_do_tom(arranjo, segundos=args.segundos, common=common, seq0=1)
        intervalo = ms_por_report(arranjo) / 1000.0
        for forma in formas:
            corpo = [aplicar_forma(p, forma) for p in pacotes]
            print(f"\n  {arranjo} × {forma}: {len(corpo)} report(s) de {len(corpo[0])} B")
            print(f"  >>> OUÇA O ALTO-FALANTE DO CONTROLE DO CABO — {args.segundos:g} s",
                  flush=True)
            recusas, motivo = 0, ""
            for pkt in corpo:
                try:
                    os.write(no.fd, pkt)
                except OSError as erro:
                    recusas += 1
                    # UM KERNEL QUE RECUSA O PRIMEIRO RECUSA OS 200: insistir só
                    # enche o log e atrasa a resposta na tela dela.
                    motivo = f"{erro.__class__.__name__} {erro.errno} — {erro.strerror}"
                    break
                time.sleep(intervalo)
            total_recusas += recusas
            if motivo:
                print(f"  RECUSADO na primeira escrita: {motivo}")
            else:
                print(f"  {len(corpo)} enviados, 0 recusa(s)")
            time.sleep(1.0)

    fechar = getattr(no, "fechar", None)
    if callable(fechar):
        fechar()
    print(resumo(
        "se ela OUVIU em alguma combinação, o formato daquela linha é o certo e o "
        "silêncio do rádio é de transporte; se calou em TODAS, o formato do bloco "
        "de áudio está errado e o rádio nunca foi o problema."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
