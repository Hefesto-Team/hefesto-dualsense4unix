"""O sysfs dos nós de entrada, de mentira: o que a descoberta lê sem abrir nada."""
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
