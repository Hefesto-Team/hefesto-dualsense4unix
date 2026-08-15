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
DualSense físico: os espelhos `Microsoft X-Box 360 pad` (28de:11ff, Valve), os
gamepads virtuais de uinput e — desde 12/08/2026 — **os vpads do próprio
Hefesto**, que têm FF e aceitariam o efeito sem que aparelho nenhum vibrasse.

VPAD-NO-ESPELHO-01 (12/08/2026): por que o vpad do produto escapava
-------------------------------------------------------------------
Com quatro controles na mesa, o `--listar` marcava `mirar? SIM` nos QUATRO
vpads do Hefesto, rotulados como transporte `cabo` — a mesma frase acima já
prometia recusá-los, e não recusava::

    /dev/input/event21   cabo   P1  054c:0df2  SIM  DualSense … (Hefesto P1)
    /dev/input/event261  cabo   P4  054c:0df2  SIM  DualSense … (Hefesto P2)

A régua antiga era `vid == 054c and pid in DUALSENSE_PIDS and barramento in
TRANSPORTE_POR_BARRAMENTO`, e o vpad passa nos TRÊS: ele existe justamente
para se passar por aparelho de verdade. Ele forja `054c:0df2` (DualSense Edge,
que está em `DUALSENSE_PIDS` porque o Edge real existe) e declara `BUS_USB`
no `UHID_CREATE2` — logo, barramento `0003`. Quem escapava era só o gamepad de
uinput puro, que não tem `HID_ID` nenhum.

A régua nova pergunta antes **de quem é o device**, e só depois o que ele diz
ser. O critério é o que o PRODUTO carimba de propósito no `UHID_CREATE2`
(`integrations/uhid_gamepad.py::_create2_event`) e que o kernel republica no
`uevent` do device HID pai — o MESMO arquivo que este instrumento já abre para
achar o barramento::

    DRIVER=playstation                       DRIVER=playstation
    HID_ID=0003:0000054C:00000DF2            HID_ID=0005:0000054C:00000CE6
    HID_NAME=DualSense … (Hefesto P1)        HID_NAME=DualSense Wireless Controller
    HID_PHYS=hefesto-vpad          <-- nós    HID_PHYS=<MAC do adaptador>
    HID_UNIQ=02:fe:00:00:00:01     <-- nós    HID_UNIQ=<MAC do controle>

E ela NÃO usa "é virtual", que reintroduziria a armadilha paga em 11/08 (ver
`inventario`): os dois controles do rádio também moram sob
`/sys/devices/virtual/misc/uhid/`, e recusá-los seria recusar metade da mesa.

Uso:
    ensaio_rumble_em_par.py --listar
    ensaio_rumble_em_par.py --alvo /dev/input/event23 --alvo /dev/input/event30 \
        --motor esquerdo --segundos 2
    ensaio_rumble_em_par.py --parar-tudo
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ensaios"))
import time

import identidade_do_vpad
from comum import declaracao_da_porta, estado_do_grab, linha_do_grab

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

#: Onde este instrumento enumera os nós de entrada. É parâmetro só para o teste
#: poder montar uma mesa de mentira em `tmp_path` — a medição de verdade não
#: tem por que apontar para outro lugar.
RAIZ_SYSFS_INPUT = "/sys/class/input"

# --- VPAD-NO-ESPELHO-01: as marcas que o PRODUTO carimba no próprio vpad ----
#
# Contrato de fio replicado aqui de propósito, e não importado: este é um
# instrumento avulso, que tem de rodar mesmo com o pacote quebrado ou fora do
# venv. A mesma decisão que `app/actions/emulation_actions.py` já tomou, e pela
# mesma razão. Quem trava as duas pontas é
# `tests/unit/test_ensaio_em_par_recusa_o_vpad_do_proprio_produto.py`, que
# compara estas constantes com o que o `uhid_gamepad` de fato emite.

#: RÉGUA ÚNICA (12/08/2026): as três marcas e a função que as lê moram em
#: `scripts/identidade_do_vpad.py`, importado também pelos outros dois ensaios.
#: Antes cada instrumento tinha a sua cópia, e a cópia deste era a única que
#: separava o vpad de verdade — os outros dois escapavam POR ACIDENTE, só
#: porque aceitam apenas o PID `0CE6` e o vpad se apresenta como `0DF2`
#: (DualSense Edge). O Edge real existe: no dia em que alguém acrescentar o PID
#: dele, a imunidade por acidente evapora. Reusar em vez de reimplementar é
#: regra desta casa — duas leituras do mesmo dado são duas réguas, e uma delas
#: envelhece calada.
#: Os nomes ficam reexportados porque
#: `tests/unit/test_ensaio_em_par_recusa_o_vpad_do_proprio_produto.py` os le
#: daqui e trava o contrato com o `uhid_gamepad`.
VPAD_HID_PHYS = identidade_do_vpad.VPAD_HID_PHYS
VPAD_UNIQ_PREFIXO = identidade_do_vpad.VPAD_UNIQ_PREFIXO
VPAD_MARCA_NO_NOME = identidade_do_vpad.VPAD_MARCA_NO_NOME


def _ler(caminho: str) -> str:
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read().strip()
    except OSError:
        return ""


def _hid_pai(caminho_device: str) -> tuple[str, str, dict[str, str]]:
    """Sobe a arvore ate o `uevent` com HID_ID; devolve (barramento, dir, campos).

    `campos` são as linhas `CHAVE=valor` desse mesmo `uevent` — de onde saem o
    `HID_PHYS` e o `HID_UNIQ` que separam o vpad do aparelho (ver as constantes
    `VPAD_*`). Ler o arquivo uma vez só e devolver tudo evita que a régua de
    identidade abra um arquivo DIFERENTE do que decidiu o barramento: seriam
    duas fontes podendo discordar sobre o mesmo device.
    """
    atual = caminho_device
    for _ in range(6):
        atual = os.path.dirname(os.path.realpath(atual))
        uevent = os.path.join(atual, "uevent")
        if os.path.exists(uevent):
            texto = _ler(uevent)
            achado = re.search(r"HID_ID=(\w+):", texto)
            if achado:
                campos = dict(
                    linha.split("=", 1) for linha in texto.splitlines() if "=" in linha
                )
                return achado.group(1), atual, campos
    return "", "", {}


def _e_vpad_do_hefesto(campos: dict[str, str], dir_device: str, nome: str) -> bool:
    """True quando o nó é um gamepad virtual DESTE produto (VPAD-NO-ESPELHO-01).

    Delega para `identidade_do_vpad.e_vpad_do_hefesto`, a régua única dos três
    ensaios. A assinatura local sobrevive porque quem chama já tem o diretório
    do nó em mãos e lê o `uniq` dele de graça; o módulo comum aceita esse valor
    em vez de reabrir o arquivo.
    """
    return identidade_do_vpad.e_vpad_do_hefesto(
        campos,
        uniq_do_no=identidade_do_vpad.uniq_do_no_de_entrada(dir_device),
        nome=nome,
    )


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


def inventario(raiz: str = RAIZ_SYSFS_INPUT) -> list[dict[str, object]]:
    """Todos os nos de input com forca-feedback, rotulados e classificados."""
    achados: list[dict[str, object]] = []
    nos = glob.glob(os.path.join(raiz, "event*"))
    for no in sorted(nos, key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)))):
        dir_device = os.path.join(no, "device")
        nome = _ler(os.path.join(dir_device, "name"))
        if not nome or not _tem_ff(dir_device):
            continue
        vid = int(_ler(os.path.join(dir_device, "id", "vendor")) or "0", 16)
        pid = int(_ler(os.path.join(dir_device, "id", "product")) or "0", 16)
        virtual = "/devices/virtual/" in os.path.realpath(no)
        barramento, dir_hid, campos = _hid_pai(dir_device)
        # ARMADILHA, paga em 11/08/2026: um DualSense POR BLUETOOTH vive sob
        # `/sys/devices/virtual/misc/uhid/`, porque o BlueZ cria o dispositivo
        # HID por uhid. Filtrar por "não e virtual" recusa METADE da mesa —
        # exatamente os dois controles do radio, que sao o ensaio. O que separa
        # aparelho de espelho e ter HID_ID de barramento conhecido: os espelhos
        # da Steam sao uinput puro e não tem HID_ID nenhum.
        #
        # VPAD-NO-ESPELHO-01, 12/08/2026: o barramento é condição NECESSÁRIA e
        # não suficiente. O vpad deste produto também nasce por uhid, e declara
        # `BUS_USB` — ele é feito para se passar por aparelho. Por isso a
        # identidade do vpad é perguntada ANTES, e com as marcas que o produto
        # carimba (`_e_vpad_do_hefesto`), nunca com "é virtual".
        eh_vpad = _e_vpad_do_hefesto(campos, dir_device, nome)
        eh_fisico = (
            not eh_vpad
            and vid == DUALSENSE_VID
            and pid in DUALSENSE_PIDS
            and barramento in TRANSPORTE_POR_BARRAMENTO
        )
        # O rótulo de transporte do vpad NÃO é `cabo`. "cabo" e "radio" respondem
        # "por onde o report viaja até o aparelho", e do outro lado do vpad não
        # há aparelho nenhum: o `0003` dele é parte do disfarce, e imprimi-lo
        # como cabo é repetir o disfarce para quem está lendo a mesa.
        if eh_vpad:
            transporte = "vpad"
        else:
            transporte = TRANSPORTE_POR_BARRAMENTO.get(
                barramento, "virtual" if virtual else "?"
            )
        achados.append(
            {
                "no": f"/dev/input/{os.path.basename(no)}",
                "nome": nome,
                "vid_pid": f"{vid:04x}:{pid:04x}",
                "transporte": transporte,
                "jogador": _padrao_do_jogador(dir_hid),
                "dualsense_fisico": eh_fisico,
                "vpad_do_hefesto": eh_vpad,
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
        elif item["vpad_do_hefesto"]:
            veredito = "NAO/vpad"
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
    if achado["vpad_do_hefesto"]:
        raise SystemExit(
            f"RECUSO mirar {caminho}: e um gamepad VIRTUAL do próprio Hefesto "
            f"({achado['vid_pid']}, {achado['nome']}).\n"
            "Ele anuncia 054c:0df2 no barramento do cabo porque foi feito para se "
            "passar por aparelho, mas do outro lado dele não há motor nenhum: o efeito\n"
            "seria aceito em silêncio e a medição sairia falsa. O controle FÍSICO deste "
            "jogador está noutro nó — use --listar e mire nos de `mirar? SIM`."
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
    print(declaracao_da_porta())
    print(f"efeito: forte(esquerdo)={forte}  fraco(direito)={fraco}  por {segundos}s\n")
    for _dispositivo, meta in abertos:
        print(f"  ALVO {meta['no']:22} {meta['jogador']:4} {meta['transporte']:6} {meta['nome']}")
        # O grab do evdev, declarado por alvo: um nó grabado por terceiro pode
        # aceitar o `upload_effect` e não vibrar, e "não vibrou" seria então a
        # resposta errada — não sobre o aparelho, mas sobre quem estava lendo.
        print(f"       {linha_do_grab(str(meta['no']), estado_do_grab(str(meta['no'])))}")
    print()

    efeitos: list[tuple[object, int]] = []
    try:
        for dispositivo, _meta in abertos:
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
            with contextlib.suppress(OSError):
                dispositivo.write(ecodes.EV_FF, identificador, 0)
                dispositivo.erase_effect(identificador)
        for dispositivo, _ in abertos:
            with contextlib.suppress(OSError):
                dispositivo.close()
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
