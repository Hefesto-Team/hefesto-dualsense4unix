#!/usr/bin/env python3
"""Fecha a premissa do `keepalive neutro`: o report neutro PARA um motor alheio?

A PERGUNTA, e por que ela precisa de ensaio próprio
---------------------------------------------------
Em 11/08/2026 ficou medido, por dose-resposta, que o keepalive do daemon cancela
o rumble que chega por EV_FF no no físico: com `OUT_REPORT_KEEPALIVE_SEC` em
0,5 s o motor da um pulso; com 8,0 s ele dura oito segundos exatos.

A cura chamada `keepalive neutro` (GUERRA-01, `core/backend_pydualsense.py:712`)
supoe que desligar os BITS que autorizam vibracao basta para o firmware conservar
o motor. Mas o report continua carregando `common[2] = 0` e `common[3] = 0` — os
bytes sao escritos SEMPRE, fora do `if not rumble_asserted`. A premissa e:
*o firmware honra os bits*. Se ela for falsa, o firmware honra os BYTES, e a cura
inteira e um endereco errado.

Este ensaio decide isso, e a decisão muda o desenho da cura:

  o motor PARA com o report neutro
      -> o firmware obedece aos BYTES. A cura tem de deixar de mandar zeros:
         ou o keepalive não sai quando não ha nada nosso a afirmar, ou ele
         carrega o último valor conhecido em vez de zero.
  o motor CONTINUA
      -> o report neutro e inocente, a premissa se sustenta, e a causa do
         cancelamento e OUTRA escrita — e este ensaio a inocenta por eliminacao.

E ha a metade inversa, que fecha o cerco: com os bits desligados e os bytes
ALTOS, o motor gira? Se girar, o firmware ignora os bits nos dois sentidos.

A FONTE, DECLARADA
------------------
  monta o report ....... `_build_common` do PROPRIO produto, mais
                         `ds_output_report.build_usb_report` / `build_bt_report`
  liga o motor ......... python-evdev, EV_FF — o caminho do jogo
  escreve o report ..... hidraw cru, direto no no do aparelho
  NAO usa .............. o daemon (que tem de estar parado), nem sysfs

Montar o report pelo `_build_common` do produto e deliberado: um report montado
a mão mediria o meu palpite, não o que o daemon manda de verdade.

Uso:
    ensaio_o_keepalive_mata_o_rumble.py --listar
    ensaio_o_keepalive_mata_o_rumble.py --alvo P4 --fase para
    ensaio_o_keepalive_mata_o_rumble.py --alvo P4 --fase liga
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import time

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


def inventario() -> list[dict[str, str]]:
    """Casa jogador -> (nó hidraw, nó evdev, transporte), pelo mesmo device HID."""
    achados: list[dict[str, str]] = []
    for dir_hid in sorted(glob.glob("/sys/bus/hid/devices/*")):
        uevent = _ler(os.path.join(dir_hid, "uevent"))
        casado = re.search(r"HID_ID=(\w+):(\w+):(\w+)", uevent)
        if not casado:
            continue
        barramento, vid, pid = casado.groups()
        if (int(vid, 16), int(pid, 16)) != DUALSENSE:
            continue
        hidraws = os.listdir(os.path.join(dir_hid, "hidraw")) if os.path.isdir(
            os.path.join(dir_hid, "hidraw")
        ) else []
        # O nó de gamepad é o que tem força-feedback; os irmãos (Motion, Touchpad,
        # Headset) não têm, e mirar num deles seria medir o nada.
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
    """O report que o daemon manda no keepalive — montado pelo código dele.

    `rumble_asserted=False` é o estado do keepalive sem rumble nosso: os bits de
    vibração saem DESLIGADOS. Os bytes de motor são preenchidos aqui depois, para
    que o ensaio possa separar o efeito dos BITS do efeito dos BYTES.
    """
    from hefesto_dualsense4unix.core import ds_output_report as rep
    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    class _Valor:
        value = 0x00

    class _Luz:
        ledOption = pulseOptions = brightness = playerNumber = _Valor()
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
    """Um efeito de gatilho escrito COMO SE FOSSE DE TERCEIRO.

    A previsão que este report existe para testar: em 11/08/2026 ficou medido que
    o firmware obedece aos BYTES de motor mesmo com os bits de vibração
    desligados. Os blocos de gatilho — `common[10..20]` (direito) e
    `common[21..31]` (esquerdo) — também são escritos em TODO report do produto,
    fora de qualquer condicional. Se o firmware os tratar do mesmo jeito, o
    keepalive apaga o efeito de gatilho que um jogo aplicou, e ninguém nunca
    mediu isso.

    O efeito é o `rigid(3, 8)` do próprio produto — modo 0x21 (FEEDBACK), forças
    (248, 3, 0, 0, 0, 0, 0) — para que o ensaio meça o que o produto manda, e não
    um bloco que eu inventei.
    """
    from hefesto_dualsense4unix.core import ds_output_report as rep
    from hefesto_dualsense4unix.core.trigger_effects import rigid

    efeito = rigid(3, 8)
    common = bytearray(rep.COMMON_LEN)
    # UM lado por vez, e o outro fica sem bit de autorização — ele é o controle
    # negativo na mesma mão dela. Os offsets vêm de `_build_common` do produto:
    # `common[10]` é o triggerR (direito) e `common[21]` é o triggerL (esquerdo).
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
        print(f"instrumento: {BIBLIOTECA}\nmontagem   : {MONTAGEM}\n")
        print(f"{'jogador':9} {'transporte':11} {'hidraw':16} evdev")
        print("-" * 62)
        for i in itens:
            print(f"{i['jogador']:9} {i['transporte']:11} {i['hidraw']:16} {i['evdev']}")
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

    # A fase `gatilho` é a única que PRECISA poder rodar com o daemon vivo: o que
    # ela mede é justamente a briga entre o keepalive dele e um efeito escrito por
    # terceiro. As outras fases medem o firmware, e ali o daemon só contamina.
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
            with open(alvo["hidraw"], "wb", buffering=0) as fio:
                fio.write(report)
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

    # `troca-de-lado`: o EV_FF liga o ESQUERDO (strong); o report pede só o
    # DIREITO (weak). Nenhuma das duas leituras exige relógio.
    weak, strong = {
        "para": (0, 0),
        "liga": (0, 200),
        "troca-de-lado": (200, 0),
    }[args.fase]
    report = _montar_report_neutro(alvo["transporte"], weak, strong)

    print(f"instrumento: {BIBLIOTECA}")
    print(f"montagem   : {MONTAGEM}")
    print(f"alvo       : {alvo['jogador']} {alvo['transporte']} {alvo['hidraw']} {alvo['evdev']}")
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

        with open(alvo["hidraw"], "wb", buffering=0) as fio:
            fio.write(report)
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
