#!/usr/bin/env python3
"""Fecha a premissa do `keepalive neutro`: o report neutro PARA um motor alheio?"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "ensaios"))
import identidade_do_vpad
from comum import (
    PortaFechadaError,
    abrir_no_hidraw,
    declaracao_da_porta,
    estado_do_grab,
    linha_do_grab,
)

BIBLIOTECA = "python-evdev (EV_FF) + hidraw cru"
MONTAGEM = "_build_common do produto + ds_output_report.build_{usb,bt}_report"

PADRAO_DO_JOGADOR = {
    "--x--": "P1",
    "-x-x-": "P2",
    "x-x-x": "P3",
    "xx-xx": "P4",
    "xxxxx": "P5",
}
TRANSPORTE_POR_BARRAMENTO = {"0003": "cabo", "0005": "radio"}
DUALSENSE = (0x054C, 0x0CE6)

RAIZ_SYSFS_HID = "/sys/bus/hid/devices"


def _ler(caminho: str) -> str:
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read().strip()
    except OSError:
        return ""


def _padrao(dir_hid: str) -> str:
    nos = sorted(glob.glob(os.path.join(dir_hid, "leds", "*:white:player-*")))
    if not nos:
        return "—"
    desenho = "".join("x" if _ler(os.path.join(n, "brightness")) == "1" else "-" for n in nos)
    return PADRAO_DO_JOGADOR.get(desenho, desenho)


def inventario(raiz: str = RAIZ_SYSFS_HID) -> list[dict[str, str]]:
    """Casa jogador -> (nó hidraw, nó evdev, transporte), pelo mesmo device HID.

    VPAD-NO-ESPELHO-01 (12/08/2026): o vpad do PRÓPRIO produto é recusado
    explicitamente, por `identidade_do_vpad`. Hoje ele já não entrava, mas por
    acidente e não por régua: o `DUALSENSE` daqui só aceita `0CE6`, e o vpad se
    apresenta como `0DF2` (DualSense Edge). O Edge REAL existe, e acrescentar o
    PID dele é uma coisa razoável de se querer fazer — no dia em que alguém
    fizer, sem esta linha o inventário passaria a listar os vpads como se
    fossem aparelho, e o ensaio mediria um motor que não existe.
    """
    achados: list[dict[str, str]] = []
    for dir_hid in sorted(glob.glob(os.path.join(raiz, "*"))):
        uevent = _ler(os.path.join(dir_hid, "uevent"))
        casado = re.search(r"HID_ID=(\w+):(\w+):(\w+)", uevent)
        if not casado:
            continue
        barramento, vid, pid = casado.groups()
        if (int(vid, 16), int(pid, 16)) != DUALSENSE:
            continue
        if identidade_do_vpad.e_vpad_do_hefesto(
            identidade_do_vpad.campos_do_uevent(uevent)
        ):
            continue
        hidraws = os.listdir(os.path.join(dir_hid, "hidraw")) if os.path.isdir(
            os.path.join(dir_hid, "hidraw")
        ) else []
        evdev_no = ""
        for entrada in glob.glob(os.path.join(dir_hid, "input", "input*", "event*")):
            capacidade = _ler(os.path.join(os.path.dirname(entrada), "capabilities", "ff"))
            if capacidade and capacidade.strip("0 "):
                evdev_no = "/dev/input/" + os.path.basename(entrada)
                break
        if not hidraws or not evdev_no:
            continue
        achados.append(
            {
                "jogador": _padrao(dir_hid),
                "transporte": TRANSPORTE_POR_BARRAMENTO.get(barramento, "?"),
                "hidraw": "/dev/" + hidraws[0],
                "evdev": evdev_no,
            }
        )
    return achados


def _daemon_vivo() -> bool:
    return os.system("systemctl --user is-active --quiet hefesto-dualsense4unix.service") == 0


def _montar_report_neutro(transporte: str, weak: int, strong: int) -> bytes:
    """O report que o daemon manda no keepalive — montado pelo código dele."""
    from hefesto_dualsense4unix.core import ds_output_report as rep
    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    class _Valor:
        value = 0x00

    class _Luz:
        ledOption = pulseOptions = brightness = playerNumber = _Valor()  # noqa: N815 — nomes do contrato da pydualsense, não nossos
        TouchpadColor = (0, 0, 0)

    class _Gatilho:
        mode = _Valor()
        forces = (0,) * 7

    class _Audio:
        microphone_led = 0
        microphone_mute = 0

    handle = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    handle.leftMotor = handle.rightMotor = 0
    handle._rumble_active = handle._rumble_stop_pending = False
    handle._suppress_leds = True
    handle._volumes_audio = handle._mic_mute_desejado = handle._preamp_audio = None
    handle._raw_trigger_right = handle._raw_trigger_left = None
    handle.light, handle.audio = _Luz(), _Audio()
    handle.triggerR = handle.triggerL = _Gatilho()

    common = handle._build_common(rumble_asserted=False)
    common[2] = weak & 0xFF
    common[3] = strong & 0xFF
    quadro = rep.build_bt_report(common) if transporte == "radio" else rep.build_usb_report(common)
    return bytes(quadro)


def _montar_report_gatilho(transporte: str, lado: str = "esquerdo") -> bytes:
    """Um efeito de gatilho escrito COMO SE FOSSE DE TERCEIRO."""
    from hefesto_dualsense4unix.core import ds_output_report as rep
    from hefesto_dualsense4unix.core.trigger_effects import rigid

    efeito = rigid(3, 8)
    common = bytearray(rep.COMMON_LEN)
    if lado == "direito":
        common[0] = rep.VALID_FLAG0_RIGHT_TRIGGER_FFB
        base = 10
    else:
        common[0] = rep.VALID_FLAG0_LEFT_TRIGGER_FFB
        base = 21
    common[base] = int(efeito.mode) & 0xFF
    for i in range(6):
        common[base + 1 + i] = int(efeito.forces[i]) & 0xFF
    common[base + 9] = int(efeito.forces[6]) & 0xFF
    quadro = rep.build_bt_report(common) if transporte == "radio" else rep.build_usb_report(common)
    return bytes(quadro)


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        description="O report neutro do keepalive para um motor que outro dono ligou?",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analisador.add_argument("--listar", action="store_true")
    analisador.add_argument("--alvo", metavar="P1|P2|P3|P4")
    analisador.add_argument(
        "--fase",
        choices=("para", "liga", "troca-de-lado", "gatilho"),
        default="troca-de-lado",
        help=(
            "`troca-de-lado` (padrão): o EV_FF liga o motor ESQUERDO e o report "
            "neutro pede só o DIREITO. Quem sente não precisa cronometrar — ou o "
            "tremor muda de lado na mão, ou não muda. É o desenho certo, e nasceu "
            "de o anterior exigir cronômetro humano (11/08/2026). "
            "`para`: report neutro com bytes ZERO — mede se ele mata. "
            "`liga`: report neutro com bytes ALTOS no mesmo motor"
        ),
    )
    analisador.add_argument("--antes", type=float, default=6.0, help="segundos antes do report")
    analisador.add_argument("--depois", type=float, default=8.0, help="segundos depois")
    analisador.add_argument(
        "--lado",
        choices=("esquerdo", "direito"),
        default="esquerdo",
        help="qual gatilho autorizar na fase `gatilho`. O outro fica sem bit e serve de controle",
    )
    analisador.add_argument("--confirmo-parar-o-daemon", action="store_true")
    analisador.add_argument(
        "--com-o-daemon-vivo",
        action="store_true",
        help=(
            "não pare o daemon. Só faz sentido na fase `gatilho`, cujo objeto de "
            "medida É a briga entre o keepalive dele e um escritor de fora"
        ),
    )
    args = analisador.parse_args(argv)

    itens = inventario()
    if args.listar:
        print(f"instrumento: {BIBLIOTECA}\nmontagem   : {MONTAGEM}")
        print(declaracao_da_porta() + "\n")
        print(f"{'jogador':9} {'transporte':11} {'hidraw':16} {'evdev':17} grab")
        print("-" * 90)
        for i in itens:
            print(
                f"{i['jogador']:9} {i['transporte']:11} {i['hidraw']:16} "
                f"{i['evdev']:17} {estado_do_grab(i['evdev'])}"
            )
        return 0

    if not args.alvo:
        print("erro: informe --alvo (P1..P4) ou use --listar", file=sys.stderr)
        return 2
    alvo = next((i for i in itens if i["jogador"] == args.alvo.upper()), None)
    if alvo is None:
        print(f"erro: {args.alvo} não está na mesa. Use --listar.", file=sys.stderr)
        return 2

    if _daemon_vivo() and not args.confirmo_parar_o_daemon and not args.com_o_daemon_vivo:
        print(
            "RECUSO rodar com o daemon vivo: ele escreve no mesmo hidraw e a medição\n"
            "sairia contaminada sem erro na tela — foi assim que a casa perdeu uma\n"
            "sessão inteira. Pare com:\n"
            "    systemctl --user stop hefesto-dualsense4unix.service\n"
            "ou passe --confirmo-parar-o-daemon para eu parar e religar sozinha.",
            file=sys.stderr,
        )
        return 5

    religar = False
    if _daemon_vivo() and not args.com_o_daemon_vivo:
        os.system("systemctl --user stop hefesto-dualsense4unix.service")
        religar = True
        time.sleep(2)

    if args.fase == "gatilho":
        report = _montar_report_gatilho(alvo["transporte"], args.lado)
        vivo = _daemon_vivo()
        print(f"instrumento: {BIBLIOTECA}")
        print(f"montagem   : {MONTAGEM}")
        print(f"alvo       : {alvo['jogador']} {alvo['transporte']} {alvo['hidraw']}")
        print(f"daemon     : {'VIVO' if vivo else 'PARADO'}  <- a variável deste ensaio")
        bit = "0x08" if args.lado == "esquerdo" else "0x04"
        base = 21 if args.lado == "esquerdo" else 10
        print(f"efeito     : rigid(3,8) no gatilho {args.lado.upper()} — modo 0x21, "
              f"bloco common[{base}..{base+9}], flag0 {bit}")
        print(f"report     : {len(report)} B, id 0x{report[0]:02x}\n")
        try:
            try:
                escrita = abrir_no_hidraw(alvo["hidraw"], escrita=True)
            except PortaFechadaError as erro:
                print(f"  {erro}", file=sys.stderr)
                return 4
            print(f"  {escrita.linha_de_relatorio}")
            try:
                os.write(escrita.fd, report)
            finally:
                escrita.fechar()
            print(f"  efeito de gatilho ESCRITO. Esperando {args.depois}s antes de você apertar")
            print("  (a espera é de propósito: dá tempo do keepalive agir, se ele agir)")
            time.sleep(args.depois)
        finally:
            if religar:
                os.system("systemctl --user start hefesto-dualsense4unix.service")
                print("\n  daemon religado.")
        print(
            f"\nA PERGUNTA: qual gatilho está DURO — o L2 ou o R2?\n"
            f"  eu autorizei o {args.lado.upper()}. Se endurecer o outro, o mapeamento\n"
            f"  de lado do produto está INVERTIDO, e isso é defeito.\n"
            "  duro  = o efeito sobreviveu; o keepalive não apaga gatilho\n"
            "  solto = o efeito foi apagado — e se a rodada com o daemon PARADO der\n"
            "          duro, o keepalive apaga o gatilho igual apaga o rumble\n"
            "  (o R2 é o controle negativo: tem de estar solto nas duas rodadas)"
        )
        return 0

    import evdev
    from evdev import ecodes

    weak, strong = {
        "para": (0, 0),
        "liga": (0, 200),
        "troca-de-lado": (200, 0),
    }[args.fase]
    report = _montar_report_neutro(alvo["transporte"], weak, strong)

    print(f"instrumento: {BIBLIOTECA}")
    print(f"montagem   : {MONTAGEM}")
    print(f"alvo       : {alvo['jogador']} {alvo['transporte']} {alvo['hidraw']} {alvo['evdev']}")
    print(declaracao_da_porta())
    print(linha_do_grab(alvo["evdev"], estado_do_grab(alvo["evdev"])))
    print(f"fase       : {args.fase}  (report neutro com common[2]={weak}, common[3]={strong})")
    print(f"report     : {len(report)} B, id 0x{report[0]:02x}\n")

    dispositivo = evdev.InputDevice(alvo["evdev"])
    identificador = None
    try:
        duracao_ms = int((args.antes + args.depois + 2) * 1000)
        efeito = evdev.ff.Effect(
            ecodes.FF_RUMBLE, -1, 0,
            evdev.ff.Trigger(0, 0),
            evdev.ff.Replay(duracao_ms, 0),
            evdev.ff.EffectType(ff_rumble_effect=evdev.ff.Rumble(45000, 0)),
        )
        identificador = dispositivo.upload_effect(efeito)
        dispositivo.write(ecodes.EV_FF, identificador, 1)
        print(f"  motor LIGADO por EV_FF; o report neutro sai em {args.antes}s...")
        time.sleep(args.antes)

        escrita = abrir_no_hidraw(alvo["hidraw"], escrita=True)
        print(f"  {escrita.linha_de_relatorio}")
        try:
            os.write(escrita.fd, report)
        finally:
            escrita.fechar()
        print(f"  >>> REPORT NEUTRO ESCRITO agora <<<  (mais {args.depois}s de observação)")
        time.sleep(args.depois)
    finally:
        if identificador is not None:
            try:
                dispositivo.write(ecodes.EV_FF, identificador, 0)
                dispositivo.erase_effect(identificador)
            except OSError:
                pass
        dispositivo.close()
        if religar:
            os.system("systemctl --user start hefesto-dualsense4unix.service")
            print("\n  daemon religado.")

    perguntas = {
        "para": "o motor parou NO MEIO (quando o report saiu), ou seguiu até o fim?",
        "liga": "o motor MUDOU de força quando o report saiu?",
        "troca-de-lado": (
            "o tremor TROCOU DE LADO na sua mão em algum momento?\n"
            "  esquerdo -> direito = o report AGIU, e os BYTES mandam\n"
            "  parou de vez         = o report agiu MATANDO (o strong zerado venceu)\n"
            "  ficou no esquerdo    = o report foi INÓCUO, os bits protegem"
        ),
    }
    print(f"\nA PERGUNTA: {perguntas[args.fase]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
