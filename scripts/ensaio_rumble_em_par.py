#!/usr/bin/env python3
"""Dispara rumble em DOIS OU MAIS controles ao mesmo tempo, por evdev.

POR QUE ESTE INSTRUMENTO EXISTE
-------------------------------
Nenhum instrumento desta casa mediu mais de um controle por vez. O
`ensaio_rumble_um_bit_por_vez.py` escreve report cru no hidraw, exige o daemon
parado e mira `achar_fisico()`, que pega o PRIMEIRO DualSense que encontrar. Com
quatro na mesa isso e cego por construcao — e as nove linhas de `familia =
combinacao` do mapa de canais so se respondem com dois ou mais ligados juntos.

O QUE ELE MEDE, E POR QUE ISSO E DIFERENTE
------------------------------------------
Ele dispara forca-feedback (FF) pelo **evdev**, que e o caminho que os JOGOS
usam: o jogo escreve o efeito no no de input, o `hid_playstation` traduz para o
report de saida e o envia no transporte certo (0x02 no cabo, 0x31 com CRC-32 no
radio). Ele NAO passa pelo daemon do Hefesto e NAO disputa o hidraw, entao roda
com o daemon vivo sem contaminar a medicao — ao contrario do ensaio por report
cru, que exige parar o servico.

Isso responde a linha `vibracao.rumble.ff` do mapa, que ate hoje so tinha
`inferido-do-codigo` nos dois transportes.

A FONTE, DECLARADA (a casa exige, e a armadilha ja custou uma sessão inteira)
-----------------------------------------------------------------------------
  biblioteca ...... python-evdev (`import evdev`), a do venv do projeto
  rota ............ evdev FF: EVIOCSFF (upload_effect) + write(EV_FF, id, 1)
  quem monta o report .. o kernel, em `hid_playstation`
  o que NAO e ..... não e hidraw cru, não e sysfs, não e o daemon

O ALVO E EXPLICITO, SEMPRE
--------------------------
não ha descoberta automática de "o controle". Cada alvo entra pelo caminho do
no, e o programa imprime jogador e transporte de cada um antes de vibrar, para
que ninguem confunda qual aparelho respondeu. Ele RECUSA mirar no que não for
DualSense físico: os espelhos `Microsoft X-Box 360 pad` (28de:11ff, Valve) e os
gamepads virtuais tem FF e aceitariam o efeito sem que aparelho nenhum vibrasse.

Uso:
    ensaio_rumble_em_par.py --listar
    ensaio_rumble_em_par.py --alvo /dev/input/event23 --alvo /dev/input/event30 \
        --motor esquerdo --segundos 2
    ensaio_rumble_em_par.py --parar-tudo
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import time

BIBLIOTECA = "python-evdev"
ROTA = "evdev FF (EVIOCSFF) -> hid_playstation -> report de saida"

# Os quatro padrões que o driver produz, do fonte:
# assets/dkms/hid-playstation/hid-playstation.c:1836-1842 (player_ids[5]).
# Sao palindromos; não ha como errar por orientacao.
PADRAO_DO_JOGADOR = {
    "--x--": "P1",
    "-x-x-": "P2",
    "x-x-x": "P3",
    "xx-xx": "P4",
    "xxxxx": "P5",
}

# HID_ID comeca com o barramento: 0003 = USB (cabo), 0005 = Bluetooth (radio).
TRANSPORTE_POR_BARRAMENTO = {"0003": "cabo", "0005": "radio"}

# O espelho que a Steam cria de CADA controle que enxerga. Tem FF e aceitaria o
# efeito calado. Ver docs/protocol/pilha-steam-input-xpad-sdl.md.
VALVE_VID = 0x28DE

DUALSENSE_VID = 0x054C
DUALSENSE_PIDS = (0x0CE6, 0x0DF2)


def _ler(caminho: str) -> str:
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read().strip()
    except OSError:
        return ""


def _hid_pai(caminho_device: str) -> tuple[str, str]:
    """Sobe a arvore ate achar o `uevent` com HID_ID; devolve (barramento, dir)."""
    atual = caminho_device
    for _ in range(6):
        atual = os.path.dirname(os.path.realpath(atual))
        uevent = os.path.join(atual, "uevent")
        if os.path.exists(uevent):
            achado = re.search(r"HID_ID=(\w+):", _ler(uevent))
            if achado:
                return achado.group(1), atual
    return "", ""


def _padrao_do_jogador(dir_hid: str) -> str:
    if not dir_hid:
        return "—"
    nos = sorted(glob.glob(os.path.join(dir_hid, "leds", "*:white:player-*")))
    if not nos:
        return "—"
    desenho = "".join("x" if _ler(os.path.join(no, "brightness")) == "1" else "-" for no in nos)
    return PADRAO_DO_JOGADOR.get(desenho, desenho)


def _tem_ff(dir_device: str) -> bool:
    bits = _ler(os.path.join(dir_device, "capabilities", "ff"))
    return bool(bits) and bits.strip("0 ") != ""


def inventario() -> list[dict[str, object]]:
    """Todos os nos de input com forca-feedback, rotulados e classificados."""
    achados: list[dict[str, object]] = []
    nos = glob.glob("/sys/class/input/event*")
    for no in sorted(nos, key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)))):
        dir_device = os.path.join(no, "device")
        nome = _ler(os.path.join(dir_device, "name"))
        if not nome or not _tem_ff(dir_device):
            continue
        vid = int(_ler(os.path.join(dir_device, "id", "vendor")) or "0", 16)
        pid = int(_ler(os.path.join(dir_device, "id", "product")) or "0", 16)
        virtual = "/devices/virtual/" in os.path.realpath(no)
        barramento, dir_hid = _hid_pai(dir_device)
        # ARMADILHA, paga em 11/08/2026: um DualSense POR BLUETOOTH vive sob
        # `/sys/devices/virtual/misc/uhid/`, porque o BlueZ cria o dispositivo
        # HID por uhid. Filtrar por "não e virtual" recusa METADE da mesa —
        # exatamente os dois controles do radio, que sao o ensaio. O que separa
        # aparelho de espelho e ter HID_ID de barramento conhecido: os espelhos
        # da Steam sao uinput puro e não tem HID_ID nenhum.
        eh_fisico = (
            vid == DUALSENSE_VID
            and pid in DUALSENSE_PIDS
            and barramento in TRANSPORTE_POR_BARRAMENTO
        )
        achados.append(
            {
                "no": f"/dev/input/{os.path.basename(no)}",
                "nome": nome,
                "vid_pid": f"{vid:04x}:{pid:04x}",
                "transporte": TRANSPORTE_POR_BARRAMENTO.get(barramento, "virtual" if virtual else "?"),
                "jogador": _padrao_do_jogador(dir_hid),
                "dualsense_fisico": eh_fisico,
                "espelho_da_steam": vid == VALVE_VID,
            }
        )
    return achados


def imprimir_inventario(itens: list[dict[str, object]]) -> None:
    print(f"instrumento: {BIBLIOTECA} | rota: {ROTA}\n")
    print(f"{'no':22} {'transporte':11} {'jogador':8} {'vid:pid':10} {'mirar?':8} nome")
    print("-" * 108)
    for item in itens:
        if item["dualsense_fisico"]:
            veredito = "SIM"
        elif item["espelho_da_steam"]:
            veredito = "NAO/steam"
        else:
            veredito = "NAO"
        print(
            f"{item['no']:22} {item['transporte']:11} {item['jogador']:8} "
            f"{item['vid_pid']:10} {veredito:8} {item['nome']}"
        )


def _abrir(caminho: str, itens: list[dict[str, object]]):
    import evdev

    achado = next((i for i in itens if i["no"] == caminho), None)
    if achado is None:
        raise SystemExit(f"erro: {caminho} não tem forca-feedback, ou não existe. Use --listar.")
    if achado["espelho_da_steam"]:
        raise SystemExit(
            f"RECUSO mirar {caminho}: e o espelho que a Steam cria ({achado['vid_pid']}, Valve).\n"
            "Ele aceita o efeito e nenhum aparelho vibra — seria medicao falsa. Use --listar."
        )
    if not achado["dualsense_fisico"]:
        raise SystemExit(
            f"RECUSO mirar {caminho}: não e um DualSense físico ({achado['vid_pid']}, "
            f"{achado['nome']}). Use --listar."
        )
    return evdev.InputDevice(caminho), achado


def disparar(alvos: list[str], forte: int, fraco: int, segundos: float) -> int:
    import evdev
    from evdev import ecodes

    itens = inventario()
    abertos = []
    for caminho in alvos:
        abertos.append(_abrir(caminho, itens))

    print(f"instrumento: {BIBLIOTECA} | rota: {ROTA}")
    print(f"efeito: forte(esquerdo)={forte}  fraco(direito)={fraco}  por {segundos}s\n")
    for dispositivo, meta in abertos:
        print(f"  ALVO {meta['no']:22} {meta['jogador']:4} {meta['transporte']:6} {meta['nome']}")
    print()

    efeitos: list[tuple[object, int]] = []
    try:
        for dispositivo, meta in abertos:
            efeito = evdev.ff.Effect(
                ecodes.FF_RUMBLE,
                -1,
                0,
                evdev.ff.Trigger(0, 0),
                evdev.ff.Replay(int(segundos * 1000), 0),
                evdev.ff.EffectType(ff_rumble_effect=evdev.ff.Rumble(forte, fraco)),
            )
            identificador = dispositivo.upload_effect(efeito)
            efeitos.append((dispositivo, identificador))

        # O disparo dos alvos acontece o mais junto possivel: e o que faz deste
        # ensaio um ensaio de COEXISTENCIA, e não dois ensaios em fila.
        instante = time.monotonic()
        for dispositivo, identificador in efeitos:
            dispositivo.write(ecodes.EV_FF, identificador, 1)
        espalhamento_ms = (time.monotonic() - instante) * 1000
        print(f"  disparados em janela de {espalhamento_ms:.1f} ms")
        time.sleep(segundos + 0.2)
    finally:
        # Nunca deixar motor preso. A casa ja pagou por isso.
        for dispositivo, identificador in efeitos:
            try:
                dispositivo.write(ecodes.EV_FF, identificador, 0)
                dispositivo.erase_effect(identificador)
            except OSError:
                pass
        for dispositivo, _ in abertos:
            try:
                dispositivo.close()
            except OSError:
                pass
    print("\nparado. Diga o que sentiu em CADA controle, um por um.")
    return 0


def parar_tudo() -> int:
    """Apaga todo efeito que este processo consiga apagar, em todo alvo valido."""
    import evdev
    from evdev import ecodes

    itens = [i for i in inventario() if i["dualsense_fisico"]]
    for meta in itens:
        try:
            dispositivo = evdev.InputDevice(str(meta["no"]))
        except OSError:
            continue
        try:
            efeito = evdev.ff.Effect(
                ecodes.FF_RUMBLE,
                -1,
                0,
                evdev.ff.Trigger(0, 0),
                evdev.ff.Replay(1, 0),
                evdev.ff.EffectType(ff_rumble_effect=evdev.ff.Rumble(0, 0)),
            )
            identificador = dispositivo.upload_effect(efeito)
            dispositivo.write(ecodes.EV_FF, identificador, 1)
            time.sleep(0.05)
            dispositivo.erase_effect(identificador)
            print(f"  zerado {meta['no']} ({meta['jogador']} {meta['transporte']})")
        except OSError as erro:
            print(f"  falhou em {meta['no']}: {erro}")
        finally:
            dispositivo.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        description="Rumble em dois ou mais controles ao mesmo tempo, por evdev.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analisador.add_argument("--listar", action="store_true", help="mostra os nos e sai")
    analisador.add_argument("--parar-tudo", action="store_true", help="zera o motor de todos")
    analisador.add_argument(
        "--alvo", action="append", default=[], metavar="NO", help="caminho do no (repetivel)"
    )
    analisador.add_argument(
        "--motor",
        choices=("esquerdo", "direito", "ambos", "zero"),
        default="ambos",
        help="esquerdo = so o forte; direito = so o fraco",
    )
    analisador.add_argument("--intensidade", type=int, default=45000, help="0 a 65535")
    analisador.add_argument("--segundos", type=float, default=2.0)
    args = analisador.parse_args(argv)

    try:
        import evdev  # noqa: F401
    except ImportError:
        print(
            "erro: python-evdev não esta neste interpretador.\n"
            "  use: .venv/bin/python scripts/ensaio_rumble_em_par.py ...",
            file=sys.stderr,
        )
        return 2

    if args.listar:
        imprimir_inventario(inventario())
        return 0
    if args.parar_tudo:
        return parar_tudo()
    if not args.alvo:
        print("erro: informe ao menos um --alvo, ou use --listar.", file=sys.stderr)
        return 2

    intensidade = max(0, min(65535, args.intensidade))
    forte = intensidade if args.motor in ("esquerdo", "ambos") else 0
    fraco = intensidade if args.motor in ("direito", "ambos") else 0
    if args.motor == "zero":
        forte = fraco = 0
    return disparar(args.alvo, forte, fraco, args.segundos)


if __name__ == "__main__":
    raise SystemExit(main())
