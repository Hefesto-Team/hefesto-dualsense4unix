#!/usr/bin/env python3
"""o_byte_do_microfone_muda_a_captura.py — o ganho do aparelho, medido no PICO da voz dela.

A PERGUNTA QUE ELE DECIDE (MIC-VOLUME-02, decisão dela de 09/09/2026: *"3-c"*)
--------------------------------------------------------------------------------
O campo `ControllerMicOverride.volume` já TEM ato: `mic.volume.set` mexe no
ganho da FONTE no PipeWire (MIC-VOLUME-01), e a docstring dele afirma que *"o
DualSense não expõe registrador de ganho de microfone em transporte nenhum"*.
O mapa (`audio.microfone.volume@dualsense`) e o kernel desta máquina dizem o
contrário: `common[6]` (`mic_volume`, `0x0 - 0x40`), autorizado por flag0
`0x40`, com porta no produto (`set_audio_volumes(microphone=…)`) e, até este
ensaio, **zero chamadores** — por decisão datada (SOM-SEMPRE-01, 06/09). Duas
afirmações da casa se contradizem, e ela decidiu ligar o byte. **Antes de
ligar, medir.**

**MEDIDO EM 09/09/2026, e a resposta foi «obedece»:** *"Deu certo. funciona"*
(`docs/data/ensaios.csv`, `folha-mic-volume-o-byte-age-cabo-0909`, no CABO).
O byte tem DOIS chamadores desde então — o gesto (`mic.volume.set`) e o perfil
(`apply_profile_mic`) —, e a docstring do `mic.volume.set` que dizia que o
registrador não existe foi corrigida. O que este instrumento ainda decide é o
lado que ninguém mediu: o RÁDIO.

O DESENHO — e a sacada é medir o número, não o adjetivo
--------------------------------------------------------
Ela fala um "aaaa" contínuo no microfone do controle. O byte vai a `0x00`,
`0x20` e `0x40`, e a CADA nível o instrumento grava N segundos da placa do
controle (o mesmo `arecord` e o mesmo analisador do `microfone_no_cabo.py`) e
mede o PICO e o RMS. A fonte no sistema fica onde estiver — o ganho do
sistema é fator comum às três gravações, e um fator comum não muda a razão
entre elas::

    byte 0x00  ->  pico p0
    byte 0x20  ->  pico p1
    byte 0x40  ->  pico p2

    p2 / p0 >= 1,5   -> o byte é ganho de HARDWARE: obedece
    p2 / p0 <  1,5   -> não obedece (a docstring do mic.volume.set estava certa)

O 1,5 é a régua declarada. Ele não é físico: é o mínimo que separa o ganho de
uma variação de voz entre duas gravações. Um resultado entre 1,2 e 1,5 é
"não sei" — e o instrumento diz isso, em vez de arredondar.

E o negativo (`--sem-bit`): `0x40` sem o flag0 `0x40`. Se o pico subir sem o
bit, a autorização não vale nada.

O DAEMON PASSOU A TOCAR NESTE BYTE EM 09/09/2026 — e isto muda como se roda
este instrumento
-------------------------------------------------------------------------
Este bloco dizia *"o daemon NÃO toca neste byte (AUDIO-OWNER-01 apaga os bits
de áudio que não são dele, e o microfone nunca é), então uma escrita basta e
não há martelo"*. **Caducou na mesma semana, por esta medição.** Ela mandou
ligar o byte, e a MIC-VOLUME-02 ligou: `set_microphone_volume` toma a posse do
`common[6]` quando ela mexe no deslizante (`mic.volume.set`) ou quando um
perfil com `mic.volume` é aplicado. A partir daí o `_build_common` manda
aquele byte, com o flag0 `0x40`, em **todo report** — e a escrita deste
instrumento é desfeita pelo keepalive seguinte.

Como se roda depois disso, e é a armadilha de sempre (*o instrumento pode
estar brigando com o produto*):

* **numa sessão em que ninguém mexeu no volume do microfone daquele controle**
  o byte continua sem dono e este instrumento manda sozinho, como antes;
* se alguém mexeu, devolva a posse primeiro — `release_microphone_volume` no
  serviço de saída — ou reconecte o controle. Sem isso, medir aqui é medir a
  disputa, não o aparelho.

O valor fica no firmware até o controle reconectar — o instrumento devolve
`0x40` (o teto) no fim, e `--deixar N` deixa outro.

NO RÁDIO
--------
Não há placa ALSA: a captura vem da fonte que a ponte publica
(`integrations/audio_control.fonte_de_captura_do_controle`). O instrumento
grava por `-D pulse` com `PULSE_SOURCE` nela. Sem ponte de pé, ele diz e para.

Porta: o broker (`comum.abrir_no_hidraw`), com o daemon VIVO. Escreve no
aparelho? SIM — `common[6]` e o flag0 `0x40`.

USO
    o_byte_do_microfone_muda_a_captura.py --listar
    o_byte_do_microfone_muda_a_captura.py --alvo <MAC>              # 0x00, 0x20, 0x40
    o_byte_do_microfone_muda_a_captura.py --alvo <MAC> --sem-bit    # o negativo
    o_byte_do_microfone_muda_a_captura.py --alvo <MAC> --segundos 4 --deixar 0x20
"""

from __future__ import annotations

import argparse
import os
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from comum import CABO, cabecalho_do_instrumento, resumo
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
    COMMON_MIC_VOLUME,
    TETO_MIC_VOLUME,
    VALID_FLAG0_MIC_VOLUME,
)
from microfone_no_cabo import Captura, gravar, placas_de_dualsense

LINHA_DO_MAPA = "audio.microfone.volume@dualsense"
NIVEIS_PADRAO = (0x00, 0x20, 0x40)
RAZAO_QUE_DECIDE = 1.5
RAZAO_DO_NAO_SEI = 1.2


def common_do_nivel(nivel: int, *, com_bit: bool) -> bytearray:
    """SÓ o `common[6]` (e o bit que o autoriza) existem neste common."""
    if not 0 <= nivel <= TETO_MIC_VOLUME:
        raise ValueError(f"volume do mic fora de 0..{TETO_MIC_VOLUME:#x}: {nivel:#x}")
    c = common_vazio()
    c[COMMON_MIC_VOLUME] = nivel
    if com_bit:
        c[0] |= VALID_FLAG0_MIC_VOLUME
    return c


def veredito(capturas: list[tuple[int, Captura]]) -> str:
    """A frase, pela razão entre o maior e o menor pico — com o "não sei" no meio."""
    validas = [(n, c) for n, c in capturas if c.captou]
    if len(validas) < 2:
        return "SEM MEDIÇÃO: menos de duas gravações com voz (fale durante a gravação)"
    menor = min(validas, key=lambda x: x[0])
    maior = max(validas, key=lambda x: x[0])
    if menor[1].pico <= 0:
        return "SEM MEDIÇÃO: o pico do nível mais baixo é zero"
    razao = maior[1].pico / menor[1].pico
    if razao >= RAZAO_QUE_DECIDE:
        return f"OBEDECE: pico {maior[1].pico} a {maior[0]:#04x} contra {menor[1].pico} a {menor[0]:#04x} (x{razao:.2f} >= {RAZAO_QUE_DECIDE})"
    if razao >= RAZAO_DO_NAO_SEI:
        return f"NÃO SEI: x{razao:.2f} fica entre {RAZAO_DO_NAO_SEI} e {RAZAO_QUE_DECIDE} — repita com mais segundos"
    return f"NÃO OBEDECE: x{razao:.2f} (< {RAZAO_DO_NAO_SEI}); o byte não é ganho de hardware"


def _fonte_do_radio() -> str:
    try:
        from hefesto_dualsense4unix.integrations import audio_control
    except ImportError:
        return ""
    try:
        return audio_control.fonte_de_captura_do_controle() or ""
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--alvo", help="MAC (inteira ou mascarada) ou nome do hidraw")
    ap.add_argument("--nivel", type=lambda s: int(s, 0), action="append",
                    help="os níveis do byte (padrão: 0x00, 0x20, 0x40)")
    ap.add_argument("--sem-bit", action="store_true", help="o negativo: 0x40 SEM o flag0 0x40")
    ap.add_argument("--segundos", type=float, default=3.0, help="a gravação de cada nível")
    ap.add_argument("--deixar", type=lambda s: int(s, 0), default=TETO_MIC_VOLUME,
                    help="o valor que fica no fim (padrão: 0x40, o teto)")
    ap.add_argument("--fonte-pulse", default=None, help="força a fonte (PULSE_SOURCE) da gravação")
    args = ap.parse_args()

    aparelhos = alvos_da_mesa()
    pergunta = "o common[6] muda o pico da captura do microfone do controle?"
    if args.listar or not args.alvo:
        print(cabecalho_do_instrumento(
            "o_byte_do_microfone_muda_a_captura", pergunta,
            bibliotecas=["hefesto_dualsense4unix.core.ds_output_report"],
            escreve_no_aparelho=True))
        print("\ncontroles físicos na mesa:")
        print(listar(aparelhos))
        for placa in placas_de_dualsense(aparelhos):
            dono = mascarar(placa.dono.mac) if placa.dono else "sem dono conhecido"
            print(f"  placa {placa.dispositivo:<8} {placa.canais} canais  -> {dono}")
        return 0

    alvo = escolher_alvo(aparelhos, args.alvo)
    if alvo is None:
        print(f"alvo {args.alvo!r} não está na mesa. Conhecidos: {[mascarar(a.mac) for a in aparelhos]}")
        return 1
    niveis = list(args.nivel) if args.nivel else list(NIVEIS_PADRAO)
    com_bit = not args.sem_bit
    if args.sem_bit and not args.nivel:
        niveis = [TETO_MIC_VOLUME]

    print(cabecalho_do_instrumento(
        "o_byte_do_microfone_muda_a_captura", pergunta,
        bibliotecas=["hefesto_dualsense4unix.core.ds_output_report", "microfone_no_cabo"],
        escreve_no_aparelho=True))
    print(f"\nalvo ....... {mascarar(alvo.mac)}  {alvo.transporte}  ({alvo.caminho_hidraw})")

    dispositivo, canais, fonte_pulse = "", 2, ""
    if alvo.transporte == CABO:
        placa = next((p for p in placas_de_dualsense([alvo]) if p.dono is alvo), None)
        if args.fonte_pulse:
            dispositivo, fonte_pulse = "pulse", args.fonte_pulse
        elif placa is None:
            print("a placa ALSA deste controle não apareceu em /proc/asound — cabo de só-carga?")
            return 1
        else:
            dispositivo, canais = placa.dispositivo, placa.canais
    else:
        fonte_pulse = args.fonte_pulse or _fonte_do_radio()
        if not fonte_pulse:
            print("no rádio a captura vem da ponte, e a ponte não publicou fonte nenhuma — levante-a antes.")
            return 1
        dispositivo = "pulse"
    print(f"gravação ... {dispositivo}{f' (PULSE_SOURCE={fonte_pulse})' if fonte_pulse else ''}, {canais} canais, {args.segundos:g} s por nível")
    print(f"bit ........ {'LIGADO' if com_bit else 'APAGADO (o negativo)'}")

    escritor = Escritor(alvo)
    try:
        print(f"porta ...... {escritor.abrir()}")
    except Exception as erro:
        print(f"sem porta para {mascarar(alvo.mac)}: {erro}")
        return 1

    capturas: list[tuple[int, Captura]] = []
    print("\nFALE UM «AAAA» CONTÍNUO NO MICROFONE DO CONTROLE DURANTE CADA GRAVAÇÃO.\n")
    perguntar("  [Enter quando estiver falando]  ")
    try:
        for nivel in niveis:
            escritor.escrever(common_do_nivel(nivel, com_bit=com_bit))
            time.sleep(0.5)
            captura = gravar(dispositivo, args.segundos, canais, f"byte {nivel:#04x}", fonte_pulse=fonte_pulse)
            capturas.append((nivel, captura))
            print(f"byte {nivel:#04x}  bit {'ligado' if com_bit else 'apagado'}  ->  "
                  f"{captura.veredito:<14} pico {captura.pico:>6}  rms {captura.rms:8.1f}"
                  f"{'  ERRO: ' + captura.erro if captura.erro else ''}")
    finally:
        escritor.escrever(common_do_nivel(args.deixar & 0xFF, com_bit=True))
        escritor.fechar()
        print(f"\nbyte deixado em {args.deixar:#04x} com o bit, porta fechada.")

    frase = veredito(capturas)
    print("\nLINHAS PROPOSTAS PARA O CADERNO (docs/data/ensaios.csv — quem coordena escreve):")
    for nivel, captura in capturas:
        print(linha_do_caderno(
            id=f"mic-byte-do-aparelho-{nivel:02x}-{'com' if com_bit else 'sem'}-bit-{time.strftime('%d%m')}",
            linha_id=LINHA_DO_MAPA,
            transporte="cabo" if alvo.transporte == CABO else "radio",
            suspeito="o common[6] (mic_volume, teto 0x40) é ganho de hardware da captura",
            presente="sim" if com_bit else "não",
            resultado="obedece" if frase.startswith("OBEDECE") else ("não obedece" if frase.startswith("NÃO OBEDECE") else ""),
            observado_por="bancada",
            fonte="scripts/ensaios/o_byte_do_microfone_muda_a_captura.py",
            nota=f"byte {nivel:#04x}, pico {captura.pico}, rms {captura.rms:.1f}, {captura.veredito}; {frase}",
        ))
    print(resumo(frase))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
