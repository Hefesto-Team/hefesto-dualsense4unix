#!/usr/bin/env python3
"""o_fone_tem_volume_proprio.py — o byte do fone, variado SOZINHO, na orelha dela.

A PERGUNTA QUE ELE DECIDE (FONE-01, decisão dela de 09/09/2026: *"1-b"*)
--------------------------------------------------------------------------
O DualSense tem DUAS saídas — o alto-falante e o fone do jack — e o produto
manda **o mesmo byte** para as duas: `set_audio_volumes(headphone=efetivo,
speaker=efetivo)` (`core/backend_pydualsense.py`), por uma razão medida em
15/08 (`sfx-o-fone-manda-por-cima`: o fone manda por cima da rota, e um fone
em zero silenciaria quem plugasse um headset). Ela decidiu que o fone ganha
campo próprio no perfil, por controle. **Antes do campo, a bancada:** o
firmware obedece a um `common[4]` diferente do `common[5]`?

O mapa diz `MONTOU` nos dois transportes para `audio.jack.volume@dualsense`, e
diz mais: **o kernel desta máquina não define o bit que autoriza o fone**
(bit4 do flag0). O `VALID_FLAG0_HEADPHONE_VOLUME = 0x10` desta árvore é de
comunidade. Este ensaio é o que diz se ele vale.

O DESENHO
---------
Um tom (440 Hz, contínuo) toca no SINK do controle enquanto o `common[4]` vai
de `0x7F` a `0x00` com o alto-falante FIXO — e a orelha dela, no fone, diz o
que mudou. Os passos, e cada um é uma pergunta::

    1  fone 0x7F, bit ligado       controle POSITIVO — tem de sair som no fone
    2  fone 0x40, bit ligado       metade — ficou mais baixo?
    3  fone 0x10, bit ligado       quase nada — quase silêncio?
    4  fone 0x00, bit ligado       controle NEGATIVO — silêncio no fone
    5  fone 0x00, SEM o bit        o bit importa? Se silenciar sem o bit, o
                                   firmware ignora a autorização (e o kernel
                                   estava certo em não a definir)

    Se 1 soa e 4 cala  -> o byte do fone manda sozinho: o campo pode nascer.
    Se 4 soa igual a 1 -> o firmware iguala fone e alto-falante por baixo, e
                          o campo seria um número na tela sobre nada. É o
                          achado que derruba a FONE-01 — e vale mais que um verde.
    Se 5 = 4           -> o bit não faz diferença.

O MARTELO, e por que ele existe
-------------------------------
O daemon é dono do volume e reescreve fone E alto-falante em cada report de
áudio dele. Uma escrita minha pode ser desfeita antes de ela ouvir. Por isso
cada passo **martela** o byte a 10 Hz durante a janela (`--uma-vez` desliga).
O relatório diz quantas escritas foram — e se o som "piscar" entre dois
volumes, isso é o daemon e eu disputando, e é um SIM do firmware.

NO RÁDIO
--------
Não há sink de som para o controle no rádio (seis passadas em 08/09,
silêncio nas seis — ensaio 13 do índice do rádio). Este instrumento ESCREVE
o `0x31` igual, mas não tem o que tocar: no rádio ele só monta, e diz isso.

Porta: o broker (`comum.abrir_no_hidraw`), com o daemon VIVO. Escreve no
aparelho? SIM — dois bytes do common (fone, e o alto-falante se `--alto-falante`).

USO
    o_fone_tem_volume_proprio.py --listar
    o_fone_tem_volume_proprio.py --alvo <MAC>                  # os cinco passos
    o_fone_tem_volume_proprio.py --alvo <MAC> --passo 1 --passo 4
    o_fone_tem_volume_proprio.py --alvo <MAC> --alto-falante 0x40 --sink <nome>
"""

from __future__ import annotations

import argparse
import contextlib
import math
import os
import struct
import subprocess
import sys
import tempfile
import time
import wave

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from comum import CABO, RADIO, cabecalho_do_instrumento, resumo
from escrita_pelo_broker import (
    Escritor,
    alvos_da_mesa,
    common_vazio,
    escolher_alvo,
    linha_do_caderno,
    listar,
    mascarar,
    perguntar,
)
from hefesto_dualsense4unix.core.ds_output_report import (
    COMMON_HEADPHONE_VOLUME,
    COMMON_SPEAKER_VOLUME,
    TETO_HEADPHONE_VOLUME,
    VALID_FLAG0_HEADPHONE_VOLUME,
    VALID_FLAG0_SPEAKER_VOLUME,
)

LINHA_DO_MAPA = "audio.jack.volume@dualsense"

#: passo -> (volume do fone, com o bit?, o que ela deve esperar)
PASSOS: dict[int, tuple[int, bool, str]] = {
    1: (0x7F, True, "CONTROLE POSITIVO: tem de sair som no fone"),
    2: (0x40, True, "metade — mais baixo que o passo 1?"),
    3: (0x10, True, "quase nada — quase silêncio?"),
    4: (0x00, True, "CONTROLE NEGATIVO: silêncio no fone"),
    5: (0x00, False, "SEM o bit de autorização — o bit importa?"),
}


def common_do_passo(volume_do_fone: int, *, com_bit: bool, alto_falante: int | None) -> bytearray:
    """O common em que SÓ o fone (e, se pedido, o alto-falante fixo) existe."""
    if not 0 <= volume_do_fone <= TETO_HEADPHONE_VOLUME:
        raise ValueError(f"fone fora de 0..{TETO_HEADPHONE_VOLUME:#x}: {volume_do_fone:#x}")
    c = common_vazio()
    c[COMMON_HEADPHONE_VOLUME] = volume_do_fone
    if com_bit:
        c[0] |= VALID_FLAG0_HEADPHONE_VOLUME
    if alto_falante is not None:
        c[COMMON_SPEAKER_VOLUME] = alto_falante & 0xFF
        c[0] |= VALID_FLAG0_SPEAKER_VOLUME
    return c


def escrever_tom(caminho: str, segundos: float, hz: float = 440.0, taxa: int = 48000) -> None:
    """Um WAV estéreo de `segundos` a `hz`, amplitude 0.3 — nada que doa no ouvido."""
    quadros = int(segundos * taxa)
    with wave.open(caminho, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(taxa)
        amostras = bytearray()
        for i in range(quadros):
            v = int(0.3 * 32767 * math.sin(2 * math.pi * hz * i / taxa))
            amostras += struct.pack("<hh", v, v)
        w.writeframes(bytes(amostras))


def sink_do_alvo(mac: str, macs_na_mesa: list[str]) -> str:
    """O sink de SAÍDA do controle, pela regra do produto — "" quando não dá para saber."""
    try:
        from hefesto_dualsense4unix.app import audio_saida
    except ImportError:
        return ""
    try:
        return audio_saida.sink_do_controle(mac, macs_na_mesa) or ""
    except Exception:
        return ""


def tocar(sink: str, caminho_do_wav: str) -> subprocess.Popen[bytes] | None:
    """`paplay` no sink do controle, em segundo plano. Sem sink, não toca — na TV dela, nunca."""
    if not sink:
        return None
    try:
        return subprocess.Popen(
            ["paplay", f"--device={sink}", caminho_do_wav],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--alvo", help="MAC (inteira ou mascarada) ou nome do hidraw")
    ap.add_argument("--passo", type=int, action="append", choices=sorted(PASSOS))
    ap.add_argument("--segundos", type=float, default=6.0, help="a janela de cada passo")
    ap.add_argument("--alto-falante", default=None,
                    help="fixa o alto-falante neste valor (0..0xFF) em todo passo; "
                         "sem isto o byte dele não é tocado")
    ap.add_argument("--sink", default=None, help="o sink onde tocar o tom (padrão: o do controle)")
    ap.add_argument("--sem-tom", action="store_true", help="não toca nada: ela põe o som")
    ap.add_argument("--uma-vez", action="store_true", help="escreve uma vez por passo, sem martelar")
    ap.add_argument("--hz", type=float, default=10.0, help="o ritmo do martelo")
    args = ap.parse_args()

    aparelhos = alvos_da_mesa()
    if args.listar or not args.alvo:
        print(cabecalho_do_instrumento(
            "o_fone_tem_volume_proprio", "o byte do fone manda sozinho no volume do jack?",
            bibliotecas=["hefesto_dualsense4unix.core.ds_output_report"],
            escreve_no_aparelho=True))
        print("\ncontroles físicos na mesa:")
        print(listar(aparelhos))
        return 0

    alvo = escolher_alvo(aparelhos, args.alvo)
    if alvo is None:
        print(f"alvo {args.alvo!r} não está na mesa. Conhecidos: {[mascarar(a.mac) for a in aparelhos]}")
        return 1
    alto_falante = int(args.alto_falante, 0) if args.alto_falante else None
    passos = sorted(set(args.passo or PASSOS))

    print(cabecalho_do_instrumento(
        "o_fone_tem_volume_proprio", "o byte do fone manda sozinho no volume do jack?",
        bibliotecas=["hefesto_dualsense4unix.core.ds_output_report"],
        escreve_no_aparelho=True))
    print(f"\nalvo ........... {mascarar(alvo.mac)}  {alvo.transporte}  ({alvo.caminho_hidraw})")
    print(f"alto-falante ... {'não tocado' if alto_falante is None else f'fixo em {alto_falante:#04x}'}")
    print(f"martelo ........ {'desligado (uma escrita por passo)' if args.uma_vez else f'{args.hz:g} Hz'}")

    sink = ""
    if alvo.transporte == RADIO:
        print("\nNO RÁDIO NÃO HÁ SINK DE SOM: este instrumento só ESCREVE o 0x31 e não tem o que tocar.")
        print("A orelha dela depende do ensaio 13 do índice do rádio. O que sai daqui é MONTOU.\n")
    elif not args.sem_tom:
        sink = args.sink or sink_do_alvo(alvo.mac, [a.mac for a in aparelhos if a.transporte == CABO])
        print(f"sink do tom .... {sink or 'NÃO SEI — passe --sink <nome> ou --sem-tom'}")
        if not sink:
            return 1

    escritor = Escritor(alvo)
    try:
        print(f"porta .......... {escritor.abrir()}")
    except Exception as erro:
        print(f"sem porta para {mascarar(alvo.mac)}: {erro}")
        return 1

    wav = ""
    respostas: dict[int, str] = {}
    print("\nO RETORNO DO os.write NÃO É A MEDIÇÃO — quem mede é a orelha dela, no fone.\n")
    try:
        if sink:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav = f.name
            escrever_tom(wav, args.segundos + 1.0)
        for passo in passos:
            volume, com_bit, esperado = PASSOS[passo]
            common = common_do_passo(volume, com_bit=com_bit, alto_falante=alto_falante)
            print(f"PASSO {passo} — fone {volume:#04x}, bit {'ligado' if com_bit else 'APAGADO'}")
            print(f"  esperado: {esperado}")
            tocador = tocar(sink, wav) if sink else None
            inicio = time.monotonic()
            if args.uma_vez:
                escritor.escrever(common)
                time.sleep(args.segundos)
                feitas = 1
            else:
                feitas = escritor.martelar(common, args.segundos, hz=args.hz)
            if tocador is not None:
                tocador.terminate()
            print(f"  {feitas} escrita(s) em {time.monotonic() - inicio:.1f} s")
            respostas[passo] = perguntar("  -> o que o fone fez? (verbatim)  ")
    finally:
        # Devolve o fone ao teto com o bit: é o que o produto manda hoje
        # (fone = alto-falante), e deixa o daemon reassumir na próxima escrita dele.
        escritor.escrever(common_do_passo(TETO_HEADPHONE_VOLUME, com_bit=True, alto_falante=None))
        escritor.fechar()
        if wav:
            with contextlib.suppress(OSError):
                os.unlink(wav)
        print("\nfone devolvido ao teto (0x7F), porta fechada.")

    print("\nLINHAS PROPOSTAS PARA O CADERNO (docs/data/ensaios.csv — quem coordena escreve):")
    for passo, resposta in respostas.items():
        volume, com_bit, _ = PASSOS[passo]
        print(linha_do_caderno(
            id=f"fone-volume-proprio-passo{passo}-{time.strftime('%d%m')}",
            linha_id=LINHA_DO_MAPA,
            transporte="cabo" if alvo.transporte == CABO else "radio",
            suspeito="o byte do fone (common[4]) manda sozinho, sem o do alto-falante",
            presente="sim" if com_bit else "não",
            resultado="",
            observado_por="olho-dela",
            fonte="scripts/ensaios/o_fone_tem_volume_proprio.py",
            nota=f"fone {volume:#04x}, bit {'ligado' if com_bit else 'apagado'}, "
                 f"alto-falante {'não tocado' if alto_falante is None else f'{alto_falante:#04x}'}; "
                 f"ela: {resposta or '(sem resposta)'}",
        ))
    print(resumo("o resultado é a orelha dela: preencha `resultado` (obedece / não obedece) por passo."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
