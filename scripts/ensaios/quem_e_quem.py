#!/usr/bin/env python3
"""quem_e_quem.py — a correspondência MAC ↔ hidraw ↔ evdev ↔ vpad ↔ placa ALSA.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Qual controle físico é qual jogador?* Este instrumento nasceu em 15/08/2026
porque isso **não era observável pelo estado publicado**: o `state_full` trazia
`coop.players` como um NÚMERO (4), não como lista, e a pergunta "o vpad e o
físico correspondem?" só pôde ser respondida apertando botão em cada controle —
quatro vezes, à mão.

FATO SUBSTITUÍDO (15/08/2026, QUEM-ALIMENTA-QUEM-01): o produto passou a
publicar `coop.jogadores` — uma LISTA com, por jogador, o MAC do físico, o
`vpad_uniq` (o MAC forjado `02:fe:…` que o `HID_UNIQ` do vpad carrega) e o
backend. **Com um daemon novo, `hefesto coop status --json` responde a ligação
vpad↔MAC sem apertar nada.** Este instrumento continua valendo por outra razão:
ele mede o aparelho por FORA (sysfs, LED aceso), e é assim que se confere se o
que o daemon PUBLICA bate com o que o kernel MOSTRA.

Este instrumento resolve por sysfs **tudo o que sysfs resolve**, e diz com todas
as letras o que sobra — em vez de deixar o buraco calado, que é o defeito que
ele existe para não repetir.

O QUE ELE RESOLVE SOZINHO, E COMO
----------------------------------
  MAC ↔ hidraw ..... `HID_UNIQ` do `uevent` do device HID pai;
  hidraw ↔ evdev ... os `input*/event*` pendurados no mesmo device;
  hidraw ↔ placa ... o dispositivo USB em comum (interface `:1.0` é o áudio,
                     `:1.3` é o HID; as duas penduram no mesmo `usbN/X-Y`).
                     Só existe no cabo, por construção;
  hidraw ↔ bateria . o nome do `power_supply` carrega o MAC;
  vpad ↔ jogador ... o `HID_NAME`/`HID_UNIQ` que o produto carimba no vpad.

O QUE ELE MEDE E QUASE NINGUÉM PERCEBE QUE DÁ PARA MEDIR
---------------------------------------------------------
**O desenho do player LED sai do sysfs.** O `hid_playstation` publica cada um
dos cinco LEDs em `leds/<...>:white:player-N/brightness`, e o padrão aceso
decodifica direto para o número do jogador que o APARELHO está mostrando:

    00100 = P1     01010 = P2     10101 = P3     11011 = P4

Isso transforma "olhar o controle com o olho e contar as luzinhas" numa
**medição**, e é como este instrumento enxerga, sem pedir nada a ninguém, a
divergência entre o número que o daemon diz e o desenho que ele de fato
escreve — o defeito medido em 15/08/2026, que outro agente está curando em
`src/`. Aqui ele só é OBSERVADO; este instrumento não conserta nada.

O QUE SÓ SE RESOLVE APERTANDO BOTÃO — e por quê
------------------------------------------------
**A ligação vpad ↔ MAC, por SYSFS.** Nenhum arquivo de `/sys` a carrega: o vpad
é criado pelo produto via `/dev/uhid` e não guarda ponteiro para o controle que
o alimenta. (Quem a carrega agora é o daemon, em `coop.jogadores` — ver acima;
o que segue vale para conferir o daemon por fora, ou com ele parado.)

E há um agravante medido: com o co-op ativo, o daemon faz `EVIOCGRAB`
nos nós FÍSICOS, então um leitor externo não vê botão nenhum vindo deles — só
dos vpads. Logo:

  - com o daemon RODANDO: aperte X num controle que você identifica com os
    olhos; o vpad que acender é o dele. Resolve **físico(humano) ↔ vpad**, que
    é o que interessa na prática;
  - com o daemon PARADO: os físicos voltam a falar, e o mesmo aperto resolve
    **MAC ↔ vpad** sem depender de você saber qual controle pegou.

`--apertar` faz esse ensaio e diz, na saída, qual dos dois mundos mediu.

PRECISA DO DAEMON PARADO? Não para a tabela (é tudo sysfs). Para `--apertar`,
leia o parágrafo acima: os dois modos valem, e medem coisas diferentes.

USO
    quem_e_quem.py
    quem_e_quem.py --apertar
"""

from __future__ import annotations

import argparse
import contextlib
import os
import selectors
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    CABO,
    Aparelho,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    estado_do_daemon,
    fisicos,
    ler_texto,
    resumo,
    tabela,
    vpads,
)

# Importado no topo de propósito: o cabeçalho declara de QUAL ARQUIVO veio cada
# biblioteca, e um import preguiçoso lá dentro faria essa linha mentir
# ("NÃO IMPORTADO") justamente no instrumento que existe para não deixar buraco
# calado. Ausente, o `--apertar` cai fora sozinho; a tabela de sysfs não precisa.
try:
    import evdev
    from evdev import ecodes
except ImportError:  # pragma: no cover - só quando falta a dep do projeto
    evdev = None  # type: ignore[assignment]
    ecodes = None  # type: ignore[assignment]

# Os padrões de player LED do DualSense: cinco luzes, e só quatro desenhos
# válidos. Conferidos contra os quatro controles da mesa em 15/08/2026.
DESENHOS_DO_LED = {
    (0, 0, 1, 0, 0): 1,
    (0, 1, 0, 1, 0): 2,
    (1, 0, 1, 0, 1): 3,
    (1, 1, 0, 1, 1): 4,
}


def _placa_alsa_do_usb(usb: str) -> str:
    if not usb:
        return "-"
    for entrada in sorted(os.listdir("/sys/class/sound")):
        if not entrada.startswith("card"):
            continue
        alvo = os.path.realpath(f"/sys/class/sound/{entrada}/device")
        if alvo.startswith(usb + "/") or alvo == usb:
            nome = ler_texto(f"/proc/asound/{entrada}/id").strip()
            return f"{entrada} ({nome})" if nome else entrada
    return "-"


def _dispositivo_usb_pai(caminho: str) -> str:
    atual = os.path.realpath(caminho)
    while atual and atual != "/":
        if os.path.exists(os.path.join(atual, "busnum")):
            return atual
        atual = os.path.dirname(atual)
    return ""


def _nos_de_entrada(aparelho: Aparelho) -> dict[str, str]:
    """{"principal": "/dev/input/eventN", "movimento": ..., ...} deste aparelho."""
    achados: dict[str, str] = {}
    raiz = os.path.join(aparelho.dir_device, "input")
    if not os.path.isdir(raiz):
        return achados
    for entrada in sorted(os.listdir(raiz)):
        dir_input = os.path.join(raiz, entrada)
        if not os.path.isdir(dir_input):
            continue
        nome = ler_texto(os.path.join(dir_input, "name")).strip()
        if "Motion" in nome:
            papel = "movimento"
        elif "Touchpad" in nome:
            papel = "touchpad"
        elif "Headset" in nome:
            papel = "fone"
        else:
            papel = "principal"
        for sub in sorted(os.listdir(dir_input)):
            if sub.startswith("event"):
                achados.setdefault(papel, f"/dev/input/{sub}")
    return achados


def _player_led(aparelho: Aparelho) -> tuple[str, str]:
    """(desenho aceso, jogador que o desenho significa) lido do sysfs."""
    dir_leds = os.path.join(aparelho.dir_device, "leds")
    if not os.path.isdir(dir_leds):
        return "-", "-"
    acesos: list[int] = []
    for numero in range(1, 6):
        achado = [d for d in os.listdir(dir_leds) if d.endswith(f":player-{numero}")]
        if not achado:
            return "-", "-"
        bruto = ler_texto(os.path.join(dir_leds, achado[0], "brightness")).strip()
        acesos.append(1 if bruto not in ("", "0") else 0)
    desenho = "".join(str(x) for x in acesos)
    jogador = DESENHOS_DO_LED.get(tuple(acesos))
    return desenho, (f"P{jogador}" if jogador else "padrão inválido")


def _bateria(aparelho: Aparelho) -> str:
    dir_ps = os.path.join(aparelho.dir_device, "power_supply")
    if not os.path.isdir(dir_ps):
        return "-"
    for entrada in sorted(os.listdir(dir_ps)):
        capacidade = ler_texto(os.path.join(dir_ps, entrada, "capacity")).strip()
        estado = ler_texto(os.path.join(dir_ps, entrada, "status")).strip()
        if capacidade:
            return f"{capacidade}% {estado}".strip()
    return "-"


def tabela_dos_fisicos(alvos: list[Aparelho]) -> list[str]:
    """Imprime a tabela dos controles físicos. Devolve os avisos que achou."""
    cabecalho = [
        "MAC",
        "transporte",
        "hidraw",
        "evdev principal",
        "placa ALSA",
        "LED aceso",
        "LED diz",
        "hardware",
        "bateria",
    ]
    linhas: list[list[str]] = []
    avisos: list[str] = []
    vistos: dict[str, list[str]] = {}

    for aparelho in alvos:
        nos = _nos_de_entrada(aparelho)
        desenho, jogador = _player_led(aparelho)
        if jogador.startswith("P"):
            vistos.setdefault(jogador, []).append(aparelho.mac)
        elif desenho != "-":
            avisos.append(f"{aparelho.mac}: LED em {desenho}, que não é desenho de jogador nenhum")
        linhas.append(
            [
                aparelho.mac or "?",
                aparelho.transporte,
                aparelho.hidraw,
                nos.get("principal", "-"),
                _placa_alsa_do_usb(_dispositivo_usb_pai(aparelho.dir_device))
                if aparelho.transporte == CABO
                else "- (só no cabo)",
                desenho,
                jogador,
                ler_texto(os.path.join(aparelho.dir_device, "hardware_version")).strip() or "-",
                _bateria(aparelho),
            ]
        )
    print()
    print("  OS CONTROLES FÍSICOS")
    print()
    print(tabela(cabecalho, linhas))

    for jogador, macs in sorted(vistos.items()):
        if len(macs) > 1:
            avisos.append(f"{jogador} está aceso em {len(macs)} controles: {', '.join(macs)}")
    return avisos


def tabela_dos_vpads(saidas: list[Aparelho]) -> None:
    cabecalho = ["vpad", "jogador", "hidraw", "evdev principal", "MAC forjado"]
    linhas = [
        [
            v.rotulo,
            v.rotulo,
            v.hidraw,
            _nos_de_entrada(v).get("principal", "-"),
            v.mac or "?",
        ]
        for v in saidas
    ]
    print()
    print("  OS VPADS — a saída do produto, o que o jogo enxerga")
    print()
    print(tabela(cabecalho, linhas))


def ensaio_de_aperto(aparelhos: list[Aparelho], segundos: float) -> None:
    """Resolve, apertando botão, o que o sysfs não liga."""
    if evdev is None:
        print("\n  python-evdev ausente — rode com .venv/bin/python para usar --apertar.")
        return

    daemon = estado_do_daemon()
    print()
    print("  ENSAIO DO APERTO — o que o sysfs não resolve")
    print()
    if daemon.rodando:
        print("  O daemon está RODANDO: os nós FÍSICOS estão sob EVIOCGRAB e não")
        print("  falam com este instrumento. O que este ensaio resolve, então, é")
        print("  FÍSICO(que você identifica com os olhos) ↔ VPAD.")
    else:
        print("  O daemon está PARADO: os nós físicos falam. Este ensaio resolve")
        print("  MAC ↔ VPAD sem depender de você saber qual controle pegou.")
    print()
    print(f"  >> APERTE O BOTÃO X num controle. Esperando {segundos:.0f} s…")
    print()

    seletor = selectors.DefaultSelector()
    dono_do_fd: dict[int, tuple[Aparelho, str]] = {}
    for aparelho in aparelhos:
        caminho = _nos_de_entrada(aparelho).get("principal")
        if not caminho:
            continue
        try:
            dispositivo = evdev.InputDevice(caminho)
        except OSError:
            continue
        seletor.register(dispositivo, selectors.EVENT_READ)
        dono_do_fd[dispositivo.fd] = (aparelho, caminho)

    if not dono_do_fd:
        print("  Nenhum nó principal abriu. Nada a medir.")
        return

    acertos: list[tuple[Aparelho, str]] = []
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        for chave, _ in seletor.select(0.25):
            aparelho, caminho = dono_do_fd[chave.fileobj.fd]
            try:
                eventos = list(chave.fileobj.read())
            except OSError:
                continue
            for evento in eventos:
                pressionou_x = (
                    evento.type == ecodes.EV_KEY
                    and evento.code == ecodes.BTN_SOUTH
                    and evento.value == 1
                )
                if pressionou_x and (aparelho, caminho) not in acertos:
                    acertos.append((aparelho, caminho))
                    marca = "vpad " + aparelho.rotulo if aparelho.e_vpad else aparelho.mac
                    print(f"    X em {marca:<20} ({caminho}, {aparelho.transporte})")

    for chave in list(seletor.get_map().values()):
        with contextlib.suppress(OSError):
            chave.fileobj.close()
    seletor.close()

    print()
    if not acertos:
        print("  Nenhum X apertado — nada resolvido. Repita e aperte durante a janela.")
        return
    dos_vpads = [a for a, _ in acertos if a.e_vpad]
    dos_fisicos = [a for a, _ in acertos if not a.e_vpad]
    if dos_vpads and dos_fisicos:
        print("  RESOLVIDO: o mesmo aperto saiu do físico e do vpad abaixo —")
        for aparelho in dos_fisicos:
            print(f"    físico {aparelho.mac}")
        for aparelho in dos_vpads:
            print(f"    vpad   {aparelho.rotulo}")
        print("  Estes são o mesmo controle.")
    elif dos_vpads:
        print(f"  Só vpad(s) responderam: {', '.join(v.rotulo for v in dos_vpads)}.")
        print("  O controle que você apertou alimenta esse vpad. O MAC dele NÃO foi")
        print("  resolvido por aqui — para isso, pare o daemon e repita.")
    else:
        print(f"  Só físico(s) responderam: {', '.join(a.mac for a in dos_fisicos)}.")


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Quem é quem: MAC, hidraw, evdev, vpad e placa ALSA na mesma tabela.",
    )
    analisador.add_argument(
        "--apertar",
        action="store_true",
        help="ensaio interativo que resolve o que o sysfs não liga",
    )
    analisador.add_argument("--segundos", type=float, default=15.0, help="janela do --apertar")
    argumentos = analisador.parse_args()

    print(
        cabecalho_do_instrumento(
            "quem_e_quem.py",
            "qual controle físico é qual jogador, e o que só se resolve apertando botão?",
            bibliotecas=["evdev", "os"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
        )
    )

    aparelhos = descobrir_aparelhos()
    alvos = fisicos(aparelhos)
    saidas = vpads(aparelhos)
    print(f"\n  {censo_da_mesa(aparelhos)}")
    if not aparelhos:
        print(resumo("nenhum DualSense na mesa — nada a resolver."))
        return 1

    avisos = tabela_dos_fisicos(alvos) if alvos else []
    if saidas:
        tabela_dos_vpads(saidas)

    print()
    print("  O QUE ESTA TABELA NÃO RESOLVE POR SYSFS, e é honesto dizer:")
    print("    - qual vpad é alimentado por qual MAC. Nenhum arquivo de /sys carrega")
    print("      essa ligação. Quem a carrega é o daemon, desde 15/08/2026:")
    print("      `hefesto coop status --json` traz `coop.jogadores` (MAC do físico +")
    print("      `vpad_uniq`). Aqui, use --apertar — ou compare com aquela lista.")

    if avisos:
        print()
        print("  DIVERGÊNCIAS VISTAS NO DESENHO DO PLAYER LED:")
        for aviso in avisos:
            print(f"    - {aviso}")
        print("    (defeito ABERTO, sob cura de outro agente em src/. Aqui só se observa.)")

    if argumentos.apertar:
        ensaio_de_aperto(aparelhos, argumentos.segundos)

    leds = [_player_led(a)[1] for a in alvos]
    validos = [x for x in leds if x.startswith("P")]
    numeros_dos_vpads = sorted(v.rotulo for v in saidas)
    veredito = (
        f"{len(alvos)} físico(s) e {len(saidas)} vpad(s) resolvidos por sysfs; "
        f"LED lido em {len(validos)}/{len(alvos)} ({', '.join(sorted(validos)) or '-'}) "
        f"contra vpads {', '.join(numeros_dos_vpads) or '-'}. "
        "A ligação vpad↔MAC não sai do sysfs: use --apertar, ou "
        "`hefesto coop status --json` (`coop.jogadores`, desde 15/08/2026)."
    )
    print(resumo(veredito))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
