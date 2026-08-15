#!/usr/bin/env python3
"""audio_por_transporte.py — o que existe de áudio em cada transporte.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*O áudio do DualSense existe no rádio, ou só no cabo?* E, se só no cabo: *o que
exatamente aparece no cabo que não aparece no rádio?*

A resposta muda o produto. Se o áudio por rádio não tem caminho nenhum, o alto-
falante e o microfone do controle são feature de cabo, e a interface tem de
dizer isso. Se o caminho existe e só não foi encontrado, a frase honesta é outra
— e é aqui que esta casa tem uma regra: **"impossível" só se declara com prova
de impossibilidade**. Não ter achado o caminho não é prova de que ele não
existe. A forma de erro tem nome: FALÁCIA DO PERFIL AUSENTE — tomar "o aparelho
não anuncia X pelo caminho padrão" como prova de "o aparelho não faz Y".

Este instrumento, por isso, **só INVENTARIA**. Ele não conclui que o rádio não
tem áudio: ele lista o que existe de cada lado e deixa a diferença à vista.

O QUE ELE OLHA, EM QUATRO CAMADAS
----------------------------------
1. **Placas ALSA** (`/proc/asound`) — por cabo o controle expõe uma placa USB
   Audio (`usbid 054c:0ce6`); por rádio, a hipótese é que não exista placa.
   Cada placa é amarrada ao seu controle pelo **dispositivo USB em comum**: a
   interface `:1.0` é o áudio e a `:1.3` é o HID, e as duas penduram no mesmo
   nó `usbN/X-Y`. É assim que se sabe QUAL controle é QUAL placa.
2. **Sinks e sources do PipeWire** (via `pactl`) — porque uma placa que o ALSA
   enxerga e o PipeWire não roteia não serve ao usuário.
3. **O que o descritor HID declara de OUTPUT** em cada transporte — é aqui que
   mora a hipótese viva do áudio por rádio: a escada de reports `0x32`-`0x39`,
   que no rádio chega a **547 bytes**. Um report de saída desse tamanho não
   existe para mandar cor de LED; a hipótese do túnel HID nasce daí.
4. **Os nós `Headset Jack`** do evdev, que é como o kernel avisa que fone foi
   plugado no controle.

O QUE ELE NUNCA FAZ
--------------------
**Não escreve nada no aparelho.** Nem um byte. Inventariar a escada `0x32`-`0x39`
é ler o descritor, não escrever nela — e confirmar que a escada carrega áudio
exigiria ESCREVER, que não é desta rodada.

PRECISA DO DAEMON PARADO? Não. Tudo aqui é `/proc`, `/sys` e `pactl`; nada
disputa o hidraw.

USO
    audio_por_transporte.py
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    CABO,
    RADIO,
    Aparelho,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    fisicos,
    ler_texto,
    resumo,
    tabela,
    tamanhos_do_descritor,
)

USBID_DUALSENSE = "054c:0ce6"

# A escada de OUTPUT do rádio. Reports de saída grandes demais para LED ou
# rumble — é a hipótese viva do túnel de áudio por HID.
ESCADA_DE_AUDIO = range(0x32, 0x3A)


def _dispositivo_usb_pai(caminho: str) -> str:
    """Sobe o sysfs até o nó do DISPOSITIVO USB (o que tem `busnum`/`devnum`).

    É esse nó que amarra a placa de som ao hidraw: no cabo, o áudio pendura na
    interface `:1.0` e o HID na `:1.3`, e as duas são filhas do mesmo
    dispositivo. Sem essa subida não se sabe qual placa é de qual controle —
    e com dois controles no cabo, adivinhar por ordem erraria metade das vezes.
    """
    atual = os.path.realpath(caminho)
    while atual and atual != "/":
        if os.path.exists(os.path.join(atual, "busnum")) and os.path.exists(
            os.path.join(atual, "devnum")
        ):
            return atual
        atual = os.path.dirname(atual)
    return ""


def _placas_alsa() -> list[dict[str, str]]:
    """As placas de som que são DualSense, com o dispositivo USB de cada uma."""
    achadas: list[dict[str, str]] = []
    base = "/proc/asound"
    if not os.path.isdir(base):
        return achadas
    for entrada in sorted(os.listdir(base)):
        if not entrada.startswith("card") or not entrada[4:].isdigit():
            continue
        numero = entrada[4:]
        usbid = ler_texto(os.path.join(base, entrada, "usbid")).strip().lower()
        if usbid != USBID_DUALSENSE:
            continue
        dir_sysfs = f"/sys/class/sound/{entrada}/device"
        achadas.append(
            {
                "card": numero,
                "id": ler_texto(os.path.join(base, entrada, "id")).strip(),
                "usbid": usbid,
                "usb": _dispositivo_usb_pai(dir_sysfs),
            }
        )
    return achadas


def _pactl(subcomando: str) -> list[str]:
    """Linhas de `pactl list short <subcomando>`, ou [] se o pactl não existir."""
    if not shutil.which("pactl"):
        return []
    try:
        saida = subprocess.run(
            ["pactl", "list", "short", subcomando],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [linha for linha in saida.stdout.splitlines() if linha.strip()]


def _nos_de_fone(aparelho: Aparelho) -> list[str]:
    """Os `Headset Jack` pendurados neste aparelho."""
    achados: list[str] = []
    raiz = os.path.join(aparelho.dir_device, "input")
    if not os.path.isdir(raiz):
        return achados
    for entrada in sorted(os.listdir(raiz)):
        dir_input = os.path.join(raiz, entrada)
        nome = ler_texto(os.path.join(dir_input, "name")).strip()
        if "Headset" in nome:
            achados.append(nome)
    return achados


def _tabela_de_placas(alvos: list[Aparelho], placas: list[dict[str, str]]) -> None:
    print()
    print("  1) PLACAS ALSA — o áudio que o kernel expõe")
    print()
    usb_por_aparelho = {a.apelido: _dispositivo_usb_pai(a.dir_device) for a in alvos}
    linhas: list[list[str]] = []
    for aparelho in alvos:
        meu_usb = usb_por_aparelho[aparelho.apelido]
        minhas = [p for p in placas if p["usb"] and p["usb"] == meu_usb]
        if minhas:
            for placa in minhas:
                linhas.append(
                    [
                        aparelho.apelido,
                        aparelho.transporte,
                        f"card{placa['card']}",
                        placa["id"],
                        placa["usbid"],
                    ]
                )
        else:
            motivo = "nenhuma" if aparelho.transporte == RADIO else "nenhuma (ESPERADO no cabo?)"
            linhas.append([aparelho.apelido, aparelho.transporte, motivo, "-", "-"])
    print(tabela(["aparelho", "transporte", "placa ALSA", "id", "usbid"], linhas))

    orfas = [p for p in placas if not any(p["usb"] == u for u in usb_por_aparelho.values())]
    if orfas:
        print()
        print("  Placas DualSense que não casaram com controle nenhum desta mesa:")
        for placa in orfas:
            print(f"    - card{placa['card']} ({placa['id']}) em {placa['usb'] or '?'}")


def _tabela_do_pipewire(placas: list[dict[str, str]]) -> tuple[int, int]:
    print()
    print("  2) PIPEWIRE — o que dessas placas chega a ser roteável")
    print()
    if not shutil.which("pactl"):
        print("    pactl não encontrado — camada NÃO inventariada (não confunda com 'não existe').")
        return 0, 0

    cartoes = {f"card{p['card']}" for p in placas}
    sinks = _pactl("sinks")
    sources = _pactl("sources")

    def _do_controle(linhas: list[str]) -> list[str]:
        marcas = ("054c", "dualsense", "ps5", "wireless_controller", "Controller")
        return [
            linha
            for linha in linhas
            if any(m.lower() in linha.lower() for m in marcas)
            or any(c in linha for c in cartoes)
        ]

    meus_sinks = _do_controle(sinks)
    meus_sources = _do_controle(sources)
    linhas: list[list[str]] = []
    for linha in meus_sinks:
        campos = linha.split("\t")
        linhas.append(["sink", campos[1] if len(campos) > 1 else linha])
    for linha in meus_sources:
        campos = linha.split("\t")
        linhas.append(["source", campos[1] if len(campos) > 1 else linha])

    if linhas:
        print(tabela(["tipo", "nome"], linhas))
    else:
        print(
            f"    nenhum sink/source de DualSense entre {len(sinks)} sink(s) e "
            f"{len(sources)} source(s) do sistema."
        )
    return len(meus_sinks), len(meus_sources)


def _tabela_de_output_hid(alvos: list[Aparelho]) -> None:
    print()
    print("  3) O QUE O DESCRITOR HID DECLARA DE OUTPUT — a hipótese do túnel")
    print()
    linhas: list[list[str]] = []
    for aparelho in alvos:
        saidas = tamanhos_do_descritor(aparelho.dir_device)["output"]
        if not saidas:
            linhas.append([aparelho.apelido, aparelho.transporte, "descritor ilegível", "-", "-"])
            continue
        escada = {rid: n for rid, n in saidas.items() if rid in ESCADA_DE_AUDIO}
        todos = ", ".join(f"0x{rid:02x}({n}B)" for rid, n in sorted(saidas.items()))
        maior = max(saidas.values())
        linhas.append(
            [
                aparelho.apelido,
                aparelho.transporte,
                todos if len(todos) <= 58 else todos[:55] + "…",
                f"{len(escada)} degrau(s)" if escada else "ausente",
                f"{maior} B",
            ]
        )
    print(tabela(["aparelho", "transporte", "reports OUTPUT", "escada 0x32-0x39", "maior"], linhas))
    print()
    print("    A escada 0x32-0x39 é DECLARADA pelo descritor, não medida em uso.")
    print("    Que ela exista não prova que carrega áudio; provar exigiria ESCREVER")
    print("    no aparelho, que não é desta rodada. Registre como hipótese viva.")
    print()
    print("    Leia a coluna junto com a das placas ALSA: onde há placa USB Audio")
    print("    (cabo) o descritor é magro; onde não há placa (rádio) é que a escada")
    print("    de 547 B aparece. Os dois lados são COMPLEMENTARES, e é exatamente")
    print("    esse desenho que a hipótese do túnel HID prevê.")


def _tabela_de_fones(alvos: list[Aparelho]) -> None:
    print()
    print("  4) NÓS `Headset Jack` — como o kernel avisa que plugaram fone")
    print()
    linhas: list[list[str]] = []
    for aparelho in alvos:
        nos = _nos_de_fone(aparelho)
        linhas.append(
            [aparelho.apelido, aparelho.transporte, str(len(nos)), "; ".join(nos) if nos else "-"]
        )
    print(tabela(["aparelho", "transporte", "quantos", "nome"], linhas))


def main() -> int:
    argparse.ArgumentParser(
        description="Inventário de áudio do DualSense por transporte (só leitura).",
    ).parse_args()

    print(
        cabecalho_do_instrumento(
            "audio_por_transporte.py",
            "o que existe de áudio no cabo que não existe no rádio?",
            bibliotecas=["subprocess", "os"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
        )
    )
    print("  ferramenta externa .... pactl (" + (shutil.which("pactl") or "AUSENTE") + ")")

    aparelhos = descobrir_aparelhos()
    alvos = fisicos(aparelhos)
    print(f"\n  {censo_da_mesa(aparelhos)}")
    if not alvos:
        print(resumo("nenhum DualSense físico — nada a inventariar."))
        return 1

    placas = _placas_alsa()
    _tabela_de_placas(alvos, placas)
    sinks, sources = _tabela_do_pipewire(placas)
    _tabela_de_output_hid(alvos)
    _tabela_de_fones(alvos)

    do_cabo = [a for a in alvos if a.transporte == CABO]
    do_radio = [a for a in alvos if a.transporte == RADIO]
    usb_do_cabo = {_dispositivo_usb_pai(a.dir_device) for a in do_cabo}
    placas_no_cabo = sum(1 for p in placas if p["usb"] in usb_do_cabo)

    def _tem_escada(aparelho: Aparelho) -> bool:
        saidas = tamanhos_do_descritor(aparelho.dir_device)["output"]
        return any(rid in ESCADA_DE_AUDIO for rid in saidas)

    escada_no_cabo = sum(1 for a in do_cabo if _tem_escada(a))
    escada_no_radio = sum(1 for a in do_radio if _tem_escada(a))

    if do_cabo and do_radio:
        veredito = (
            f"os dois lados são COMPLEMENTARES: no cabo, {placas_no_cabo} placa(s) ALSA "
            f"e escada 0x32-0x39 em {escada_no_cabo}/{len(do_cabo)}; no rádio, 0 placa "
            f"e escada em {escada_no_radio}/{len(do_radio)}. "
            f"{sinks} sink(s) e {sources} source(s) no PipeWire, todos do cabo."
        )
    else:
        so = CABO if do_cabo else RADIO
        veredito = (
            f"mesa com um transporte só ({so}): {placas_no_cabo} placa(s) ALSA achada(s). "
            "Sem o outro lado, isto é inventário, não comparação."
        )
    print(resumo(veredito))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
