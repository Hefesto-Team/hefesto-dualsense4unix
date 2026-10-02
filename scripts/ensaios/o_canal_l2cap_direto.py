#!/usr/bin/env python3
"""o_canal_l2cap_direto.py — o report de saída por SOCKET L2CAP, sem passar pelo hidraw.

A PERGUNTA QUE ELE DECIDE
--------------------------
**O firmware do DualSense trata diferente um report que chega por L2CAP direto
e um que chega pelo HIDP do kernel?**

Ela nasceu de uma ressalva que esta casa escreveu e nunca atacou —
`integrations/alto_falante_bt.py`, ressalva (c) do achado do alto-falante:

    *"o DS5Dongle é um DONGLE — fala L2CAP direto e nunca toca `/dev/hidraw`.
     Ele prova «report HID de saída», não «hidraw»."*

**A fonte que documentou o protocolo do alto-falante nunca usou o caminho que
esta casa usa.** Todas as passadas daqui — as seis de 08/09, os seis cruzamentos
de 10/09 — foram por `/dev/hidraw`, onde quem manda no MTU, no enquadramento e
no canal é o BlueZ. Ninguém desta casa mandou um byte por socket L2CAP.

O QUE A MEDIÇÃO DELA DE 10/09/2026 DEIXOU DE PÉ, e é o que torna este ensaio o
próximo
--------------------------------------------------------------------------------
Com dois controles na mesa, um no cabo e um no rádio, ela mediu:

* o tom pelo CABO — **ouviu**. O instrumento não é mudo;
* o `0x31` de COR pelo rádio, nos **DOIS** envelopes (`write()` no canal de
  interrupção e `HIDIOCSOUTPUT` no de controle) — **a barra acendeu nos dois**;
* os seis cruzamentos de áudio (3 arranjos × 2 envelopes) — **silêncio nos seis**.

Logo: **não é o envelope, não é o CRC, não é o canal.** Os dois envelopes chegam
ao firmware e ele os obedece. O que ele recusa é o bloco de áudio de saída.

E a direção contrária já funciona: o microfone por rádio entrega voz desde
25/07/2026 (`integrations/dualsense_bt_audio.py`), com Opus dentro do mesmo HID.
O cano existe nas duas direções.

O DESENHO — o POSITIVO primeiro, e ele é o mesmo que ela já viu acender
-----------------------------------------------------------------------
Este ensaio **não manda áudio**. Ele manda o `0x31` de COR — o report que ela
acabou de ver acender pelo hidraw — pelo caminho novo. A ordem importa:

1. **conectar** um socket L2CAP ao controle no PSM de interrupção (`0x13`).
   Se nem conectar, o resto não se mede;
2. **a mesma cor, pelo canal novo.** Se a barra acender, o caminho L2CAP
   direto está aberto e serve; se não acender, o caminho está fechado e o
   áudio não vai por aqui tampouco.

**Sem o passo 2 dando positivo, um silêncio de áudio por L2CAP não diria nada** —
seria a mesma armadilha do tom mudo que a folha do som evita pondo o cabo ao lado.

O QUE MUDA NO PACOTE, e é UM byte
----------------------------------
Pelo hidraw, o kernel HIDP escreve o cabeçalho `0xA2` (DATA | OUTPUT) e ele é
invisível a quem escreve. Aqui não há HIDP: **o `0xA2` é nosso**. O CRC não muda
— `bt_crc32` já usa `seed=0xA2` justamente porque esse byte entra na conta.

    pelo hidraw:  write(fd, [0x31][seq][common…][CRC])
    por L2CAP:    send(sk, [0xA2][0x31][seq][common…][CRC])

DOIS DEGRAUS, E O SEGUNDO CUSTA O CONTROLE DELA
------------------------------------------------
* **degrau A (`--conectar`)** — abre um SEGUNDO canal no mesmo PSM, com o BlueZ
  ainda conectado. Não derruba nada. Pode ser recusado pelo firmware, e a
  recusa é resultado: diz que o controle só aceita um canal por PSM;
* **degrau B (`--assumir-o-canal`)** — desconecta o perfil de input do BlueZ
  antes de abrir. **O controle SOME como gamepad enquanto o ensaio corre**, e
  volta com `--devolver`. Só com ela sabendo, e nunca no meio de um jogo.

ESCREVE NO APARELHO? Só com `--acender`. Sem ele, este ensaio conecta, mede o
que o socket aceitou e não manda byte nenhum.

USO
    o_canal_l2cap_direto.py --listar       # a mesa e o que este ensaio faria
    o_canal_l2cap_direto.py --conectar     # degrau A: só abre o canal e mede
    o_canal_l2cap_direto.py --conectar --acender   # e manda a cor pelo canal novo
    o_canal_l2cap_direto.py --assumir-o-canal --acender   # degrau B
    o_canal_l2cap_direto.py --devolver     # devolve o controle ao BlueZ
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import hefesto_dualsense4unix.core.ds_output_report as rep
from comum import RADIO, cabecalho_do_instrumento, descobrir_aparelhos, fisicos, resumo

from o_envelope_do_som_no_radio import common_vazio, report_de_cor

import hefesto_dualsense4unix.integrations.alto_falante_bt as af
from a_folha_do_som_por_controle import ms_por_report, pacotes_do_tom

PSM_CONTROLE = 0x11
PSM_INTERRUPCAO = 0x13

HIDP_DATA_OUTPUT = 0xA2

SOL_L2CAP = 6
L2CAP_OPTIONS = 0x01

COR_AZUL = (0, 0, 255)


def mascarar(mac: str) -> str:
    """Os octetos 4 e 5 zerados — a máscara desta casa, e ela vale na tela também."""
    partes = mac.split(":")
    if len(partes) != 6:
        return mac
    return ":".join([partes[0], partes[1], partes[2], "00", "00", partes[5]])


def o_controle_no_radio() -> object | None:
    """O DualSense do rádio. Um só: com dois, o ensaio não sabe de quem é a luz."""
    reais = [a for a in fisicos(descobrir_aparelhos()) if a.transporte == RADIO]
    if len(reais) != 1:
        return None
    return reais[0]


def perfil_de_input(mac: str, ligar: bool) -> str:
    """Liga ou desliga o perfil de input do BlueZ para este controle."""
    acao = "connect" if ligar else "disconnect"
    try:
        saida = subprocess.run(
            ["bluetoothctl", acao, mac],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        return f"não consegui falar com o bluetoothctl: {erro}"
    if saida.returncode != 0:
        return (saida.stderr or saida.stdout or "").strip()[:200]
    return ""


def subir_o_mtu(sk: object, mtu: int) -> str:
    """Sobe `imtu`/`omtu` do canal — o botão que o perfil de input do BlueZ não toca."""
    import struct

    FORMA = "<HHHBBBxH"
    try:
        crua = sk.getsockopt(SOL_L2CAP, L2CAP_OPTIONS, struct.calcsize(FORMA))  # type: ignore[attr-defined]
        omtu, imtu, flush_to, modo, fcs, max_tx, txwin = struct.unpack(FORMA, crua)
        nova = struct.pack(FORMA, mtu, mtu, flush_to, modo, fcs, max_tx, txwin)
        sk.setsockopt(SOL_L2CAP, L2CAP_OPTIONS, nova)  # type: ignore[attr-defined]
        return f"MTU {omtu}/{imtu} -> {mtu}/{mtu}"
    except OSError as erro:
        return f"NÃO subiu o MTU ({erro.__class__.__name__} {erro.errno}) — segue no padrão"


def abrir_canal(mac: str, psm: int, mtu: int = 0) -> tuple[object | None, str]:
    """Um socket L2CAP para o controle, no PSM pedido."""
    try:
        sk = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    except (AttributeError, OSError) as erro:
        return None, f"este Python não abre socket L2CAP: {erro}"
    recado = ""
    try:
        sk.settimeout(10.0)
        if mtu:
            recado = subir_o_mtu(sk, mtu)
        sk.connect((mac, psm))
    except OSError as erro:
        sk.close()
        return None, f"{erro.__class__.__name__} {erro.errno} — {erro.strerror or erro}"
    return sk, recado


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--listar", action="store_true", help="só lê: a mesa e o que ele faria")
    ap.add_argument("--conectar", action="store_true", help="degrau A: abre o canal com o BlueZ de pé")
    ap.add_argument("--assumir-o-canal", action="store_true",
                    help="degrau B: desconecta o perfil de input ANTES (o controle some)")
    ap.add_argument("--acender", action="store_true", help="manda o 0x31 de COR pelo canal aberto")
    ap.add_argument("--devolver", action="store_true", help="devolve o controle ao BlueZ e sai")
    ap.add_argument("--tocar", metavar="ARRANJO", nargs="?", const="__todos__",
                    help="a rajada de áudio pelo canal direto: um arranjo, ou todos")
    ap.add_argument("--mtu", type=int, default=0,
                    help="sobe imtu/omtu antes de conectar (o dongle usa 1024)")
    ap.add_argument("--segundos", type=float, default=3.0,
                    help="quanto tempo a cor fica acesa antes de devolver — ela precisa OLHAR")
    ap.add_argument("--psm", type=lambda s: int(s, 0), default=PSM_INTERRUPCAO,
                    help="0x13 interrupção (padrão) ou 0x11 controle")
    args = ap.parse_args()

    alvo = o_controle_no_radio()
    escreve = bool(args.acender or args.tocar)
    print(cabecalho_do_instrumento(
        "o_canal_l2cap_direto",
        "o firmware trata diferente um report que chega por L2CAP direto e um que vem do HIDP?",
        bibliotecas=["hefesto_dualsense4unix.core.ds_output_report"],
        escreve_no_aparelho=escreve))
    print(f"  porta ............ socket L2CAP (AF_BLUETOOTH), PSM {args.psm:#04x} "
          f"— NAO e o hidraw".replace("NAO e", "NÃO é"))

    if alvo is None:
        print(resumo("preciso de EXATAMENTE UM DualSense no rádio — com dois, "
                     "não sei de quem é a luz que acender."))
        raise SystemExit(1)
    mac = alvo.mac
    print(f"o controle do rádio: {mascarar(mac)}\n")

    if args.devolver:
        erro = perfil_de_input(mac, ligar=True)
        print(resumo(erro or f"perfil de input devolvido ao BlueZ para {mascarar(mac)}"))
        raise SystemExit(1 if erro else 0)

    if args.listar or not (args.conectar or args.assumir_o_canal):
        print("O QUE ESTE ENSAIO FARIA, na ordem:")
        print(f"  1. socket L2CAP para {mascarar(mac)} no PSM {args.psm:#04x}")
        print(f"  2. o MESMO 0x31 de cor AZUL que acendeu pelo hidraw, com o "
              f"{HIDP_DATA_OUTPUT:#04x} escrito por nós")
        print("  3. ela olha a barra e diz")
        print("\n  o degrau A (--conectar) não derruba nada.")
        print("  o degrau B (--assumir-o-canal) TIRA o controle dela enquanto corre.")
        print(resumo("leitura pura — nenhum socket aberto, nenhum byte escrito."))
        return

    if args.assumir_o_canal:
        print("DESCONECTANDO o perfil de input — o controle vai sumir do sistema…")
        erro = perfil_de_input(mac, ligar=False)
        if erro:
            print(resumo(f"não consegui desconectar o perfil: {erro}"))
            raise SystemExit(1)
        time.sleep(2.0)

    sk, erro = abrir_canal(mac, args.psm, mtu=args.mtu)
    if sk is None:
        print(f"O CANAL NÃO ABRIU: {erro}")
        print(resumo("o canal L2CAP direto não abriu — e o porquê está na linha acima. "
                     "Se foi EPERM, falta privilégio e nada se mediu do aparelho."))
        raise SystemExit(1)

    print(f"O CANAL ABRIU — socket L2CAP para {mascarar(mac)} no PSM {args.psm:#04x}")
    if erro:
        print(f"  {erro}")
    try:
        if args.tocar:
            nomes = (list(af.ARRANJO_POR_NOME) if args.tocar == "__todos__"
                     else [args.tocar])
            desconhecidos = [n for n in nomes if n not in af.ARRANJO_POR_NOME]
            if desconhecidos:
                print(resumo(f"arranjo que o produto não conhece: {desconhecidos} — "
                             f"os que existem: {', '.join(af.ARRANJO_POR_NOME)}"))
                raise SystemExit(1)
            for nome in nomes:
                common = af.common_de_audio(
                    volume=af.VOLUME_QUE_ELA_OUVIU,
                    rota=rep.SAIDA_SO_NO_ALTO_FALANTE,
                    preamp=rep.SP_PREAMP_GAIN_PADRAO,
                )
                pacotes = pacotes_do_tom(nome, segundos=args.segundos, common=common,
                                         crc_errado=False, seq0=1)
                intervalo = ms_por_report(nome) / 1000.0
                print(f"\n  {nome}: {len(pacotes)} report(s) de {len(pacotes[0])} B, "
                      f"um a cada {intervalo * 1000:.0f} ms", flush=True)
                print(f"  >>> OUÇA O ALTO-FALANTE DO CONTROLE — {args.segundos:g} s", flush=True)
                recusas = 0
                for pkt in pacotes:
                    try:
                        sk.send(bytes([HIDP_DATA_OUTPUT]) + pkt)
                    except OSError as erro_envio:
                        recusas += 1
                        if recusas == 1:
                            print(f"  RECUSA: {erro_envio.__class__.__name__} "
                                  f"{erro_envio.errno} — {erro_envio.strerror}")
                            break
                    time.sleep(intervalo)
                print(f"  {len(pacotes) - recusas} enviados, {recusas} recusa(s)")
                time.sleep(1.0)
            print(resumo("os reports de áudio SAÍRAM pelo socket L2CAP direto — o mesmo "
                         "canal em que a cor acendeu. Se ela ouviu, o caminho é este; "
                         "se não ouviu, o canal não era a parede e a recusa é do "
                         "FORMATO do bloco de áudio."))
            return
        if not args.acender:
            print(resumo("o canal abriu e NADA foi escrito. Rode com --acender para "
                         "mandar a cor por ele."))
            return
        pacote = bytes([HIDP_DATA_OUTPUT]) + report_de_cor(*COR_AZUL, seq=1)
        enviados = sk.send(pacote)
        print(f"ESCREVI {enviados} B pelo canal novo "
              f"({HIDP_DATA_OUTPUT:#04x} + report 0x31 de {len(pacote) - 1} B)")
        print(f"\n  >>> OLHE A BARRA DE LUZ DO CONTROLE pelos próximos "
              f"{args.segundos:g} s. Ela ficou AZUL?", flush=True)
        fim = time.monotonic() + args.segundos
        seq = 1
        while time.monotonic() < fim:
            time.sleep(0.1)
            seq = (seq + 1) % 16
            sk.send(bytes([HIDP_DATA_OUTPUT]) + report_de_cor(*COR_AZUL, seq=seq))
        vazio = bytes([HIDP_DATA_OUTPUT]) + bytes(rep.build_bt_report(common_vazio(), seq=(seq + 1) % 16))
        sk.send(vazio)
        print("  (devolvido: common vazio, o daemon repinta em ~100 ms)")
        print(resumo("o byte SAIU pelo socket L2CAP. Se a barra acendeu, o caminho "
                     "direto serve e o áudio pode ir por ele; se não acendeu, o "
                     "firmware distingue os dois caminhos — e isso é o achado."))
    finally:
        sk.close()
        if args.assumir_o_canal:
            print("\ndevolvendo o perfil de input ao BlueZ…")
            print(perfil_de_input(mac, ligar=True) or "  devolvido.")


if __name__ == "__main__":
    main()
