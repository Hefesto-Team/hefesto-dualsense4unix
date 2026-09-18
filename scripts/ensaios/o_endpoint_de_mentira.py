#!/usr/bin/env python3
"""O endpoint de mentira — HAPTICA-POR-RADIO-01, P3.

PELO CABO o jogo acha a háptica porque existe uma placa de áudio de verdade no
controle. PELO RÁDIO não existe: o DualSense não publica endpoint nenhum, e o
jogo não tem onde tocar os canais 3 e 4. Este ensaio monta o endpoint que falta
— um ``module-null-sink`` do PipeWire vestido de DualSense — e MEDE, campo a
campo, o que o GE-Proton leria dele.

POR QUE ISTO BASTA (lido no fonte, 18/09/2026)
-----------------------------------------------
``wine/dlls/winepulse.drv/pulse.c``:

* ``fill_device_info`` (:668) lê barramento, fabricante e produto **do proplist
  do sink** — ``device.bus``, ``device.vendor.id``, ``device.product.id``. Não
  pergunta ao sysfs;
* ``get_container_id`` (:608) só é chamado quando o proplist traz
  ``sysfs.path``; ele sobe ao pai ``usb_device`` no udev e compõe o GUID com
  ``PRODUCT``, ``BUSNUM``, ``DEVNUM`` e ``USEC_INITIALIZED`` **daquele pai**.
  Sem pai USB, devolve ``GUID_NULL``.

Patches ``proton-ds5-haptic``:

* ``is_dualsense_audio_device`` (0063): ``bus == usb && vid == 0x054c && pid in
  (0x0ce6, 0x0df2)`` — tudo do proplist;
* ``is_dualsense_haptic_format`` (0063): ``eRender``, ``FLOAT32LE``, 48 kHz,
  **4 canais**;
* ``pulse_name_looks_like_dualsense_speaker_sink`` (0060): o NOME tem de conter
  ``alsa_output.usb-Sony_Interactive_Entertainment_``, ``Wireless_Controller``
  e ``Speaker__sink``;
* ``is_dualsense_backend_name`` (mmdevapi): ``Sony_Interactive_Entertainment``
  no nome.

**Nada disso pergunta pelo transporte do CONTROLE.** O que o GE inspeciona é o
SINK — e um sink é coisa que o PipeWire monta sem root, sem módulo de kernel e
sem gadget USB. É por isso que o gadget (``usbip-vudc``) deixa de ser
necessário: ele existia para produzir estes mesmos campos.

A ÂNCORA, E POR QUE NÃO SE DEIXA O ``ContainerId`` ZERADO
----------------------------------------------------------
Zerado *funciona* do ponto de vista do casamento — basta o device KS do
prefixo declarar zero também. Mas zero **não é único**: toda saída que não é
USB tem o ``ContainerId`` zerado, e um device KS declarando zero casaria também
com a caixa de som da pessoa. O jogo abriria a háptica no aparelho errado.

Então o sink aponta o ``sysfs.path`` para um ``usb_device`` REAL que não tem
placa de som — uma ÂNCORA. O GUID que sai dali é real, é único e é calculável
dos dois lados: aqui, e no ``audio_ks_dualsense.py``, que grava o device KS.
A âncora é só um endereço de onde tirar quatro números; nada é escrito nela.

O QUE ESTE ENSAIO NÃO DECIDE
-----------------------------
Se a RE Engine ACEITA este endpoint. Isso é medida de bancada, com o jogo
aberto e o controle no rádio, e está escrita na sprint. Aqui se mede só o que é
medível sem o jogo: que os campos chegam ao nó como o GE os lê.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
if str(_RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(_RAIZ / "src"))

from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl

#: O VID/PID que o GE exige NO PROPLIST — não no aparelho.
VID_SONY = "054c"
PID_DUALSENSE = "0ce6"

#: O nome tem de carregar as TRÊS agulhas dos patches, e um discriminador por
#: controle: dois controles com o mesmo nome viram um endpoint só (patch 0186,
#: `is_shared_sony_mono_backend_name`).
_MOLDE_DO_NOME = (
    "alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller_HEFESTO{marca}-00.HiFi__Speaker__sink"
)
_AGULHAS = (
    "alsa_output.usb-Sony_Interactive_Entertainment_",
    "Wireless_Controller",
    "Speaker__sink",
)
#: `PA_NAME_MAX` é 128 com o `\0`; um nome maior é recusado pelo servidor.
_MAX_NOME = 127

TAXA = 48000
CANAIS = 4

#: O nó não pode virar a saída padrão da máquina. Mesma razão e mesmo valor do
#: nó do alto-falante (`alto_falante_bt.PRIORIDADE_SESSAO_DO_SOM`).
_PRIORIDADE = 0


@dataclass(frozen=True)
class Ancora:
    """Um ``usb_device`` de onde o ``winepulse`` tira o ``ContainerId``."""

    syspath: str
    vid: int
    pid: int
    bus: int
    dev: int
    usec: int
    nome: str

    def container_id(self) -> str:
        """A conta do ``create_usb_dev_container_id`` (pulse.c:597).

        ``Data1 = MAKELONG(vid, pid)`` — e a ordem é essa mesmo: o campo BAIXO
        é o ``vid``. ``Data4`` são os 8 bytes little-endian do
        ``USEC_INITIALIZED``.

        **O `& 0xFF` no barramento e no device não é zelo:** na origem os dois
        são ``uint8_t`` (``create_usb_dev_container_id``), e um `devnum` acima
        de 255 — que acontece em host cheio — dobra ali. Sem a máscara, esta
        conta e a do Wine divergiriam exatamente nos casos raros, que são os
        piores de diagnosticar.
        """
        data1 = ((self.pid & 0xFFFF) << 16) | (self.vid & 0xFFFF)
        d4 = (self.usec & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "little")
        bus, dev = self.bus & 0xFF, self.dev & 0xFF
        return f"{{{data1:08x}-{bus:04x}-{dev:04x}-{d4[:2].hex()}-{d4[2:].hex()}}}"


def _ler(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="ascii", errors="replace").strip()
    except OSError:
        return ""


def _usec(dev: Path, udev_data: Path) -> int:
    majmin = _ler(dev / "dev")
    if ":" not in majmin:
        return 0
    for linha in _ler(udev_data / f"c{majmin}").splitlines():
        if linha.startswith("I:"):
            try:
                return int(linha[2:])
            except ValueError:
                return 0
    return 0


def ancoras(
    sysfs: Path = Path("/sys"), udev_data: Path = Path("/run/udev/data")
) -> list[Ancora]:
    """Os ``usb_device`` que servem de âncora, na ordem do barramento.

    **Fora ficam os que têm placa de som**: o ``ContainerId`` de um deles já é o
    de um endpoint de verdade, e reusá-lo faria dois endpoints dizerem ser o
    mesmo aparelho.
    """
    raiz = sysfs / "bus" / "usb" / "devices"
    achadas: list[Ancora] = []
    try:
        entradas = sorted(raiz.iterdir())
    except OSError:
        return achadas
    for dev in entradas:
        vendor, produto = _ler(dev / "idVendor"), _ler(dev / "idProduct")
        bus, num = _ler(dev / "busnum"), _ler(dev / "devnum")
        if not (vendor and produto and bus.isdigit() and num.isdigit()):
            continue
        if any(dev.glob("*/sound/card*")):
            continue
        try:
            vid, pid = int(vendor, 16), int(produto, 16)
        except ValueError:
            continue
        achadas.append(
            Ancora(
                syspath=str(dev.resolve()).replace(str(sysfs.resolve()), "", 1),
                vid=vid,
                pid=pid,
                bus=int(bus),
                dev=int(num),
                usec=_usec(dev, udev_data),
                nome=_ler(dev / "product") or f"{vendor}:{produto}",
            )
        )
    return achadas


def nome_do_endpoint(marca: str) -> str:
    """``marca`` são os seis hex do rabo do ``uniq`` — a identidade do controle."""
    nome = _MOLDE_DO_NOME.format(marca=marca)
    if len(nome) > _MAX_NOME:
        raise ValueError(f"nome de {len(nome)} bytes; o servidor recusa acima de {_MAX_NOME}")
    return nome


def propriedades(ancora: Ancora, marca: str) -> str:
    """O ``sink_properties=``, ENTRE ASPAS DUPLAS.

    As aspas são a cura conhecida desta casa: sem elas o parser do
    ``pipewire-pulse`` corta o valor no primeiro espaço e só a primeira
    propriedade chega — com a régua dando verde por ler o argv, não o nó.
    """
    campos = (
        "device.bus=usb",
        f"device.vendor.id={VID_SONY}",
        f"device.product.id={PID_DUALSENSE}",
        f"sysfs.path={ancora.syspath}",
        "device.vendor.name='Sony Interactive Entertainment'",
        f"device.description='DualSense {marca} (háptica pelo rádio)'",
        f"priority.session={_PRIORIDADE}",
        "device.icon_name=audio-speakers",
    )
    return 'sink_properties="' + " ".join(campos) + '"'


# -- o que o servidor responde ------------------------------------------------


def _blocos_de_sinks(saida: str) -> list[str]:
    blocos, atual = [], []
    for linha in saida.splitlines():
        if re.match(r"^Sink #\d+", linha):
            if atual:
                blocos.append("\n".join(atual))
            atual = [linha]
        elif atual:
            atual.append(linha)
    if atual:
        blocos.append("\n".join(atual))
    return blocos


def _campo(bloco: str, chave: str) -> str:
    m = re.search(rf'^\s*{re.escape(chave)} = "(.*)"\s*$', bloco, re.M)
    return m.group(1) if m else ""


def nossos_sinks() -> list[dict[str, str]]:
    saida = rodar_pactl(["pactl", "list", "sinks"]) or ""
    achados = []
    for bloco in _blocos_de_sinks(saida):
        m = re.search(r"^\tName: (.+)$", bloco, re.M)
        if not m or "HEFESTO" not in m.group(1):
            continue
        espec = re.search(r"^\tSample Specification: (.+)$", bloco, re.M)
        achados.append(
            {
                "nome": m.group(1),
                "espec": espec.group(1) if espec else "",
                "bus": _campo(bloco, "device.bus"),
                "vid": _campo(bloco, "device.vendor.id"),
                "pid": _campo(bloco, "device.product.id"),
                "sysfs": _campo(bloco, "sysfs.path"),
                "canais": _campo(bloco, "audio.channels"),
                "id": re.search(r"^Sink #(\d+)", bloco, re.M).group(1),
            }
        )
    return achados


def _laudo(sink: dict[str, str]) -> list[tuple[bool, str]]:
    """As perguntas do GE, uma linha por pergunta. Nenhuma delas é opinião."""
    nome = sink["nome"]
    return [
        (sink["bus"] == "usb", f'device.bus == "usb"  (é "{sink["bus"]}")'),
        (sink["vid"].lower() == VID_SONY, f"device.vendor.id == {VID_SONY}  (é {sink['vid']})"),
        (sink["pid"].lower() == PID_DUALSENSE, f"device.product.id == {PID_DUALSENSE}  (é {sink['pid']})"),
        (sink["canais"] == str(CANAIS), f"audio.channels == {CANAIS}  (é {sink['canais']})"),
        (all(a in nome for a in _AGULHAS), "o nome tem as três agulhas dos patches"),
        (bool(sink["sysfs"]), f"sysfs.path presente → ContainerId real  ({sink['sysfs'] or 'AUSENTE: sairia zerado'})"),
    ]


# -- os verbos ----------------------------------------------------------------


def _default_sink() -> str:
    return (rodar_pactl(["pactl", "get-default-sink"]) or "").strip()


def montar(marca: str, ancora: Ancora) -> int:
    nome = nome_do_endpoint(marca)
    antes = _default_sink()
    saida = rodar_pactl(
        [
            "pactl",
            "load-module",
            "module-null-sink",
            f"sink_name={nome}",
            "format=float32le",
            f"rate={TAXA}",
            f"channels={CANAIS}",
            "channel_map=front-left,front-right,rear-left,rear-right",
            propriedades(ancora, marca),
        ]
    )
    linhas = [ln.strip() for ln in (saida or "").splitlines() if ln.strip()]
    if not linhas or not linhas[-1].isdigit():
        print(f"NÃO MONTOU: {saida!r}")
        return 1
    print(f"montado  module #{linhas[-1]}")
    print(f"nome     {nome}")
    print(f"âncora   {ancora.nome}  {ancora.syspath}")
    print(f"Container{ancora.container_id()}   ← é ISTO que o device KS tem de declarar")
    depois = _default_sink()
    if depois != antes and antes:
        rodar_pactl(["pactl", "set-default-sink", antes])
        print(f"a saída padrão tinha mudado para {depois}; devolvida a {antes}")
    return 0


def desmontar() -> int:
    saida = rodar_pactl(["pactl", "list", "short", "modules"]) or ""
    ids = [
        ln.split("\t", 1)[0]
        for ln in saida.splitlines()
        if "module-null-sink" in ln and "HEFESTO" in ln
    ]
    for mid in ids:
        rodar_pactl(["pactl", "unload-module", mid])
    print(f"removidos: {len(ids)} módulo(s)")
    return 0


def status() -> int:
    achados = nossos_sinks()
    if not achados:
        print("nenhum endpoint de mentira montado")
        return 0
    for sink in achados:
        print(f"\nSink #{sink['id']}  {sink['nome']}")
        print(f"  {sink['espec']}")
        for ok, frase in _laudo(sink):
            print(f"  [{'x' if ok else ' '}] {frase}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--montar", action="store_true", help="sobe o endpoint")
    p.add_argument("--desmontar", action="store_true", help="derruba os nossos")
    p.add_argument("--marca", default="4846d8", help="os seis hex do rabo do uniq do controle")
    p.add_argument("--ancora", default="", help="syspath do usb_device âncora (o padrão é o primeiro)")
    p.add_argument("--ancoras", action="store_true", help="lista as âncoras candidatas")
    args = p.parse_args(argv)

    disponiveis = ancoras()
    if args.ancoras:
        for a in disponiveis:
            print(f"{a.syspath:36s} {a.nome[:34]:34s} {a.container_id()}")
        return 0
    if args.desmontar:
        return desmontar()
    if args.montar:
        if not disponiveis:
            print("sem âncora: nenhum usb_device sem placa de som neste host")
            return 1
        escolhida = next((a for a in disponiveis if a.syspath == args.ancora), disponiveis[0])
        rc = montar(args.marca, escolhida)
        return rc or status()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
