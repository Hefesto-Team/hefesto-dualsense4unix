"""O sysfs dos nós de entrada, de mentira: o que a descoberta lê sem abrir nada.

A-DESCOBERTA-LE-O-SYSFS-E-NAO-ABRE-O-NO-01 (28/09/2026). A descoberta dos nós
auxiliares (touchpad e movimento) deixou de abrir o nó para ler vendor,
product, nome e endereço: lê os quatro em
`<SYS_CLASS_INPUT>/eventN/device/{id/vendor,id/product,name,uniq}`. Uma régua
que dubla o `evdev.InputDevice` para alimentar a descoberta passou a medir um
caminho que o produto não percorre mais.

Este módulo publica o que o kernel publica, com os mesmos arquivos e o mesmo
formato (hexadecimal de quatro dígitos no `id/`, texto com quebra de linha no
resto). O `id/bustype` vai junto, como vai no aparelho: uma régua de paridade
de transporte precisa que um porteiro de barramento tenha o que ler.

A raiz é a do módulo (`evdev_reader.SYS_CLASS_INPUT`), que o `tests/conftest.py`
aponta para uma pasta vazia e nova em todo teste.
"""
from __future__ import annotations

from pathlib import Path

BUS_USB = 0x03
BUS_BLUETOOTH = 0x05


def publicar_no(
    raiz: str | Path,
    no: str,
    *,
    nome: str,
    uniq: str = "",
    vendor: int = 0x054C,
    product: int = 0x0CE6,
    bus: int = BUS_BLUETOOTH,
    teclas: str | None = None,
) -> Path:
    """Escreve o `device/` de um nó (`/dev/input/eventN`) e devolve a pasta."""
    dispositivo = Path(raiz) / Path(no).name / "device"
    (dispositivo / "id").mkdir(parents=True, exist_ok=True)
    (dispositivo / "id" / "vendor").write_text(f"{vendor:04x}\n", encoding="ascii")
    (dispositivo / "id" / "product").write_text(f"{product:04x}\n", encoding="ascii")
    (dispositivo / "id" / "bustype").write_text(f"{bus:04x}\n", encoding="ascii")
    (dispositivo / "name").write_text(nome + "\n", encoding="utf-8")
    (dispositivo / "uniq").write_text(uniq + "\n", encoding="ascii")
    if teclas is not None:
        (dispositivo / "capabilities").mkdir(exist_ok=True)
        (dispositivo / "capabilities" / "key").write_text(teclas + "\n", encoding="ascii")
    return dispositivo
