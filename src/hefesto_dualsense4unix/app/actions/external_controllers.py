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

#: Marca por OUI do MAC (3 primeiros octetos = 6 hex minúsculos, sem ``:``).
#: É o ÚNICO sinal que desambigua um 8BitDo em modo DualShock4 — que MENTE o
#: VID 054c (Sony) e o nome "Wireless Controller", ficando IDÊNTICO a um DS4
#: Sony de verdade — de um controle Sony genuíno: o OUI ``e4:17:d8`` é da
#: 8BitDo (registro IEEE "8BITDO TECHNOLOGY HK LIMITED"). Quando presente e
#: conhecido, o OUI VENCE o VID (o firmware clone mente o VID, nunca o MAC).
#: Só existe por Bluetooth — por cabo o ``uniq`` vem vazio e caímos no VID.
_BRAND_BY_OUI: dict[str, str] = {
    "e417d8": "8BitDo",
}


def _vidpid(entry: dict[str, Any]) -> str:
    vid = str(entry.get("vid") or "").lower()
    pid = str(entry.get("pid") or "").lower()
    return f"{vid}:{pid}"


def _oui_of(entry: dict[str, Any]) -> str | None:
    """OUI (6 hex minúsculos) do MAC do controle, ou ``None`` sem ``uniq``.

    ``uniq`` vem preenchido por Bluetooth (ex.: ``e4:17:d8:00:00:03``) e vazio
    por cabo — por isso a marca por OUI só desambigua no transporte BT.
    """
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    uniq = entry.get("uniq")
    mac = norm_mac(uniq if isinstance(uniq, str) else None)
    return mac[:6] if mac and len(mac) >= 6 else None


def friendly_type(entry: dict[str, Any]) -> str:
    """Tipo amigável do controle externo (ex.: 'Pro Controller (modo Switch)').

    Ordem: VID:PID conhecido → marca por OUI do MAC (desambigua o clone que
    mente o VID) → fabricante (por VID) → o nome cru do device.
    """
    vp = _vidpid(entry)
    if vp in _TYPE_BY_VIDPID:
        return _TYPE_BY_VIDPID[vp]
    oui = _oui_of(entry)
    if oui and oui in _BRAND_BY_OUI:
        return _BRAND_BY_OUI[oui]
    vid = str(entry.get("vid") or "").lower()
    vendor = _VENDOR_BY_VID.get(vid)
    if vendor:
        return vendor
    name = str(entry.get("name") or "").strip()
    return name or "Controle externo"


def brand_of(entry: dict[str, Any]) -> str:
    """Marca do controle, com o OUI do MAC VENCENDO o VID.

    Um 8BitDo em modo DualShock4 reporta VID 054c (Sony) e nome genérico
    "Wireless Controller" — indistinguível de um DS4 real por VID/nome. O OUI
    do MAC (``e4:17:d8`` = 8BitDo) é o único sinal que os separa, então vem
    primeiro. Sem OUI conhecido (ou sem ``uniq``, caso USB) cai no fabricante
    por VID e, por fim, no :func:`friendly_type`.
    """
    oui = _oui_of(entry)
    if oui and oui in _BRAND_BY_OUI:
        return _BRAND_BY_OUI[oui]
    vid = str(entry.get("vid") or "").lower()
    return _VENDOR_BY_VID.get(vid) or friendly_type(entry)


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
    curto = brand_of(entry)
    bus = str(entry.get("bus") or "").lower()
    via = "cabo" if bus == "usb" else ("BT" if bus in ("bluetooth", "bt") else bus)
    return f"{curto} · {via}" if via else curto


def external_slot(dualsense_count: int, index: int) -> int:
    """Slot GLOBAL de co-op de um externo: continua a numeração dos DualSense.

    Com 2 DualSense (slots 1 e 2), o 1º externo é o Controle 3, o 2º é o 4 —
    o MESMO número que o Hefesto escreve no LED de player do controle, para a
    GUI e o LED nunca discordarem. ``index`` é 0-based na lista de externos.
    """
    return dualsense_count + index + 1


def slot_of(entry: dict[str, Any], dualsense_count: int, index: int) -> int:
    """Slot do externo: o `player_slot` que o DAEMON já mandou (fonte única —
    é o MESMO que ele escreveu no LED), com fallback para o cálculo local em
    daemons antigos que não expõem o campo."""
    slot = entry.get("player_slot")
    if isinstance(slot, int) and not isinstance(slot, bool) and slot >= 1:
        return slot
    return external_slot(dualsense_count, index)


def button_labels_for(
    externals: list[dict[str, Any]], dualsense_count: int = 0
) -> list[str]:
    """Rótulos dos botões dos externos, numerados pelo SLOT GLOBAL de co-op.

    Continua a contagem dos DualSense (``dualsense_count``): com 2 DualSense,
    os externos viram "Nintendo 3 · cabo", "Nintendo 4 · cabo" — SINCRONIZADO
    com o número que aparece no LED de player do próprio controle. Ordem = a
    do inventário (estável por ``uniq`` no backend).
    """
    saida: list[str] = []
    for i, e in enumerate(externals):
        slot = slot_of(e, dualsense_count, i)
        nome = brand_of(e)
        bus = str(e.get("bus") or "").lower()
        via = "cabo" if bus == "usb" else ("BT" if bus in ("bluetooth", "bt") else bus)
        saida.append(f"{nome} {slot} · {via}" if via else f"{nome} {slot}")
    return saida


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


def input_mode(entry: dict[str, Any]) -> str:
    """Modo do controle: 'nintendo' (Switch), 'xbox' (X-input) ou 'outro'.

    O 8BitDo/Pro Controller tem DOIS modos de HARDWARE (combo ao ligar):
    - Switch/Nintendo: enumera 057e:2009, driver hid-nintendo — dá giroscópio,
      mas por Bluetooth o driver do kernel desiste (morte conhecida);
    - X-input/Xbox: enumera 045e:xxxx, driver xpad/hid-generic — descriptor
      Xbox padrão, PULA o hid-nintendo e o descriptor clone malformado; por
      cabo é um Xbox 360 de verdade, à prova de travas (sem gyro).
    """
    vid = str(entry.get("vid") or "").lower()
    driver = str(entry.get("driver") or "").lower()
    if vid == "057e" or driver in ("nintendo", "hid-nintendo"):
        return "nintendo"
    if vid == "045e" or driver in ("xpad", "microsoft"):
        return "xbox"
    return "outro"


def mode_guidance(entry: dict[str, Any]) -> tuple[str, str] | None:
    """(modo_atual_legível, orientação) para a ficha — ou None se não se aplica.

    Só para controles que TÊM os dois modos (Nintendo/8BitDo). A orientação é
    HONESTA: X-input (Xbox) é a raiz da estabilidade (foge do driver que morre
    em BT), Switch (Nintendo) dá gyro mas trava em BT. Como é modo de HARDWARE,
    a "troca" é no controle (combo ao ligar), não no software.
    """
    modo = input_mode(entry)
    if modo == "nintendo":
        atual = "Nintendo (modo Switch)"
        orient = (
            "O jogo vê botões da Nintendo e você tem giroscópio — mas por "
            "Bluetooth esse modo pode travar (é o driver do Linux desistindo, "
            "não o Hefesto). Para o co-op à prova de travas, troque o controle "
            "para o modo Xbox (X-input): ele vira um Xbox 360 de verdade e foge "
            "do driver problemático. No 8BitDo isso é um combo ao ligar/conectar "
            "(veja o manual do seu controle). Por cabo, o modo Xbox é o mais sólido."
        )
        return atual, orient
    if modo == "xbox":
        atual = "Xbox (X-input)"
        orient = (
            "Modo sólido: o jogo vê um Xbox 360 de verdade (driver xpad), sem o "
            "problema do Bluetooth do modo Switch. Você perde o giroscópio — se "
            "precisar de gyro, troque o controle para o modo Switch (combo ao "
            "ligar), sabendo que por Bluetooth ele fica instável."
        )
        return atual, orient
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
    guia = mode_guidance(entry)
    if guia is not None:
        rows.append(("O jogo vê como", guia[0]))
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
