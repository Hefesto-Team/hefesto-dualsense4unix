"""Controles externos (não-DualSense) na GUI — 8BIT-02.

Lógica PURA (testável sem GTK) para a superfície read-only dos controles que o
Hefesto VÊ mas NÃO adota (8BitDo, Nintendo, Xbox, etc.). Consome o inventário
do IPC ``controller.list {external: true}`` (8BIT-01): cada entrada tem
``name, vid, pid, bus, uniq, driver, evdev_path, hidraw`` e, opcionalmente,
``holders``.

Regra de ouro desta frente (escopo ditado pela mantenedora): "só uma aba pra
ver como os controles aparecem, não uma super central". Aqui NÃO se controla
nada — só se traduz a identidade crua para linguagem de gente e se avisa a
armadilha conhecida (o Nintendo/8BitDo por Bluetooth morre — é o driver
``hid-nintendo`` do kernel desistindo, NÃO o Hefesto).
"""
from __future__ import annotations

from typing import Any

#: VID:PID → tipo amigável. Chave "vvvv:pppp" minúsculo; fallback só por VID.
_TYPE_BY_VIDPID: dict[str, str] = {
    "057e:2009": "Pro Controller (modo Switch)",
    "057e:2017": "Pro Controller (modo Switch)",
    "057e:2006": "Joy-Con (E)",
    "057e:2007": "Joy-Con (D)",
    "045e:028e": "Xbox 360",
    "045e:02ea": "Xbox One",
    "045e:02fd": "Xbox One (Bluetooth)",
    "045e:0b12": "Xbox Series",
    "045e:0b13": "Xbox Series (Bluetooth)",
    "28de:1142": "Steam Controller",
}

#: Fabricante por VID (quando o PID não é conhecido).
_VENDOR_BY_VID: dict[str, str] = {
    "057e": "Nintendo",
    "045e": "Xbox",
    "2dc8": "8BitDo",
    "0f0d": "HORI",
    "20d6": "PowerA",
    "28de": "Valve",
    "054c": "Sony",  # não deveria chegar aqui (o inventário exclui DualSense)
}

#: VIDs cujo controle, por Bluetooth, cai no driver ``hid-nintendo`` — que
#: desiste por timeouts com firmware clone (8BitDo em modo Switch). Provado nos
#: estudos: a morte acontece SEM a Steam aberta; a cura é decisão de modo dela
#: (cabo Switch = estável), não código nosso.
_NINTENDO_MODE_VIDS = frozenset({"057e"})


def _vidpid(entry: dict[str, Any]) -> str:
    vid = str(entry.get("vid") or "").lower()
    pid = str(entry.get("pid") or "").lower()
    return f"{vid}:{pid}"


def friendly_type(entry: dict[str, Any]) -> str:
    """Tipo amigável do controle externo (ex.: 'Pro Controller (modo Switch)').

    Ordem: VID:PID conhecido → fabricante (por VID) → o nome cru do device.
    """
    vp = _vidpid(entry)
    if vp in _TYPE_BY_VIDPID:
        return _TYPE_BY_VIDPID[vp]
    vid = str(entry.get("vid") or "").lower()
    vendor = _VENDOR_BY_VID.get(vid)
    if vendor:
        return vendor
    name = str(entry.get("name") or "").strip()
    return name or "Controle externo"


def transport_label(entry: dict[str, Any]) -> str:
    """'Cabo (USB)' | 'Bluetooth' | o valor cru quando desconhecido."""
    bus = str(entry.get("bus") or "").lower()
    if bus == "usb":
        return "Cabo (USB)"
    if bus in ("bluetooth", "bt"):
        return "Bluetooth"
    return bus or "desconhecido"


def short_button_label(entry: dict[str, Any]) -> str:
    """Rótulo curto para o botão do seletor no topo (cabe ao lado dos DualSense).

    Ex.: '8BitDo · cabo', 'Pro Controller · BT'. Prioriza o fabricante para
    ficar curto; o tooltip/ficha carregam o nome completo.
    """
    vid = str(entry.get("vid") or "").lower()
    vp = _vidpid(entry)
    curto = _VENDOR_BY_VID.get(vid)
    if not curto:
        curto = _TYPE_BY_VIDPID.get(vp, str(entry.get("name") or "Externo"))
    bus = str(entry.get("bus") or "").lower()
    via = "cabo" if bus == "usb" else ("BT" if bus in ("bluetooth", "bt") else bus)
    return f"{curto} · {via}" if via else curto


def nintendo_bt_warning(entry: dict[str, Any]) -> str | None:
    """Aviso honesto quando é um controle Nintendo-mode POR Bluetooth.

    ``None`` quando não se aplica. O texto NÃO promete cura pelo Hefesto — a
    morte é do driver ``hid-nintendo`` do kernel; a saída estável é cabo.
    """
    vid = str(entry.get("vid") or "").lower()
    bus = str(entry.get("bus") or "").lower()
    if vid in _NINTENDO_MODE_VIDS and bus in ("bluetooth", "bt"):
        return (
            "Por Bluetooth, controles em modo Switch (8BitDo/Nintendo) costumam "
            "travar sozinhos depois de um tempo — é o driver do Linux "
            "desistindo, não o Hefesto. Para jogar sem sustos, use por cabo."
        )
    return None


def detail_rows(entry: dict[str, Any]) -> list[tuple[str, str]]:
    """Linhas ``(rótulo, valor)`` da ficha read-only do controle externo.

    Só o que interessa a quem vai jogar; nada de caminho cru de /dev. O
    ``holders`` (Steam segurando o hidraw) NÃO vira alarme — é estado normal.
    """
    rows: list[tuple[str, str]] = [
        ("Controle", friendly_type(entry)),
        ("Como conectou", transport_label(entry)),
    ]
    driver = str(entry.get("driver") or "").strip()
    if driver:
        rows.append(("Driver do Linux", driver))
    nome = str(entry.get("name") or "").strip()
    if nome and nome != friendly_type(entry):
        rows.append(("Nome do sistema", nome))
    rows.append(("Gerenciado por", "Linux + Steam (o Hefesto não mexe nele)"))
    return rows


def external_key(entry: dict[str, Any]) -> str:
    """Chave estável do controle externo (uniq quando há; senão evdev_path).

    Usada para casar o botão do seletor com a entrada do inventário sem
    depender da posição na lista (que muda a cada replug).
    """
    uniq = entry.get("uniq")
    if isinstance(uniq, str) and uniq:
        return uniq
    return str(entry.get("evdev_path") or entry.get("hidraw") or entry.get("name") or "?")
