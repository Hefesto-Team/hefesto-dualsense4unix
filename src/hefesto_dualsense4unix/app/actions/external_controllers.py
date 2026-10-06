"""Controles externos (não-DualSense) na GUI — 8BIT-02.

Lógica PURA (testável sem GTK) para a superfície read-only dos controles que o
Hefesto VÊ mas NÃO adota (8BitDo, Nintendo, Xbox, etc.). Consome o inventário
do IPC ``controller.list {external: true}`` (8BIT-01): cada entrada tem
``name, vid, pid, bus, uniq, driver, evdev_path, hidraw, identity,
player_slot`` e, opcionalmente, ``holders``.

Regra de ouro desta frente (escopo ditado pela mantenedora): "só uma aba pra
ver como os controles aparecem, não uma super central". Aqui NÃO se controla
nada — só se traduz a identidade crua para linguagem de gente e se avisa a
armadilha conhecida (o Nintendo/8BitDo por Bluetooth morre — é o driver
``hid-nintendo`` do kernel desistindo, NÃO o Hefesto).

**NOTA DATADA — 21/08/2026: o escopo acima foi REABERTO por ela.** A ``D-A2`` do
registro «DECISOES-ABERTAS» da aba Configurações foi
respondida mantendo a seção "Os controles" na leva da aba Configurações —
**contrária à recomendação**, que era cortá-la justamente por causa da fala
acima. A escolha é de produto e está registrada com data; a fala de origem fica onde
está, porque decisão revogada nesta casa ganha uma segunda data, nunca some.

O que a reabertura acrescenta a este arquivo, e só isso: as funções puras que a
seção consome (:func:`modo_deduzido`, :func:`declaracoes_do_aparelho`,
:func:`cores_do_plastico_items`). Continua sem controlar nada — o único gesto
que sai desta seção para o aparelho é o número de jogador, que já existia de
ponta a ponta, e as declarações, que vão para o ``maquina.json`` e não para o
firmware de ninguém.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.core.linhagem_nintendo import OUIS_CLONE

_IDENTITY_FIELD = "identity"

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

_VENDOR_BY_VID: dict[str, str] = {
    "057e": "Nintendo",
    "045e": "Xbox",
    "2dc8": "8BitDo",
    "0f0d": "HORI",
    "20d6": "PowerA",
    "28de": "Valve",
    "054c": "Sony",  # não deveria chegar aqui (o inventário exclui DualSense)
}

_NINTENDO_MODE_VIDS = frozenset({"057e"})

_BRAND_BY_OUI: dict[str, str] = dict.fromkeys(OUIS_CLONE, "8BitDo")


def _vidpid(entry: dict[str, Any]) -> str:
    vid = str(entry.get("vid") or "").lower()
    pid = str(entry.get("pid") or "").lower()
    return f"{vid}:{pid}"


def _oui_of(entry: dict[str, Any]) -> str | None:
    """OUI (6 hex minúsculos) do MAC do controle, ou ``None`` sem ``uniq``."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    uniq = entry.get("uniq")
    mac = norm_mac(uniq if isinstance(uniq, str) else None)
    return mac[:6] if mac and len(mac) >= 6 else None


def friendly_type(entry: dict[str, Any]) -> str:
    """Tipo amigável do controle externo (ex.: 'Pro Controller (modo Switch)')."""
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
    """Marca do controle, com o OUI do MAC VENCENDO o VID."""
    oui = _oui_of(entry)
    if oui and oui in _BRAND_BY_OUI:
        return _BRAND_BY_OUI[oui]
    vid = str(entry.get("vid") or "").lower()
    return _VENDOR_BY_VID.get(vid) or friendly_type(entry)


def external_slot(dualsense_count: int, index: int) -> int:
    """Slot GLOBAL de co-op de um externo: continua a numeração dos DualSense.

    Com 2 DualSense (slots 1 e 2), o 1º externo é o Controle 3, o 2º é o 4 —
    o MESMO número que o Hefesto escreve no LED de player do controle, para a
    GUI e o LED nunca discordarem. ``index`` é 0-based na lista de externos.
    """
    return dualsense_count + index + 1


def slot_of(entry: dict[str, Any], dualsense_count: int, index: int) -> int | None:
    """Slot do externo: o `player_slot` que o DAEMON já mandou (fonte única —
    é o MESMO que ele escreveu no LED), com fallback para o cálculo local
    SÓ em daemons antigos que nem sequer expõem o campo.

    NUMA-05: a chave `player_slot` PRESENTE (ainda que valendo ``None`` — o
    registry sem opinião ainda) é a fonte única e vence SEMPRE — devolve
    ``None`` sem calcular nada. O posicional `external_slot` (que
    reembaralhava a numeração a cada troca de `dualsense_count` — o ponto
    cego do incidente de 14:42) só roda quando a CHAVE está AUSENTE (daemon
    de antes do 8BIT-02, que nunca mandou `player_slot`). Null honesto
    (exibido como "—" via :func:`slot_label`) vale mais que número errado.
    """
    if "player_slot" in entry:
        slot = entry["player_slot"]
        if isinstance(slot, int) and not isinstance(slot, bool) and slot >= 1:
            return slot
        return None
    return external_slot(dualsense_count, index)


def slot_label(slot: int | None) -> str:
    """Texto de exibição do slot: o número, ou "—" honesto (NUMA-05).

    Centraliza a regra "null > número errado" num único ponto — a GUI nunca
    mais inventa um número quando o registry ainda não opinou.
    """
    return str(slot) if slot is not None else "—"


def nintendo_bt_warning(entry: dict[str, Any]) -> str | None:
    """Aviso honesto quando é um controle Nintendo-mode POR Bluetooth."""
    vid = str(entry.get("vid") or "").lower()
    bus = str(entry.get("bus") or "").lower()
    if vid in _NINTENDO_MODE_VIDS and bus in ("bluetooth", "bt"):
        return (
            "Pelo BT o modo Switch pode travar (driver do kernel); "
            "pelo USB é estável."
        )
    return None


def external_key(entry: dict[str, Any]) -> str:
    """Chave estável do controle externo — o `identity` que o daemon carimbou."""
    identity = entry.get(_IDENTITY_FIELD)
    if isinstance(identity, str) and identity:
        return identity
    uniq = entry.get("uniq")
    if isinstance(uniq, str) and uniq:
        return uniq
    return str(entry.get("evdev_path") or entry.get("hidraw") or entry.get("name") or "?")


def chave_de_maquina(entry: dict[str, Any]) -> str | None:
    """A chave deste controle no ``maquina.json``, ou ``None`` se não há uma."""
    bruto = external_key(entry) if entry.get(_IDENTITY_FIELD) else entry.get("uniq")
    if not isinstance(bruto, str):
        return None
    limpo = bruto.replace(":", "").replace("-", "").strip().lower()
    if len(limpo) != 12 or any(caractere not in "0123456789abcdef" for caractere in limpo):
        return None
    if limpo.startswith("02"):
        return None
    return limpo
